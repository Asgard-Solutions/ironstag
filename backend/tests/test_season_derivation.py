"""
test_season_derivation.py
Comprehensive unit tests for the season derivation utility.

Covers:
- Valid state + date → pre_rut, rut, post_rut
- Missing date → unknown
- Missing state → unknown
- Invalid date → unknown
- Lowercase / full-name state normalization
- Boundary-date behavior
- Region fallback behavior
- South Texas special-case
- Deterministic output
- Confidence levels
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest
from datetime import date
from season_derivation import (
    derive_season_phase,
    normalize_state,
    resolve_date_taken,
    parse_date_taken,
    SeasonPhaseResult,
)


# ============================================================================
# 1. VALID STATE + DATE → PRE_RUT
# ============================================================================

class TestPreRut:
    def test_midwest_pre_rut(self):
        result = derive_season_phase(state="IA", date_taken=date(2025, 10, 15))
        assert result.season_phase == "pre_rut"
        assert result.confidence in ("high", "medium")
        assert result.region == "midwest"

    def test_northeast_pre_rut(self):
        result = derive_season_phase(state="NY", date_taken=date(2025, 10, 10))
        assert result.season_phase == "pre_rut"
        assert result.region == "northeast"

    def test_south_texas_pre_rut(self):
        result = derive_season_phase(state="TX", date_taken=date(2025, 12, 1))
        assert result.season_phase == "pre_rut"
        assert result.region == "south_texas"

    def test_plains_pre_rut(self):
        result = derive_season_phase(state="CO", date_taken=date(2025, 10, 20))
        assert result.season_phase == "pre_rut"
        assert result.region == "plains"

    def test_northern_pre_rut(self):
        result = derive_season_phase(state="AK", date_taken=date(2025, 10, 1))
        assert result.season_phase == "pre_rut"
        assert result.region == "northern"


# ============================================================================
# 2. VALID STATE + DATE → RUT
# ============================================================================

class TestRut:
    def test_midwest_rut(self):
        result = derive_season_phase(state="IA", date_taken=date(2025, 11, 10))
        assert result.season_phase == "rut"
        assert result.confidence in ("high", "medium")

    def test_northeast_rut(self):
        result = derive_season_phase(state="PA", date_taken=date(2025, 11, 15))
        assert result.season_phase == "rut"

    def test_southeast_rut(self):
        result = derive_season_phase(state="GA", date_taken=date(2025, 12, 1))
        assert result.season_phase == "rut"
        assert result.region == "southeast"

    def test_south_texas_rut(self):
        result = derive_season_phase(state="TX", date_taken=date(2025, 12, 25))
        assert result.season_phase == "rut"
        assert result.region == "south_texas"

    def test_south_texas_rut_jan(self):
        """South Texas rut wraps into January."""
        result = derive_season_phase(state="TX", date_taken=date(2026, 1, 5))
        assert result.season_phase == "rut"

    def test_plains_rut(self):
        result = derive_season_phase(state="MT", date_taken=date(2025, 11, 15))
        assert result.season_phase == "rut"

    def test_northern_rut(self):
        result = derive_season_phase(state="AK", date_taken=date(2025, 11, 5))
        assert result.season_phase == "rut"


# ============================================================================
# 3. VALID STATE + DATE → POST_RUT
# ============================================================================

class TestPostRut:
    def test_midwest_post_rut(self):
        result = derive_season_phase(state="WI", date_taken=date(2025, 12, 10))
        assert result.season_phase == "post_rut"

    def test_northeast_post_rut(self):
        result = derive_season_phase(state="NY", date_taken=date(2025, 12, 15))
        assert result.season_phase == "post_rut"

    def test_southeast_post_rut(self):
        result = derive_season_phase(state="GA", date_taken=date(2026, 1, 15))
        assert result.season_phase == "post_rut"

    def test_south_texas_post_rut(self):
        result = derive_season_phase(state="TX", date_taken=date(2026, 2, 1))
        assert result.season_phase == "post_rut"

    def test_northern_post_rut(self):
        result = derive_season_phase(state="AK", date_taken=date(2025, 12, 1))
        assert result.season_phase == "post_rut"


# ============================================================================
# 4. MISSING DATE → UNKNOWN
# ============================================================================

class TestMissingDate:
    def test_no_date(self):
        result = derive_season_phase(state="IA", date_taken=None)
        assert result.season_phase == "unknown"
        assert result.confidence == "low"
        assert "No date_taken" in result.reason

    def test_no_date_with_region(self):
        result = derive_season_phase(state="TX", date_taken=None, region="south_texas")
        assert result.season_phase == "unknown"


# ============================================================================
# 5. MISSING STATE → UNKNOWN (unless region fallback works)
# ============================================================================

class TestMissingState:
    def test_no_state_no_region(self):
        result = derive_season_phase(state=None, date_taken=date(2025, 11, 10))
        assert result.season_phase == "unknown"
        assert result.confidence == "low"

    def test_no_state_with_region_fallback(self):
        result = derive_season_phase(state=None, date_taken=date(2025, 11, 10), region="midwest")
        assert result.season_phase == "rut"
        assert result.confidence == "medium"  # Region fallback = medium
        assert "region fallback" in result.reason.lower()

    def test_empty_state(self):
        result = derive_season_phase(state="", date_taken=date(2025, 11, 10))
        assert result.season_phase == "unknown"

    def test_whitespace_state(self):
        result = derive_season_phase(state="  ", date_taken=date(2025, 11, 10))
        assert result.season_phase == "unknown"


# ============================================================================
# 6. INVALID DATE → UNKNOWN
# ============================================================================

class TestInvalidDate:
    def test_parse_invalid_string(self):
        assert parse_date_taken("not-a-date") is None

    def test_parse_empty(self):
        assert parse_date_taken("") is None

    def test_parse_none(self):
        assert parse_date_taken(None) is None

    def test_parse_number(self):
        assert parse_date_taken("12345") is None

    def test_parse_valid(self):
        result = parse_date_taken("2025-11-15")
        assert result == date(2025, 11, 15)


# ============================================================================
# 7. LOWERCASE / FULL-NAME STATE NORMALIZATION
# ============================================================================

class TestStateNormalization:
    def test_lowercase(self):
        assert normalize_state("ia") == "IA"

    def test_mixed_case(self):
        assert normalize_state("Tx") == "TX"

    def test_full_name(self):
        assert normalize_state("Texas") == "TX"

    def test_full_name_lowercase(self):
        assert normalize_state("iowa") == "IA"

    def test_full_name_with_spaces(self):
        assert normalize_state("  New York  ") == "NY"

    def test_none(self):
        assert normalize_state(None) is None

    def test_empty(self):
        assert normalize_state("") is None

    def test_invalid(self):
        # "ZZ" is structurally valid (2-letter alpha) so it normalizes,
        # but it won't match any season config — derivation handles that.
        assert normalize_state("ZZ") == "ZZ"

    def test_truly_invalid(self):
        assert normalize_state("123") is None
        assert normalize_state("ABCD") is None

    def test_derives_correctly_with_full_name(self):
        result = derive_season_phase(state="Iowa", date_taken=date(2025, 11, 10))
        assert result.season_phase == "rut"
        assert result.state == "IA"


# ============================================================================
# 8. BOUNDARY-DATE BEHAVIOR
# ============================================================================

class TestBoundaryDates:
    def test_midwest_pre_rut_start_boundary(self):
        """Oct 1 is the very start of pre-rut for midwest."""
        result = derive_season_phase(state="IA", date_taken=date(2025, 10, 1))
        assert result.season_phase == "pre_rut"
        assert result.near_boundary is True
        # Boundary → confidence should be downgraded from high to medium
        assert result.confidence == "medium"

    def test_midwest_pre_rut_end_boundary(self):
        """Oct 31 is the end of pre-rut / boundary with rut."""
        result = derive_season_phase(state="IA", date_taken=date(2025, 10, 31))
        assert result.season_phase == "pre_rut"
        assert result.near_boundary is True

    def test_midwest_rut_mid(self):
        """Nov 12 is solidly mid-rut, should be high confidence."""
        result = derive_season_phase(state="IA", date_taken=date(2025, 11, 12))
        assert result.season_phase == "rut"
        assert result.near_boundary is False
        assert result.confidence == "high"

    def test_midwest_rut_start_boundary(self):
        """Nov 1 is the start of rut window — near boundary."""
        result = derive_season_phase(state="IA", date_taken=date(2025, 11, 1))
        assert result.season_phase == "rut"
        assert result.near_boundary is True
        assert result.confidence == "medium"


# ============================================================================
# 9. REGION FALLBACK BEHAVIOR
# ============================================================================

class TestRegionFallback:
    def test_unknown_state_with_region(self):
        """Unknown state but known region should use region fallback."""
        result = derive_season_phase(state="ZZ", date_taken=date(2025, 11, 15), region="midwest")
        assert result.season_phase == "rut"
        assert result.confidence == "medium"  # Region fallback = medium max

    def test_no_state_no_region(self):
        result = derive_season_phase(state=None, date_taken=date(2025, 11, 15))
        assert result.season_phase == "unknown"

    def test_region_fallback_near_boundary_is_low(self):
        """Region fallback + near boundary = low confidence."""
        result = derive_season_phase(state=None, date_taken=date(2025, 11, 1), region="midwest")
        assert result.season_phase == "rut"
        assert result.near_boundary is True
        assert result.confidence == "low"


# ============================================================================
# 10. SOUTH TEXAS SPECIAL CASE
# ============================================================================

class TestSouthTexas:
    def test_south_texas_late_rut(self):
        """TX has a uniquely late rut peaking mid-Dec to mid-Jan."""
        result = derive_season_phase(state="TX", date_taken=date(2025, 12, 20))
        assert result.season_phase == "rut"
        assert result.region == "south_texas"

    def test_south_texas_off_season(self):
        """Summer in TX is off-season."""
        result = derive_season_phase(state="TX", date_taken=date(2025, 7, 15))
        assert result.season_phase == "unknown"
        assert result.confidence == "high"  # Known off-season is confident

    def test_south_texas_different_from_midwest(self):
        """Nov 10 is rut in midwest but pre-rut/off-season in south TX."""
        midwest = derive_season_phase(state="IA", date_taken=date(2025, 11, 10))
        texas = derive_season_phase(state="TX", date_taken=date(2025, 11, 10))
        assert midwest.season_phase == "rut"
        # TX should NOT be rut yet on Nov 10
        assert texas.season_phase != "rut"


# ============================================================================
# 11. DETERMINISTIC OUTPUT
# ============================================================================

class TestDeterministic:
    def test_same_input_same_output(self):
        """Repeated calls with identical input must produce identical output."""
        results = [
            derive_season_phase(state="IA", date_taken=date(2025, 11, 10))
            for _ in range(10)
        ]
        first = results[0]
        for r in results[1:]:
            assert r.season_phase == first.season_phase
            assert r.confidence == first.confidence
            assert r.reason == first.reason
            assert r.near_boundary == first.near_boundary


# ============================================================================
# 12. OFF-SEASON / UNKNOWN HANDLING
# ============================================================================

class TestOffSeason:
    def test_summer_is_unknown(self):
        result = derive_season_phase(state="IA", date_taken=date(2025, 6, 15))
        assert result.season_phase == "unknown"

    def test_spring_is_unknown(self):
        result = derive_season_phase(state="PA", date_taken=date(2025, 4, 1))
        assert result.season_phase == "unknown"


# ============================================================================
# 13. RESOLVE DATE TAKEN
# ============================================================================

class TestResolveDateTaken:
    def test_client_date_priority(self):
        from datetime import datetime
        d, src = resolve_date_taken("2025-11-15", datetime(2025, 10, 1))
        assert d == date(2025, 11, 15)
        assert src == "client"

    def test_exif_fallback(self):
        from datetime import datetime
        d, src = resolve_date_taken(None, datetime(2025, 10, 1, 14, 30))
        assert d == date(2025, 10, 1)
        assert src == "image_metadata"

    def test_no_date(self):
        d, src = resolve_date_taken(None, None)
        assert d is None
        assert src == "unknown"

    def test_invalid_client_falls_to_exif(self):
        from datetime import datetime
        d, src = resolve_date_taken("bad-date", datetime(2025, 10, 1))
        assert d == date(2025, 10, 1)
        assert src == "image_metadata"


# ============================================================================
# 14. RESULT SERIALIZATION
# ============================================================================

class TestSerialization:
    def test_to_dict(self):
        result = derive_season_phase(state="IA", date_taken=date(2025, 11, 10))
        d = result.to_dict()
        assert isinstance(d, dict)
        assert "season_phase" in d
        assert "confidence" in d
        assert "reason" in d
        assert "near_boundary" in d


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
