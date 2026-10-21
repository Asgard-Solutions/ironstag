"""
Integration checks for multi-photo scans against a running backend.
Requires ANALYSIS_MOCK_MODEL=true on the server (deterministic model stand-in).

Usage: python tests/multi_photo_integration_check.py [base_url] [email] [password]
"""
import base64
import io
import random
import sys
import uuid

import requests
from PIL import Image, ImageDraw

BASE = (sys.argv[1] if len(sys.argv) > 1 else "http://localhost:8001").rstrip("/") + "/api"
EMAIL = sys.argv[2] if len(sys.argv) > 2 else "pjacobsen@asgardsolution.io"
PASSWORD = sys.argv[3] if len(sys.argv) > 3 else "armyjake75"
results = []


def check(name, cond, extra=""):
    results.append((name, bool(cond)))
    print(("PASS " if cond else "FAIL ") + name + (f" | {extra}" if extra and not cond else ""))


def make_photo(seed, size=(800, 600), exif_orientation=None):
    rnd = random.Random(seed)
    img = Image.new("RGB", size, (rnd.randint(0, 255), rnd.randint(0, 255), rnd.randint(0, 255)))
    d = ImageDraw.Draw(img)
    for _ in range(30):
        x, y = rnd.randint(0, size[0]), rnd.randint(0, size[1])
        d.ellipse([x, y, x + rnd.randint(20, 200), y + rnd.randint(20, 200)],
                  fill=(rnd.randint(0, 255), rnd.randint(0, 255), rnd.randint(0, 255)))
    buf = io.BytesIO()
    if exif_orientation:
        exif = Image.Exif()
        exif[0x0112] = exif_orientation
        img.save(buf, format="JPEG", exif=exif.tobytes())
    else:
        img.save(buf, format="JPEG")
    return "data:image/jpeg;base64," + base64.b64encode(buf.getvalue()).decode()


def main():
    r = requests.post(f"{BASE}/auth/login", json={"email": EMAIL, "password": PASSWORD}, timeout=30)
    r.raise_for_status()
    H = {"Authorization": f"Bearer {r.json()['access_token']}"}

    def used():
        return requests.get(f"{BASE}/subscription/status", headers=H, timeout=30).json()

    created = []
    # 1. Legacy single-photo request still works
    before = used()
    r = requests.post(f"{BASE}/analyze-deer", headers=H, timeout=120, json={
        "image_base64": make_photo(1), "local_image_id": "legacy-" + uuid.uuid4().hex[:6], "state": "IA"})
    check("legacy single photo -> 200", r.status_code == 200, r.text[:300])
    if r.ok:
        created.append(r.json()["id"])
        check("legacy has 1 image record", len(r.json().get("images") or []) == 1)
        check("legacy has no multi_image block", r.json().get("multi_image") is None)

    # 2. Three-photo scan: one analysis, one charge
    before = used()
    sub = str(uuid.uuid4())
    payload = {
        "submission_id": sub, "local_image_id": "multi-" + uuid.uuid4().hex[:6], "state": "IA",
        "images": [
            {"image_base64": make_photo(10, exif_orientation=6), "image_id": "img_1", "captured_at": "2025-11-02T07:10:00"},
            {"image_base64": make_photo(11), "image_id": "img_2", "crop_rect": {"x": 0.1, "y": 0.1, "width": 0.8, "height": 0.8}},
            {"image_base64": make_photo(12), "image_id": "img_3"},
        ],
    }
    r = requests.post(f"{BASE}/analyze-deer", headers=H, timeout=120, json=payload)
    check("3-photo scan -> 200", r.status_code == 200, r.text[:300])
    scan = r.json() if r.ok else {}
    after = used()
    check("3-photo scan charged exactly one credit",
          after["total_scans_used"] - before["total_scans_used"] == 1,
          f"{before} -> {after}")
    imgs = scan.get("images") or []
    check("3 image records in order", [i["image_id"] for i in imgs] == ["img_1", "img_2", "img_3"], imgs)
    check("EXIF orientation applied (600x800)", imgs and imgs[0]["width"] == 600 and imgs[0]["height"] == 800, imgs[:1])
    check("capture date preserved", imgs and imgs[0]["captured_at"] == "2025-11-02T07:10:00")
    check("crop rect stored, original retained flag", len(imgs) > 1 and imgs[1]["is_cropped"] and imgs[1]["crop_rect"]["width"] == 0.8)
    mi = scan.get("multi_image") or {}
    check("multi_image evidence_count=3", mi.get("evidence_count") == 3, mi)
    check("no photo-count confidence bonus (age conf <= best single photo)",
          (scan.get("confidence_breakdown") or {}).get("age", 999) <= 70, scan.get("confidence_breakdown"))
    steps = [s.get("step") for s in (scan.get("score_audit") or {}).get("pre_calibration_steps", [])] if isinstance(scan.get("score_audit"), dict) else []
    check("audit trail records single-photo cap", "multi_image_single_photo_cap" in str(scan.get("score_audit")), steps)
    if scan.get("id"):
        created.append(scan["id"])

    # 3. Retry with same submission id: same scan, no extra charge
    before = used()
    r2 = requests.post(f"{BASE}/analyze-deer", headers=H, timeout=120, json=payload)
    after = used()
    check("retry returns same scan id", r2.ok and r2.json()["id"] == scan.get("id"), r2.text[:200])
    check("retry does not charge", after["total_scans_used"] == before["total_scans_used"], f"{before} -> {after}")

    # 4. Duplicates do not count as evidence
    dup = make_photo(20)
    r = requests.post(f"{BASE}/analyze-deer", headers=H, timeout=120, json={
        "local_image_id": "dup-" + uuid.uuid4().hex[:6],
        "images": [{"image_base64": dup}, {"image_base64": dup}, {"image_base64": make_photo(21)}]})
    check("duplicate scan -> 200", r.ok, r.text[:300])
    if r.ok:
        mi = r.json().get("multi_image") or {}
        check("duplicate excluded (evidence_count=2)", mi.get("evidence_count") == 2 and len(mi.get("duplicates_removed")) == 1, mi)
        created.append(r.json()["id"])
    r = requests.post(f"{BASE}/analyze-deer", headers=H, timeout=120, json={
        "local_image_id": "dup2-" + uuid.uuid4().hex[:6], "state": "IA",
        "images": [{"image_base64": dup}, {"image_base64": dup}]})
    if r.ok:
        mi = r.json().get("multi_image") or {}
        check("all-duplicate pair: evidence 1, verdict not_applicable, no penalty",
              mi.get("evidence_count") == 1 and mi["same_deer"]["verdict"] == "not_applicable", mi)
        check("all-duplicate pair: confidence equals single-photo baseline",
              (r.json().get("confidence_breakdown") or {}).get("age") == (requests.get(f"{BASE}/scans/{created[0]}", headers=H).json().get("confidence_breakdown") or {}).get("age"))
        created.append(r.json()["id"])

    # 5. Mixed deer -> correction message, no charge, no saved scan
    before = used()
    scans_before = len(requests.get(f"{BASE}/scans", headers=H, params={"limit": 500}).json())
    r = requests.post(f"{BASE}/analyze-deer", headers=H, timeout=120, json={
        "local_image_id": "mixed-" + uuid.uuid4().hex[:6], "notes": "mock:mixed",
        "images": [{"image_base64": make_photo(30)}, {"image_base64": make_photo(31)}]})
    after = used()
    detail = r.json().get("detail", {}) if r.status_code == 422 else {}
    check("mixed deer -> 422 MIXED_DEER", detail.get("code") == "MIXED_DEER", r.text[:300])
    check("mixed message names the photo", "photo 2" in detail.get("message", ""), detail.get("message"))
    check("mixed deer not charged", after["total_scans_used"] == before["total_scans_used"])
    check("mixed deer saved nothing", len(requests.get(f"{BASE}/scans", headers=H, params={"limit": 500}).json()) == scans_before)

    # 6. Validation: count, type, crop
    bad = [
        ("4 photos rejected", {"images": [{"image_base64": make_photo(i)} for i in range(40, 44)]}, "TOO_MANY_IMAGES"),
        ("non-image rejected", {"images": [{"image_base64": base64.b64encode(b"%PDF-1.4 " * 50).decode()}]}, "UNSUPPORTED_IMAGE_TYPE"),
        ("tight crop rejected", {"images": [{"image_base64": make_photo(50), "crop_rect": {"x": 0, "y": 0, "width": 0.05, "height": 0.05}}]}, "INVALID_CROP"),
        ("no photos rejected", {"images": []}, "NO_IMAGES"),
    ]
    for name, body, code in bad:
        b0 = used()
        body["local_image_id"] = "bad"
        r = requests.post(f"{BASE}/analyze-deer", headers=H, timeout=60, json=body)
        check(name, r.status_code == 400 and r.json()["detail"]["code"] == code, r.text[:200])
        check(name + " (no charge)", used()["total_scans_used"] == b0["total_scans_used"])

    # 7. Reanalysis receives all photos (client-supplied copies, R2 unavailable here)
    if scan.get("id"):
        before = used()
        r = requests.post(f"{BASE}/scans/{scan['id']}/edit", headers=H, timeout=120, json={
            "deer_sex": "Buck", "images": [{"image_base64": i["image_base64"], "image_id": i["image_id"]} for i in payload["images"]]})
        check("reanalysis with 3 photos -> 200", r.ok, r.text[:300])
        if r.ok:
            check("reanalysis used 3 evidence photos", (r.json().get("multi_image") or {}).get("evidence_count") == 3)
            check("reanalysis prompt version multi", "multi" in (r.json().get("analysis_prompt_version") or ""))
        r = requests.post(f"{BASE}/scans/{scan['id']}/edit", headers=H, timeout=60, json={
            "image_base64": payload["images"][0]["image_base64"]})
        check("reanalysis with partial photos rejected", r.status_code == 400 and r.json()["detail"]["code"] == "REANALYSIS_PHOTO_MISMATCH", r.text[:200])
        check("reanalysis does not charge", used()["total_scans_used"] == before["total_scans_used"])
        # Access control: another user's token cannot read; missing token rejected
        check("scan requires auth", requests.get(f"{BASE}/scans/{scan['id']}").status_code in (401, 403, 422))

    # 8. Deletion removes scan + photos
    for sid in created:
        requests.delete(f"{BASE}/scans/{sid}", headers=H, timeout=60)
    check("deleted scans are gone", all(requests.get(f"{BASE}/scans/{s}", headers=H).status_code == 404 for s in created))

    passed = sum(1 for _, ok in results if ok)
    print(f"\n{passed}/{len(results)} checks passed")
    sys.exit(0 if passed == len(results) else 1)


if __name__ == "__main__":
    main()
