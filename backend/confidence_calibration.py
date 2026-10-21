"""
Validated confidence calibration (artifact-based).

A calibration ARTIFACT maps the pipeline's pre-calibration age confidence (`raw_age_confidence`, 0-100)
to the observed probability that ONE declared target is met:

  exact_age_class      predicted age class == reference age class
  within_one_year      |predicted - reference| <= 1.0 year
  age_range_coverage   reference age inside the reported age_range

An artifact is fitted ONLY on the benchmark's calibration split and evaluated on the held-out test split
(see evaluation/README.md). It records the model, prompt version, preprocessing version and input field it
was fitted for; it is never applied to scans produced by a different pipeline.

When no compatible, validated artifact covers a case, the documented heuristic
(region_calibration.compute_age_confidence_with_region) is used and the fallback reason is recorded.
The heuristic is a reliability SCORE, not a calibrated probability.
"""

import hashlib
import json
import math
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

ARTIFACT_SCHEMA_VERSION = "cal-artifact-v1"
TARGETS = {
    "exact_age_class": "Probability the predicted age class equals the reference age class",
    "within_one_year": "Probability the predicted age is within 1.0 year of the reference age",
    "age_range_coverage": "Probability the reference age falls inside the reported age range",
}
HEURISTIC_TARGET = "heuristic_reliability_score"
HEURISTIC_TARGET_DEFINITION = "Rule-based reliability score (not a calibrated probability of any target)"
METHODS = ("global_binning", "isotonic", "platt")
INPUT_FIELD = "raw_age_confidence"
MIN_BIN_SAMPLES = 20
MAX_OUTPUT = 0.85  # existing MAX_AGE_CONFIDENCE safeguard is retained for artifacts too


# ── Fitting ─────────────────────────────────────────────────────────────────
def _pool_blocks(points: List[Tuple[float, int]], min_n: int) -> List[Dict[str, Any]]:
    """Pool-adjacent-violators isotonic fit with every block holding >= min_n samples."""
    blocks = []
    for x, y in sorted(points):
        blocks.append({"lo": x, "hi": x, "n": 1, "k": y})
    # merge undersized blocks first (left to right), then enforce monotonicity
    merged: List[Dict[str, Any]] = []
    for b in blocks:
        if merged and merged[-1]["n"] < min_n:
            m = merged[-1]
            m.update(hi=b["hi"], n=m["n"] + b["n"], k=m["k"] + b["k"])
        else:
            merged.append(dict(b))
    if len(merged) > 1 and merged[-1]["n"] < min_n:
        last = merged.pop()
        merged[-1].update(hi=last["hi"], n=merged[-1]["n"] + last["n"], k=merged[-1]["k"] + last["k"])
    changed = True
    while changed:
        changed = False
        for i in range(len(merged) - 1):
            a, b = merged[i], merged[i + 1]
            if a["k"] / a["n"] > b["k"] / b["n"]:
                a.update(hi=b["hi"], n=a["n"] + b["n"], k=a["k"] + b["k"])
                merged.pop(i + 1)
                changed = True
                break
    return [{"lo": b["lo"], "hi": b["hi"], "n": b["n"], "rate": round(b["k"] / b["n"], 4)} for b in merged]


def fit_binning(points, min_n=MIN_BIN_SAMPLES) -> Dict[str, Any]:
    bins = []
    for i in range(10):
        members = [y for x, y in points if (i * 10 <= x < (i + 1) * 10) or (i == 9 and x == 100)]
        n = len(members)
        bins.append({"lo": i * 10, "hi": (i + 1) * 10, "n": n,
                     "rate": round(sum(members) / n, 4) if n else None, "supported": n >= min_n})
    # Enforce monotonicity across supported bins (weighted pool-adjacent-violators); sparse bins stay unsupported.
    pools = [{"idx": [i], "n": b["n"], "k": b["rate"] * b["n"]} for i, b in enumerate(bins) if b["supported"]]
    i = 0
    while i < len(pools) - 1:
        if pools[i]["k"] / pools[i]["n"] > pools[i + 1]["k"] / pools[i + 1]["n"]:
            a, b = pools[i], pools.pop(i + 1)
            a.update(idx=a["idx"] + b["idx"], n=a["n"] + b["n"], k=a["k"] + b["k"])
            i = max(0, i - 1)
        else:
            i += 1
    for p in pools:
        for idx in p["idx"]:
            bins[idx]["rate"] = round(p["k"] / p["n"], 4)
    return {"bins": bins}


def fit_isotonic(points, min_n=MIN_BIN_SAMPLES) -> Dict[str, Any]:
    return {"blocks": _pool_blocks(points, min_n)}


def fit_platt(points, iters: int = 100) -> Dict[str, Any]:
    a, b = 0.0, 0.0
    for _ in range(iters):  # Newton-Raphson on logistic(a * x/100 + b)
        ga = gb = haa = hab = hbb = 0.0
        for x, y in points:
            z = x / 100
            p = 1 / (1 + math.exp(-(a * z + b)))
            w = p * (1 - p)
            ga += (p - y) * z; gb += (p - y)
            haa += w * z * z; hab += w * z; hbb += w
        det = haa * hbb - hab * hab
        if abs(det) < 1e-12:
            break
        a -= (hbb * ga - hab * gb) / det
        b -= (haa * gb - hab * ga) / det
    xs = [x for x, _ in points]
    return {"a": round(a, 6), "b": round(b, 6), "support": [min(xs), max(xs)]}


FITTERS = {"global_binning": fit_binning, "isotonic": fit_isotonic, "platt": lambda p, min_n=None: fit_platt(p)}


def build_artifact(*, method: str, target: str, points: List[Tuple[float, int]], compatibility: Dict[str, Any],
                   fit_info: Dict[str, Any], scope: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    if target not in TARGETS:
        raise ValueError(f"Unknown target {target}")
    mapping = FITTERS[method](points, min_n=MIN_BIN_SAMPLES)
    body = {
        "schema": ARTIFACT_SCHEMA_VERSION, "method": method, "target": target, "target_definition": TARGETS[target],
        "scope": scope or {"type": "global"}, "compatibility": dict(compatibility, input_field=INPUT_FIELD, target=target),
        "fit": dict(fit_info, n=len(points)), "mapping": mapping, "min_bin_samples": MIN_BIN_SAMPLES,
        "max_output": MAX_OUTPUT, "created_at": datetime.utcnow().isoformat(),
    }
    body["artifact_id"] = "cal-" + hashlib.sha256(json.dumps(body, sort_keys=True, default=str).encode()).hexdigest()[:12]
    return body


# ── Validation / compatibility ──────────────────────────────────────────────
def validate_artifact(art: Dict[str, Any]) -> List[str]:
    errors = []
    for key in ("schema", "artifact_id", "method", "target", "scope", "compatibility", "fit", "mapping"):
        if key not in art:
            errors.append(f"missing:{key}")
    if errors:
        return errors
    if art["schema"] != ARTIFACT_SCHEMA_VERSION:
        errors.append("unsupported_schema")
    if art["method"] not in METHODS:
        errors.append("unknown_method")
    if art["target"] not in TARGETS:
        errors.append("unknown_target")
    comp = art["compatibility"]
    for key in ("model", "prompt_version", "preprocessing_version", "input_field", "target"):
        if not comp.get(key):
            errors.append(f"compatibility_missing:{key}")
    if comp.get("target") != art["target"]:
        errors.append("target_mismatch")
    m = art["mapping"]
    try:
        if art["method"] == "global_binning":
            bins = m["bins"]
            if len(bins) != 10:
                errors.append("malformed_bins")
            rates = [b["rate"] for b in bins if b.get("supported")]
            if any(not (isinstance(r, (int, float)) and math.isfinite(r) and 0 <= r <= 1) for r in rates):
                errors.append("invalid_numeric_output")
            if any(b.get("supported") and b["n"] < art.get("min_bin_samples", MIN_BIN_SAMPLES) for b in bins):
                errors.append("sparse_bin_marked_supported")
            if any(rates[i] > rates[i + 1] + 1e-9 for i in range(len(rates) - 1)):
                errors.append("not_monotonic")
            if not rates:
                errors.append("no_supported_bins")
        elif art["method"] == "isotonic":
            blocks = m["blocks"]
            if not blocks:
                errors.append("no_blocks")
            if any(b["n"] < art.get("min_bin_samples", MIN_BIN_SAMPLES) for b in blocks):
                errors.append("sparse_block")
            if any(not (math.isfinite(b["rate"]) and 0 <= b["rate"] <= 1) for b in blocks):
                errors.append("invalid_numeric_output")
            if any(blocks[i]["rate"] > blocks[i + 1]["rate"] + 1e-9 or blocks[i]["hi"] > blocks[i + 1]["lo"]
                   for i in range(len(blocks) - 1)):
                errors.append("not_monotonic")
        else:
            if not (math.isfinite(m["a"]) and math.isfinite(m["b"])):
                errors.append("invalid_numeric_output")
            if m["a"] < 0:
                errors.append("not_monotonic")
    except (KeyError, TypeError):
        errors.append("malformed_mapping")
    return errors


def check_compatibility(art: Dict[str, Any], *, model: Optional[str], prompt_version: Optional[str],
                        preprocessing_version: Optional[str]) -> List[str]:
    comp = art.get("compatibility") or {}
    reasons = []
    if comp.get("model") != model:
        reasons.append(f"model:{comp.get('model')}!={model}")
    if comp.get("prompt_version") != prompt_version:
        reasons.append(f"prompt:{comp.get('prompt_version')}!={prompt_version}")
    if comp.get("preprocessing_version") != preprocessing_version:
        reasons.append(f"preprocessing:{comp.get('preprocessing_version')}!={preprocessing_version}")
    return reasons


# ── Application ─────────────────────────────────────────────────────────────
def apply_artifact(art: Dict[str, Any], raw_confidence: Optional[float]) -> Tuple[Optional[float], Optional[str]]:
    """Returns (probability 0-1, None) or (None, fallback_reason). Never extrapolates or fills sparse bins."""
    if raw_confidence is None:
        return None, "artifact_no_input_confidence"
    x = float(raw_confidence)
    m = art["mapping"]
    value = None
    if art["method"] == "global_binning":
        b = m["bins"][min(int(x // 10), 9)]
        if not b.get("supported"):
            return None, "artifact_sparse_bin"
        value = b["rate"]
    elif art["method"] == "isotonic":
        block = next((b for b in m["blocks"] if b["lo"] <= x <= b["hi"]), None)
        if block is None:
            lower = [b for b in m["blocks"] if b["hi"] < x]
            upper = [b for b in m["blocks"] if b["lo"] > x]
            if not lower or not upper:
                return None, "artifact_input_outside_support"
            block = lower[-1]  # inside support gap: take the lower (conservative) block
        value = block["rate"]
    else:
        lo, hi = m["support"]
        if not lo <= x <= hi:
            return None, "artifact_input_outside_support"
        value = 1 / (1 + math.exp(-(m["a"] * x / 100 + m["b"])))
    if value is None or not math.isfinite(value) or not 0 <= value <= 1:
        return None, "artifact_invalid_output"
    return min(value, art.get("max_output", MAX_OUTPUT)), None


def select_artifact(artifacts: List[Dict[str, Any]], region_key: Optional[str]) -> List[Dict[str, Any]]:
    """Region-scoped artifacts first (only if present and active), then global."""
    region = [a for a in artifacts if (a.get("scope") or {}).get("type") == "region" and a["scope"].get("region_key") == region_key]
    glob = [a for a in artifacts if (a.get("scope") or {}).get("type") == "global"]
    return region + glob


# ── Reliability metrics ─────────────────────────────────────────────────────
def reliability(pairs: List[Tuple[Optional[float], int]], bins: int = 10) -> Dict[str, Any]:
    """pairs: (predicted probability 0-1 or None for fallback, outcome 0/1)."""
    used = [(p, y) for p, y in pairs if p is not None]
    n = len(used)
    if not n:
        return {"n": 0, "n_fallback": len(pairs), "ece": None, "brier": None, "log_loss": None, "table": []}
    table, ece = [], 0.0
    for i in range(bins):
        members = [(p, y) for p, y in used if i / bins <= p < (i + 1) / bins or (i == bins - 1 and p == 1)]
        if members:
            conf = sum(p for p, _ in members) / len(members)
            rate = sum(y for _, y in members) / len(members)
            ece += abs(conf - rate) * len(members)
            table.append({"bin": f"{i/bins:.1f}-{(i+1)/bins:.1f}", "n": len(members),
                          "mean_predicted": round(conf, 4), "observed": round(rate, 4)})
    eps = 1e-6
    return {
        "n": n, "n_fallback": len(pairs) - n,
        "ece": round(ece / n, 4),
        "brier": round(sum((p - y) ** 2 for p, y in used) / n, 4),
        "log_loss": round(-sum(y * math.log(max(p, eps)) + (1 - y) * math.log(max(1 - p, eps)) for p, y in used) / n, 4),
        "table": table,
    }
