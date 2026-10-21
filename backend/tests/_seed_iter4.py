"""Seed: ensure at least one scan on multiphoto user has raw_response.confidence_reasoning
Also set tags on 3 scans to new 'Big 8'/'Creek Stand' casing + leave one old lowercase 'big 8' intact to verify case-insensitive filter.
"""
import os, requests, json

BASE = "https://date-persist-deploy.preview.emergentagent.com"
EMAIL = "multiphoto.test@ironstag.dev"
PWD = "MultiPhoto#2026"

r = requests.post(f"{BASE}/api/auth/login", json={"email": EMAIL, "password": PWD})
tok = r.json()["access_token"]
H = {"Authorization": f"Bearer {tok}", "Content-Type": "application/json"}

scans = requests.get(f"{BASE}/api/scans", headers=H).json()
print(f"Found {len(scans)} scans")
for s in scans[:5]:
    print(f" - {s['id'][:8]} tags={s.get('tags')} cr={bool(s.get('confidence_reasoning'))}")

# Set specific tags: first scan "Big 8", second "Creek Stand", third "big 8" lowercase (legacy)
if len(scans) >= 3:
    tag_plan = [
        (scans[0]["id"], ["Big 8"]),
        (scans[1]["id"], ["Creek Stand", "Big 8"]),
        (scans[2]["id"], ["big 8"]),  # legacy lowercase to verify case-insensitive filter
    ]
    for sid, tags in tag_plan:
        r = requests.post(f"{BASE}/api/scans/{sid}/tags", headers=H, json={"tags": tags})
        print(f"Set tags on {sid[:8]} -> {r.status_code} {r.json().get('tags')}")

# Verify tags/all
r = requests.get(f"{BASE}/api/scans/tags/all", headers=H)
print("all tags:", r.json())

# Count scans with confidence_reasoning
cr_scans = [s for s in requests.get(f"{BASE}/api/scans", headers=H).json() if s.get("confidence_reasoning")]
print(f"scans with confidence_reasoning: {len(cr_scans)}")
if cr_scans:
    print(" first:", cr_scans[0]["id"], cr_scans[0]["confidence_reasoning"][:80])
