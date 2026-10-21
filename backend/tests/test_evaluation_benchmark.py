"""
Synthetic-fixture tests for the known-age benchmark.
These verify scoring, validation and leakage detection ONLY. They are not accuracy evidence.
"""
import json
import os
import random
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest
from PIL import Image, ImageDraw

from evaluation import dataset as ds
from evaluation import metrics


def _img(path, seed, size=(640, 480)):
    rnd = random.Random(seed)
    im = Image.new("RGB", size, (rnd.randint(0, 255), rnd.randint(0, 255), rnd.randint(0, 255)))
    d = ImageDraw.Draw(im)
    for _ in range(25):
        x, y = rnd.randint(0, size[0] - 60), rnd.randint(0, size[1] - 60)
        d.rectangle([x, y, x + rnd.randint(10, 60), y + rnd.randint(10, 60)],
                    fill=(rnd.randint(0, 255), rnd.randint(0, 255), rnd.randint(0, 255)))
    os.makedirs(os.path.dirname(path), exist_ok=True)
    im.save(path, format="JPEG")


def _rec(eid, did, imgs, age=3.5, basis="tagged_as_fawn", unc=0.0, split="development", **kw):
    r = {"encounter_id": eid, "deer_id": did, "species": "whitetail", "sex": "buck", "region_state": "IA",
         "encounter_date": "2025-11-02", "images": [{"path": p} for p in imgs], "reference_age": age,
         "age_basis": basis, "label_uncertainty_years": unc, "image_quality": "good", "split": split}
    r.update(kw)
    return r


def _write(tmp_path, records, synthetic=True):
    path = tmp_path / "data.jsonl"
    with open(path, "w") as fh:
        fh.write(json.dumps({"_dataset": {"name": "fixture", "synthetic": synthetic}}) + "\n")
        for r in records:
            fh.write(json.dumps(r) + "\n")
    return str(path)


def _codes(result, level=None):
    return {i.code for i in result.issues if level is None or i.level == level}


# ── Scoring ──
def test_age_class_and_scoring():
    assert metrics.age_class(3.5) == "3.5" and metrics.age_class(7.5) == "6.5+" and metrics.age_class(0.5) == "0.5"
    base = {"encounter_id": "e", "deer_id": "d", "reference_age": 4.5}
    hit = metrics.score_case({**base, "status": "answered", "predicted_age": 4.5, "predicted_range": "4.5-5.5"})
    near = metrics.score_case({**base, "status": "answered", "predicted_age": 3.5, "predicted_range": "2.5-3.5"})
    abst = metrics.score_case({**base, "status": "abstained", "predicted_age": None})
    assert hit["exact"] and hit["within_one_year"] and hit["range_covers"] and hit["abs_error"] == 0
    assert not near["exact"] and near["within_one_year"] and not near["range_covers"] and near["abs_error"] == 1.0
    assert not abst["answered"] and not abst["exact"] and abst["abs_error"] is None


def test_summary_reports_unanswered_and_failures():
    rows = [metrics.score_case({"encounter_id": f"e{i}", "deer_id": f"d{i}", "reference_age": 2.5, **s})
            for i, s in enumerate([
                {"status": "answered", "predicted_age": 2.5}, {"status": "answered", "predicted_age": 4.5},
                {"status": "abstained"}, {"status": "failed_error"}])]
    s = metrics.summarize(rows)
    assert (s["n_eligible"], s["n_answered"], s["n_abstained"], s["n_failed"]) == (4, 2, 1, 1)
    assert s["exact_class_accuracy_answered"]["value"] == 0.5
    assert s["exact_class_accuracy_overall"]["value"] == 0.25
    assert s["coverage"] == 0.5 and s["inconclusive"] is True
    lo, hi = s["exact_class_accuracy_answered"]["ci95"]
    assert lo < 0.5 < hi


def test_calibration_uses_declared_target():
    rows = [metrics.score_case({"encounter_id": f"e{i}", "deer_id": f"d{i}", "reference_age": 3.5,
                                "status": "answered", "predicted_age": 3.5 if i % 2 else 4.5, "age_confidence": 75})
            for i in range(10)]
    cal = metrics.calibration(rows, target="exact")
    assert cal["correctness_target"] == "exact" and cal["n"] == 10
    assert cal["bins"][0]["observed_rate"] == 0.5 and cal["ece"] == 0.25


def test_paired_comparison_requires_identical_cases():
    mk = lambda ids, ok: [metrics.score_case({"encounter_id": i, "deer_id": i, "reference_age": 2.5,
                                              "status": "answered", "predicted_age": 2.5 if ok else 4.5}) for i in ids]
    cmp = metrics.paired_comparison(mk(["a", "b", "c"], False), mk(["a", "b", "c"], True))
    assert cmp["accuracy_difference_overall"] == 1.0 and cmp["discordant_candidate_only"] == 3
    assert cmp["inconclusive"] is True  # n < 30
    with pytest.raises(ValueError):
        metrics.paired_comparison(mk(["a", "b"], False), mk(["a", "c"], True))


# ── Validation / leakage ──
def test_deer_level_split_is_stable():
    assert all(ds.assign_split("deer-X") == ds.assign_split("deer-X") for _ in range(5))


def test_deer_in_two_splits_is_error_and_excluded(tmp_path):
    _img(str(tmp_path / "a1.jpg"), 1); _img(str(tmp_path / "a2.jpg"), 2); _img(str(tmp_path / "b1.jpg"), 3)
    path = _write(tmp_path, [
        _rec("e1", "deerA", ["a1.jpg"], split="development"),
        _rec("e2", "deerA", ["a2.jpg"], split="test"),
        _rec("e3", "deerB", ["b1.jpg"], split="test"),
    ])
    result = ds.validate_dataset(path)
    assert "deer_in_multiple_splits" in _codes(result, "error")
    test_cases, _ = ds.eligible_cases(result, "test")
    dev_cases, _ = ds.eligible_cases(result, "development")
    assert [c["encounter_id"] for c in test_cases] == ["e3"] and dev_cases == []


def test_duplicate_image_across_deer_is_leakage(tmp_path):
    _img(str(tmp_path / "x.jpg"), 7)
    _img(str(tmp_path / "y.jpg"), 8)
    path = _write(tmp_path, [_rec("e1", "deerA", ["x.jpg"]), _rec("e2", "deerB", ["x.jpg", "y.jpg"])])
    result = ds.validate_dataset(path)
    assert "duplicate_image_across_deer" in _codes(result, "error")
    assert ds.eligible_cases(result, "development")[0] == []


def test_unreliable_and_missing_labels_are_flagged(tmp_path):
    for n in range(4):
        _img(str(tmp_path / f"{n}.jpg"), 20 + n)
    path = _write(tmp_path, [
        _rec("ok", "d0", ["0.jpg"]),
        _rec("guess", "d1", ["1.jpg"], basis="hunter_best_estimate", unc=1.5),
        _rec("nounc", "d2", ["2.jpg"], basis="cementum_annuli", unc=None),
        {k: v for k, v in _rec("noage", "d3", ["3.jpg"]).items() if k != "reference_age"},
    ])
    result = ds.validate_dataset(path)
    codes = _codes(result)
    assert {"label_not_ground_truth", "label_uncertainty_high", "label_uncertainty_missing", "missing_required_fields"} <= codes
    eligible, excluded = ds.eligible_cases(result, "development")
    assert [c["encounter_id"] for c in eligible] == ["ok"]
    reasons = {e["encounter_id"]: e["reason"] for e in excluded}
    assert reasons["guess"].startswith("label_not_eligible") and reasons["noage"] == "validation_error"


# ── Runner (mock model; never evidence) ──
def test_mock_run_is_isolated_labelled_and_reports_failures(tmp_path):
    from evaluation.runner import load_config, run_evaluation
    from evaluation.report import build_report, NOT_EVIDENCE_BANNER

    _img(str(tmp_path / "a.jpg"), 31); _img(str(tmp_path / "b.jpg"), 32); _img(str(tmp_path / "c.jpg"), 33)
    _img(str(tmp_path / "tiny.jpg"), 34, size=(120, 90))  # rejected by input validation -> failure row
    path = _write(tmp_path, [
        _rec("e1", "d1", ["a.jpg", "b.jpg"], age=3.5),
        _rec("e2", "d2", ["c.jpg"], age=5.5),
        _rec("e3", "d3", ["tiny.jpg"], age=2.5),
    ])
    result = ds.validate_dataset(path)
    cases, excluded = ds.eligible_cases(result, "development")
    configs = [load_config({"name": "baseline"}), load_config({"name": "multi", "multi_photo": True})]
    out = run_evaluation(cases=cases, excluded=excluded, configs=configs, dataset_path=path,
                         dataset_sha256=result.dataset_sha256, synthetic_dataset=True, split="development",
                         mock=True, budget_usd=None, max_calls=None, output_dir=str(tmp_path / "run"))
    report = build_report(out["output_dir"])
    assert report["banner"] == NOT_EVIDENCE_BANNER
    base = report["per_config"]["baseline"]
    assert base["overall"]["n_eligible"] == 3 and base["overall"]["n_failed"] == 1
    assert base["failures"][0]["encounter_id"] == "e3"
    assert {r["encounter_id"] for r in out["results"]["baseline"]} == {r["encounter_id"] for r in out["results"]["multi"]}
    multi_e1 = next(r for r in out["results"]["multi"] if r["encounter_id"] == "e1")
    assert multi_e1["preprocessing"]["evidence_photos"] == 2 and multi_e1["mock_model"] is True
    cmp = report["comparisons"][0]
    assert cmp["factors_changed"] == ["multi_photo"] and cmp["verdict"].startswith("NOT EVIDENCE")
    assert "NOT ACCURACY EVIDENCE" in open(os.path.join(out["output_dir"], "report.md")).read()


def test_paid_run_requires_agreed_budget(tmp_path):
    from evaluation.runner import load_config, run_evaluation
    _img(str(tmp_path / "a.jpg"), 41)
    path = _write(tmp_path, [_rec("e1", "d1", ["a.jpg"])])
    result = ds.validate_dataset(path)
    cases, excluded = ds.eligible_cases(result, "development")
    kwargs = dict(cases=cases, excluded=excluded, dataset_path=path, dataset_sha256="x", synthetic_dataset=True,
                  split="development", mock=False, output_dir=str(tmp_path / "run"))
    with pytest.raises(PermissionError):
        run_evaluation(configs=[load_config({"name": "b"})], budget_usd=None, max_calls=None, **kwargs)
    priced = load_config({"name": "b", "pricing_usd_per_1m_tokens": {"input": 2.5, "output": 10}})
    with pytest.raises(PermissionError):
        run_evaluation(configs=[priced], budget_usd=0.001, max_calls=1, **kwargs)
