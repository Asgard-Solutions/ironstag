from server import apply_age_estimation_gate


def test_single_quality_issue_does_not_block_age_when_enough_critical_cues():
    result = apply_age_estimation_gate(
        {
            "deer_age": 2.5,
            "age_bucket": "2.5",
            "age_range": "2.5-3.0",
            "buck_age_class": "2.5",
            "recommendation": "PASS",
            "raw_age_confidence": 62,
            "raw_recommendation_confidence": 64,
            "confidence": 64,
            "image_quality_bucket": "poor",
            "posture_bucket": "angled",
            "quality_factors": {"body_visibility": "medium", "occlusion": "low", "blur": "low"},
            "visible_age_cues": ["backline", "body_mass", "chest_depth"],
            "cue_checklist": {},
            "age_evidence": [],
        }
    )

    assert result["age_estimation_allowed"] is True
    assert result["deer_age"] == 2.5
    assert result["retake_reason"] is None


def test_compound_visibility_failures_still_block_age():
    result = apply_age_estimation_gate(
        {
            "deer_age": 2.5,
            "age_bucket": "2.5",
            "age_range": "2.5-3.0",
            "buck_age_class": "2.5",
            "recommendation": "PASS",
            "raw_age_confidence": 62,
            "raw_recommendation_confidence": 64,
            "confidence": 64,
            "image_quality_bucket": "poor",
            "posture_bucket": "angled",
            "quality_factors": {"body_visibility": "low", "occlusion": "high", "blur": "low"},
            "visible_age_cues": ["backline"],
            "cue_checklist": {},
            "age_evidence": [],
        }
    )

    assert result["age_estimation_allowed"] is False
    assert result["deer_age"] is None
    assert result["retake_reason"] is not None


def test_model_supplied_age_does_not_lower_evidence_threshold():
    result = apply_age_estimation_gate(
        {
            "deer_age": 3.5,
            "age_bucket": "3.5",
            "age_range": "3.5-4.0",
            "buck_age_class": "3.5",
            "recommendation": "HARVEST",
            "raw_age_confidence": 70,
            "raw_recommendation_confidence": 72,
            "confidence": 72,
            "image_quality_bucket": "fair",
            "posture_bucket": "frontal",
            "quality_factors": {"body_visibility": "medium", "occlusion": "low", "blur": "low"},
            "visible_age_cues": ["backline", "body_mass"],
            "cue_checklist": {},
            "age_evidence": [],
        }
    )

    # Two critical cues are below MIN_VISIBLE_CRITICAL_AGE_CUES; a model-supplied age no longer bypasses that.
    assert result["age_estimation_allowed"] is False
    assert result["deer_age"] is None
    assert "side" in result["retake_reason"].lower() or "body" in result["retake_reason"].lower()


def test_no_age_and_no_visible_cues_still_block():
    result = apply_age_estimation_gate(
        {
            "deer_age": None,
            "age_bucket": None,
            "age_range": None,
            "buck_age_class": None,
            "recommendation": None,
            "raw_age_confidence": 20,
            "raw_recommendation_confidence": 20,
            "confidence": 20,
            "image_quality_bucket": "fair",
            "posture_bucket": "frontal",
            "quality_factors": {"body_visibility": "medium", "occlusion": "low", "blur": "low"},
            "visible_age_cues": [],
            "cue_checklist": {},
            "age_evidence": [],
        }
    )

    assert result["age_estimation_allowed"] is False
    assert result["abstain_reason"] == "pose_not_supported"
