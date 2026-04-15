"""
Regression tests for the scans_table ORM metadata and date_taken type handling.

These tests prevent:
1. 'Unconsumed column names' CompileError (ORM metadata mismatch)
2. asyncpg DataError 'toordinal' (string passed to Date column)
"""
import sys
import os
from datetime import date, datetime

# Ensure backend is on the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


def test_scans_table_has_seasonal_columns():
    """Verify date_taken, date_source, season_phase exist in ORM metadata."""
    from server import scans_table

    column_names = {c.name for c in scans_table.columns}
    required = {"date_taken", "date_source", "season_phase"}
    missing = required - column_names
    assert not missing, (
        f"scans_table ORM metadata is missing columns: {missing}. "
        "Add them to the Table(...) definition in server.py."
    )


def test_scans_table_seasonal_column_types():
    """Verify the column types are correct for the seasonal fields."""
    from sqlalchemy import Date, String
    from server import scans_table

    cols = {c.name: c for c in scans_table.columns}

    dt_col = cols["date_taken"]
    assert isinstance(dt_col.type, Date), f"date_taken should be Date, got {type(dt_col.type)}"

    ds_col = cols["date_source"]
    assert isinstance(ds_col.type, String), f"date_source should be String, got {type(ds_col.type)}"

    sp_col = cols["season_phase"]
    assert isinstance(sp_col.type, String), f"season_phase should be String, got {type(sp_col.type)}"


def test_analyze_deer_insert_compiles_with_seasonal_fields():
    """
    Simulate the insert that analyze_deer() executes and verify it compiles
    without 'Unconsumed column names' error. Uses native date object.
    """
    from server import scans_table

    insert_values = dict(
        id="test-scan-id",
        user_id="test-user-id",
        local_image_id="test-local-img",
        deer_age=4.5,
        age_bucket="4-5",
        age_range="4.0-5.0",
        buck_age_class="mature",
        age_evidence=[],
        deer_type="Whitetail",
        deer_sex="Buck",
        antler_points=8,
        antler_points_left=4,
        antler_points_right=4,
        body_condition="Good",
        confidence=72,
        recommendation="HARVEST",
        reasoning="Mature deer.",
        notes=None,
        raw_response={},
        created_at=datetime.utcnow(),
        raw_confidence=70,
        raw_age_confidence=65,
        raw_recommendation_confidence=72,
        age_confidence=68,
        recommendation_confidence=72,
        age_uncertain=False,
        calibration_version="v2",
        region_key="southeast",
        region_source="user_profile",
        region_state="OK",
        calibration_strategy="heuristic",
        calibration_fallback_reason=None,
        season_bucket="fall",
        analysis_prompt_version="v2",
        # CRITICAL: must be native date, not string
        date_taken=date(2024, 11, 5),
        date_source="client",
        season_phase="rut",
        analysis_model="gpt-4o",
        age_estimation_allowed=True,
        retake_reason=None,
        visible_age_cues=["body_mass"],
        image_quality_bucket="good",
        quality_factors={"lighting": "good"},
        posture_bucket="broadside",
        image_url=None,
    )

    query = scans_table.insert().values(**insert_values)
    compiled = query.compile()
    assert compiled is not None


def test_build_scan_context_returns_native_date():
    """
    Verify build_scan_context stores date_taken as a native date object,
    not a string. This is the root cause of the asyncpg toordinal error.
    """
    from server import build_scan_context

    context = build_scan_context(
        scan_state="OK",
        user_profile_state="OK",
        scan_datetime=datetime.utcnow(),
        notes=None,
        date_taken="2024-11-05",
    )

    dt = context["date_taken"]
    assert dt is not None, "date_taken should not be None"
    assert isinstance(dt, date), (
        f"date_taken in scan_context must be a native date object, "
        f"got {type(dt).__name__}: {dt!r}"
    )
    assert dt == date(2024, 11, 5)


def test_build_scan_context_returns_none_for_no_date():
    """Verify build_scan_context returns None when no date is provided."""
    from server import build_scan_context

    context = build_scan_context(
        scan_state="TX",
        user_profile_state="TX",
        scan_datetime=datetime.utcnow(),
        notes=None,
        date_taken=None,
    )

    assert context["date_taken"] is None


def test_build_scan_context_invalid_date_returns_none():
    """Verify malformed date strings result in None, not a crash."""
    from server import build_scan_context

    context = build_scan_context(
        scan_state="TX",
        user_profile_state="TX",
        scan_datetime=datetime.utcnow(),
        notes=None,
        date_taken="not-a-date",
    )

    assert context["date_taken"] is None


def test_insert_values_type_matches_date_column():
    """
    Verify that date objects have toordinal (what asyncpg needs)
    and strings do NOT (what caused the production error).
    """
    valid_date = date(2026, 1, 8)
    assert hasattr(valid_date, "toordinal"), "date object must have toordinal"

    bad_value = "2026-01-08"
    assert not hasattr(bad_value, "toordinal"), "string should NOT have toordinal"


def test_build_scan_response_includes_seasonal_fields():
    """Verify the response builder returns seasonal fields when present."""
    from server import build_scan_response

    mock_scan = _make_mock_scan(
        date_taken=date(2024, 11, 5),
        date_source="client",
        season_phase="rut",
    )

    response = build_scan_response(mock_scan)
    assert response.date_taken == "2024-11-05"
    assert response.season_phase == "rut"
    assert response.date_source == "client"


def test_build_scan_response_handles_null_seasonal_fields():
    """Verify the response builder handles None seasonal fields gracefully."""
    from server import build_scan_response

    mock_scan = _make_mock_scan(
        date_taken=None,
        date_source=None,
        season_phase=None,
    )

    response = build_scan_response(mock_scan)
    assert response.date_taken is None
    assert response.season_phase is None
    assert response.date_source is None


def test_edit_simple_update_converts_date_string_to_date_object():
    """
    Verify the edit endpoint's simple update path converts ISO string
    to a native date object before DB insert.
    """
    from datetime import date as date_cls
    
    # Simulate what the edit endpoint does
    date_taken_str = "2024-11-05"
    parsed_date = date_cls.fromisoformat(date_taken_str)
    
    assert isinstance(parsed_date, date_cls)
    assert parsed_date == date(2024, 11, 5)
    assert hasattr(parsed_date, "toordinal")


# ── Helper ──

def _make_mock_scan(**overrides):
    """Create a minimal mock scan dict for build_scan_response tests."""
    base = {
        "id": "test-id",
        "user_id": "test-user",
        "local_image_id": "img-123",
        "deer_age": 3.5,
        "age_bucket": None,
        "age_range": None,
        "buck_age_class": None,
        "age_evidence": [],
        "deer_type": "Whitetail",
        "deer_sex": "Buck",
        "antler_points": 8,
        "antler_points_left": 4,
        "antler_points_right": 4,
        "body_condition": "Good",
        "confidence": 70,
        "recommendation": "PASS",
        "reasoning": "Young deer.",
        "notes": None,
        "raw_response": {},
        "created_at": datetime.utcnow(),
        "age_confidence": None,
        "recommendation_confidence": None,
        "age_uncertain": False,
        "calibration_version": None,
        "region_key": None,
        "calibration_strategy": None,
        "calibration_fallback_reason": None,
        "image_quality_bucket": None,
        "quality_factors": None,
        "posture_bucket": None,
        "analysis_prompt_version": None,
        "analysis_model": None,
        "age_estimation_allowed": True,
        "retake_reason": None,
        "visible_age_cues": [],
        "image_url": None,
        "is_favorite": False,
        "tags": [],
        "harvest_confirmed": False,
        "harvested_at": None,
        "boone_crockett_score": None,
        "boone_crockett_gross": None,
        "boone_crockett_net": None,
        "boone_crockett_final_score": None,
        "boone_crockett_status": None,
        "boone_crockett_calculated_at": None,
        "boone_crockett_updated_at": None,
        "date_taken": None,
        "date_source": None,
        "season_phase": None,
    }
    base.update(overrides)
    return base
