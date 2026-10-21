"""
Scoring for the known-age benchmark.

Definitions (used everywhere, stated in every report):
- age class: 0.5, 1.5, 2.5, 3.5, 4.5, 5.5, 6.5+ (ages >= 6.5 collapse into 6.5+)
- exact: predicted age class == reference age class
- within_one_year: |predicted - reference| <= 1.0
- answered: the pipeline returned a numeric age (not abstained, not failed)
- overall accuracy counts every unanswered case as incorrect; answered accuracy uses answered cases only
- range coverage: reference age falls inside the reported age_range (scored separately from exact accuracy)
Intervals: Wilson 95% for proportions; deer-clustered bootstrap 95% for MAE and paired differences.
"""

import math
import random
from typing import Any, Dict, Iterable, List, Optional, Tuple

MIN_SUBGROUP_N = 30
BOOTSTRAP_RESAMPLES = 1000
BOOTSTRAP_SEED = 1234


def age_class(age: Optional[float]) -> Optional[str]:
    if age is None:
        return None
    if age >= 6.5:
        return "6.5+"
    return f"{max(0.5, math.floor(age) + 0.5):.1f}"


def age_group(age: Optional[float]) -> str:
    if age is None:
        return "unknown"
    if age < 1.0:
        return "fawn"
    if age < 2.0:
        return "yearling"
    if age < 4.0:
        return "young_adult_2.5-3.5"
    if age < 6.0:
        return "mature_4.5-5.5"
    return "older_6.5+"


def parse_range(age_range: Optional[str]) -> Optional[Tuple[float, float]]:
    if not age_range:
        return None
    text = str(age_range).strip()
    try:
        if text.endswith("+"):
            return float(text[:-1]), 99.0
        if "-" in text:
            lo, hi = text.split("-", 1)
            return float(lo), float(hi)
        v = float(text)
        return v, v
    except ValueError:
        return None


def wilson(successes: int, n: int, z: float = 1.96) -> Tuple[Optional[float], Optional[float]]:
    if n == 0:
        return None, None
    p = successes / n
    denom = 1 + z * z / n
    centre = (p + z * z / (2 * n)) / denom
    half = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / denom
    return round(max(0.0, centre - half), 4), round(min(1.0, centre + half), 4)


def _cluster_bootstrap(rows: List[Dict[str, Any]], stat, seed: int = BOOTSTRAP_SEED,
                       resamples: int = BOOTSTRAP_RESAMPLES) -> Tuple[Optional[float], Optional[float]]:
    clusters: Dict[str, List[Dict[str, Any]]] = {}
    for r in rows:
        clusters.setdefault(r["deer_id"], []).append(r)
    keys = sorted(clusters)
    if len(keys) < 2:
        return None, None
    rng = random.Random(seed)
    values = []
    for _ in range(resamples):
        sample = [row for k in (rng.choice(keys) for _ in keys) for row in clusters[k]]
        v = stat(sample)
        if v is not None:
            values.append(v)
    if not values:
        return None, None
    values.sort()
    return round(values[int(0.025 * len(values))], 4), round(values[min(len(values) - 1, int(0.975 * len(values)))], 4)


def score_case(result: Dict[str, Any]) -> Dict[str, Any]:
    """Attach correctness fields to one runner result row."""
    ref = result["reference_age"]
    pred = result.get("predicted_age")
    answered = result.get("status") == "answered" and pred is not None
    out = dict(result)
    out["answered"] = answered
    out["exact"] = bool(answered and age_class(pred) == age_class(ref))
    out["within_one_year"] = bool(answered and abs(pred - ref) <= 1.0)
    out["abs_error"] = round(abs(pred - ref), 3) if answered else None
    rng = parse_range(result.get("predicted_range"))
    out["range_reported"] = bool(answered and rng is not None)
    out["range_covers"] = bool(answered and rng is not None and rng[0] - 1e-6 <= ref <= rng[1] + 1e-6)
    out["range_width"] = (None if not rng or rng[1] >= 99 else round(rng[1] - rng[0], 2)) if answered else None
    return out


def _mean(values: Iterable[float]) -> Optional[float]:
    vals = list(values)
    return round(sum(vals) / len(vals), 4) if vals else None


def summarize(rows: List[Dict[str, Any]]) -> Dict[str, Any]:
    n = len(rows)
    answered = [r for r in rows if r["answered"]]
    a = len(answered)
    abstained = sum(1 for r in rows if r.get("status") == "abstained")
    failed = sum(1 for r in rows if r.get("status") not in ("answered", "abstained"))
    exact = sum(r["exact"] for r in rows)
    within = sum(r["within_one_year"] for r in rows)
    ranged = [r for r in answered if r["range_reported"]]
    mae = _mean(r["abs_error"] for r in answered)
    return {
        "n_eligible": n,
        "n_answered": a,
        "n_unanswered": n - a,
        "n_abstained": abstained,
        "n_failed": failed,
        "coverage": round(a / n, 4) if n else None,
        "abstention_rate": round(abstained / n, 4) if n else None,
        "failure_rate": round(failed / n, 4) if n else None,
        "exact_class_accuracy_answered": {"value": round(exact / a, 4) if a else None, "ci95": wilson(exact, a), "n": a},
        "exact_class_accuracy_overall": {"value": round(exact / n, 4) if n else None, "ci95": wilson(exact, n), "n": n},
        "within_one_year_answered": {"value": round(within / a, 4) if a else None, "ci95": wilson(within, a), "n": a},
        "within_one_year_overall": {"value": round(within / n, 4) if n else None, "ci95": wilson(within, n), "n": n},
        "mae_years_answered": {
            "value": mae,
            "ci95": _cluster_bootstrap(answered, lambda s: _mean(r["abs_error"] for r in s if r["answered"])),
            "n": a,
        },
        "range_coverage": {
            "value": round(sum(r["range_covers"] for r in ranged) / len(ranged), 4) if ranged else None,
            "ci95": wilson(sum(r["range_covers"] for r in ranged), len(ranged)),
            "n": len(ranged),
            "mean_width_years": _mean(r["range_width"] for r in ranged if r["range_width"] is not None),
            "open_ended_6_5_plus": sum(1 for r in ranged if r["range_width"] is None),
        },
        "inconclusive": n < MIN_SUBGROUP_N,
    }


BREAKDOWN_KEYS = {
    "species": lambda r: r.get("species") or "unknown",
    "sex": lambda r: r.get("sex") or "unknown",
    "region": lambda r: r.get("region_key") or r.get("region_state") or "unknown",
    "age_group": lambda r: age_group(r.get("reference_age")),
    "image_quality": lambda r: r.get("image_quality") or "unknown",
    "label_tier": lambda r: r.get("label_tier") or "unknown",
}


def breakdowns(rows: List[Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
    out: Dict[str, Dict[str, Any]] = {}
    for name, key in BREAKDOWN_KEYS.items():
        groups: Dict[str, List[Dict[str, Any]]] = {}
        for r in rows:
            groups.setdefault(key(r), []).append(r)
        out[name] = {g: summarize(v) for g, v in sorted(groups.items())}
    return out


def calibration(rows: List[Dict[str, Any]], target: str = "exact", bins: int = 10) -> Dict[str, Any]:
    """Reliability of age confidence vs ONE declared correctness target, on answered cases only."""
    answered = [r for r in rows if r["answered"] and r.get("age_confidence") is not None]
    table, ece, brier = [], 0.0, 0.0
    for b in range(bins):
        lo, hi = b * 100 / bins, (b + 1) * 100 / bins
        members = [r for r in answered if lo <= r["age_confidence"] < hi or (b == bins - 1 and r["age_confidence"] == 100)]
        if not members:
            continue
        acc = sum(r[target] for r in members) / len(members)
        conf = sum(r["age_confidence"] for r in members) / len(members) / 100
        ece += abs(acc - conf) * len(members)
        table.append({"bin": f"{int(lo)}-{int(hi)}", "n": len(members), "mean_confidence": round(conf, 4),
                      "observed_rate": round(acc, 4), "ci95": wilson(sum(r[target] for r in members), len(members))})
    for r in answered:
        brier += (r["age_confidence"] / 100 - (1.0 if r[target] else 0.0)) ** 2
    n = len(answered)
    return {
        "correctness_target": target,
        "target_definition": "predicted age class == reference age class" if target == "exact" else "|predicted - reference| <= 1.0 year",
        "confidence_field": "age_confidence (post-calibration)",
        "n": n,
        "ece": round(ece / n, 4) if n else None,
        "brier": round(brier / n, 4) if n else None,
        "bins": table,
        "inconclusive": n < MIN_SUBGROUP_N,
    }


def mcnemar_exact(b: int, c: int) -> Optional[float]:
    """Two-sided exact McNemar p-value from discordant counts."""
    n = b + c
    if n == 0:
        return None
    k = min(b, c)
    p = sum(math.comb(n, i) for i in range(0, k + 1)) / 2 ** n
    return round(min(1.0, 2 * p), 6)


def paired_comparison(baseline: List[Dict[str, Any]], candidate: List[Dict[str, Any]], metric: str = "exact") -> Dict[str, Any]:
    """Compare two configs on IDENTICAL eligible cases. Unanswered counts as incorrect."""
    base = {r["encounter_id"]: r for r in baseline}
    cand = {r["encounter_id"]: r for r in candidate}
    if set(base) != set(cand):
        raise ValueError("Configs were not evaluated on the same eligible cases; comparison refused.")
    ids = sorted(base)
    pairs = [{"deer_id": base[i]["deer_id"], "b": bool(base[i][metric]), "c": bool(cand[i][metric]),
              "b_ans": base[i]["answered"], "c_ans": cand[i]["answered"],
              "b_err": base[i]["abs_error"], "c_err": cand[i]["abs_error"]} for i in ids]
    n = len(pairs)
    diff = (sum(p["c"] for p in pairs) - sum(p["b"] for p in pairs)) / n if n else None
    b_only = sum(1 for p in pairs if p["b"] and not p["c"])
    c_only = sum(1 for p in pairs if p["c"] and not p["b"])
    both_answered = [p for p in pairs if p["b_ans"] and p["c_ans"]]
    ci = _cluster_bootstrap(pairs, lambda s: (sum(p["c"] for p in s) - sum(p["b"] for p in s)) / len(s) if s else None)
    mae_diff = _mean(p["c_err"] - p["b_err"] for p in both_answered)
    return {
        "metric": metric,
        "n_cases": n,
        "accuracy_difference_overall": round(diff, 4) if diff is not None else None,
        "ci95": ci,
        "discordant_baseline_only": b_only,
        "discordant_candidate_only": c_only,
        "mcnemar_p": mcnemar_exact(b_only, c_only),
        "coverage_difference": round((sum(p["c_ans"] for p in pairs) - sum(p["b_ans"] for p in pairs)) / n, 4) if n else None,
        "mae_difference_on_jointly_answered": {
            "value": mae_diff, "n": len(both_answered),
            "ci95": _cluster_bootstrap(both_answered, lambda s: _mean(p["c_err"] - p["b_err"] for p in s)),
        },
        "inconclusive": n < MIN_SUBGROUP_N or ci[0] is None or (ci[0] <= 0 <= ci[1]),
    }
