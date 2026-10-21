"""
Activation gates for calibration artifacts.

An artifact becomes active ONLY if every check passes; otherwise it can stay in shadow mode
(computed on live scans and recorded in score_audit.shadow_calibration, never displayed).
Existing maturity safeguards are preserved: GLOBAL_CURVE_MIN_SAMPLES / REGION_CURVE_MIN_SAMPLES.
"""

from typing import Any, Dict, List

from confidence_calibration import check_compatibility, validate_artifact

MIN_EVAL_CASES = 100
MAX_EVAL_FALLBACK_RATE = 0.5


def activation_checks(art: Dict[str, Any], *, runtime: Dict[str, Any], active_targets: List[str],
                      global_min: int, region_min: int) -> Dict[str, Any]:
    checks: List[Dict[str, Any]] = []

    def add(name: str, ok: bool, detail: Any = None):
        checks.append({"check": name, "passed": bool(ok), "detail": detail})

    errors = validate_artifact(art)
    add("artifact_valid", not errors, errors)
    if errors:
        return {"passed": False, "checks": checks}
    reasons = check_compatibility(art, **runtime)
    add("compatible_with_production_pipeline", not reasons, reasons or runtime)
    fit, ev = art.get("fit") or {}, art.get("evaluation") or {}
    add("fitted_on_calibration_split", fit.get("split") == "calibration", fit.get("split"))
    add("evaluated_on_held_out_test_split", ev.get("split") == "test", ev.get("split"))
    add("same_dataset_disjoint_splits", fit.get("dataset_sha256") and fit.get("dataset_sha256") == ev.get("dataset_sha256"),
        {"fit": fit.get("dataset_sha256"), "eval": ev.get("dataset_sha256")})
    add("real_data_not_synthetic_or_mock",
        not any([fit.get("synthetic"), fit.get("mock"), ev.get("synthetic"), ev.get("mock")]),
        {"fit": [fit.get("synthetic"), fit.get("mock")], "eval": [ev.get("synthetic"), ev.get("mock")]})
    is_region = (art.get("scope") or {}).get("type") == "region"
    min_fit = region_min if is_region else global_min
    add("fit_sample_maturity", (fit.get("n") or 0) >= min_fit, {"n": fit.get("n"), "required": min_fit})
    cand, heur = ev.get("candidate") or {}, ev.get("heuristic") or {}
    add("eval_sample_size", (cand.get("n") or 0) >= MIN_EVAL_CASES, {"n": cand.get("n"), "required": MIN_EVAL_CASES})
    total = (cand.get("n") or 0) + (cand.get("n_fallback") or 0)
    fb_rate = (cand.get("n_fallback") or 0) / total if total else 1.0
    add("eval_fallback_rate", fb_rate <= MAX_EVAL_FALLBACK_RATE, {"rate": round(fb_rate, 4), "max": MAX_EVAL_FALLBACK_RATE})
    add("ece_better_than_heuristic", cand.get("ece") is not None and heur.get("ece") is not None and cand["ece"] < heur["ece"],
        {"candidate": cand.get("ece"), "heuristic": heur.get("ece")})
    add("brier_not_worse_than_heuristic",
        cand.get("brier") is not None and heur.get("brier") is not None and cand["brier"] <= heur["brier"],
        {"candidate": cand.get("brier"), "heuristic": heur.get("brier")})
    # Range coverage is displayed separately, so it may coexist with one exact-age/within-one-year target.
    same_slot = lambda t: (t == "age_range_coverage") == (art["target"] == "age_range_coverage")
    others = sorted({t for t in active_targets if same_slot(t)} - {art["target"]})
    add("single_target_for_displayed_score", not others, {"other_active_targets": others})
    return {"passed": all(c["passed"] for c in checks), "checks": checks}


def scope_key(art: Dict[str, Any]) -> str:
    scope = art.get("scope") or {}
    return f"region:{scope.get('region_key')}" if scope.get("type") == "region" else "global"
