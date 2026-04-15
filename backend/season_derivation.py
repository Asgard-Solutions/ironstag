"""
season_derivation.py
Isolated, pure utility for deriving season_phase from state + date_taken.

IMPORTANT: The output of this utility is heuristic support for prompt context,
NOT biological truth. Rut timing varies by local herd, weather, photoperiod,
and genetics. These ranges are deliberately conservative.

Designed for:
- Wildlife experts to tune season_config.py without changing this code.
- Prompt builders to receive structured, debug-friendly results.
- Future refinement without breaking the API contract.
"""

from datetime import datetime, date
from typing import Optional, Dict, Tuple
from dataclasses import dataclass, asdict

from season_config import (
    SeasonWindowConfig,
    DateWindow,
    STATE_SEASON_INDEX,
    REGION_SEASON_INDEX,
    STATE_NAME_TO_ABBR,
    SEASON_WINDOW_CONFIGS,
)


# ============================================================================
# OUTPUT MODEL
# ============================================================================

@dataclass(frozen=True)
class SeasonPhaseResult:
    """Structured result from season phase derivation."""
    season_phase: str          # pre_rut | rut | post_rut | unknown
    confidence: str            # high | medium | low
    reason: str                # Human/machine-readable explanation
    state: Optional[str]       # Normalized state abbreviation or None
    region: Optional[str]      # Resolved region key or None
    date_taken: Optional[str]  # Normalized YYYY-MM-DD or None
    # Debug metadata
    matched_config_key: Optional[str] = None
    matched_window: Optional[str] = None
    near_boundary: bool = False

    def to_dict(self) -> dict:
        return asdict(self)


# ============================================================================
# STATE NORMALIZATION
# ============================================================================

def normalize_state(raw: Optional[str]) -> Optional[str]:
    """
    Normalize state input to uppercase two-letter abbreviation.
    Handles: None, empty, lowercase, full names, extra whitespace.
    Returns None if normalization fails.
    """
    if not raw or not isinstance(raw, str):
        return None

    cleaned = raw.strip()
    if not cleaned:
        return None

    # Try as 2-letter abbreviation
    if len(cleaned) <= 3:
        upper = cleaned.upper()
        if upper in STATE_SEASON_INDEX:
            return upper
        # Might be a valid state not in our season config
        # Still return it normalized
        if len(upper) == 2 and upper.isalpha():
            return upper
        return None

    # Try as full state name
    lower = cleaned.lower()
    abbr = STATE_NAME_TO_ABBR.get(lower)
    if abbr:
        return abbr

    return None


# ============================================================================
# DATE HANDLING
# ============================================================================

def parse_date_taken(raw: Optional[str]) -> Optional[date]:
    """
    Parse and validate a date_taken string in YYYY-MM-DD format.
    Returns None for invalid, empty, or unparseable input.
    Never raises exceptions.
    """
    if not raw or not isinstance(raw, str):
        return None
    try:
        return date.fromisoformat(raw.strip())
    except (ValueError, TypeError):
        return None


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
    parsed = parse_date_taken(client_date)
    if parsed:
        return parsed, "client"

    if exif_date and isinstance(exif_date, datetime):
        return exif_date.date(), "image_metadata"

    return None, "unknown"


def extract_exif_date(image_bytes: bytes) -> Optional[datetime]:
    """
    Try to extract the capture date from JPEG EXIF metadata.
    Returns None if no reliable date is found. Never raises.
    """
    try:
        import io
        from PIL import Image as PilImage

        img = PilImage.open(io.BytesIO(image_bytes))
        exif_data = img.getexif()
        if not exif_data:
            return None

        # Try DateTimeOriginal (tag 36867) first, then DateTime (tag 306)
        for tag_id in (36867, 306):
            raw = exif_data.get(tag_id)
            if raw and isinstance(raw, str):
                try:
                    return datetime.strptime(raw, "%Y:%m:%d %H:%M:%S")
                except ValueError:
                    continue

        return None
    except Exception:
        return None


# ============================================================================
# CORE DATE-IN-WINDOW LOGIC
# ============================================================================

def _day_of_year(month: int, day: int) -> int:
    """Approximate day-of-year for month/day (ignoring leap years, good enough for windows)."""
    # Cumulative days per month (non-leap)
    cum = [0, 31, 59, 90, 120, 151, 181, 212, 243, 273, 304, 334]
    return cum[month - 1] + day


def _date_in_window(month: int, day: int, window: DateWindow) -> bool:
    """Check if month/day falls within a DateWindow (inclusive)."""
    sm, sd, em, ed = window
    if sm <= em:
        # Normal range within same year segment
        return (month > sm or (month == sm and day >= sd)) and \
               (month < em or (month == em and day <= ed))
    else:
        # Year wrap-around (e.g., Dec 15 – Jan 15)
        return (month > sm or (month == sm and day >= sd)) or \
               (month < em or (month == em and day <= ed))


def _days_from_boundary(month: int, day: int, window: DateWindow) -> int:
    """
    Compute minimum distance (in days) from current date to the nearest
    boundary of the window. Used to detect "near boundary" dates.
    Returns 0 if exactly on a boundary, or a positive integer.
    """
    doy = _day_of_year(month, day)
    start_doy = _day_of_year(window.start_month, window.start_day)
    end_doy = _day_of_year(window.end_month, window.end_day)

    dist_start = abs(doy - start_doy)
    dist_end = abs(doy - end_doy)

    # Handle year wrap (distances can't exceed ~183)
    dist_start = min(dist_start, 365 - dist_start)
    dist_end = min(dist_end, 365 - dist_end)

    return min(dist_start, dist_end)


# ============================================================================
# MAIN DERIVATION FUNCTION
# ============================================================================

def derive_season_phase(
    state: Optional[str] = None,
    date_taken: Optional[date] = None,
    region: Optional[str] = None,
) -> SeasonPhaseResult:
    """
    Derive season_phase from state + date_taken.

    This function is pure, deterministic, and side-effect free.

    Priority for config resolution:
      1. State-specific config (highest confidence)
      2. Region-level fallback (medium confidence)
      3. Unknown (low confidence)

    Args:
        state:      Raw state input (abbreviation or full name). Normalized internally.
        date_taken: Parsed date object, or None.
        region:     Optional pre-resolved region key. Used as fallback if state
                    doesn't map to a config.

    Returns:
        SeasonPhaseResult with phase, confidence, reason, and debug metadata.
    """
    # Step 1: Normalize state
    norm_state = normalize_state(state)

    # Step 2: No date → unknown immediately
    if date_taken is None:
        return SeasonPhaseResult(
            season_phase="unknown",
            confidence="low",
            reason="No date_taken provided; cannot determine seasonal phase.",
            state=norm_state,
            region=region,
            date_taken=None,
        )

    date_str = date_taken.isoformat()
    month = date_taken.month
    day = date_taken.day

    # Step 3: Resolve config by state (highest specificity)
    config: Optional[SeasonWindowConfig] = None
    config_source = "none"

    if norm_state and norm_state in STATE_SEASON_INDEX:
        config = STATE_SEASON_INDEX[norm_state]
        config_source = "state"

    # Step 4: Fall back to region config
    if config is None and region:
        rk = region.strip().lower()
        if rk in REGION_SEASON_INDEX:
            config = REGION_SEASON_INDEX[rk]
            config_source = "region_fallback"

    # Step 5: No config found
    if config is None:
        return SeasonPhaseResult(
            season_phase="unknown",
            confidence="low",
            reason=f"No season config for state={norm_state} region={region}. "
                   f"Date {date_str} cannot be evaluated.",
            state=norm_state,
            region=region,
            date_taken=date_str,
        )

    resolved_region = config.region_key

    # Step 6: Check each phase window
    phase_windows = [
        ("pre_rut", config.pre_rut),
        ("rut", config.rut),
        ("post_rut", config.post_rut),
    ]

    for phase_name, window in phase_windows:
        if _date_in_window(month, day, window):
            # Determine boundary proximity
            boundary_dist = _days_from_boundary(month, day, window)
            near_boundary = boundary_dist <= config.boundary_edge_days

            # Determine confidence
            if config_source == "state":
                confidence = "medium" if near_boundary else "high"
            else:
                # Region fallback is inherently less precise
                confidence = "low" if near_boundary else "medium"

            window_str = (
                f"{window.start_month:02d}/{window.start_day:02d}"
                f"–{window.end_month:02d}/{window.end_day:02d}"
            )

            reason_parts = [
                f"Date {date_str} falls within {phase_name} window "
                f"({window_str}) for {resolved_region}.",
            ]
            if near_boundary:
                reason_parts.append(
                    f"Near phase boundary ({boundary_dist}d from edge); "
                    f"confidence downgraded."
                )
            if config_source == "region_fallback":
                reason_parts.append(
                    f"Derived from region fallback ({region}), not state-specific config."
                )

            return SeasonPhaseResult(
                season_phase=phase_name,
                confidence=confidence,
                reason=" ".join(reason_parts),
                state=norm_state,
                region=resolved_region,
                date_taken=date_str,
                matched_config_key=config.region_key,
                matched_window=window_str,
                near_boundary=near_boundary,
            )

    # Step 7: Date doesn't fall in any phase window (off-season / velvet)
    return SeasonPhaseResult(
        season_phase="unknown",
        confidence="high" if config_source == "state" else "medium",
        reason=f"Date {date_str} is outside all season windows for "
               f"{resolved_region}. Likely off-season or velvet period.",
        state=norm_state,
        region=resolved_region,
        date_taken=date_str,
        matched_config_key=config.region_key,
    )
