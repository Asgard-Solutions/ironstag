"""
Fit calibration artifacts on the calibration split and evaluate them on the held-out test split.

  python -m evaluation calibrate --fit-run RUN_DIR(calibration split) --eval-run RUN_DIR(test split) \
      --config-name baseline --target exact_age_class [--out DIR]

Outputs: one artifact JSON per candidate method/scope + calibration_report.md/json.
Judged by reliability metrics (ECE, Brier, log loss, reliability table), never by average confidence.
"""

import json
import os
from typing import Any, Dict, List, Tuple

import calibration_activation
import confidence_calibration as cc
from evaluation import metrics
from region_calibration import RegionCalibrationConfig

OUTCOME_FIELD = {"exact_age_class": "exact", "within_one_year": "within_one_year", "age_range_coverage": "range_covers"}
MIN_REGION_EVAL = metrics.MIN_SUBGROUP_N


def _load(run_dir: str, config_name: str) -> Tuple[Dict[str, Any], List[Dict[str, Any]]]:
    with open(os.path.join(run_dir, "run.json")) as fh:
        meta = json.load(fh)
    rows = []
    with open(os.path.join(run_dir, "results.jsonl")) as fh:
        for line in fh:
            r = json.loads(line)
            if r.get("config") == config_name:
                rows.append(metrics.score_case(r))
    if not rows:
        raise SystemExit(f"No rows for config '{config_name}' in {run_dir}")
    return meta, rows


def _points(rows, target):
    field = OUTCOME_FIELD[target]
    return [(float(r["raw_age_confidence"]), int(bool(r[field]))) for r in rows
            if r["answered"] and r.get("raw_age_confidence") is not None
            and (target != "age_range_coverage" or r["range_reported"])]


def _pipeline_identity(rows) -> Dict[str, Any]:
    ids = {(r.get("model"), r.get("prompt_version"), r.get("preprocessing_version")) for r in rows if r["answered"]}
    if len(ids) != 1:
        raise SystemExit(f"Rows come from more than one pipeline version {ids}; fit per version.")
    model, prompt, prep = ids.pop()
    return {"model": model, "prompt_version": prompt, "preprocessing_version": prep}


def _evaluate(art, rows, target, meta) -> Dict[str, Any]:
    field = OUTCOME_FIELD[target]
    usable = [r for r in rows if r["answered"] and r.get("raw_age_confidence") is not None
              and (target != "age_range_coverage" or r["range_reported"])]
    if (art.get("scope") or {}).get("type") == "region":
        usable = [r for r in usable if (r.get("region_key") or r.get("region_state")) == art["scope"]["region_key"]]
    cand, eff, heur, raw = [], [], [], []
    for r in usable:
        y = int(bool(r[field]))
        value, _ = cc.apply_artifact(art, r["raw_age_confidence"])
        h = (r.get("age_confidence") or 0) / 100
        cand.append((value, y))
        eff.append((value if value is not None else h, y))
        heur.append((h, y))
        raw.append((r["raw_age_confidence"] / 100, y))
    return {
        "split": meta.get("split"), "dataset_sha256": meta.get("dataset_sha256"),
        "synthetic": meta.get("synthetic_dataset"), "mock": meta.get("mock_model"),
        "candidate": cc.reliability(cand), "effective_with_heuristic_fallback": cc.reliability(eff),
        "heuristic": cc.reliability(heur), "raw_model_confidence": cc.reliability(raw),
    }


def fit_and_evaluate(fit_run: str, eval_run: str, config_name: str, target: str, out_dir: str) -> Dict[str, Any]:
    if target not in cc.TARGETS:
        raise SystemExit(f"target must be one of {list(cc.TARGETS)}")
    fit_meta, fit_rows = _load(fit_run, config_name)
    eval_meta, eval_rows = _load(eval_run, config_name)
    identity = _pipeline_identity(fit_rows)
    if _pipeline_identity(eval_rows) != identity:
        raise SystemExit("Fit and evaluation runs used different model/prompt/preprocessing; refusing to compare.")
    if set(fit_meta["eligible_case_ids"]) & set(eval_meta["eligible_case_ids"]):
        raise SystemExit("Fit and evaluation runs share cases; calibration data must be separate from test data.")
    fit_info = {"split": fit_meta.get("split"), "dataset_sha256": fit_meta.get("dataset_sha256"),
                "synthetic": fit_meta.get("synthetic_dataset"), "mock": fit_meta.get("mock_model"),
                "run_id": fit_meta.get("run_id")}
    os.makedirs(out_dir, exist_ok=True)
    candidates, skipped = [], []
    global_points = _points(fit_rows, target)
    for method in cc.METHODS:
        if not global_points:
            skipped.append({"method": method, "reason": "no answered fit cases"})
            continue
        candidates.append(cc.build_artifact(method=method, target=target, points=global_points,
                                            compatibility=identity, fit_info=fit_info))
    regions = sorted({r.get("region_key") or r.get("region_state") for r in fit_rows if r["answered"]} - {None})
    for region in regions:
        pts = _points([r for r in fit_rows if (r.get("region_key") or r.get("region_state")) == region], target)
        n_eval = len([r for r in eval_rows if (r.get("region_key") or r.get("region_state")) == region and r["answered"]])
        if len(pts) < RegionCalibrationConfig.REGION_CURVE_MIN_SAMPLES or n_eval < MIN_REGION_EVAL:
            skipped.append({"scope": f"region:{region}", "reason": "insufficient representative data",
                            "fit_n": len(pts), "eval_n": n_eval,
                            "required": [RegionCalibrationConfig.REGION_CURVE_MIN_SAMPLES, MIN_REGION_EVAL]})
            continue
        candidates.append(cc.build_artifact(method="isotonic", target=target, points=pts, compatibility=identity,
                                            fit_info=fit_info, scope={"type": "region", "region_key": region}))
    summary = []
    for art in candidates:
        art["evaluation"] = _evaluate(art, eval_rows, target, eval_meta)
        checks = calibration_activation.activation_checks(
            art, runtime=identity, active_targets=[],
            global_min=RegionCalibrationConfig.GLOBAL_CURVE_MIN_SAMPLES,
            region_min=RegionCalibrationConfig.REGION_CURVE_MIN_SAMPLES)
        path = os.path.join(out_dir, f"{art['artifact_id']}.json")
        with open(path, "w") as fh:
            json.dump(art, fh, indent=2)
        summary.append({"artifact_id": art["artifact_id"], "method": art["method"], "scope": art["scope"],
                        "file": path, "fit_n": art["fit"]["n"], "evaluation": art["evaluation"],
                        "eligible_for_activation": checks["passed"],
                        "blocking_checks": [c for c in checks["checks"] if not c["passed"]]})
    report = {"target": target, "target_definition": cc.TARGETS[target], "pipeline": identity,
              "fit_run": fit_run, "eval_run": eval_run, "candidates": summary, "skipped": skipped,
              "not_evidence": bool(fit_info["synthetic"] or fit_info["mock"] or eval_meta.get("synthetic_dataset") or eval_meta.get("mock_model"))}
    with open(os.path.join(out_dir, "calibration_report.json"), "w") as fh:
        json.dump(report, fh, indent=2, default=str)
    with open(os.path.join(out_dir, "calibration_report.md"), "w") as fh:
        fh.write(_markdown(report))
    return report


def _markdown(rep: Dict[str, Any]) -> str:
    lines = [f"# Calibration fit — target `{rep['target']}`", "", rep["target_definition"], ""]
    if rep["not_evidence"]:
        lines += ["> **SYNTHETIC / MOCK DATA — NOT EVIDENCE. Artifacts from this run cannot activate.**", ""]
    lines += [f"Pipeline: {rep['pipeline']}", "", "| Artifact | Method | Scope | Fit n | Eval n (fallback) | ECE cand / heuristic / raw | Brier cand / heuristic | Activatable |",
              "|---|---|---|---|---|---|---|---|"]
    for c in rep["candidates"]:
        e = c["evaluation"]
        lines.append(f"| {c['artifact_id']} | {c['method']} | {c['scope']} | {c['fit_n']} | {e['candidate']['n']} ({e['candidate']['n_fallback']}) | "
                     f"{e['candidate']['ece']} / {e['heuristic']['ece']} / {e['raw_model_confidence']['ece']} | "
                     f"{e['candidate']['brier']} / {e['heuristic']['brier']} | {'yes' if c['eligible_for_activation'] else 'no'} |")
    lines += ["", "## Blocking checks"]
    for c in rep["candidates"]:
        lines.append(f"- {c['artifact_id']}: " + (", ".join(b["check"] for b in c["blocking_checks"]) or "none"))
    lines += ["", "## Skipped (insufficient data)"] + [f"- {s}" for s in rep["skipped"]]
    return "\n".join(lines) + "\n"
