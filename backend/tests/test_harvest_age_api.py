"""Light re-check of harvest_age_threshold API against preview backend."""
import os
import pytest
import requests

BASE_URL = "https://date-persist-deploy.preview.emergentagent.com"
EMAIL = "multiphoto.test@ironstag.dev"
PASSWORD = "MultiPhoto#2026"


@pytest.fixture(scope="module")
def auth_headers():
    r = requests.post(f"{BASE_URL}/api/auth/login", json={"email": EMAIL, "password": PASSWORD}, timeout=20)
    assert r.status_code == 200, r.text
    token = r.json()["access_token"]
    return {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}


def _get_me(headers):
    r = requests.get(f"{BASE_URL}/api/auth/me", headers=headers, timeout=20)
    assert r.status_code == 200, r.text
    return r.json()


def test_me_returns_harvest_age_threshold(auth_headers):
    me = _get_me(auth_headers)
    assert "harvest_age_threshold" in me
    assert isinstance(me["harvest_age_threshold"], (int, float))


def test_update_profile_accepts_allowed_value(auth_headers):
    # Set to 5.5
    r = requests.put(f"{BASE_URL}/api/auth/profile", headers=auth_headers, json={"harvest_age_threshold": 5.5}, timeout=20)
    assert r.status_code == 200, r.text
    me = _get_me(auth_headers)
    assert me["harvest_age_threshold"] == 5.5
    # restore
    r = requests.put(f"{BASE_URL}/api/auth/profile", headers=auth_headers, json={"harvest_age_threshold": 3.5}, timeout=20)
    assert r.status_code == 200
    assert _get_me(auth_headers)["harvest_age_threshold"] == 3.5


def test_update_profile_rejects_out_of_range(auth_headers):
    r = requests.put(f"{BASE_URL}/api/auth/profile", headers=auth_headers, json={"harvest_age_threshold": 7.0}, timeout=20)
    assert r.status_code == 400, r.text


def test_update_profile_accepts_2_0_and_6_5(auth_headers):
    for v in (2.0, 6.5):
        r = requests.put(f"{BASE_URL}/api/auth/profile", headers=auth_headers, json={"harvest_age_threshold": v}, timeout=20)
        assert r.status_code == 200
        assert _get_me(auth_headers)["harvest_age_threshold"] == v
    # restore to default
    requests.put(f"{BASE_URL}/api/auth/profile", headers=auth_headers, json={"harvest_age_threshold": 3.5}, timeout=20)


def test_scans_recompute_with_threshold(auth_headers):
    # Set threshold to 5.5 and verify scans adapt
    requests.put(f"{BASE_URL}/api/auth/profile", headers=auth_headers, json={"harvest_age_threshold": 5.5}, timeout=20)
    r = requests.get(f"{BASE_URL}/api/scans", headers=auth_headers, timeout=20)
    assert r.status_code == 200, r.text
    scans = r.json()
    assert isinstance(scans, list)
    for s in scans:
        assert "harvest_age_threshold" in s
        assert s["harvest_age_threshold"] == 5.5
        age = s.get("deer_age")
        rec = s.get("recommendation")
        rec_status = s.get("recommendation_status")
        if age is not None and rec_status == "age_based":
            if age >= 5.5:
                assert rec == "HARVEST", f"age {age} expected HARVEST got {rec}"
            else:
                assert rec == "PASS", f"age {age} expected PASS got {rec}"
    # restore
    requests.put(f"{BASE_URL}/api/auth/profile", headers=auth_headers, json={"harvest_age_threshold": 3.5}, timeout=20)


def test_scan_detail_and_stats_include_threshold(auth_headers):
    r = requests.get(f"{BASE_URL}/api/scans", headers=auth_headers, timeout=20)
    scans = r.json()
    if not scans:
        pytest.skip("no scans")
    sid = scans[0]["id"]
    requests.put(f"{BASE_URL}/api/auth/profile", headers=auth_headers, json={"harvest_age_threshold": 4.5}, timeout=20)
    r = requests.get(f"{BASE_URL}/api/scans/{sid}", headers=auth_headers, timeout=20)
    assert r.status_code == 200
    assert r.json()["harvest_age_threshold"] == 4.5
    r2 = requests.get(f"{BASE_URL}/api/scans/stats/summary", headers=auth_headers, timeout=20)
    assert r2.status_code == 200
    # restore
    requests.put(f"{BASE_URL}/api/auth/profile", headers=auth_headers, json={"harvest_age_threshold": 3.5}, timeout=20)
