from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from analysis_consensus import merge_consensus_analyses, should_trigger_selective_consensus


def _analysis(
    *,
    deer_age=3.5,
    age_allowed=True,
    age_conf=80,
    rec_conf=82,
    recommendation="HARVEST",
):
    return {
        "is_valid_deer": True,
        "age_estimation_allowed": age_allowed,
        "deer_age": deer_age,
        "raw_age_confidence": age_conf,
        "raw_recommendation_confidence": rec_conf,
        "confidence": rec_conf,
        "recommendation": recommendation,
        "deer_type": "Whitetail",
        "deer_sex": "Buck",
        "visible_age_cues": ["chest_depth", "backline"],
        "quality_factors": {"body_visibility": "high"},
    }


def test_should_trigger_selective_consensus_on_low_age_confidence():
    analysis = _analysis(age_conf=70, rec_conf=90)
    assert should_trigger_selective_consensus(
        analysis,
        enabled=True,
        max_age_confidence=78,
        max_recommendation_confidence=80,
    )


def test_should_not_trigger_selective_consensus_on_high_confidence():
    analysis = _analysis(age_conf=92, rec_conf=91)
    assert not should_trigger_selective_consensus(
        analysis,
        enabled=True,
        max_age_confidence=78,
        max_recommendation_confidence=80,
    )


def test_merge_consensus_uses_median_age_and_majority_recommendation():
    analyses = [
        _analysis(deer_age=2.5, age_conf=78, rec_conf=80, recommendation="PASS"),
        _analysis(deer_age=3.5, age_conf=80, rec_conf=81, recommendation="HARVEST"),
        _analysis(deer_age=3.5, age_conf=79, rec_conf=82, recommendation="HARVEST"),
    ]
    merged, meta = merge_consensus_analyses(analyses)
    assert meta["applied"] is True
    assert merged["deer_age"] == 3.5
    assert merged["recommendation"] == "HARVEST"
    assert merged["age_estimation_allowed"] is True
    assert merged["raw_age_confidence"] <= 80
    assert merged["raw_recommendation_confidence"] <= 82


def test_merge_consensus_rejects_when_majority_disallows_age():
    analyses = [
        _analysis(deer_age=3.5, age_allowed=False, age_conf=0, rec_conf=0, recommendation=None),
        _analysis(deer_age=None, age_allowed=False, age_conf=0, rec_conf=0, recommendation=None),
        _analysis(deer_age=3.5, age_allowed=True, age_conf=82, rec_conf=84, recommendation="HARVEST"),
    ]
    merged, meta = merge_consensus_analyses(analyses)
    assert meta["applied"] is True
    assert merged["age_estimation_allowed"] is False
    assert merged["deer_age"] is None
    assert merged["recommendation"] is None
    assert merged["raw_age_confidence"] == 0
    assert merged["raw_recommendation_confidence"] == 0
