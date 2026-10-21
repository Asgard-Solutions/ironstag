"""
Synthetic tests for validated confidence calibration. Synthetic data verifies mechanics only; it is not evidence.
"""
import os
import random
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import calibration_activation
import confidence_calibration as cc
import region_calibration as rc  # module attribute access: other tests reload region_calibration

COMPAT = {"model": "gpt-4o", "prompt_version": "age-v5", "preprocessing_version": "img-prep-v1"}
RUNTIME = dict(COMPAT)


def _points(n, seed=1):
    rnd = random.Random(seed)
    pts = []
    for _ in range(n):
        x = rnd.uniform(20, 95)
        pts.append((round(x, 1), int(rnd.random() < x / 100 * 0.6)))
    return pts


def _art(method="isotonic", n=800, **fit):
    info = {"split": "calibration", "dataset_sha256": "abc", "synthetic": False, "mock": False}
    info.update(fit)
    return cc.build_artifact(method=method, target="exact_age_class", points=_points(n), compatibility=COMPAT, fit_info=info)


def _analysis(**kw):
    a = {"deer_age": 4.5, "deer_sex": "Buck", "raw_age_confidence": 70, "raw_recommendation_confidence": 70,
         "raw_confidence": 70, "recommendation": "HARVEST", "analysis_model": "gpt-4o", "analysis_prompt_version": "age-v5",
         "image_quality_bucket": "good", "posture_bucket": "broadside", "quality_factors": {}}
    a.update(kw)
    return a


def test_all_methods_produce_valid_monotone_artifacts():
    for method in cc.METHODS:
        art = _art(method)
        assert cc.validate_artifact(art) == [], method
        vals = [cc.apply_artifact(art, x)[0] for x in (25, 50, 75, 94)]
        known = [v for v in vals if v is not None]
        assert known == sorted(known)
        assert all(v <= cc.MAX_OUTPUT for v in known)


def test_malformed_and_non_monotone_artifacts_rejected():
    art = _art("global_binning")
    bad = dict(art, mapping={"bins": [dict(b, rate=1.5 if b["supported"] else b["rate"]) for b in art["mapping"]["bins"]]})
    assert "invalid_numeric_output" in cc.validate_artifact(bad)
    supported = [i for i, b in enumerate(art["mapping"]["bins"]) if b["supported"]]
    bins = [dict(b) for b in art["mapping"]["bins"]]
    bins[supported[0]]["rate"], bins[supported[-1]]["rate"] = 0.9, 0.1
    assert "not_monotonic" in cc.validate_artifact(dict(art, mapping={"bins": bins}))
    assert "missing:mapping" in cc.validate_artifact({k: v for k, v in art.items() if k != "mapping"})
    assert "target_mismatch" in cc.validate_artifact(dict(art, compatibility=dict(art["compatibility"], target="within_one_year")))


def test_sparse_bins_fall_back_instead_of_inflating():
    pts = [(85.0, 1)] * 5 + [(45.0, 0)] * 30 + [(45.0, 1)] * 10
    art = cc.build_artifact(method="global_binning", target="exact_age_class", points=pts, compatibility=COMPAT,
                            fit_info={"split": "calibration"})
    value, reason = cc.apply_artifact(art, 85)
    assert value is None and reason == "artifact_sparse_bin"
    value, _ = cc.apply_artifact(art, 45)
    assert value == 0.25


def test_incompatible_artifact_is_not_applied_and_reason_recorded():
    art = dict(_art(), _status="active")
    _, out = rc.calibrate_from_dict_with_region(_analysis(analysis_model="gpt-4.1"), state="IA", artifacts=[art],
                                             preprocessing_version="img-prep-v1")
    shown = out["score_audit"]["displayed_score"]
    assert shown["target"] == cc.HEURISTIC_TARGET and shown["method"].startswith("heuristic")
    assert "incompatible" in (out["calibration_fallback_reason"] or "")


def test_compatible_active_artifact_drives_score_with_target():
    art = dict(_art(), _status="active")
    _, out = rc.calibrate_from_dict_with_region(_analysis(), state="IA", artifacts=[art], preprocessing_version="img-prep-v1")
    shown = out["score_audit"]["displayed_score"]
    assert shown["target"] == "exact_age_class" and shown["method_version"] == art["artifact_id"]
    assert out["age_confidence"] == round(cc.apply_artifact(art, 70)[0] * 100)


def test_shadow_artifact_is_recorded_but_not_displayed():
    art = dict(_art(), _status="shadow")
    _, base = rc.calibrate_from_dict_with_region(_analysis(), state="IA")
    _, out = rc.calibrate_from_dict_with_region(_analysis(), state="IA", artifacts=[art], preprocessing_version="img-prep-v1")
    assert out["age_confidence"] == base["age_confidence"]
    assert out["score_audit"]["shadow_calibration"][0]["artifact_id"] == art["artifact_id"]


def test_production_default_unchanged_without_artifacts():
    assert rc.RegionCalibrationConfig.HEURISTIC_VERSION == "v2" and rc.RegionCalibrationConfig.REGION_MAPPING_VERSION == "v1"
    _, out = rc.calibrate_from_dict_with_region(_analysis(), state="TX")
    assert out["region_key"] == "south_texas"
    assert out["score_audit"]["displayed_score"]["target"] == cc.HEURISTIC_TARGET


def test_heuristic_v3_counts_visual_evidence_once_and_drops_antler_penalty():
    qa = _analysis(image_quality_bucket="poor", quality_factors={"blur": "high", "occlusion": "high"},
                   antler_points=None)
    _, v2 = rc.calibrate_from_dict_with_region(qa, state="IA")
    rc.RegionCalibrationConfig.HEURISTIC_VERSION = "v3"
    try:
        _, v3 = rc.calibrate_from_dict_with_region(qa, state="IA")
    finally:
        rc.RegionCalibrationConfig.HEURISTIC_VERSION = "v2"
    assert v3["age_confidence"] > v2["age_confidence"]  # not stacked: 0.80 instead of 0.80*0.86*0.82*0.9
    assert v3["age_confidence"] <= 70 * 0.75  # still never above the scaled input (no bonus)


def test_region_mapping_v2_keeps_texas_uncertain():
    rc.RegionCalibrationConfig.REGION_MAPPING_VERSION = "v2"
    try:
        _, out = rc.calibrate_from_dict_with_region(_analysis(), state="TX")
    finally:
        rc.RegionCalibrationConfig.REGION_MAPPING_VERSION = "v1"
    assert out["region_key"] == "unknown"


def _with_eval(art, cand_ece=0.03, heur_ece=0.2, n=300, **ev):
    e = {"split": "test", "dataset_sha256": "abc", "synthetic": False, "mock": False,
         "candidate": {"n": n, "n_fallback": 10, "ece": cand_ece, "brier": 0.18},
         "heuristic": {"n": n, "n_fallback": 0, "ece": heur_ece, "brier": 0.22}}
    e.update(ev)
    return dict(art, evaluation=e)


def _gate(art, active_targets=()):
    return calibration_activation.activation_checks(art, runtime=RUNTIME, active_targets=list(active_targets),
                                                    global_min=500, region_min=200)


def test_activation_gates():
    good = _with_eval(_art())
    assert _gate(good)["passed"]
    failed = lambda a, **k: {c["check"] for c in _gate(a, **k)["checks"] if not c["passed"]}
    assert "compatible_with_production_pipeline" in failed(dict(good, compatibility=dict(good["compatibility"], model="x")))
    assert "fit_sample_maturity" in failed(_with_eval(_art(n=120)))
    assert "real_data_not_synthetic_or_mock" in failed(_with_eval(_art(synthetic=True)))
    assert "ece_better_than_heuristic" in failed(_with_eval(_art(), cand_ece=0.3))
    assert "eval_sample_size" in failed(_with_eval(_art(), n=40))
    assert "fitted_on_calibration_split" in failed(_with_eval(_art(split="test")))
    assert "single_target_for_displayed_score" in failed(good, active_targets=["within_one_year"])


def test_reliability_metrics():
    rel = cc.reliability([(0.8, 1), (0.8, 0), (0.2, 0), (None, 1)])
    assert rel["n"] == 3 and rel["n_fallback"] == 1 and rel["ece"] is not None and rel["brier"] is not None
