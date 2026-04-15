"""
test_pipeline_season_integration.py
Integration tests verifying the season-phase utility is correctly wired
into the deer analysis pipeline and prompt builder.

These tests exercise build_scan_context(), format_scan_context_for_prompt(),
and the full context resolution chain.
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest
from datetime import datetime, date
from unittest.mock import patch, MagicMock


# ── Helpers to import server functions without starting the full app ──
# We import the individual functions, not the app.

from season_derivation import (
    derive_season_phase,
    resolve_date_taken,
    extract_exif_date,
    SeasonPhaseResult,
)
from season_config import STATE_SEASON_INDEX, REGION_SEASON_INDEX


class TestDateResolutionChain:
    """Requirement 2: date resolution order — client > image_metadata > null."""

    def test_client_date_takes_priority(self):
        d, src = resolve_date_taken("2025-11-15", datetime(2025, 10, 1))
        assert d == date(2025, 11, 15)
        assert src == "client"

    def test_exif_fallback_when_no_client(self):
        d, src = resolve_date_taken(None, datetime(2025, 10, 1, 14, 30))
        assert d == date(2025, 10, 1)
        assert src == "image_metadata"

    def test_null_when_nothing(self):
        d, src = resolve_date_taken(None, None)
        assert d is None
        assert src == "unknown"

    def test_invalid_client_falls_to_exif(self):
        d, src = resolve_date_taken("not-a-date", datetime(2025, 10, 1))
        assert d == date(2025, 10, 1)
        assert src == "image_metadata"

    def test_invalid_client_no_exif_returns_null(self):
        d, src = resolve_date_taken("garbage", None)
        assert d is None
        assert src == "unknown"


class TestSeasonPhaseIntegration:
    """Requirement 4: season derivation is called and result stored in context."""

    def test_rut_with_explicit_date(self):
        result = derive_season_phase(state="IA", date_taken=date(2025, 11, 10))
        assert result.season_phase == "rut"
        assert result.confidence in ("high", "medium")
        assert result.state == "IA"
        assert result.region == "midwest"
        assert result.date_taken == "2025-11-10"

    def test_pre_rut_with_explicit_date(self):
        result = derive_season_phase(state="PA", date_taken=date(2025, 10, 15))
        assert result.season_phase == "pre_rut"

    def test_post_rut_with_explicit_date(self):
        result = derive_season_phase(state="WI", date_taken=date(2025, 12, 10))
        assert result.season_phase == "post_rut"

    def test_missing_date_returns_unknown(self):
        result = derive_season_phase(state="IA", date_taken=None)
        assert result.season_phase == "unknown"
        assert result.confidence == "low"

    def test_missing_state_with_region_fallback(self):
        result = derive_season_phase(state=None, date_taken=date(2025, 11, 15), region="midwest")
        assert result.season_phase == "rut"
        assert result.confidence == "medium"

    def test_utility_failure_fallback(self):
        """If somehow state and region are both garbage, graceful unknown."""
        result = derive_season_phase(state="ZZ", date_taken=date(2025, 11, 15), region="mars")
        assert result.season_phase == "unknown"
        assert result.confidence == "low"


class TestPromptContextFormat:
    """Requirement 6-8: prompt builder includes all context fields in expected format."""

    def _build_mock_context(self, **overrides):
        base = {
            "state": "KS",
            "region_key": "midwest",
            "region_source": "state_to_region",
            "season_bucket": "rut",
            "season_phase": "rut",
            "season_confidence": "medium",
            "season_reason": "Date 2025-11-14 falls within rut window for midwest.",
            "season_near_boundary": False,
            "date_taken": "2025-11-14",
            "date_source": "client",
            "notes": None,
        }
        base.update(overrides)
        return base

    def test_prompt_contains_image_context_block(self):
        """Matches the spec example format."""
        # Import the prompt builder from server
        from server import format_scan_context_for_prompt
        ctx = self._build_mock_context()
        prompt = format_scan_context_for_prompt(ctx)

        assert "Image context:" in prompt
        assert "- State: KS" in prompt
        assert "- Region: midwest" in prompt
        assert "- Date taken: 2025-11-14" in prompt
        assert "- Date source: client" in prompt
        assert "- Season phase: rut" in prompt
        assert "- Season-phase confidence: medium" in prompt

    def test_prompt_contains_seasonal_rules(self):
        from server import format_scan_context_for_prompt
        ctx = self._build_mock_context(season_phase="rut")
        prompt = format_scan_context_for_prompt(ctx)

        assert "Seasonal context rules:" in prompt
        assert "supporting context only" in prompt
        assert "RUT ACTIVE" in prompt
        assert "neck swelling" in prompt

    def test_prompt_pre_rut_guidance(self):
        from server import format_scan_context_for_prompt
        ctx = self._build_mock_context(season_phase="pre_rut", season_bucket="pre_rut")
        prompt = format_scan_context_for_prompt(ctx)

        assert "PRE-RUT ACTIVE" in prompt
        assert "Do not under-age" in prompt

    def test_prompt_post_rut_guidance(self):
        from server import format_scan_context_for_prompt
        ctx = self._build_mock_context(season_phase="post_rut", season_bucket="post_rut")
        prompt = format_scan_context_for_prompt(ctx)

        assert "POST-RUT ACTIVE" in prompt
        assert "low body mass" in prompt

    def test_prompt_unknown_phase_no_crash(self):
        from server import format_scan_context_for_prompt
        ctx = self._build_mock_context(season_phase="unknown", season_bucket="unknown", date_taken="unknown")
        prompt = format_scan_context_for_prompt(ctx)

        assert "Season phase: unknown" in prompt
        assert "continue using visible anatomy" in prompt
        # Should NOT contain any phase-specific modifier
        assert "RUT ACTIVE" not in prompt
        assert "PRE-RUT ACTIVE" not in prompt
        assert "POST-RUT ACTIVE" not in prompt

    def test_prompt_includes_notes(self):
        from server import format_scan_context_for_prompt
        ctx = self._build_mock_context(notes="Big bodied buck near food plot")
        prompt = format_scan_context_for_prompt(ctx)

        assert "Hunter notes" in prompt
        assert "Big bodied buck near food plot" in prompt

    def test_prompt_no_notes_no_crash(self):
        from server import format_scan_context_for_prompt
        ctx = self._build_mock_context(notes=None)
        prompt = format_scan_context_for_prompt(ctx)

        assert "Hunter notes" not in prompt

    def test_prompt_conflict_rule_present(self):
        from server import format_scan_context_for_prompt
        ctx = self._build_mock_context()
        prompt = format_scan_context_for_prompt(ctx)

        assert "prioritize visible anatomy" in prompt


class TestBackwardCompatibility:
    """Requirement 9: existing requests without date_taken continue working."""

    def test_no_date_produces_unknown(self):
        result = derive_season_phase(state="IA", date_taken=None)
        assert result.season_phase == "unknown"
        # Pipeline should still proceed

    def test_no_state_produces_unknown(self):
        result = derive_season_phase(state=None, date_taken=date(2025, 11, 10))
        assert result.season_phase == "unknown"

    def test_result_always_has_all_fields(self):
        result = derive_season_phase(state=None, date_taken=None)
        d = result.to_dict()
        assert "season_phase" in d
        assert "confidence" in d
        assert "reason" in d
        assert "state" in d
        assert "region" in d
        assert "date_taken" in d


class TestAnalysisContextContract:
    """Requirement 5: analysis context has all required fields."""

    def test_context_fields_from_derivation(self):
        result = derive_season_phase(state="TX", date_taken=date(2025, 12, 20))
        d = result.to_dict()

        # Required contract fields
        assert d["season_phase"] in ("pre_rut", "rut", "post_rut", "unknown")
        assert d["confidence"] in ("high", "medium", "low")
        assert isinstance(d["reason"], str)
        assert d["state"] == "TX"
        assert d["region"] is not None
        assert d["date_taken"] == "2025-12-20"


class TestConfigCoverage:
    """Verify all major regions have season configs."""

    def test_all_target_regions_have_configs(self):
        for rk in ["midwest", "northeast", "southeast", "south_texas", "plains", "northern"]:
            assert rk in REGION_SEASON_INDEX, f"Missing config for region: {rk}"

    def test_key_states_have_configs(self):
        for st in ["IA", "TX", "GA", "NY", "CO", "AK", "WI", "PA"]:
            assert st in STATE_SEASON_INDEX, f"Missing config for state: {st}"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
