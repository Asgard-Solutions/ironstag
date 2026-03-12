from datetime import datetime, timezone
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from bc_typical_whitetail import (
    BC_SCORE_TYPE_NON_TYPICAL_MULE_DEER,
    BC_SCORE_TYPE_NON_TYPICAL_WHITETAIL,
    BC_SCORE_TYPE_TYPICAL_MULE_DEER,
    build_bc_score_record,
    calculate_spread_credit,
    calculate_typical_whitetail_column_totals,
    calculate_typical_whitetail_deductions,
    calculate_typical_whitetail_final_score,
    format_inches_to_eighths,
    get_bc_score_type_label,
    is_bc_score_type_allowed_for_scan,
    is_bc_score_complete,
    is_harvested_buck_eligible,
    is_supported_bc_score_type,
    normalize_bc_score_entry,
)


def _build_entry(overrides=None, disclaimer_accepted=True):
    payload = {
        "pointsSummary": {
            "rightPointsCount": 5,
            "leftPointsCount": 5,
            "tipToTipSpread": 16.0,
            "greatestSpread": 18.0,
        },
        "spread": {
            "insideSpreadOfMainBeams": 18.0,
        },
        "abnormalPoints": {
            "right": [],
            "left": [],
        },
        "right": {
            "mainBeam": 24.0,
            "g1": 5.0,
            "g2": 10.0,
            "g3": 8.0,
            "g4": 6.0,
            "g5": None,
            "g6": None,
            "g7": None,
            "h1": 4.5,
            "h2": 4.0,
            "h3": 3.75,
            "h4": 3.5,
            "extraPoints": [],
        },
        "left": {
            "mainBeam": 23.5,
            "g1": 5.0,
            "g2": 9.5,
            "g3": 7.5,
            "g4": 6.0,
            "g5": None,
            "g6": None,
            "g7": None,
            "h1": 4.25,
            "h2": 3.75,
            "h3": 3.5,
            "h4": 3.5,
            "extraPoints": [],
        },
    }
    if overrides:
        for key, value in overrides.items():
            if isinstance(value, dict) and isinstance(payload.get(key), dict):
                payload[key].update(value)
            else:
                payload[key] = value
    entry = normalize_bc_score_entry(payload, disclaimer_accepted)
    assert entry is not None
    return entry


def _build_mule_entry(overrides=None, disclaimer_accepted=True):
    payload = {
        "type": BC_SCORE_TYPE_TYPICAL_MULE_DEER,
        "pointsSummary": {
            "rightPointsCount": 4,
            "leftPointsCount": 4,
            "tipToTipSpread": 24.0,
            "greatestSpread": 25.0,
        },
        "spread": {
            "insideSpreadOfMainBeams": 22.0,
        },
        "abnormalPoints": {
            "right": [1.5],
            "left": [0.5],
        },
        "right": {
            "mainBeam": 25.0,
            "g1": 16.0,
            "g2": 15.0,
            "g3": 8.0,
            "g4": 5.0,
            "g5": 10.0,
            "g6": 9.0,
            "g7": None,
            "h1": 5.0,
            "h2": 4.5,
            "h3": 4.0,
            "h4": 3.75,
            "extraPoints": [2.5],
        },
        "left": {
            "mainBeam": 24.5,
            "g1": 15.5,
            "g2": 14.5,
            "g3": 7.5,
            "g4": 4.5,
            "g5": 9.0,
            "g6": 8.0,
            "g7": None,
            "h1": 4.75,
            "h2": 4.5,
            "h3": 4.0,
            "h4": 3.5,
            "extraPoints": [1.5],
        },
    }
    if overrides:
        for key, value in overrides.items():
            if isinstance(value, dict) and isinstance(payload.get(key), dict):
                payload[key].update(value)
            else:
                payload[key] = value
    entry = normalize_bc_score_entry(payload, disclaimer_accepted)
    assert entry is not None
    return entry


def _build_non_typical_whitetail_entry(overrides=None, disclaimer_accepted=True):
    payload = {
        "type": BC_SCORE_TYPE_NON_TYPICAL_WHITETAIL,
        "pointsSummary": {
            "rightPointsCount": 6,
            "leftPointsCount": 5,
            "tipToTipSpread": 18.0,
            "greatestSpread": 19.0,
        },
        "spread": {
            "insideSpreadOfMainBeams": 18.0,
        },
        "abnormalPoints": {
            "right": [1.0, 0.5],
            "left": [0.25],
        },
        "right": {
            "mainBeam": 24.0,
            "g1": 5.0,
            "g2": 10.0,
            "g3": 8.0,
            "g4": 6.0,
            "g5": 3.5,
            "g6": None,
            "g7": None,
            "h1": 4.5,
            "h2": 4.0,
            "h3": 3.75,
            "h4": 3.5,
            "extraPoints": [1.5],
        },
        "left": {
            "mainBeam": 23.5,
            "g1": 5.0,
            "g2": 9.5,
            "g3": 7.5,
            "g4": 6.0,
            "g5": None,
            "g6": None,
            "g7": None,
            "h1": 4.25,
            "h2": 3.75,
            "h3": 3.5,
            "h4": 3.5,
            "extraPoints": [0.5],
        },
    }
    if overrides:
        for key, value in overrides.items():
            if isinstance(value, dict) and isinstance(payload.get(key), dict):
                payload[key].update(value)
            else:
                payload[key] = value
    entry = normalize_bc_score_entry(payload, disclaimer_accepted)
    assert entry is not None
    return entry


def _build_non_typical_mule_entry(overrides=None, disclaimer_accepted=True):
    payload = {
        "type": BC_SCORE_TYPE_NON_TYPICAL_MULE_DEER,
        "pointsSummary": {
            "rightPointsCount": 5,
            "leftPointsCount": 4,
            "tipToTipSpread": 28.0,
            "greatestSpread": 29.0,
        },
        "spread": {
            "insideSpreadOfMainBeams": 27.0,
        },
        "abnormalPoints": {
            "right": [4.0, 2.5],
            "left": [1.5],
        },
        "right": {
            "mainBeam": 26.0,
            "g1": 17.0,
            "g2": 14.0,
            "g3": 10.0,
            "g4": 6.0,
            "g5": 9.0,
            "g6": None,
            "g7": None,
            "h1": 5.0,
            "h2": 4.75,
            "h3": 4.25,
            "h4": 4.0,
            "extraPoints": [2.0],
        },
        "left": {
            "mainBeam": 25.5,
            "g1": 16.0,
            "g2": 13.5,
            "g3": 9.0,
            "g4": 5.5,
            "g5": 8.0,
            "g6": None,
            "g7": None,
            "h1": 4.75,
            "h2": 4.5,
            "h3": 4.0,
            "h4": 3.75,
            "extraPoints": [1.0],
        },
    }
    if overrides:
        for key, value in overrides.items():
            if isinstance(value, dict) and isinstance(payload.get(key), dict):
                payload[key].update(value)
            else:
                payload[key] = value
    entry = normalize_bc_score_entry(payload, disclaimer_accepted)
    assert entry is not None
    return entry


def test_spread_credit_caps_at_longer_main_beam():
    entry = _build_entry({"spread": {"insideSpreadOfMainBeams": 30.0}})
    assert calculate_spread_credit(entry) == 24.0


def test_final_score_uses_column_totals_minus_deductions():
    entry = _build_entry()
    assert calculate_typical_whitetail_column_totals(entry) == {
        "rightTotal": 68.75,
        "leftTotal": 66.5,
    }
    assert calculate_typical_whitetail_deductions(entry)["pairedDifferencesTotal"] == 2.25
    assert calculate_typical_whitetail_final_score(entry) == 151.0


def test_deductions_include_paired_measurements_and_abnormal_points():
    entry = _build_entry(
        {
            "abnormalPoints": {
                "right": [1.0, 0.5],
                "left": [0.25],
            }
        }
    )
    deductions = calculate_typical_whitetail_deductions(entry)
    assert deductions["pairedDifferencesTotal"] == 2.25
    assert deductions["abnormalDeductionTotal"] == 1.75
    assert deductions["deductionsTotal"] == 4.0
    assert calculate_typical_whitetail_final_score(entry) == 149.25


def test_typical_whitetail_supports_points_beyond_g7_and_keeps_abnormal_totals():
    entry = _build_entry(
        {
            "right": {"extraPoints": [1.5]},
            "left": {"extraPoints": [0.5]},
            "abnormalPoints": {
                "right": [1.25, 0.5],
                "left": [0.25],
            },
        }
    )
    score = build_bc_score_record(entry)
    assert score["computed"]["rightTotal"] == 70.25
    assert score["computed"]["leftTotal"] == 67.0
    assert score["computed"]["deductionsTotal"] == 5.25
    assert score["computed"]["finalScore"] == 150.0
    assert score["differences"]["g8"] == 1.0
    assert score["abnormalPoints"]["rightTotalLength"] == 1.75
    assert score["abnormalPoints"]["leftTotalLength"] == 0.25
    assert score["abnormalPoints"]["totalLength"] == 2.0


def test_typical_mule_deer_uses_g1_to_g4_and_separate_abnormal_points():
    entry = _build_mule_entry()
    assert calculate_typical_whitetail_column_totals(entry) == {
        "rightTotal": 86.25,
        "leftTotal": 83.25,
    }
    deductions = calculate_typical_whitetail_deductions(entry)
    assert deductions["pairedDifferencesTotal"] == 3.0
    assert deductions["abnormalDeductionTotal"] == 6.0
    assert deductions["deductionsTotal"] == 9.0
    assert calculate_typical_whitetail_final_score(entry) == 182.5

    score = build_bc_score_record(entry)
    assert score["computed"]["grossScore"] == 191.5
    assert score["computed"]["finalScore"] == 182.5
    assert "g5" not in score["differences"]
    assert "g8" not in score["differences"]
    assert score["abnormalPoints"]["rightTotalLength"] == 4.0
    assert score["abnormalPoints"]["leftTotalLength"] == 2.0
    assert score["abnormalPoints"]["totalLength"] == 6.0


def test_non_typical_whitetail_adds_abnormal_total_after_subtotal_two():
    entry = _build_non_typical_whitetail_entry()
    assert calculate_typical_whitetail_column_totals(entry) == {
        "rightTotal": 72.25,
        "leftTotal": 66.5,
    }
    deductions = calculate_typical_whitetail_deductions(entry)
    assert deductions["pairedDifferencesTotal"] == 5.75
    assert deductions["abnormalDeductionTotal"] == 3.75
    assert deductions["deductionsTotal"] == 5.75
    assert calculate_typical_whitetail_final_score(entry) == 154.75

    score = build_bc_score_record(entry)
    assert score["computed"]["subtotalOne"] == 156.75
    assert score["computed"]["subtotalTwo"] == 151.0
    assert score["computed"]["grossScore"] == 160.5
    assert score["computed"]["finalScore"] == 154.75
    assert "g8" not in score["differences"]
    assert score["abnormalPoints"]["rightTotalLength"] == 3.0
    assert score["abnormalPoints"]["leftTotalLength"] == 0.75
    assert score["abnormalPoints"]["totalLength"] == 3.75


def test_non_typical_mule_deer_uses_mule_field_set_and_non_typical_totals():
    entry = _build_non_typical_mule_entry()
    assert calculate_typical_whitetail_column_totals(entry) == {
        "rightTotal": 91.0,
        "leftTotal": 86.5,
    }
    deductions = calculate_typical_whitetail_deductions(entry)
    assert deductions["pairedDifferencesTotal"] == 4.5
    assert deductions["abnormalDeductionTotal"] == 11.0
    assert deductions["deductionsTotal"] == 4.5
    assert calculate_spread_credit(entry) == 26.0
    assert calculate_typical_whitetail_final_score(entry) == 210.0

    score = build_bc_score_record(entry)
    assert score["computed"]["subtotalOne"] == 203.5
    assert score["computed"]["subtotalTwo"] == 199.0
    assert score["computed"]["grossScore"] == 214.5
    assert score["computed"]["finalScore"] == 210.0
    assert "g5" not in score["differences"]
    assert "g8" not in score["differences"]
    assert score["abnormalPoints"]["rightTotalLength"] == 8.5
    assert score["abnormalPoints"]["leftTotalLength"] == 2.5
    assert score["abnormalPoints"]["totalLength"] == 11.0


def test_a_b_c_values_are_not_added_to_final_score():
    base_entry = _build_entry()
    changed_entry = _build_entry(
        {
            "pointsSummary": {
                "rightPointsCount": 8,
                "leftPointsCount": 7,
                "tipToTipSpread": 25.0,
                "greatestSpread": 26.0,
            }
        }
    )
    assert calculate_typical_whitetail_final_score(base_entry) == calculate_typical_whitetail_final_score(changed_entry)


def test_optional_fields_can_remain_null_without_blocking_completion():
    entry = _build_entry(
        {
            "pointsSummary": {
                "rightPointsCount": 4,
                "leftPointsCount": 4,
            },
            "right": {
                "g4": None,
                "h4": None,
            },
            "left": {
                "g4": None,
                "h4": None,
            },
        }
    )
    assert is_bc_score_complete(entry) is True


def test_format_inches_to_eighths_rounds_to_nearest_eighth():
    assert format_inches_to_eighths(18.126) == "18 1/8"
    assert format_inches_to_eighths(19.0) == "19"
    assert format_inches_to_eighths(None) == "—"


def test_draft_vs_complete_depends_on_disclaimer_and_required_fields():
    incomplete_entry = _build_entry(disclaimer_accepted=False)
    incomplete_score = build_bc_score_record(incomplete_entry)
    assert incomplete_score["status"] == "draft"

    complete_entry = _build_entry()
    complete_score = build_bc_score_record(complete_entry)
    assert complete_score["status"] == "complete"


def test_harvested_buck_only_gating():
    assert is_harvested_buck_eligible("Whitetail", "Buck", True) is True
    assert is_harvested_buck_eligible("Whitetail", "Doe", True) is False
    assert is_harvested_buck_eligible("Mule Deer", "Buck", True) is True
    assert is_harvested_buck_eligible("Whitetail", "Buck", False) is False
    assert is_harvested_buck_eligible("mule deer", "buck", True) is True


def test_all_current_score_types_are_supported():
    assert is_supported_bc_score_type("typical_whitetail_unofficial") is True
    assert is_supported_bc_score_type(BC_SCORE_TYPE_NON_TYPICAL_WHITETAIL) is True
    assert is_supported_bc_score_type(BC_SCORE_TYPE_TYPICAL_MULE_DEER) is True
    assert is_supported_bc_score_type(BC_SCORE_TYPE_NON_TYPICAL_MULE_DEER) is True


def test_score_type_must_match_harvested_buck_record():
    assert is_bc_score_type_allowed_for_scan("typical_whitetail_unofficial", "Whitetail", "Buck", True) is True
    assert is_bc_score_type_allowed_for_scan(BC_SCORE_TYPE_NON_TYPICAL_WHITETAIL, "Whitetail", "Buck", True) is True
    assert is_bc_score_type_allowed_for_scan(BC_SCORE_TYPE_TYPICAL_MULE_DEER, "Whitetail", "Buck", True) is False
    assert is_bc_score_type_allowed_for_scan(BC_SCORE_TYPE_TYPICAL_MULE_DEER, "Mule Deer", "Buck", True) is True
    assert is_bc_score_type_allowed_for_scan(BC_SCORE_TYPE_TYPICAL_MULE_DEER, "mule deer", "buck", True) is True


def test_build_bc_score_record_uses_timezone_aware_iso_timestamps():
    score = build_bc_score_record(
        _build_mule_entry(),
        calculated_at=datetime(2026, 3, 11, 12, 0, tzinfo=timezone.utc),
    )
    assert score["calculatedAt"].endswith("+00:00")
    assert score["updatedAt"].endswith("+00:00")


def test_score_type_label_matches_supported_options():
    assert get_bc_score_type_label("typical_whitetail_unofficial") == "Typical Whitetail Deer"
    assert get_bc_score_type_label(BC_SCORE_TYPE_NON_TYPICAL_WHITETAIL) == "Non-Typical Whitetail Deer"
