"""
Command-line workflow for the known-age benchmark.

  python -m evaluation validate  DATASET.jsonl
  python -m evaluation splits    DATASET.jsonl [--out manifest.json]
  python -m evaluation plan      DATASET.jsonl --split test --config A.json [--config B.json ...]
  python -m evaluation run       DATASET.jsonl --split test --config A.json --config B.json \
                                 (--mock | --budget-usd 25 --max-calls 600) [--allow-test-split]
  python -m evaluation report    RUN_DIR [--calibration-target exact|within_one_year]
  python -m evaluation export-labels --out exported.jsonl   (read-only DB export of feedback labels)

Run from /app/backend. See evaluation/README.md.
"""

import argparse
import asyncio
import json
import sys

from evaluation import dataset as ds


def _tiers(args):
    return tuple(args.label_tiers.split(",")) if args.label_tiers else ds.GROUND_TRUTH_TIERS


def cmd_validate(args) -> int:
    result = ds.validate_dataset(args.dataset)
    print(json.dumps(result.summary(), indent=2))
    for issue in result.issues:
        print(f"[{issue.level.upper()}] {issue.code} enc={issue.encounter_id} deer={issue.deer_id}: {issue.message}")
    return 1 if any(i.level == "error" for i in result.issues) else 0


def cmd_splits(args) -> int:
    manifest = ds.split_manifest(ds.validate_dataset(args.dataset))
    text = json.dumps(manifest, indent=2)
    if args.out:
        open(args.out, "w").write(text)
    print(text)
    return 0


def _prepare(args):
    from evaluation.runner import load_config, estimate_budget
    result = ds.validate_dataset(args.dataset)
    cases, excluded = ds.eligible_cases(result, args.split, allowed_tiers=_tiers(args))
    configs = [load_config(p) for p in args.config]
    names = [c["name"] for c in configs]
    if len(set(names)) != len(names):
        raise SystemExit("Config names must be unique.")
    return result, cases, excluded, configs, estimate_budget(cases, configs)


def cmd_plan(args) -> int:
    from evaluation.runner import factor_differences
    result, cases, excluded, configs, plan = _prepare(args)
    print(json.dumps({"split": args.split, "eligible_cases": len(cases), "excluded": len(excluded),
                      "synthetic_dataset": result.synthetic, "budget_plan": plan,
                      "factor_changes_vs_first": {c["name"]: factor_differences(configs[0], c) for c in configs[1:]}}, indent=2))
    return 0


def cmd_run(args) -> int:
    from evaluation.runner import run_evaluation
    from evaluation.report import build_report
    if args.split == "test" and not args.allow_test_split:
        raise SystemExit("The held-out test split is sealed. Pass --allow-test-split for final comparisons only (access is logged).")
    result, cases, excluded, configs, plan = _prepare(args)
    print(json.dumps({"eligible_cases": len(cases), "budget_plan": plan}, indent=2))
    out = run_evaluation(cases=cases, excluded=excluded, configs=configs, dataset_path=args.dataset,
                         dataset_sha256=result.dataset_sha256, synthetic_dataset=result.synthetic, split=args.split,
                         mock=args.mock, budget_usd=args.budget_usd, max_calls=args.max_calls, output_dir=args.out)
    build_report(out["output_dir"], calibration_target=args.calibration_target)
    print(f"Run written to {out['output_dir']} (report.md, report.json, results.jsonl, run.json)")
    return 0


def cmd_report(args) -> int:
    from evaluation.report import build_report
    build_report(args.run_dir, calibration_target=args.calibration_target)
    print(f"Report written to {args.run_dir}/report.md")
    return 0


def cmd_export(args) -> int:
    """Read-only export of exact-age feedback labels into the dataset format (images referenced by URL)."""
    import server

    async def go():
        await server.database.connect()
        try:
            rows = await server.database.fetch_all(
                "SELECT l.scan_id, l.reported_age, l.age_source, l.labeler_role, l.harvest_confirmed, "
                "s.deer_type, s.deer_sex, s.region_state, s.region_key, s.date_taken, s.created_at, s.image_url, "
                "s.image_quality_bucket FROM scan_labels l JOIN scans s ON s.id = l.scan_id "
                "WHERE l.reported_age IS NOT NULL"
            )
            out = []
            for r in rows:
                imgs = await server.fetch_scan_image_rows(r["scan_id"])
                paths = [i.get("original_url") for i in imgs if i.get("original_url")] or ([r["image_url"]] if r["image_url"] else [])
                out.append({
                    "encounter_id": f"scan:{r['scan_id']}",
                    "deer_id": f"scan:{r['scan_id']}",
                    "identity_unverified": True,
                    "species": "mule_deer" if (r["deer_type"] or "").lower().startswith("mule") else "whitetail",
                    "sex": (r["deer_sex"] or "unknown").lower() if (r["deer_sex"] or "").lower() in ("buck", "doe") else "unknown",
                    "region_state": r["region_state"], "region_key": r["region_key"],
                    "encounter_date": str(r["date_taken"] or (r["created_at"].date() if r["created_at"] else "")),
                    "images": [{"path": p} for p in paths],
                    "reference_age": r["reported_age"],
                    "age_basis": r["age_source"] or "unknown",
                    "age_established_by": r["labeler_role"],
                    "label_uncertainty_years": None,
                    "image_quality": r["image_quality_bucket"],
                    "notes": "Exported from in-app feedback. Verify identity, basis and uncertainty before use; download images locally.",
                })
            return out
        finally:
            await server.database.disconnect()

    records = asyncio.run(go())
    with open(args.out, "w") as fh:
        fh.write(json.dumps({"_dataset": {"name": "feedback-export", "synthetic": False, "source": "scan_labels"}}) + "\n")
        for rec in records:
            fh.write(json.dumps(rec, default=str) + "\n")
    print(f"Exported {len(records)} labelled scans to {args.out} (all flagged identity_unverified, uncertainty missing)")
    return 0


def main(argv=None) -> int:
    p = argparse.ArgumentParser(prog="python -m evaluation", description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="cmd", required=True)
    v = sub.add_parser("validate"); v.add_argument("dataset"); v.set_defaults(fn=cmd_validate)
    s = sub.add_parser("splits"); s.add_argument("dataset"); s.add_argument("--out"); s.set_defaults(fn=cmd_splits)
    for name, fn in (("plan", cmd_plan), ("run", cmd_run)):
        r = sub.add_parser(name)
        r.add_argument("dataset")
        r.add_argument("--split", choices=ds.SPLITS, required=True)
        r.add_argument("--config", action="append", required=True, help="Config JSON; first one is the baseline")
        r.add_argument("--label-tiers", help=f"Comma list of eligible label tiers (default {','.join(ds.GROUND_TRUTH_TIERS)})")
        r.set_defaults(fn=fn)
        if name == "run":
            r.add_argument("--mock", action="store_true", help="Use the deterministic mock model (no cost, not evidence)")
            r.add_argument("--budget-usd", type=float)
            r.add_argument("--max-calls", type=int)
            r.add_argument("--allow-test-split", action="store_true")
            r.add_argument("--out")
            r.add_argument("--calibration-target", choices=["exact", "within_one_year"], default="exact")
    rp = sub.add_parser("report"); rp.add_argument("run_dir")
    rp.add_argument("--calibration-target", choices=["exact", "within_one_year"], default="exact"); rp.set_defaults(fn=cmd_report)
    e = sub.add_parser("export-labels"); e.add_argument("--out", required=True); e.set_defaults(fn=cmd_export)
    args = p.parse_args(argv)
    return args.fn(args)


if __name__ == "__main__":
    sys.exit(main())
