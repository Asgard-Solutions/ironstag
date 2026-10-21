"""Report generation (JSON + Markdown) from a run directory."""

import json
import os
from typing import Any, Dict, List

from evaluation import metrics
from evaluation.runner import factor_differences

NOT_EVIDENCE_BANNER = (
    "SYNTHETIC / MOCK RUN — NOT ACCURACY EVIDENCE. These numbers only verify that scoring and plumbing work."
)


def _load_run(run_dir: str):
    with open(os.path.join(run_dir, "run.json")) as fh:
        meta = json.load(fh)
    results: Dict[str, List[Dict[str, Any]]] = {}
    with open(os.path.join(run_dir, "results.jsonl")) as fh:
        for line in fh:
            row = json.loads(line)
            results.setdefault(row["config"], []).append(row)
    return meta, results


def build_report(run_dir: str, calibration_target: str = "exact") -> Dict[str, Any]:
    meta, raw = _load_run(run_dir)
    not_evidence = bool(meta.get("synthetic_dataset") or meta.get("mock_model"))
    configs = {c["name"]: c for c in meta["configs"]}
    names = [c["name"] for c in meta["configs"]]
    scored = {name: [metrics.score_case(r) for r in raw.get(name, [])] for name in names}

    per_config = {}
    for name in names:
        rows = scored[name]
        per_config[name] = {
            "config": configs[name],
            "overall": metrics.summarize(rows),
            "breakdowns": metrics.breakdowns(rows),
            "calibration": metrics.calibration(rows, target=calibration_target),
            "failures": [{"encounter_id": r["encounter_id"], "status": r["status"], "error": r.get("error")}
                         for r in rows if r["status"] not in ("answered", "abstained")],
            "abstentions": [{"encounter_id": r["encounter_id"], "reason": r.get("abstain_reason")}
                            for r in rows if r["status"] == "abstained"],
            "latency_s_mean": metrics._mean(r["latency_s"] for r in rows if r.get("latency_s") is not None),
            "tokens": {"prompt": sum(r.get("prompt_tokens") or 0 for r in rows),
                       "completion": sum(r.get("completion_tokens") or 0 for r in rows)},
            "cost_usd": round(sum(r.get("cost_usd") or 0 for r in rows), 4),
        }

    comparisons = []
    baseline = names[0]
    for name in names[1:]:
        diffs = factor_differences(configs[baseline], configs[name])
        cmp = {
            "baseline": baseline, "candidate": name, "factors_changed": diffs,
            "one_factor_at_a_time": len(diffs) <= 1,
            "exact": metrics.paired_comparison(scored[baseline], scored[name], "exact"),
            "within_one_year": metrics.paired_comparison(scored[baseline], scored[name], "within_one_year"),
        }
        if not_evidence:
            cmp["verdict"] = "NOT EVIDENCE (synthetic dataset or mock model)"
        elif cmp["exact"]["inconclusive"]:
            cmp["verdict"] = "Inconclusive: difference not distinguishable from zero on this test set"
        else:
            cmp["verdict"] = ("Candidate better" if cmp["exact"]["accuracy_difference_overall"] > 0 else "Candidate worse") + \
                             " on exact age class (95% CI excludes 0); confirm before adopting"
        comparisons.append(cmp)

    report = {
        "banner": NOT_EVIDENCE_BANNER if not_evidence else None,
        "run": meta,
        "definitions": metrics.__doc__.strip(),
        "min_subgroup_n_for_conclusions": metrics.MIN_SUBGROUP_N,
        "per_config": per_config,
        "comparisons": comparisons,
    }
    with open(os.path.join(run_dir, "report.json"), "w") as fh:
        json.dump(report, fh, indent=2, default=str)
    with open(os.path.join(run_dir, "report.md"), "w") as fh:
        fh.write(render_markdown(report))
    return report


def _fmt(metric: Dict[str, Any]) -> str:
    v, ci = metric.get("value"), metric.get("ci95") or (None, None)
    if v is None:
        return "n/a"
    ci_txt = f" [{ci[0]}, {ci[1]}]" if ci and ci[0] is not None else ""
    return f"{v}{ci_txt} (n={metric.get('n')})"


def render_markdown(report: Dict[str, Any]) -> str:
    run = report["run"]
    lines = [f"# Iron Stag known-age evaluation — run {run['run_id']}", ""]
    if report["banner"]:
        lines += [f"> **{report['banner']}**", ""]
    lines += [
        f"- Split: `{run['split']}` · eligible cases: {len(run['eligible_case_ids'])} · excluded: {len(run['excluded_cases'])}",
        f"- Dataset sha256: `{run['dataset_sha256']}` · code commit: `{run.get('code_commit')}`",
        f"- Mock model: {run['mock_model']} · synthetic dataset: {run['synthetic_dataset']} · spent: ${run['spent_usd']}",
        f"- Subgroups with n < {report['min_subgroup_n_for_conclusions']} are marked **inconclusive**.", "",
        "## Definitions", "```", report["definitions"], "```", "",
    ]
    for name, pc in report["per_config"].items():
        o = pc["overall"]
        cfg = pc["config"]
        lines += [
            f"## Config `{name}`",
            f"model `{cfg['model']}` · prompt `{cfg['prompt']['label']}` · multi_photo {cfg['multi_photo']} · crops {cfg['use_crops']} · "
            f"max_edge {cfg['max_edge']} · consensus {cfg['consensus']} · calibration `{cfg['calibration']}`", "",
            "| Metric | Value [95% CI] |", "|---|---|",
            f"| Eligible / answered / abstained / failed | {o['n_eligible']} / {o['n_answered']} / {o['n_abstained']} / {o['n_failed']} |",
            f"| Coverage | {o['coverage']} |",
            f"| Abstention rate | {o['abstention_rate']} |",
            f"| Exact age class — answered | {_fmt(o['exact_class_accuracy_answered'])} (unanswered: {o['n_unanswered']}) |",
            f"| Exact age class — overall (unanswered = wrong) | {_fmt(o['exact_class_accuracy_overall'])} |",
            f"| Within 1 year — answered | {_fmt(o['within_one_year_answered'])} |",
            f"| Within 1 year — overall | {_fmt(o['within_one_year_overall'])} |",
            f"| MAE (years) — answered | {_fmt(o['mae_years_answered'])} |",
            f"| Age-range coverage (separate from exact accuracy) | {_fmt(o['range_coverage'])}, mean width {o['range_coverage']['mean_width_years']} |",
            f"| Mean latency (s) / cost ($) | {pc['latency_s_mean']} / {pc['cost_usd']} |", "",
        ]
        cal = pc["calibration"]
        lines += [f"**Calibration** — target: {cal['target_definition']} · n={cal['n']} · ECE {cal['ece']} · Brier {cal['brier']}"
                  + (" · inconclusive" if cal["inconclusive"] else ""), ""]
        for dim, groups in pc["breakdowns"].items():
            lines += [f"**By {dim}**", "", "| Group | n | Answered | Exact (answered) | Within 1 yr (answered) | MAE | Note |", "|---|---|---|---|---|---|---|"]
            for g, s in groups.items():
                lines.append(f"| {g} | {s['n_eligible']} | {s['n_answered']} | {_fmt(s['exact_class_accuracy_answered'])} | "
                             f"{_fmt(s['within_one_year_answered'])} | {s['mae_years_answered']['value']} | "
                             f"{'inconclusive' if s['inconclusive'] else ''} |")
            lines.append("")
        lines += [f"**Failures ({len(pc['failures'])})**"] + [f"- {f['encounter_id']}: {f['status']} — {f['error']}" for f in pc["failures"]] + [""]
        lines += [f"**Abstentions ({len(pc['abstentions'])})**"] + [f"- {a['encounter_id']}: {a['reason']}" for a in pc["abstentions"]] + [""]
    if report["comparisons"]:
        lines += ["## Paired comparisons (identical eligible cases)", ""]
        for c in report["comparisons"]:
            e = c["exact"]
            lines += [
                f"### `{c['candidate']}` vs `{c['baseline']}`",
                f"- Factors changed: {c['factors_changed']}" + ("" if c["one_factor_at_a_time"] else " ⚠️ more than one factor changed"),
                f"- Exact class Δ (overall): {e['accuracy_difference_overall']} CI {e['ci95']} · McNemar p={e['mcnemar_p']} · n={e['n_cases']}",
                f"- Within 1 yr Δ: {c['within_one_year']['accuracy_difference_overall']} CI {c['within_one_year']['ci95']}",
                f"- Coverage Δ: {e['coverage_difference']} · MAE Δ (jointly answered): {e['mae_difference_on_jointly_answered']}",
                f"- **Verdict: {c['verdict']}**", "",
            ]
    return "\n".join(lines) + "\n"
