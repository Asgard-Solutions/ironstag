"""Age range / abstention / consensus-consistency behavior (synthetic inputs; not accuracy evidence)."""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from server import finalize_age_estimate, merge_consensus_analyses, format_age_range
from evaluation import metrics


def _n(**kw):
    base = {"is_valid_deer": True, "age_estimation_allowed": True, "deer_sex": "Buck", "deer_age": 3.5}
    base.update(kw)
    return finalize_age_estimate(base)


def test_point_estimate_is_not_widened():
    n = _n()
    assert (n["age_lower"], n["age_upper"], n["age_range"]) == (3.5, 3.5, "3.5")
    assert n["range_basis"] == "point_estimate" and n["recommendation"] == "HARVEST"


def test_plausible_range_keeps_both_bounds_uncalibrated():
    n = _n(age_lower=3.5, age_upper=4.5, range_reasoning="belly does not rule out 4.5")
    assert n["age_range"] == "3.5-4.5" and n["range_status"] == "plausible_uncalibrated"
    assert n["recommendation"] == "HARVEST" and n["recommendation_status"] == "age_based"


def test_range_crossing_threshold_makes_recommendation_uncertain():
    n = _n(deer_age=3.5, age_lower=2.5, age_upper=3.5, recommendation="HARVEST")
    assert n["recommendation"] is None and n["recommendation_status"] == "uncertain_range_crosses_threshold"
    assert n["deer_age"] == 3.5 and n["buck_age_class"] == "3.5"


def test_open_ended_range():
    n = _n(deer_age=5.5, age_lower=5.5, age_upper=None, age_upper_open=True)
    assert n["age_range"] == "5.5+" and n["age_upper"] is None and n["age_upper_open"] is True
    n2 = _n(deer_age=6.5, age_lower=5.5, age_upper=7.5)
    assert n2["age_range"] == "5.5+" and n2["age_upper_open"] is True
    assert format_age_range(6.5, None, True) == "6.5+"


def test_alternate_age_defines_range_when_no_bounds():
    n = _n(deer_age=2.5, alternate_age=3.5)
    assert n["age_range"] == "2.5-3.5" and n["range_basis"] == "alternate_age" and n["recommendation"] is None


def test_too_wide_range_abstains_with_actionable_retake():
    n = _n(deer_age=3.5, age_lower=1.5, age_upper=5.5)
    assert n["age_estimation_allowed"] is False and n["deer_age"] is None and n["age_range"] is None
    assert "broadside" in n["retake_reason"] and n["abstain_reason"] == "range_too_wide"


def test_null_age_abstains_even_when_allowed_flag_missing():
    n = finalize_age_estimate({"is_valid_deer": True, "deer_age": None})
    assert n["age_estimation_allowed"] is False and n["retake_reason"]


def test_consensus_output_is_internally_consistent():
    passes = [
        {"is_valid_deer": True, "age_estimation_allowed": True, "deer_sex": "Buck", "deer_age": a,
         "age_lower": a, "age_upper": a, "buck_age_class": str(a), "age_range": str(a), "age_bucket": "x",
         "raw_age_confidence": c, "raw_recommendation_confidence": c, "recommendation": "HARVEST" if a >= 3.5 else "PASS",
         "reasoning": f"looks {a}"}
        for a, c in ((3.5, 60), (2.5, 55), (3.5, 58))
    ]
    merged, meta = merge_consensus_analyses(passes)
    merged["consensus"] = meta
    n = finalize_age_estimate(merged)
    assert n["deer_age"] == 3.5 and n["buck_age_class"] == "3.5" and n["reasoning"] == "looks 3.5"
    assert n["age_range"] == "2.5-3.5" and "consensus_spread" in n["range_basis"]
    assert n["recommendation"] is None  # range spans the 3.5 threshold


def test_benchmark_scores_open_and_closed_intervals_separately_from_exact():
    open_row = metrics.score_case({"encounter_id": "e", "deer_id": "d", "reference_age": 7.5, "status": "answered",
                                   "predicted_age": 5.5, "predicted_range": "5.5+"})
    closed = metrics.score_case({"encounter_id": "f", "deer_id": "g", "reference_age": 4.5, "status": "answered",
                                 "predicted_age": 3.5, "predicted_range": "3.5-4.5"})
    assert open_row["range_covers"] and not open_row["exact"] and open_row["range_width"] is None
    assert closed["range_covers"] and not closed["exact"] and closed["range_width"] == 1.0
