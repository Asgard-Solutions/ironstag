"""
Offline evaluation runner for the full deer-aging pipeline.

Runs the SAME code path as /api/analyze-deer (image preparation, dedupe, prompt build,
model call + selective consensus, multi-photo guards, region calibration) without touching
the database, user accounts, scan credits, R2 storage or production records.
"""

import contextlib
import json
import os
import platform
import subprocess
import time
import uuid
from copy import deepcopy
from datetime import datetime
from typing import Any, Dict, List, Optional

from fastapi import HTTPException

import multi_image
import server
from evaluation.dataset import label_tier, resolve_image_path

RUNS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "runs")
TEST_ACCESS_LOG = os.path.join(RUNS_DIR, "test_access_log.jsonl")

DEFAULT_CONFIG: Dict[str, Any] = {
    "name": "baseline",
    "model": None,  # None -> production OPENAI_ANALYSIS_MODEL
    "prompt": {"label": "production", "system_prompt_override_file": None, "system_prompt_append_file": None},
    "multi_photo": False,  # False: first photo only (production single-photo baseline)
    "use_crops": False,
    "max_edge": multi_image.MODEL_MAX_EDGE,
    "consensus": {"enabled": server.SELECTIVE_CONSENSUS_ENABLED, "total_passes": server.SELECTIVE_CONSENSUS_TOTAL_PASSES},
    "calibration": "heuristic",  # "heuristic" (production v2) | "heuristic_v3" (de-duplicated candidate) | "none" | "artifact:<path.json>"
    "pricing_usd_per_1m_tokens": {"input": None, "output": None},  # fill in to get cost estimates
}
# Keys that define the experimental factors (used for one-factor-at-a-time checks)
FACTOR_KEYS = ("model", "prompt", "multi_photo", "use_crops", "max_edge", "consensus", "calibration")
# Conservative per-call token estimate for budget planning (high-detail images)
EST_PROMPT_TOKENS_BASE = 2600
EST_PROMPT_TOKENS_PER_IMAGE = 800
EST_COMPLETION_TOKENS = 1000


def load_config(path_or_dict) -> Dict[str, Any]:
    cfg = deepcopy(DEFAULT_CONFIG)
    data = path_or_dict
    if isinstance(path_or_dict, str):
        with open(path_or_dict) as fh:
            data = json.load(fh)
        base_dir = os.path.dirname(os.path.abspath(path_or_dict))
        for key in ("system_prompt_override_file", "system_prompt_append_file"):
            p = (data.get("prompt") or {}).get(key)
            if p and not os.path.isabs(p):
                data["prompt"][key] = os.path.join(base_dir, p)
    for k, v in data.items():
        if isinstance(v, dict) and isinstance(cfg.get(k), dict):
            cfg[k].update(v)
        else:
            cfg[k] = v
    cfg["model"] = cfg["model"] or server.OPENAI_ANALYSIS_MODEL
    return cfg


def factor_differences(baseline: Dict[str, Any], candidate: Dict[str, Any]) -> List[str]:
    return [k for k in FACTOR_KEYS if baseline.get(k) != candidate.get(k)]


def _git_commit() -> Optional[str]:
    try:
        return subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=os.path.dirname(RUNS_DIR), stderr=subprocess.DEVNULL).decode().strip()
    except Exception:
        return None


@contextlib.contextmanager
def pipeline_settings(cfg: Dict[str, Any], mock: bool, observer):
    saved = (server.SELECTIVE_CONSENSUS_ENABLED, server.SELECTIVE_CONSENSUS_TOTAL_PASSES,
             multi_image.MODEL_MAX_EDGE, server.ANALYSIS_MOCK_MODEL, server.MODEL_CALL_OBSERVER)
    server.SELECTIVE_CONSENSUS_ENABLED = bool(cfg["consensus"]["enabled"])
    server.SELECTIVE_CONSENSUS_TOTAL_PASSES = max(1, int(cfg["consensus"]["total_passes"]))
    multi_image.MODEL_MAX_EDGE = int(cfg["max_edge"])
    server.ANALYSIS_MOCK_MODEL = mock
    server.MODEL_CALL_OBSERVER = observer
    try:
        yield
    finally:
        (server.SELECTIVE_CONSENSUS_ENABLED, server.SELECTIVE_CONSENSUS_TOTAL_PASSES,
         multi_image.MODEL_MAX_EDGE, server.ANALYSIS_MOCK_MODEL, server.MODEL_CALL_OBSERVER) = saved


def _system_prompt(cfg: Dict[str, Any], default_prompt: str) -> str:
    p = cfg["prompt"]
    if p.get("system_prompt_override_file"):
        with open(p["system_prompt_override_file"]) as fh:
            return fh.read()
    if p.get("system_prompt_append_file"):
        with open(p["system_prompt_append_file"]) as fh:
            return default_prompt + "\n\n" + fh.read()
    return default_prompt


def estimate_budget(cases: List[Dict[str, Any]], configs: List[Dict[str, Any]]) -> Dict[str, Any]:
    calls, cost, unknown_price = 0, 0.0, []
    for cfg in configs:
        passes = cfg["consensus"]["total_passes"] if cfg["consensus"]["enabled"] else 1
        price = cfg.get("pricing_usd_per_1m_tokens") or {}
        for case in cases:
            n_img = min(3, len(case["images"])) if cfg["multi_photo"] else 1
            prompt_tokens = EST_PROMPT_TOKENS_BASE + EST_PROMPT_TOKENS_PER_IMAGE * n_img
            calls += passes
            if price.get("input") is None or price.get("output") is None:
                unknown_price.append(cfg["name"])
                continue
            cost += passes * (prompt_tokens * price["input"] + EST_COMPLETION_TOKENS * price["output"]) / 1e6
    return {"max_model_calls": calls, "max_cost_usd": round(cost, 2),
            "configs_without_pricing": sorted(set(unknown_price)), "note": "Upper bound: assumes every case triggers full consensus."}


def run_case(record: Dict[str, Any], cfg: Dict[str, Any], dataset_dir: str) -> Dict[str, Any]:
    calls: List[Dict[str, Any]] = []
    started = time.perf_counter()
    row: Dict[str, Any] = {
        "encounter_id": record["encounter_id"], "deer_id": record["deer_id"],
        "species": record.get("species"), "sex": record.get("sex"),
        "region_state": record.get("region_state"), "region_key": record.get("region_key"),
        "image_quality": record.get("image_quality"), "label_tier": label_tier(record),
        "reference_age": float(record["reference_age"]), "age_basis": record.get("age_basis"),
        "label_uncertainty_years": record.get("label_uncertainty_years"),
        "config": cfg["name"], "model": cfg["model"],
        "status": None, "predicted_age": None, "predicted_range": None, "buck_age_class": None,
        "age_confidence": None, "raw_age_confidence": None, "recommendation": None,
        "abstain_reason": None, "error": None,
    }
    saved_edge = multi_image.MODEL_MAX_EDGE
    multi_image.MODEL_MAX_EDGE = int(cfg["max_edge"])  # preprocessing must honour the config too
    try:
        images = record["images"][:3] if cfg["multi_photo"] else record["images"][:1]
        prepared = []
        for index, img in enumerate(images, start=1):
            with open(resolve_image_path(dataset_dir, img["path"]), "rb") as fh:
                data = fh.read()
            prepared.append(multi_image.prepare_image(
                image_bytes=data, position=index, image_id=f"img_{index}",
                captured_at=img.get("captured_at") or record.get("encounter_date"),
                crop_rect=img.get("crop_rect") if cfg["use_crops"] else None,
            ))
        duplicates = multi_image.mark_duplicates(prepared)
        evidence = multi_image.evidence_images(prepared)
        context = server.build_scan_context(
            scan_state=record.get("region_state"), user_profile_state=None,
            scan_datetime=datetime.fromisoformat(str(record["encounter_date"])[:10]),
            notes=None, date_taken=str(record["encounter_date"])[:10], image_bytes=prepared[0].original_bytes,
        )
        parts = server.build_analysis_request(server.format_scan_context_for_prompt(context), evidence)
        prompt_version = parts["prompt_version"] + ("" if cfg["prompt"]["label"] == "production" else f"+{cfg['prompt']['label']}")
        row["preprocessing"] = {
            "photos_used": len(prepared), "evidence_photos": len(evidence), "duplicates_removed": len(duplicates),
            "crops_applied": sum(1 for p in prepared if p.crop_rect), "max_edge": cfg["max_edge"],
        }
        row["prompt_version"] = prompt_version
        row["preprocessing_version"] = multi_image.preprocessing_version()
        with pipeline_settings(cfg, cfg.get("_mock", False), calls.append):
            analysis = server.run_analysis_with_consensus(
                model=cfg["model"], system_prompt=_system_prompt(cfg, parts["system_prompt"]),
                user_content=parts["user_content"], max_output_tokens=parts["max_output_tokens"],
                prompt_version=prompt_version, context=context,
            )
        if analysis is None:
            row["status"], row["error"] = "failed_parse", "Model output could not be parsed"
        elif not analysis.get("is_valid_deer", False):
            row["status"], row["error"] = "rejected_not_deer", analysis.get("detected_subject")
        else:
            try:
                analysis = server.apply_photo_set_guards(analysis, prepared, evidence, duplicates)
            except HTTPException as exc:
                row["status"], row["error"] = "rejected_mixed_deer", (exc.detail or {}).get("message")
                analysis = None
            if analysis is not None:
                if cfg["calibration"] == "none":
                    calibrated = dict(analysis)
                    calibrated["age_confidence"] = analysis.get("raw_age_confidence")
                    calibrated["calibration_version"] = "none"
                else:
                    artifacts = None
                    if str(cfg["calibration"]).startswith("artifact:"):
                        with open(cfg["calibration"].split(":", 1)[1]) as fh:
                            artifacts = [dict(json.load(fh), _status="active")]
                    heur = server.RegionCalibrationConfig.HEURISTIC_VERSION
                    if cfg["calibration"] == "heuristic_v3":
                        server.RegionCalibrationConfig.HEURISTIC_VERSION = "v3"
                    try:
                        _, calibrated = server.calibrate_from_dict_with_region(
                            analysis=analysis, state=record.get("region_state"), user_profile_state=None, active_curves=None,
                            artifacts=artifacts, preprocessing_version=row["preprocessing_version"],
                        )
                    finally:
                        server.RegionCalibrationConfig.HEURISTIC_VERSION = heur
                age = calibrated.get("deer_age")
                row.update({
                    "age_confidence_target": calibrated.get("age_confidence_target", "raw_model_confidence"),
                    "calibration_strategy": calibrated.get("calibration_strategy"),
                    "calibration_fallback_reason": calibrated.get("calibration_fallback_reason"),
                    "status": "answered" if age is not None and calibrated.get("age_estimation_allowed") is not False else "abstained",
                    "predicted_age": age,
                    "predicted_range": calibrated.get("age_range"),
                    "predicted_lower": calibrated.get("age_lower"),
                    "predicted_upper": calibrated.get("age_upper"),
                    "predicted_upper_open": calibrated.get("age_upper_open"),
                    "range_status": calibrated.get("range_status"),
                    "recommendation_status": calibrated.get("recommendation_status"),
                    "buck_age_class": calibrated.get("buck_age_class"),
                    "age_confidence": calibrated.get("age_confidence"),
                    "raw_age_confidence": calibrated.get("raw_age_confidence"),
                    "recommendation": calibrated.get("recommendation"),
                    "abstain_reason": calibrated.get("abstain_reason") or calibrated.get("retake_reason"),
                    "calibration_version": calibrated.get("calibration_version"),
                    "consensus_applied": bool(calibrated.get("consensus")),
                    "multi_image": calibrated.get("multi_image"),
                })
                if row["status"] == "abstained":
                    row["predicted_age"] = None
    except multi_image.ImageValidationError as exc:
        row["status"], row["error"] = "failed_input", f"{exc.code}: {exc.message}"
    except Exception as exc:  # recorded, never hidden
        row["status"], row["error"] = "failed_error", f"{type(exc).__name__}: {exc}"[:500]
    multi_image.MODEL_MAX_EDGE = saved_edge
    row["latency_s"] = round(time.perf_counter() - started, 3)
    row["model_calls"] = len(calls)
    row["mock_model"] = any(c.get("mock") for c in calls) or cfg.get("_mock", False)
    tokens_in = [c["prompt_tokens"] for c in calls if c.get("prompt_tokens") is not None]
    tokens_out = [c["completion_tokens"] for c in calls if c.get("completion_tokens") is not None]
    row["prompt_tokens"] = sum(tokens_in) if tokens_in else None
    row["completion_tokens"] = sum(tokens_out) if tokens_out else None
    price = cfg.get("pricing_usd_per_1m_tokens") or {}
    row["cost_usd"] = (round((row["prompt_tokens"] * price["input"] + row["completion_tokens"] * price["output"]) / 1e6, 5)
                       if row["prompt_tokens"] is not None and price.get("input") is not None and price.get("output") is not None else None)
    return row


def run_evaluation(
    *, cases: List[Dict[str, Any]], excluded: List[Dict[str, Any]], configs: List[Dict[str, Any]], dataset_path: str,
    dataset_sha256: str, synthetic_dataset: bool, split: str, mock: bool, budget_usd: Optional[float],
    max_calls: Optional[int], output_dir: Optional[str] = None,
) -> Dict[str, Any]:
    """Run every config on the same fixed eligible cases. Writes run.json + results.jsonl."""
    if not cases:
        raise ValueError("No eligible cases for this split; nothing to evaluate.")
    plan = estimate_budget(cases, configs)
    if not mock:
        if budget_usd is None or max_calls is None:
            raise PermissionError(
                f"Paid evaluation requires an agreed budget. Plan: {plan}. Re-run with --budget-usd and --max-calls, or --mock."
            )
        if plan["configs_without_pricing"]:
            raise PermissionError(f"Set pricing_usd_per_1m_tokens for: {plan['configs_without_pricing']}")
        if plan["max_model_calls"] > max_calls or plan["max_cost_usd"] > budget_usd:
            raise PermissionError(f"Planned run exceeds the agreed budget: {plan}")

    run_id = datetime.utcnow().strftime("%Y%m%dT%H%M%SZ") + "-" + uuid.uuid4().hex[:6]
    out_dir = output_dir or os.path.join(RUNS_DIR, run_id)
    os.makedirs(out_dir, exist_ok=True)
    if split == "test":
        os.makedirs(RUNS_DIR, exist_ok=True)
        with open(TEST_ACCESS_LOG, "a") as fh:
            fh.write(json.dumps({"run_id": run_id, "at": datetime.utcnow().isoformat(), "configs": [c["name"] for c in configs],
                                 "dataset_sha256": dataset_sha256, "mock": mock}) + "\n")

    dataset_dir = os.path.dirname(os.path.abspath(dataset_path))
    results: Dict[str, List[Dict[str, Any]]] = {}
    spent = 0.0
    for cfg in configs:
        cfg = dict(cfg, _mock=mock)
        rows = []
        for case in cases:
            if not mock and spent >= budget_usd:
                row = {"encounter_id": case["encounter_id"], "deer_id": case["deer_id"], "status": "not_run_budget",
                       "reference_age": float(case["reference_age"]), "config": cfg["name"], "error": "Budget exhausted"}
            else:
                row = run_case(case, cfg, dataset_dir)
                spent += row.get("cost_usd") or 0.0
            rows.append(row)
        results[cfg["name"]] = rows

    meta = {
        "run_id": run_id,
        "created_at": datetime.utcnow().isoformat(),
        "dataset_path": os.path.abspath(dataset_path),
        "dataset_sha256": dataset_sha256,
        "synthetic_dataset": synthetic_dataset,
        "mock_model": mock,
        "split": split,
        "eligible_case_ids": [c["encounter_id"] for c in cases],
        "excluded_cases": excluded,
        "configs": [{k: v for k, v in c.items() if not k.startswith("_")} for c in configs],
        "budget_plan": plan,
        "spent_usd": round(spent, 4),
        "code_commit": _git_commit(),
        "analysis_prompt_version": server.ANALYSIS_PROMPT_VERSION,
        "python": platform.python_version(),
        "isolation": "No DB writes, no user/credit changes, no R2 uploads; outputs only in this run directory.",
    }
    with open(os.path.join(out_dir, "run.json"), "w") as fh:
        json.dump(meta, fh, indent=2, default=str)
    with open(os.path.join(out_dir, "results.jsonl"), "w") as fh:
        for name, rows in results.items():
            for r in rows:
                fh.write(json.dumps(r, default=str) + "\n")
    return {"meta": meta, "results": results, "output_dir": out_dir}
