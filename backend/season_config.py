"""
season_config.py
Configuration-driven season timing rules for deer aging analysis.

This file contains ONLY data / configuration. No business logic.
Wildlife experts can update date ranges here without touching derivation code.

IMPORTANT: These windows are conservative heuristics, not biological truth.
Rut timing varies by local herd, weather, photoperiod, and genetics.
These ranges represent the broadest defensible window for each phase.
"""

from typing import Dict, List, NamedTuple


class DateWindow(NamedTuple):
    """Inclusive date range defined by month/day boundaries."""
    start_month: int
    start_day: int
    end_month: int
    end_day: int


class SeasonWindowConfig(NamedTuple):
    """Season timing configuration for a region or state group."""
    region_key: str
    states: List[str]
    pre_rut: DateWindow
    rut: DateWindow
    post_rut: DateWindow
    # Number of days at each boundary edge to treat as "near boundary"
    # and downgrade confidence. Set to 0 to disable.
    boundary_edge_days: int


# ============================================================================
# REGION-LEVEL SEASON WINDOWS
# ============================================================================
# Each entry defines approximate date ranges for pre_rut, rut, post_rut.
# Dates outside all three windows resolve to "unknown" (off-season / velvet).
#
# Boundary approach:
#   Dates within `boundary_edge_days` of a phase transition are still assigned
#   to the matching phase, but confidence is downgraded from "high" to "medium".
#   This avoids returning "unknown" for borderline dates while signaling less
#   certainty to the prompt.
# ============================================================================

SEASON_WINDOW_CONFIGS: List[SeasonWindowConfig] = [

    # ── Midwest ──────────────────────────────────────────────────────────────
    # Core whitetail states. Peak rut typically Nov 5–20.
    SeasonWindowConfig(
        region_key="midwest",
        states=["IA", "IL", "IN", "KS", "MI", "MN", "MO", "ND", "NE", "OH", "SD", "WI"],
        pre_rut=DateWindow(10, 1, 10, 31),
        rut=DateWindow(11, 1, 11, 25),
        post_rut=DateWindow(11, 26, 12, 31),
        boundary_edge_days=3,
    ),

    # ── Northeast ────────────────────────────────────────────────────────────
    # Rut typically peaks early-to-mid November.
    SeasonWindowConfig(
        region_key="northeast",
        states=["CT", "DE", "MA", "MD", "ME", "NH", "NJ", "NY", "PA", "RI", "VT"],
        pre_rut=DateWindow(10, 1, 10, 31),
        rut=DateWindow(11, 1, 11, 30),
        post_rut=DateWindow(12, 1, 12, 31),
        boundary_edge_days=3,
    ),

    # ── Southeast ────────────────────────────────────────────────────────────
    # Later rut than northern states. Peaks late Nov–Dec in many areas.
    SeasonWindowConfig(
        region_key="southeast",
        states=["AL", "AR", "FL", "GA", "KY", "LA", "MS", "NC", "OK", "SC", "TN", "VA", "WV"],
        pre_rut=DateWindow(10, 15, 11, 14),
        rut=DateWindow(11, 15, 12, 31),
        post_rut=DateWindow(1, 1, 1, 31),
        boundary_edge_days=5,
    ),

    # ── South Texas ──────────────────────────────────────────────────────────
    # Unique late rut peaking mid-Dec through mid-Jan.
    SeasonWindowConfig(
        region_key="south_texas",
        states=["TX"],
        pre_rut=DateWindow(11, 15, 12, 14),
        rut=DateWindow(12, 15, 1, 15),
        post_rut=DateWindow(1, 16, 2, 15),
        boundary_edge_days=5,
    ),

    # ── Plains / Western ─────────────────────────────────────────────────────
    # Broad region. Rut typically mid-Nov.
    SeasonWindowConfig(
        region_key="plains",
        states=["CO", "MT", "NM", "WY", "UT", "ID", "NV", "AZ", "WA", "OR", "CA"],
        pre_rut=DateWindow(10, 15, 11, 9),
        rut=DateWindow(11, 10, 11, 30),
        post_rut=DateWindow(12, 1, 12, 31),
        boundary_edge_days=3,
    ),

    # ── Northern ─────────────────────────────────────────────────────────────
    # Earliest rut. Peaks late Oct–early Nov.
    SeasonWindowConfig(
        region_key="northern",
        states=["AK"],
        pre_rut=DateWindow(9, 25, 10, 24),
        rut=DateWindow(10, 25, 11, 20),
        post_rut=DateWindow(11, 21, 12, 15),
        boundary_edge_days=3,
    ),
]


# ============================================================================
# LOOKUP INDEXES (built at import time for O(1) access)
# ============================================================================

# State abbreviation (uppercase) → SeasonWindowConfig
STATE_SEASON_INDEX: Dict[str, SeasonWindowConfig] = {}
for _cfg in SEASON_WINDOW_CONFIGS:
    for _st in _cfg.states:
        STATE_SEASON_INDEX[_st.upper()] = _cfg

# Region key (lowercase) → SeasonWindowConfig
REGION_SEASON_INDEX: Dict[str, SeasonWindowConfig] = {
    cfg.region_key.lower(): cfg for cfg in SEASON_WINDOW_CONFIGS
}


# ============================================================================
# FULL STATE NAME → ABBREVIATION
# ============================================================================
# Used to normalize user input like "Texas" → "TX"
STATE_NAME_TO_ABBR: Dict[str, str] = {
    "alabama": "AL", "alaska": "AK", "arizona": "AZ", "arkansas": "AR",
    "california": "CA", "colorado": "CO", "connecticut": "CT", "delaware": "DE",
    "florida": "FL", "georgia": "GA", "hawaii": "HI", "idaho": "ID",
    "illinois": "IL", "indiana": "IN", "iowa": "IA", "kansas": "KS",
    "kentucky": "KY", "louisiana": "LA", "maine": "ME", "maryland": "MD",
    "massachusetts": "MA", "michigan": "MI", "minnesota": "MN",
    "mississippi": "MS", "missouri": "MO", "montana": "MT", "nebraska": "NE",
    "nevada": "NV", "new hampshire": "NH", "new jersey": "NJ",
    "new mexico": "NM", "new york": "NY", "north carolina": "NC",
    "north dakota": "ND", "ohio": "OH", "oklahoma": "OK", "oregon": "OR",
    "pennsylvania": "PA", "rhode island": "RI", "south carolina": "SC",
    "south dakota": "SD", "tennessee": "TN", "texas": "TX", "utah": "UT",
    "vermont": "VT", "virginia": "VA", "washington": "WA",
    "west virginia": "WV", "wisconsin": "WI", "wyoming": "WY",
}
