# Iron Stag v1.8.0 Release Notes
**Version 1.8.0 (Build 105)**  
July 2026

## Featured
**iOS, Android**
- Major AI Accuracy Upgrade
- Security Hardening
- Android 16 Support

---

## 🧠 AI Age Estimation — Major Accuracy Upgrade

This release brings the biggest accuracy improvement to Iron Stag's deer aging engine since launch. Every analysis now benefits from deeper, species-specific intelligence.

### New Species-Specific Aging Rubrics
- **Doe Age Rubric** — Iron Stag now uses a dedicated body-profile rubric for aging does at every age class (0.5 through 5.5+), covering chest depth, belly line, backline, leg-to-body ratio, and face shape. Previously, does received only generic "age from body profile" guidance — now they get the same level of precision as bucks.
- **Mule Deer Age Rubric** — A new mule deer-specific aging rubric covers ear-to-face ratio changes, fork depth, and body proportion differences across age classes. Includes guidance to avoid the common mistake of confusing large mule deer ears with youth.
- **Fawn Identification** — Explicit fawn (0.5 year) identification cues have been added, covering spotted coats, proportionally long legs, undeveloped chest, and seasonal spot-fading behavior for both species.

### Enhanced Image Analysis
- **High-Resolution Processing** — The AI now analyzes your photos at full resolution instead of a potentially downsampled version. This means finer body details like belly sag, face length, and chest depth are more accurately assessed, especially in trail camera photos.
- **Larger Response Capacity** — Increased the AI's response capacity from 1,400 to 2,000 tokens, preventing truncation of detailed analysis results (age evidence, cue checklists, and reasoning).

### Smarter Multi-Pass Consensus
- **Diverse Perspectives** — When Iron Stag runs multiple analysis passes on borderline cases, follow-up passes now use varied parameters to produce genuinely different assessments. Previously, all passes were nearly identical.
- **Alternate Age Support** — The consensus engine now considers each pass's alternate age suggestion. If one pass says "3.5 primary, 4.5 alternate" and other passes say "4.5 primary," the alternate agreement strengthens the consensus and reduces confidence penalties.

### Confidence Transparency
- **Confidence Reasoning** — The AI now explains *why* it assigned a specific confidence level for each scan, referencing visible cues, image quality issues, and perspective limitations. This helps you understand what drives the estimate.

### Prompt Version
- Analysis prompt upgraded from `age-v5-structured-checklist` to `age-v6-species-rubrics`

---

## 🔒 Security Hardening (Phases 1–4)

A comprehensive security review was completed across the entire backend.

### Secrets & Authentication
- **JWT Secret Enforcement** — Backend now strictly requires `JWT_SECRET` from environment variables and refuses to start with a fallback. Eliminates any risk of running with a default secret.
- **Admin Secret Enforcement** — All `/admin/*` and `/calibration/*` endpoints now require the `x-admin-secret` header via FastAPI dependency injection. `ADMIN_SECRET` is required in production.
- **RevenueCat Webhook Hardening** — Webhook validation now fails closed if `REVENUECAT_WEBHOOK_SECRET` is not configured.

### Rate Limiting
- **Auth Endpoint Protection** — Login, registration, and password reset endpoints are now rate-limited (10 attempts per 15-minute window per IP) to prevent brute force attacks.

### CORS & Network
- **CORS Configuration** — Removed `allow_credentials=True` since the app uses Bearer token authentication, reducing attack surface.
- **API Timeout** — Frontend Axios client now has a configured timeout to prevent hanging requests.

### Secret Exposure Prevention
- **RevenueCat Keys Cleaned** — Secret (`sk_`) RevenueCat keys have been removed from `eas.json` and frontend `.env`. Only public SDK keys (`appl_`/`goog_`) are bundled in client builds.

---

## 📱 Android 16 (API 36) Support

- **Google Play Compliance** — Updated `targetSdkVersion` and `compileSdkVersion` from 35 to 36, and `buildToolsVersion` to 36.0.0. This meets Google Play's requirement for apps to target Android 16 by August 30, 2026.

---

## 🧹 Code Quality & TypeScript Fixes

- **11 TypeScript Errors Fixed** — Resolved compilation errors across 7 frontend files, including updated `IAPService.ts` to align with `expo-iap` v3.4.13 typed API.
- **26 Unused Imports Removed** — Cleaned unused imports and variables across 13 frontend files.
- **Dependency Vulnerabilities** — Resolved `npm audit` vulnerabilities.

---

## 🔧 Technical Details

### Backend Changes
- `server.py`: Admin auth dependency injection, rate limiting, prompt v6 with species rubrics, high-res image detail, increased token limits, confidence_reasoning field
- `analysis_consensus.py`: Alternate age support in consensus merging, confidence penalty reduction from supporting alternates
- `region_calibration.py`: No changes (stable)
- `season_derivation.py`: No changes (stable)

### Frontend Changes
- `app.json`: Version 1.8.0, build 105, Android API 36 target
- `eas.json`: Removed secret RevenueCat keys
- `services/IAPService.ts`: Updated for expo-iap v3.4.13 compatibility
- 13 files: Lint cleanup (unused imports/variables)

### New AI Features Summary
| Feature | Impact |
|---------|--------|
| Doe age rubric | ~50% of analyses now have dedicated aging guidance |
| Mule deer rubric | Species-appropriate aging for non-whitetail scans |
| Fawn identification | Accurate 0.5-year classification |
| High-res analysis | Better fine detail recognition |
| Larger token limit | Prevents truncated responses |
| Varied consensus temp | More meaningful multi-pass analysis |
| Alternate age in consensus | Smarter age agreement detection |
| Confidence reasoning | Transparent confidence explanations |

---

## 📋 Requirements

- **iOS**: 15.1 or later
- **Android**: 7.0 (API level 24) or later, targeting Android 16 (API 36)
- Internet connection for analysis
- Camera access for deer scanning
- Location access for regional calibration (optional)

---

## 🔄 Update Information

This is a **recommended update** for all users. The AI accuracy improvements apply automatically to all new scans. Existing scan data is unchanged.

### What to Expect:
- New scans use the upgraded `age-v6-species-rubrics` prompt
- Existing scans retain their original analysis
- Premium subscriptions continue uninterrupted
- All existing tags, favorites, and B&C scores are preserved

---

## 💬 Support & Feedback

Found a bug or have suggestions? We're here to help:

- **Email**: support@asgardsolution.io

---

## 🙏 Thank You

This release represents a major step forward in Iron Stag's aging accuracy. The species-specific rubrics and smarter consensus engine were built with direct feedback from our hunting community.

**Happy Hunting!** 🦌

*The Iron Stag Team*

---

## Version History
- **v1.8.0** (July 2026) - Major AI accuracy upgrade, security hardening, Android 16 support
- **v1.6.1** (April 2026) - Bug fixes and security improvements
- **v1.6.0** (April 2026) - Boone & Crockett Scoring, Learn Section, Enhanced UI
- **v1.2.0** (January 2026) - Cloud sync, offline scanning, doe aging improvements
