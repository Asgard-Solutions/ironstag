import importlib

import region_calibration
from region_calibration import calibrate_from_dict_with_region


def test_env_override_applies_region_uncertainty_threshold(monkeypatch):
    monkeypatch.setenv("AGE_UNCERTAINTY_THRESHOLD_MIDWEST", "0.30")
    reloaded = importlib.reload(region_calibration)

    try:
        assert reloaded.REGION_UNCERTAINTY_THRESHOLDS[reloaded.RegionKey.MIDWEST] == 0.30
    finally:
        monkeypatch.delenv("AGE_UNCERTAINTY_THRESHOLD_MIDWEST", raising=False)
        importlib.reload(reloaded)


def test_age_uncertain_rewrites_reasoning_without_retake_reason(monkeypatch):
    monkeypatch.setenv("AGE_UNCERTAINTY_THRESHOLD_MIDWEST", "0.45")
    monkeypatch.setenv("PREDICTED_AGE_UNCERTAINTY_MAX_THRESHOLD", "0.45")
    reloaded = importlib.reload(region_calibration)

    try:
        _, updated = reloaded.calibrate_from_dict_with_region(
            analysis={
                "is_valid_deer": True,
                "deer_age": 2.5,
                "deer_sex": "Buck",
                "confidence": 50,
                "raw_age_confidence": 50,
                "raw_recommendation_confidence": 50,
                "recommendation": "PASS",
                "reasoning": "Body cues are consistent with a 2.5-year-old buck.",
            },
            state="IA",
            user_profile_state=None,
            active_curves=None,
        )

        assert updated["age_uncertain"] is True
        assert updated["deer_age"] is None
        assert "too low" in updated["reasoning"]
        assert "2.5-year-old" not in updated["reasoning"]
    finally:
        monkeypatch.delenv("AGE_UNCERTAINTY_THRESHOLD_MIDWEST", raising=False)
        monkeypatch.delenv("PREDICTED_AGE_UNCERTAINTY_MAX_THRESHOLD", raising=False)
        importlib.reload(reloaded)


def test_age_uncertain_preserves_retake_reason(monkeypatch):
    monkeypatch.setenv("AGE_UNCERTAINTY_THRESHOLD_MIDWEST", "0.45")
    monkeypatch.setenv("PREDICTED_AGE_UNCERTAINTY_MAX_THRESHOLD", "0.45")
    reloaded = importlib.reload(region_calibration)

    try:
        _, updated = reloaded.calibrate_from_dict_with_region(
            analysis={
                "is_valid_deer": True,
                "deer_age": 2.5,
                "deer_sex": "Buck",
                "confidence": 50,
                "raw_age_confidence": 50,
                "raw_recommendation_confidence": 50,
                "recommendation": None,
                "reasoning": "Body cues are consistent with a 2.5-year-old buck.",
                "retake_reason": "The image quality is too poor for a reliable age estimate.",
            },
            state="IA",
            user_profile_state=None,
            active_curves=None,
        )

        assert updated["age_uncertain"] is True
        assert updated["reasoning"] == "Body cues are consistent with a 2.5-year-old buck."
    finally:
        monkeypatch.delenv("AGE_UNCERTAINTY_THRESHOLD_MIDWEST", raising=False)
        monkeypatch.delenv("PREDICTED_AGE_UNCERTAINTY_MAX_THRESHOLD", raising=False)
        importlib.reload(reloaded)


def test_predicted_age_threshold_cap_keeps_numeric_age(monkeypatch):
    monkeypatch.setenv("AGE_UNCERTAINTY_THRESHOLD_MIDWEST", "0.40")
    monkeypatch.setenv("PREDICTED_AGE_UNCERTAINTY_MAX_THRESHOLD", "0.18")
    reloaded = importlib.reload(region_calibration)

    try:
        _, updated = reloaded.calibrate_from_dict_with_region(
            analysis={
                "is_valid_deer": True,
                "deer_age": 2.5,
                "deer_sex": "Buck",
                "confidence": 40,
                "raw_age_confidence": 40,
                "raw_recommendation_confidence": 40,
                "recommendation": "PASS",
                "reasoning": "Body cues are consistent with a 2.5-year-old buck.",
            },
            state="IA",
            user_profile_state=None,
            active_curves=None,
        )

        assert updated["age_uncertain"] is False
        assert updated["deer_age"] == 2.5
    finally:
        monkeypatch.delenv("AGE_UNCERTAINTY_THRESHOLD_MIDWEST", raising=False)
        monkeypatch.delenv("PREDICTED_AGE_UNCERTAINTY_MAX_THRESHOLD", raising=False)
        importlib.reload(reloaded)
