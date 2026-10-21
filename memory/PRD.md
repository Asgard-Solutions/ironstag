# Iron Stag – PRD (living)

## Product
Expo (React Native) + FastAPI + Postgres (Neon) deer-aging app. Users photograph a deer and get an AI age estimate, a HARVEST/PASS call, calibrated confidence and a score audit trail.

## Done (earlier sessions)
- Security hardening: JWT secret, CORS, admin auth, rate limits, RevenueCat public keys only
- TypeScript/IAP fixes, lint cleanup
- Age vs recommendation confidence split; `score_audit` trail

## Done (this session) – Multi-photo scans (1–3 photos, same deer, same encounter)
- `/api/analyze-deer` takes `images[]` (each with image_base64, image_id img_N, local_image_id, captured_at, crop_rect) and `submission_id`. The legacy `image_base64` still works.
- `backend/multi_image.py` handles validation (JPEG/PNG/WebP, 8 MB, ≥200 px, ≤3 photos), EXIF orientation, capture date, dimensions, server-side crop (original kept), exact and near-duplicate removal (sha256 + dHash), and model images bounded to 2048 px at high detail.
- One model request with labelled photo IDs. Per-photo cues are reconciled into one estimate, with a same-deer verdict and a contradictions list.
- Guards (recorded in score_audit):
  - age confidence ≤ the best single-photo confidence (no bonus for photo count)
  - −10 for contradictions, an uncertain identity, or capture times spanning more than 24 h
  - duplicates are excluded from evidence
- A "different deer" verdict returns 422 MIXED_DEER with a correction message. Nothing is saved and nothing is charged.
- New tables: `scan_images` and `scan_submissions` (idempotency ledger). Scan + image rows + credit charge + ledger are written in one DB transaction. The conditional credit decrement prevents overdraw. Failures delete uploaded R2 objects and release the submission.
- Reanalysis (`/scans/{id}/edit`) needs every photo: client copies via `images`, or `reanalyze: true` to load from R2. Stored crops are re-applied. Reanalysis never charges.
- Deleting a scan, a batch of scans, all scans or the account removes all photos (R2 + rows).
- Frontend:
  - Scan screen: PhotoTray (add / remove / reorder / select), CropModal (drag handles, original kept), guidance text, bounded JPEG re-encode (expo-image-manipulator)
  - Result screen: photo strip and MultiPhotoEvidence card
  - Offline queue carries images + submission_id
- Dev mock: `ANALYSIS_MOCK_MODEL=true` in backend/.env (OpenAI key invalid here). Notes "mock:mixed" / "mock:notdeer" trigger the rejection paths. **Must be false or removed in production.**
- Tests: `backend/tests/multi_photo_integration_check.py` (37/37), pytest 119/119, frontend flow via testing agent.

## Backlog
- P0 RevenueCat "No subscription packages available"
- P1 valid OpenAI key + R2 credentials in dev; benchmark multi-photo vs single-photo accuracy before making accuracy claims
- P1 Tags filtering UI in History
- P2 scalability (caching, indexes); Phase 2 calibration (trigger: "Let's inspect label distributions")
- P3 admin dashboard, backfill old scans to R2
