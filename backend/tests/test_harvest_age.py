from datetime import datetime
from collections import defaultdict

import server


def _resp(threshold, **fields):
    scan = defaultdict(lambda: None, {
        "id": "s1", "user_id": "u", "local_image_id": "l", "created_at": datetime.utcnow(),
        "recommendation": "HARVEST", "recommendation_status": "age_based", **fields,
    })
    return server.build_scan_response(scan, harvest_age=threshold)


def test_point_age_uses_hunter_threshold():
    assert _resp(3.5, deer_age=3.5).recommendation == "HARVEST"
    assert _resp(4.5, deer_age=3.5).recommendation == "PASS"
    assert _resp(2.0, deer_age=2.0).recommendation == "HARVEST"
    assert _resp(4.5, deer_age=3.5).harvest_age_threshold == 4.5


def test_range_crossing_threshold_has_no_call():
    r = _resp(4.5, deer_age=4.0, age_lower=3.5, age_upper=4.5, age_upper_open=False, range_status="plausible_uncalibrated")
    assert r.recommendation is None and r.recommendation_status == "uncertain_range_crosses_threshold"
    r = _resp(3.5, deer_age=4.0, age_lower=3.5, age_upper=4.5, age_upper_open=False, range_status="plausible_uncalibrated")
    assert r.recommendation == "HARVEST"
    r = _resp(6.5, deer_age=6.0, age_lower=5.5, age_upper=6.5, age_upper_open=True, range_status="plausible_uncalibrated")
    assert r.recommendation is None


def test_age_and_range_are_never_changed_and_abstentions_keep_no_call():
    r = _resp(5.5, deer_age=4.0, age_lower=3.5, age_upper=4.5, age_upper_open=False, age_range="3.5–4.5", range_status="plausible_uncalibrated")
    assert (r.deer_age, r.age_lower, r.age_upper, r.age_range) == (4.0, 3.5, 4.5, "3.5–4.5")
    assert r.recommendation == "PASS"
    assert _resp(2.0, deer_age=None, recommendation=None).recommendation is None
    assert _resp(2.0, deer_age=3.0, age_estimation_allowed=False, recommendation=None).recommendation is None


def test_user_harvest_age_defaults_and_rejects_bad_values():
    assert server.user_harvest_age({}) == 3.5
    assert server.user_harvest_age({"harvest_age_threshold": None}) == 3.5
    assert server.user_harvest_age({"harvest_age_threshold": 7.0}) == 3.5
    assert server.user_harvest_age({"harvest_age_threshold": 4.5}) == 4.5
