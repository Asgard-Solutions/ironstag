"""
Regression tests for the scans_table ORM metadata.

These tests prevent the 'Unconsumed column names' CompileError
that occurs when the insert/update paths reference columns that
are not defined in the SQLAlchemy Table(...) metadata.
"""
import sys
import os

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
    without 'Unconsumed column names' error.
    """
    from server import scans_table
    from datetime import datetime, date

    # Build the same .values() dict that analyze_deer() uses
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
        reasoning="Mature deer with good body condition.",
        notes=None,
        raw_response={},
        created_at=datetime.utcnow(),
        raw_confidence=70,
        raw_age_confidence=65,
        raw_recommendation_confidence=72,
        age_confidence=68,
        recommendation_confidence=72,
        age_uncertain=False,
        calibration_version="v2-region-heuristic",
        region_key="southeast",
        region_source="user_profile",
        region_state="OK",
        calibration_strategy="heuristic",
        calibration_fallback_reason=None,
        season_bucket="fall",
        analysis_prompt_version="v2",
        # THE CRITICAL FIELDS — these caused the CompileError
        date_taken=date(2024, 11, 5),
        date_source="client",
        season_phase="rut",
        analysis_model="gpt-4o",
        age_estimation_allowed=True,
        retake_reason=None,
        visible_age_cues=["body_mass", "neck_girth"],
        image_quality_bucket="good",
        quality_factors={"lighting": "good"},
        posture_bucket="broadside",
        image_url=None,
    )

    # This will raise CompileError if any column name is not in the Table metadata
    query = scans_table.insert().values(**insert_values)
    # Compile it (this is what triggers the error)
    compiled = query.compile()
    assert compiled is not None, "Insert query should compile successfully"


def test_build_scan_response_includes_seasonal_fields():
    """Verify the response builder returns seasonal fields when present."""
    from server import build_scan_response
    from datetime import datetime, date

    mock_scan = {
        "id": "test-id",
        "user_id": "test-user",
        "local_image_id": "img-123",
        "deer_age": 3.5,
        "age_bucket": "3-4",
        "age_range": "3.0-4.0",
        "buck_age_class": "mature",
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
        # Seasonal fields
        "date_taken": date(2024, 11, 5),
        "date_source": "client",
        "season_phase": "rut",
    }

    response = build_scan_response(mock_scan)
    assert response.date_taken == "2024-11-05", f"Expected '2024-11-05', got {response.date_taken}"
    assert response.season_phase == "rut", f"Expected 'rut', got {response.season_phase}"
    assert response.date_source == "client", f"Expected 'client', got {response.date_source}"


def test_build_scan_response_handles_null_seasonal_fields():
    """Verify the response builder handles None seasonal fields gracefully."""
    from server import build_scan_response
    from datetime import datetime

    mock_scan = {
        "id": "test-id",
        "user_id": "test-user",
        "local_image_id": "img-123",
        "deer_age": 2.5,
        "age_bucket": None,
        "age_range": None,
        "buck_age_class": None,
        "age_evidence": [],
        "deer_type": "Whitetail",
        "deer_sex": "Doe",
        "antler_points": 0,
        "antler_points_left": None,
        "antler_points_right": None,
        "body_condition": "Good",
        "confidence": 60,
        "recommendation": "PASS",
        "reasoning": "Young doe.",
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
        # NO seasonal fields
        "date_taken": None,
        "date_source": None,
        "season_phase": None,
    }

    response = build_scan_response(mock_scan)
    assert response.date_taken is None
    assert response.season_phase is None
    assert response.date_source is None
