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
        importlib.reload(reloaded)


def test_age_uncertain_preserves_retake_reason(monkeypatch):
    monkeypatch.setenv("AGE_UNCERTAINTY_THRESHOLD_MIDWEST", "0.45")
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
        importlib.reload(reloaded)


def test_numeric_age_does_not_lower_uncertainty_threshold():
    # Default midwest threshold (0.35); a 3.5 estimate at ~20% calibrated confidence must be rejected.
    result, updated = calibrate_from_dict_with_region(
        analysis={
            "is_valid_deer": True, "deer_age": 3.5, "deer_sex": "Buck", "confidence": 27,
            "raw_age_confidence": 27, "raw_recommendation_confidence": 27, "recommendation": "PASS",
            "antler_points": 8, "antler_points_left": 4, "antler_points_right": 4,
        },
        state="IA", user_profile_state=None, active_curves=None,
    )
    assert result.calibrated_age_confidence == 20
    assert updated["age_uncertain"] is True
    assert updated["deer_age"] is None


def test_other_region_artifact_is_not_applied():
    from confidence_calibration import select_artifact
    tx = {"artifact_id": "tx", "scope": {"type": "region", "region_key": "south_texas"}}
    mw = {"artifact_id": "mw", "scope": {"type": "region", "region_key": "midwest"}}
    gl = {"artifact_id": "gl", "scope": {"type": "global"}}
    assert [a["artifact_id"] for a in select_artifact([tx, gl, mw], "midwest")] == ["mw", "gl"]
    assert [a["artifact_id"] for a in select_artifact([tx], "midwest")] == []


def test_midwest_scan_ignores_south_texas_artifact(monkeypatch):
    monkeypatch.setattr(region_calibration, "check_compatibility", lambda *a, **k: [])
    monkeypatch.setattr(region_calibration, "apply_artifact", lambda art, v: (0.85, None))
    tx = {"artifact_id": "tx", "_status": "active", "target": "exact_age_correct", "method": "isotonic",
          "scope": {"type": "region", "region_key": "south_texas"}}
    analysis = {"deer_age": 3.5, "deer_sex": "Buck", "confidence": 70}
    mw, _ = region_calibration.calibrate_from_dict_with_region(analysis, state="IA", artifacts=[tx])
    assert mw.calibration_strategy == "heuristic_region" and mw.calibrated_age_confidence != 85
    tx_res, _ = region_calibration.calibrate_from_dict_with_region(analysis, state="TX", artifacts=[tx])
    assert tx_res.calibrated_age_confidence == 85
