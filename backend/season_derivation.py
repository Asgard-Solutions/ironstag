"""
season_derivation.py
Isolated utility for deriving season_phase from state + date_taken.
Designed to be refined by wildlife experts without changing the API contract.
"""

from datetime import datetime, date
from typing import Optional, Dict, Tuple

# ============================================================================
# SEASON PHASE ENUM VALUES
# ============================================================================
# These are the canonical values exposed to clients.
SEASON_PHASES = ("pre_rut", "rut", "post_rut", "unknown")

# ============================================================================
# REGION-AWARE SEASON WINDOWS
# ============================================================================
# Each region maps to approximate date ranges for pre_rut, rut, post_rut.
# Dates outside any window default to "unknown" (off-season / velvet period).
# Format: (start_month, start_day, end_month, end_day)
# These are deliberately conservative heuristics.

REGION_SEASON_WINDOWS: Dict[str, Dict[str, Tuple[int, int, int, int]]] = {
    "northeast": {
        "pre_rut":  (10,  1, 10, 31),
        "rut":      (11,  1, 11, 30),
        "post_rut": (12,  1, 12, 31),
    },
    "midwest": {
        "pre_rut":  (10,  1, 10, 31),
        "rut":      (11,  1, 11, 25),
        "post_rut": (11, 26, 12, 31),
    },
    "southeast": {
        "pre_rut":  (10, 15, 11, 14),
        "rut":      (11, 15, 12, 31),
        "post_rut": ( 1,  1,  1, 31),
    },
    "south_texas": {
        "pre_rut":  (11, 15, 12, 14),
        "rut":      (12, 15,  1, 15),
        "post_rut": ( 1, 16,  2, 15),
    },
    "plains": {
        "pre_rut":  (10, 15, 11,  9),
        "rut":      (11, 10, 11, 30),
        "post_rut": (12,  1, 12, 31),
    },
    "northern": {
        "pre_rut":  ( 9, 25, 10, 24),
        "rut":      (10, 25, 11, 20),
        "post_rut": (11, 21, 12, 15),
    },
}

# Fallback when region is unknown
DEFAULT_SEASON_WINDOWS: Dict[str, Tuple[int, int, int, int]] = {
    "pre_rut":  (10,  1, 10, 31),
    "rut":      (11,  1, 11, 30),
    "post_rut": (12,  1, 12, 31),
}


def _date_in_window(month: int, day: int, window: Tuple[int, int, int, int]) -> bool:
    """Check if month/day falls within a (start_month, start_day, end_month, end_day) window."""
    sm, sd, em, ed = window
    if sm <= em:
        # Normal range within same year segment
        return (month > sm or (month == sm and day >= sd)) and \
               (month < em or (month == em and day <= ed))
    else:
        # Year wrap-around (e.g., Dec 15 – Jan 15)
        return (month > sm or (month == sm and day >= sd)) or \
               (month < em or (month == em and day <= ed))


def derive_season_phase(
    state: Optional[str],
    region_key: Optional[str],
    date_taken: Optional[date],
) -> str:
    """
    Derive season_phase from region + date.

    Returns one of: "pre_rut", "rut", "post_rut", "unknown".
    Conservative: returns "unknown" when confidence is low.
    """
    if date_taken is None:
        return "unknown"

    month = date_taken.month
    day = date_taken.day

    # Pick region windows; fall back to default
    rk = (region_key or "unknown").lower()
    windows = REGION_SEASON_WINDOWS.get(rk, DEFAULT_SEASON_WINDOWS)

    for phase, window in windows.items():
        if _date_in_window(month, day, window):
            return phase

    return "unknown"


def resolve_date_taken(
    client_date: Optional[str],
    exif_date: Optional[datetime],
) -> Tuple[Optional[date], str]:
    """
    Resolve the effective date_taken and its source.

    Priority: client-provided > EXIF metadata > None.

    Returns:
        (date_taken, source) where source is "client", "image_metadata", or "unknown".
    """
    # 1. Client-provided date
    if client_date:
        try:
            parsed = date.fromisoformat(client_date)
            return parsed, "client"
        except (ValueError, TypeError):
            pass

    # 2. EXIF date
    if exif_date:
        return exif_date.date(), "image_metadata"

    return None, "unknown"


def extract_exif_date(image_bytes: bytes) -> Optional[datetime]:
    """
    Try to extract the capture date from JPEG EXIF metadata.
    Returns None if no reliable date is found.
    """
    try:
        import io
        from PIL import Image as PilImage
        from PIL.ExifTags import Base as ExifBase

        img = PilImage.open(io.BytesIO(image_bytes))
        exif_data = img.getexif()
        if not exif_data:
            return None

        # Try DateTimeOriginal (tag 36867) first, then DateTime (tag 306)
        for tag_id in (36867, 306):
            raw = exif_data.get(tag_id)
            if raw and isinstance(raw, str):
                # EXIF format: "YYYY:MM:DD HH:MM:SS"
                try:
                    return datetime.strptime(raw, "%Y:%m:%d %H:%M:%S")
                except ValueError:
                    continue

        return None
    except Exception:
        return None
