"""
Known-age evaluation dataset: format, validation, leakage checks and deer-level splits.

Format: JSON Lines, one record per ENCOUNTER (one sighting of one deer, 1-3 photos).
See evaluation/README.md and evaluation/templates/dataset_template.jsonl.
"""

import hashlib
import io
import json
import os
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

from PIL import Image, ImageOps

from multi_image import _dhash, hamming, NEAR_DUPLICATE_MAX_HAMMING

SPLITS = ("development", "calibration", "test")
DEFAULT_SPLIT_RATIOS = {"development": 0.2, "calibration": 0.3, "test": 0.5}
SPLIT_SALT = "ironstag-eval-split-v1"

# How the reference age was established -> reliability tier.
# Tier A/B are treated as ground truth by default; C/D are reference ESTIMATES and are reported separately.
AGE_BASIS_TIERS = {
    # A: documented known age (tagged/marked as fawn, birth record, captive record)
    "known_birth_record": "A_documented_known_age",
    "tagged_as_fawn": "A_documented_known_age",
    "captive_record": "A_documented_known_age",
    # B: laboratory estimate
    "cementum_annuli": "B_laboratory",
    # C: expert assessment (tooth replacement/wear is an estimate with known error past 2.5 yrs)
    "jawbone": "C_expert_assessment",
    "tooth_wear": "C_expert_assessment",
    "biologist_assessment": "C_expert_assessment",
    "taxidermist": "C_expert_assessment",
    # D: hunter guesses / unknown provenance
    "hunter_best_estimate": "D_hunter_guess",
    "other": "D_hunter_guess",
    "unknown": "D_hunter_guess",
}
GROUND_TRUTH_TIERS = ("A_documented_known_age", "B_laboratory")
MAX_GROUND_TRUTH_UNCERTAINTY = 0.5  # years
SPECIES = ("whitetail", "mule_deer")
SEXES = ("buck", "doe", "unknown")
QUALITY = ("excellent", "good", "fair", "poor")
REQUIRED_FIELDS = ("encounter_id", "deer_id", "species", "sex", "encounter_date", "images", "reference_age", "age_basis")


@dataclass
class Issue:
    level: str  # "error" (record excluded) | "warning" (record kept, flagged)
    code: str
    message: str
    encounter_id: Optional[str] = None
    deer_id: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return self.__dict__.copy()


@dataclass
class ValidationResult:
    records: List[Dict[str, Any]]
    issues: List[Issue] = field(default_factory=list)
    dataset_sha256: str = ""
    synthetic: bool = False

    def errors_for(self, encounter_id: str) -> List[Issue]:
        return [i for i in self.issues if i.level == "error" and i.encounter_id == encounter_id]

    @property
    def valid_records(self) -> List[Dict[str, Any]]:
        bad = {i.encounter_id for i in self.issues if i.level == "error"}
        bad_deer = {i.deer_id for i in self.issues if i.level == "error" and i.encounter_id is None and i.deer_id}
        return [r for r in self.records if r.get("encounter_id") not in bad and r.get("deer_id") not in bad_deer]

    def summary(self) -> Dict[str, Any]:
        codes: Dict[str, int] = {}
        for i in self.issues:
            codes[f"{i.level}:{i.code}"] = codes.get(f"{i.level}:{i.code}", 0) + 1
        return {
            "records": len(self.records),
            "valid_records": len(self.valid_records),
            "deer": len({r.get("deer_id") for r in self.records}),
            "issue_counts": codes,
            "dataset_sha256": self.dataset_sha256,
            "synthetic": self.synthetic,
        }


def load_dataset(path: str) -> Tuple[List[Dict[str, Any]], Dict[str, Any], str]:
    """Returns (records, header, sha256). An optional first line {"_dataset": {...}} holds metadata."""
    with open(path, "rb") as fh:
        raw = fh.read()
    records, header = [], {}
    for line_no, line in enumerate(raw.decode("utf-8").splitlines(), start=1):
        if not line.strip() or line.lstrip().startswith("//"):
            continue
        obj = json.loads(line)
        if "_dataset" in obj:
            header = obj["_dataset"]
            continue
        obj["_line"] = line_no
        records.append(obj)
    return records, header, hashlib.sha256(raw).hexdigest()


def label_tier(record: Dict[str, Any]) -> str:
    return AGE_BASIS_TIERS.get(str(record.get("age_basis") or "unknown").strip().lower(), "D_hunter_guess")


def is_ground_truth(record: Dict[str, Any], allowed_tiers=GROUND_TRUTH_TIERS,
                    max_uncertainty: float = MAX_GROUND_TRUTH_UNCERTAINTY) -> bool:
    unc = record.get("label_uncertainty_years")
    return label_tier(record) in allowed_tiers and unc is not None and float(unc) <= max_uncertainty


def assign_split(deer_id: str, ratios: Dict[str, float] = DEFAULT_SPLIT_RATIOS, salt: str = SPLIT_SALT) -> str:
    """Deterministic, deer-level split: every encounter/image of a deer lands in the same split."""
    bucket = int(hashlib.sha256(f"{salt}:{deer_id}".encode()).hexdigest()[:8], 16) / 0xFFFFFFFF
    cumulative = 0.0
    for name in SPLITS:
        cumulative += ratios.get(name, 0)
        if bucket <= cumulative:
            return name
    return SPLITS[-1]


def resolve_image_path(dataset_dir: str, path: str) -> str:
    return path if os.path.isabs(path) or path.startswith(("http://", "https://")) else os.path.join(dataset_dir, path)


def _fingerprint(full_path: str) -> Tuple[str, str]:
    with open(full_path, "rb") as fh:
        data = fh.read()
    img = ImageOps.exif_transpose(Image.open(io.BytesIO(data))).convert("RGB")
    return hashlib.sha256(data).hexdigest(), _dhash(img)


def validate_dataset(path: str, *, check_images: bool = True, ratios: Dict[str, float] = DEFAULT_SPLIT_RATIOS) -> ValidationResult:
    records, header, sha = load_dataset(path)
    dataset_dir = os.path.dirname(os.path.abspath(path))
    result = ValidationResult(records=records, dataset_sha256=sha, synthetic=bool(header.get("synthetic")))
    add = result.issues.append

    seen_encounters = set()
    for r in records:
        eid, did = r.get("encounter_id"), r.get("deer_id")
        missing = [f for f in REQUIRED_FIELDS if r.get(f) in (None, "", [])]
        if missing:
            add(Issue("error", "missing_required_fields", f"Missing: {', '.join(missing)} (line {r['_line']})", eid, did))
        if eid in seen_encounters:
            add(Issue("error", "duplicate_encounter_id", f"encounter_id {eid} appears more than once", eid, did))
        seen_encounters.add(eid)
        if r.get("species") and r["species"] not in SPECIES:
            add(Issue("error", "invalid_species", f"species must be one of {SPECIES}", eid, did))
        if r.get("sex") and r["sex"] not in SEXES:
            add(Issue("error", "invalid_sex", f"sex must be one of {SEXES}", eid, did))
        if r.get("sex") == "unknown":
            add(Issue("warning", "sex_unknown", "Sex unknown; excluded from sex breakdowns", eid, did))
        age = r.get("reference_age")
        if age is not None:
            try:
                age = float(age)
                if not 0 < age < 20:
                    add(Issue("error", "reference_age_out_of_range", f"reference_age {age} outside (0, 20)", eid, did))
                elif abs((age * 2) % 2 - 1) > 1e-6:
                    add(Issue("warning", "reference_age_not_half_year",
                              f"reference_age {age} is not on the x.5 convention; check age at encounter date", eid, did))
            except (TypeError, ValueError):
                add(Issue("error", "reference_age_invalid", "reference_age must be a number", eid, did))
        basis = str(r.get("age_basis") or "").strip().lower()
        if basis and basis not in AGE_BASIS_TIERS:
            add(Issue("warning", "age_basis_unrecognized", f"Unrecognized age_basis '{basis}', treated as hunter guess", eid, did))
        tier = label_tier(r)
        if tier not in GROUND_TRUTH_TIERS:
            add(Issue("warning", "label_not_ground_truth",
                      f"Reference age is a {tier.split('_', 1)[1].replace('_', ' ')}, not documented ground truth", eid, did))
        unc = r.get("label_uncertainty_years")
        if unc is None:
            add(Issue("warning", "label_uncertainty_missing", "label_uncertainty_years missing; not eligible as ground truth", eid, did))
        elif float(unc) > MAX_GROUND_TRUTH_UNCERTAINTY:
            add(Issue("warning", "label_uncertainty_high", f"Label uncertainty ±{unc} yr exceeds ±{MAX_GROUND_TRUTH_UNCERTAINTY}", eid, did))
        if r.get("image_quality") not in QUALITY:
            add(Issue("warning", "image_quality_missing", f"image_quality should be one of {QUALITY}", eid, did))
        if not r.get("region_state") and not r.get("region_key"):
            add(Issue("warning", "region_missing", "No region_state/region_key; region calibration falls back", eid, did))
        if r.get("identity_unverified"):
            add(Issue("warning", "identity_unverified", "deer_id is not verified; leakage cannot be ruled out", eid, did))
        images = r.get("images") or []
        if len(images) > 3:
            add(Issue("error", "too_many_images", "At most 3 images per encounter", eid, did))
        if r.get("split") and r["split"] not in SPLITS:
            add(Issue("error", "invalid_split", f"split must be one of {SPLITS}", eid, did))

    # Deer-level split consistency (leakage between splits)
    deer_splits: Dict[str, set] = {}
    for r in records:
        r["_split"] = r.get("split") or assign_split(str(r.get("deer_id")), ratios)
        deer_splits.setdefault(r.get("deer_id"), set()).add(r["_split"])
    for did, splits in deer_splits.items():
        if len(splits) > 1:
            add(Issue("error", "deer_in_multiple_splits",
                      f"Deer {did} appears in splits {sorted(splits)}; all its encounters are excluded", None, did))

    # Image existence + duplicates across encounters/deer
    if check_images:
        fingerprints: List[Tuple[str, str, Dict[str, Any], str]] = []
        for r in records:
            for img in r.get("images") or []:
                p = img.get("path") if isinstance(img, dict) else None
                if not p:
                    add(Issue("error", "image_path_missing", "Image entry without path", r.get("encounter_id"), r.get("deer_id")))
                    continue
                if p.startswith(("http://", "https://")):
                    add(Issue("warning", "image_remote", f"Remote image not fingerprinted: {p}", r.get("encounter_id"), r.get("deer_id")))
                    continue
                full = resolve_image_path(dataset_dir, p)
                if not os.path.exists(full):
                    add(Issue("error", "image_not_found", f"Image not found: {p}", r.get("encounter_id"), r.get("deer_id")))
                    continue
                try:
                    sha_img, dh = _fingerprint(full)
                except Exception:
                    add(Issue("error", "image_unreadable", f"Unreadable image: {p}", r.get("encounter_id"), r.get("deer_id")))
                    continue
                fingerprints.append((sha_img, dh, r, p))
        for i in range(len(fingerprints)):
            for j in range(i + 1, len(fingerprints)):
                a, b = fingerprints[i], fingerprints[j]
                exact = a[0] == b[0]
                if not exact and hamming(a[1], b[1]) > NEAR_DUPLICATE_MAX_HAMMING:
                    continue
                ra, rb = a[2], b[2]
                kind = "exact" if exact else "near"
                if ra.get("deer_id") != rb.get("deer_id"):
                    msg = f"{kind} duplicate image across deer {ra.get('deer_id')} / {rb.get('deer_id')}: {a[3]} ~ {b[3]}"
                    add(Issue("error", "duplicate_image_across_deer", msg, ra.get("encounter_id"), ra.get("deer_id")))
                    add(Issue("error", "duplicate_image_across_deer", msg, rb.get("encounter_id"), rb.get("deer_id")))
                elif ra.get("encounter_id") != rb.get("encounter_id"):
                    add(Issue("warning", "duplicate_image_across_encounters",
                              f"{kind} duplicate image reused across encounters of deer {ra.get('deer_id')}: {a[3]} ~ {b[3]}",
                              rb.get("encounter_id"), rb.get("deer_id")))
                else:
                    add(Issue("warning", "duplicate_image_within_encounter",
                              f"{kind} duplicate within encounter (pipeline will drop it): {a[3]} ~ {b[3]}",
                              ra.get("encounter_id"), ra.get("deer_id")))
    return result


def eligible_cases(result: ValidationResult, split: str, *, allowed_tiers=GROUND_TRUTH_TIERS,
                   max_uncertainty: float = MAX_GROUND_TRUTH_UNCERTAINTY) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    """Returns (eligible, excluded-with-reason). Fixed BEFORE running so every config sees identical cases."""
    eligible, excluded = [], []
    valid_ids = {r["encounter_id"] for r in result.valid_records}
    for r in result.records:
        if r.get("_split") != split:
            continue
        if r.get("encounter_id") not in valid_ids:
            excluded.append({"encounter_id": r.get("encounter_id"), "reason": "validation_error"})
        elif not is_ground_truth(r, allowed_tiers, max_uncertainty):
            excluded.append({"encounter_id": r.get("encounter_id"), "reason": f"label_not_eligible:{label_tier(r)}"})
        else:
            eligible.append(r)
    eligible.sort(key=lambda r: r["encounter_id"])
    return eligible, excluded


def split_manifest(result: ValidationResult) -> Dict[str, Any]:
    by_split: Dict[str, Dict[str, Any]] = {s: {"deer": set(), "encounters": 0} for s in SPLITS}
    for r in result.valid_records:
        by_split[r["_split"]]["deer"].add(r["deer_id"])
        by_split[r["_split"]]["encounters"] += 1
    return {
        "dataset_sha256": result.dataset_sha256,
        "split_salt": SPLIT_SALT,
        "splits": {s: {"deer": sorted(v["deer"]), "deer_count": len(v["deer"]), "encounters": v["encounters"]}
                   for s, v in by_split.items()},
    }
