"""
Multi-photo scan support.

One scan may carry 1-3 photographs of the same deer from the same encounter.
This module handles:
- request validation (type, size, count)
- EXIF orientation, capture date, dimensions, stable image ids, order
- optional user crop (original always retained, crop is NOT independent evidence)
- exact / near-duplicate detection (duplicates never reach the model)
- bounded model payloads (downscaled JPEG, high detail)
- multi-image prompt addendum and post-model reconciliation guards
"""

import base64
import hashlib
import io
import logging
import os
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional

from PIL import Image, ImageOps, UnidentifiedImageError

logger = logging.getLogger(__name__)

MAX_SCAN_IMAGES = 3
MAX_IMAGE_BYTES = int(os.environ.get("SCAN_MAX_IMAGE_BYTES", str(8 * 1024 * 1024)))
MIN_IMAGE_EDGE = 200
MODEL_MAX_EDGE = int(os.environ.get("SCAN_MODEL_MAX_EDGE", "2048"))
MODEL_JPEG_QUALITY = 85
MIN_CROP_FRACTION = 0.2
NEAR_DUPLICATE_MAX_HAMMING = int(os.environ.get("SCAN_NEAR_DUPLICATE_MAX_HAMMING", "6"))
ALLOWED_FORMATS = {"JPEG": "image/jpeg", "MPO": "image/jpeg", "PNG": "image/png", "WEBP": "image/webp"}
CONTRADICTION_AGE_CONFIDENCE_PENALTY = 10
SAME_DEER_VERDICTS = {"same", "likely_same", "uncertain", "different"}


def preprocessing_version() -> str:
    """Identifies the image preprocessing feeding the model (used for calibration compatibility)."""
    return f"img-prep-v1-edge{MODEL_MAX_EDGE}-q{MODEL_JPEG_QUALITY}-dedup{NEAR_DUPLICATE_MAX_HAMMING}"


class ImageValidationError(ValueError):
    def __init__(self, code: str, message: str, image_id: Optional[str] = None):
        super().__init__(message)
        self.code = code
        self.message = message
        self.image_id = image_id

    def to_detail(self) -> Dict[str, Any]:
        detail = {"code": self.code, "message": self.message, "save_scan": False}
        if self.image_id:
            detail["image_id"] = self.image_id
        return detail


@dataclass
class PreparedImage:
    image_id: str
    position: int
    original_bytes: bytes
    original_content_type: str
    width: int
    height: int
    sha256: str
    dhash: str
    captured_at: Optional[str]
    crop_rect: Optional[Dict[str, float]]
    model_jpeg: bytes
    crop_jpeg: Optional[bytes] = None
    local_image_id: Optional[str] = None
    duplicate_of: Optional[str] = None
    meta: Dict[str, Any] = field(default_factory=dict)

    @property
    def model_data_url(self) -> str:
        return "data:image/jpeg;base64," + base64.b64encode(self.model_jpeg).decode("ascii")

    def record(self) -> Dict[str, Any]:
        """Serializable metadata (no pixel data)."""
        return {
            "image_id": self.image_id,
            "position": self.position,
            "width": self.width,
            "height": self.height,
            "captured_at": self.captured_at,
            "crop_rect": self.crop_rect,
            "is_cropped": self.crop_rect is not None,
            "sha256": self.sha256,
            "dhash": self.dhash,
            "content_type": self.original_content_type,
            "local_image_id": self.local_image_id,
            "duplicate_of": self.duplicate_of,
        }


def decode_base64_image(value: str) -> bytes:
    payload = value.split(",", 1)[1] if value.startswith("data:") and "," in value else value
    # Reject oversized payloads before decoding (base64 is ~4/3 of raw size)
    if len(payload) > (MAX_IMAGE_BYTES * 4) // 3 + 16:
        raise ImageValidationError("IMAGE_TOO_LARGE", f"Each photo must be under {MAX_IMAGE_BYTES // (1024 * 1024)} MB.")
    try:
        return base64.b64decode(payload, validate=False)
    except Exception as exc:
        raise ImageValidationError("INVALID_IMAGE", "A photo could not be decoded.") from exc


def _exif_capture_date(img: Image.Image) -> Optional[str]:
    try:
        exif = img.getexif()
        raw = None
        try:
            raw = exif.get_ifd(0x8769).get(36867)  # DateTimeOriginal
        except Exception:
            raw = None
        raw = raw or exif.get(36867) or exif.get(306)  # DateTime
        if raw:
            return datetime.strptime(str(raw).strip()[:19], "%Y:%m:%d %H:%M:%S").isoformat()
    except Exception:
        return None
    return None


def _normalize_client_date(value: Optional[str]) -> Optional[str]:
    if not value or not isinstance(value, str):
        return None
    text = value.strip()
    for fmt in ("%Y:%m:%d %H:%M:%S", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%d %H:%M:%S", "%Y-%m-%d"):
        try:
            return datetime.strptime(text[:19], fmt).isoformat()
        except ValueError:
            continue
    try:
        return datetime.fromisoformat(text.replace("Z", "+00:00")).replace(tzinfo=None).isoformat()
    except ValueError:
        return None


def validate_crop_rect(rect: Optional[Dict[str, Any]], image_id: str) -> Optional[Dict[str, float]]:
    if not rect:
        return None
    try:
        x, y = float(rect["x"]), float(rect["y"])
        w, h = float(rect["width"]), float(rect["height"])
    except (KeyError, TypeError, ValueError) as exc:
        raise ImageValidationError("INVALID_CROP", "Crop must include x, y, width and height.", image_id) from exc
    if not (0 <= x < 1 and 0 <= y < 1 and 0 < w <= 1 and 0 < h <= 1):
        raise ImageValidationError("INVALID_CROP", "Crop values must be fractions between 0 and 1.", image_id)
    if x + w > 1.0001 or y + h > 1.0001:
        raise ImageValidationError("INVALID_CROP", "Crop must stay inside the photo.", image_id)
    if w < MIN_CROP_FRACTION or h < MIN_CROP_FRACTION:
        raise ImageValidationError(
            "INVALID_CROP",
            "Crop is too tight. Keep the deer's full body, head, and legs in frame.",
            image_id,
        )
    if w >= 0.999 and h >= 0.999:
        return None  # Full-frame crop == no crop
    return {"x": round(x, 4), "y": round(y, 4), "width": round(min(w, 1 - x), 4), "height": round(min(h, 1 - y), 4)}


def _dhash(img: Image.Image) -> str:
    gray = img.convert("L").resize((9, 8), Image.Resampling.LANCZOS)
    pixels = list(gray.getdata())
    bits = 0
    for row in range(8):
        for col in range(8):
            left = pixels[row * 9 + col]
            right = pixels[row * 9 + col + 1]
            bits = (bits << 1) | (1 if left > right else 0)
    return f"{bits:016x}"


def hamming(a: str, b: str) -> int:
    return bin(int(a, 16) ^ int(b, 16)).count("1")


def _to_rgb(img: Image.Image) -> Image.Image:
    if img.mode in ("RGBA", "LA", "P"):
        img = img.convert("RGBA")
        background = Image.new("RGB", img.size, (255, 255, 255))
        background.paste(img, mask=img.split()[-1])
        return background
    return img.convert("RGB") if img.mode != "RGB" else img


def _encode_jpeg(img: Image.Image, max_edge: Optional[int]) -> bytes:
    out = img
    if max_edge and max(out.size) > max_edge:
        out = out.copy()
        out.thumbnail((max_edge, max_edge), Image.Resampling.LANCZOS)
    buffer = io.BytesIO()
    out.save(buffer, format="JPEG", quality=MODEL_JPEG_QUALITY, optimize=True)
    return buffer.getvalue()


def prepare_image(
    *,
    image_bytes: bytes,
    position: int,
    image_id: Optional[str] = None,
    captured_at: Optional[str] = None,
    crop_rect: Optional[Dict[str, Any]] = None,
    local_image_id: Optional[str] = None,
) -> PreparedImage:
    image_id = image_id or f"img_{position}"
    if len(image_bytes) > MAX_IMAGE_BYTES:
        raise ImageValidationError(
            "IMAGE_TOO_LARGE", f"Each photo must be under {MAX_IMAGE_BYTES // (1024 * 1024)} MB.", image_id
        )
    if len(image_bytes) < 100:
        raise ImageValidationError("INVALID_IMAGE", "A photo is empty or corrupted.", image_id)
    try:
        img = Image.open(io.BytesIO(image_bytes))
        fmt = (img.format or "").upper()
        img.load()
    except (UnidentifiedImageError, OSError) as exc:
        raise ImageValidationError("UNSUPPORTED_IMAGE_TYPE", "Photos must be JPEG, PNG, or WebP.", image_id) from exc
    if fmt not in ALLOWED_FORMATS:
        raise ImageValidationError("UNSUPPORTED_IMAGE_TYPE", "Photos must be JPEG, PNG, or WebP.", image_id)

    exif_date = _exif_capture_date(img)
    oriented = _to_rgb(ImageOps.exif_transpose(img))
    width, height = oriented.size
    if min(width, height) < MIN_IMAGE_EDGE:
        raise ImageValidationError(
            "IMAGE_TOO_SMALL", f"Photos must be at least {MIN_IMAGE_EDGE}px on each side.", image_id
        )

    rect = validate_crop_rect(crop_rect, image_id)
    crop_jpeg = None
    model_source = oriented
    if rect:
        box = (
            int(round(rect["x"] * width)),
            int(round(rect["y"] * height)),
            int(round((rect["x"] + rect["width"]) * width)),
            int(round((rect["y"] + rect["height"]) * height)),
        )
        model_source = oriented.crop(box)
        crop_jpeg = _encode_jpeg(model_source, None)

    return PreparedImage(
        image_id=image_id,
        position=position,
        original_bytes=image_bytes,
        original_content_type=ALLOWED_FORMATS[fmt],
        width=width,
        height=height,
        sha256=hashlib.sha256(image_bytes).hexdigest(),
        dhash=_dhash(oriented),  # hash of the full original: a crop never counts as new evidence
        captured_at=exif_date or _normalize_client_date(captured_at),
        crop_rect=rect,
        model_jpeg=_encode_jpeg(model_source, MODEL_MAX_EDGE),
        crop_jpeg=crop_jpeg,
        local_image_id=local_image_id,
    )


def mark_duplicates(images: List[PreparedImage]) -> List[Dict[str, Any]]:
    """Flag exact and near-duplicate photos. Returns duplicate records."""
    duplicates = []
    kept: List[PreparedImage] = []
    for img in images:
        match = next(
            (
                k for k in kept
                if k.sha256 == img.sha256 or hamming(k.dhash, img.dhash) <= NEAR_DUPLICATE_MAX_HAMMING
            ),
            None,
        )
        if match:
            img.duplicate_of = match.image_id
            duplicates.append({
                "image_id": img.image_id,
                "duplicate_of": match.image_id,
                "kind": "exact" if match.sha256 == img.sha256 else "near",
            })
        else:
            kept.append(img)
    return duplicates


def evidence_images(images: List[PreparedImage]) -> List[PreparedImage]:
    return [img for img in images if img.duplicate_of is None]


def capture_span_hours(images: List[PreparedImage]) -> Optional[float]:
    dates = []
    for img in images:
        if img.captured_at:
            try:
                dates.append(datetime.fromisoformat(img.captured_at))
            except ValueError:
                continue
    if len(dates) < 2:
        return None
    return round((max(dates) - min(dates)).total_seconds() / 3600, 2)


def build_multi_image_system_addendum() -> str:
    return """

MULTI-PHOTO MODE (applies when more than one photo is provided):
The hunter submitted several photos that they believe show the SAME deer from the SAME encounter.
Each photo is preceded by a text label with its stable image ID (img_1, img_2, ...).

Add these fields to the JSON (in addition to every field above):
  "per_image_observations": [
    {"image_id": "<img_N>", "usable": <true|false>, "view": <"broadside" | "angled" | "head_down" | "frontal" | "rear" | "unknown">,
     "visible_age_cues": [<cue names>], "observations": "<age cues seen in THIS photo only>",
     "suggested_age": <number or null>, "age_confidence": <0-100>}
  ],
  "same_deer_assessment": {
    "verdict": <"same" | "likely_same" | "uncertain" | "different">,
    "reason": "<short explanation>",
    "conflicting_image_ids": [<image ids that appear to show a different deer>]
  },
  "contradictions": ["<short description of each evidence conflict between photos>"]

Multi-photo rules:
- First list age cues per photo, judging each photo on its own. Then reconcile those observations into ONE estimate.
- Each photo's `age_confidence` must reflect only what that photo shows.
- The overall `age_confidence` must NOT be higher than the strongest single photo supports. More photos do not raise confidence on their own; only genuinely complementary views (e.g. a clear broadside plus a clear head view) can resolve doubt within that limit.
- Near-identical photos (burst frames, same pose) add no new evidence.
- Compare antler configuration, coat, body shape, scars, and sex across photos. If any photo appears to show a different animal, set verdict to "different" and list those image ids.
- If photos imply different ages or body shapes, record each conflict in `contradictions` and stay conservative.
- `visible_age_cues` (top level) lists cues clearly visible in at least one usable photo.
- In `age_evidence`, prefix each observation with the image id it came from, e.g. "[img_2] deep chest".
"""


def build_multi_image_user_content(intro_text: str, images: List[PreparedImage]) -> List[Dict[str, Any]]:
    """Interleave a label for each photo so the model can cite stable ids."""
    content: List[Dict[str, Any]] = [{"type": "text", "text": intro_text}]
    for img in images:
        label = f"Photo {img.image_id} (order {img.position}"
        if img.crop_rect:
            label += ", user-cropped view of the original photo"
        if img.captured_at:
            label += f", captured {img.captured_at}"
        label += "):"
        content.append({"type": "text", "text": label})
        content.append({"type": "image_url", "image_url": {"url": img.model_data_url, "detail": "high"}})
    return content


def _clamp_int(value: Any) -> Optional[int]:
    try:
        return max(0, min(100, int(round(float(value)))))
    except (TypeError, ValueError):
        return None


def apply_multi_image_guards(
    analysis: Dict[str, Any],
    images: List[PreparedImage],
    duplicates: List[Dict[str, Any]],
    span_hours: Optional[float],
) -> Dict[str, Any]:
    """Normalize multi-image fields and enforce 'no confidence bonus for photo count'."""
    valid_ids = {img.image_id for img in images}
    audit_steps = analysis.setdefault("_pre_calibration_audit_steps", [])
    multi_evidence = len(images) > 1

    observations = []
    for item in analysis.get("per_image_observations") or []:
        if not isinstance(item, dict) or item.get("image_id") not in valid_ids:
            continue
        observations.append({
            "image_id": item["image_id"],
            "usable": item.get("usable") is not False,
            "view": str(item.get("view") or "unknown")[:30],
            "visible_age_cues": [str(c)[:40] for c in (item.get("visible_age_cues") or []) if c][:15],
            "observations": str(item.get("observations") or "")[:400] or None,
            "suggested_age": item.get("suggested_age"),
            "age_confidence": _clamp_int(item.get("age_confidence")),
        })

    assessment = analysis.get("same_deer_assessment") if isinstance(analysis.get("same_deer_assessment"), dict) else {}
    verdict = str(assessment.get("verdict") or "uncertain").strip().lower()
    if verdict not in SAME_DEER_VERDICTS:
        verdict = "uncertain"
    if not multi_evidence:
        verdict = "not_applicable"  # Only one independent photo remains after de-duplication
    conflicting = [i for i in (assessment.get("conflicting_image_ids") or []) if i in valid_ids]
    contradictions = [str(c)[:240] for c in (analysis.get("contradictions") or []) if c][:6]
    warnings = []
    if multi_evidence and span_hours is not None and span_hours > 24:
        warnings.append(
            f"Photo capture times span about {round(span_hours / 24, 1)} days; they may not be from the same encounter."
        )

    multi = {
        "photo_count": len(images) + len(duplicates),
        "evidence_count": len(images),
        "image_ids": [img.image_id for img in images],
        "duplicates_removed": duplicates,
        "per_image_observations": observations,
        "same_deer": {
            "verdict": verdict,
            "reason": str(assessment.get("reason") or "")[:300] or None,
            "conflicting_image_ids": conflicting,
        },
        "contradictions": contradictions,
        "warnings": warnings,
        "capture_span_hours": span_hours,
    }
    analysis["multi_image"] = multi

    # Guard 1: overall age confidence cannot exceed the best single-photo confidence.
    per_image_conf = [o["age_confidence"] for o in observations if o["usable"] and o["age_confidence"] is not None]
    before = analysis.get("raw_age_confidence")
    if per_image_conf and isinstance(before, (int, float)) and before > max(per_image_conf):
        cap = max(per_image_conf)
        analysis["raw_age_confidence"] = cap
        audit_steps.append({
            "step": "multi_image_single_photo_cap",
            "reason": "Overall age confidence capped at the strongest single-photo confidence (no photo-count bonus).",
            "adjustments": [{"field": "age_confidence", "before": before, "after": cap}],
        })

    # Guard 2: contradictions / uncertain identity reduce confidence.
    if multi_evidence and (contradictions or verdict == "uncertain" or warnings):
        before_age = analysis.get("raw_age_confidence") or 0
        after_age = max(0, int(before_age) - CONTRADICTION_AGE_CONFIDENCE_PENALTY)
        analysis["raw_age_confidence"] = after_age
        audit_steps.append({
            "step": "multi_image_conflict_penalty",
            "reason": f"verdict={verdict}, contradictions={len(contradictions)}, warnings={len(warnings)}",
            "adjustments": [{"field": "age_confidence", "before": before_age, "after": after_age}],
        })

    if duplicates:
        audit_steps.append({
            "step": "multi_image_duplicates_excluded",
            "reason": f"{len(duplicates)} duplicate photo(s) excluded from evidence; no confidence credit given.",
            "adjustments": [],
        })
    return analysis


def mixed_deer_detail(analysis: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    multi = analysis.get("multi_image") or {}
    same = multi.get("same_deer") or {}
    if same.get("verdict") != "different":
        return None
    ids = same.get("conflicting_image_ids") or []
    which = ", ".join(f"photo {i.split('_')[-1]}" for i in ids) if ids else "one or more photos"
    return {
        "code": "MIXED_DEER",
        "message": (
            f"These photos don't appear to show the same deer ({which} looks different). "
            "Remove the photo that shows a different animal, or analyze each deer separately. No scan was used."
        ),
        "reason": same.get("reason"),
        "conflicting_image_ids": ids,
        "save_scan": False,
    }
