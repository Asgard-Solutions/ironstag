# 🦌 Iron Stag

**AI-Powered Deer Analysis for Hunters**

Iron Stag is a mobile application that uses GPT-4 Vision to analyze deer photos, estimate age, and provide harvest recommendations. Built with Expo (React Native) and FastAPI.

![Platform](https://img.shields.io/badge/Platform-iOS%20%7C%20Android-blue)
![Expo SDK](https://img.shields.io/badge/Expo%20SDK-54-000020)
![Python](https://img.shields.io/badge/Python-3.11+-3776AB)
![License](https://img.shields.io/badge/License-Private-red)

---

## 📱 Features

### Core Features
- **AI Deer Analysis** - Upload or capture photos for instant age estimation and harvest recommendations
- **Scan History** - Track all your analyses with detailed results
- **Confidence Calibration** - Region-aware confidence scoring that's honest about uncertainty
- **User Profiles** - Set your home state for calibrated regional analysis

### Subscription Tiers
| Tier | Price | Scans |
|------|-------|-------|
| **Tracker** (Free) | Free | 3 scans |
| **Master Stag** | $9.99/month or $89.99/year | Unlimited |

### Platform Support
- iOS 13+
- Android 10+ (API 29+)
- Android 15 Edge-to-Edge compliant
- Android 16 Large Screen / Foldable ready

---

## 🏗️ Architecture

```
ironstag/
├── backend/                 # FastAPI Backend
│   ├── server.py           # Main API server
│   ├── calibration.py      # Phase 1: Heuristic calibration
│   ├── region_calibration.py # Region-aware calibration
│   ├── calibration_jobs.py # Phase 2: Empirical calibration
│   ├── adaptive_calibration.py # Phase 3: Drift detection
│   ├── config/
│   │   └── season_mapping.json # Deer phenology by region
│   └── cli/
│       └── phase3_admin.py # Phase 3 CLI tool
│
├── frontend/               # Expo React Native App
│   ├── app/               # Expo Router screens
│   │   ├── (tabs)/        # Tab navigation
│   │   │   ├── index.tsx  # Dashboard
│   │   │   ├── scan.tsx   # Scan interface
│   │   │   ├── history.tsx # Scan history
│   │   │   ├── learn.tsx  # Educational content
│   │   │   └── profile.tsx # User profile
│   │   └── scan-result/   # Result screens
│   ├── components/        # Reusable components
│   ├── services/          # API services
│   ├── stores/            # Zustand state management
│   └── plugins/           # Expo config plugins
│
└── docs/                  # Documentation
```

---

## 🔧 Tech Stack

### Frontend
- **Framework**: Expo SDK 54 with Expo Router
- **Language**: TypeScript
- **State Management**: Zustand
- **UI**: React Native components + custom styling
- **Subscriptions**: RevenueCat

### Backend
- **Framework**: FastAPI (Python 3.11+)
- **Database**: PostgreSQL (Neon)
- **AI**: OpenAI GPT-4 Vision
- **Auth**: JWT tokens
- **Payments**: Stripe (web checkout)

---

## 🚀 Getting Started

### Prerequisites
- Node.js 18+
- Python 3.11+
- PostgreSQL database
- OpenAI API key

### Backend Setup

```bash
cd backend

# Create virtual environment
python -m venv venv
source venv/bin/activate  # or `venv\Scripts\activate` on Windows

# Install dependencies
pip install -r requirements.txt

# Configure environment
cp .env.example .env
# Edit .env with your credentials

# Run server
uvicorn server:app --reload --port 8001
```

### Frontend Setup

```bash
cd frontend

# Install dependencies
yarn install

# Start Expo development server
yarn start

# Or run on specific platform
yarn ios
yarn android
```

---

## ⚙️ Environment Variables

### Backend (`backend/.env`)

Local development only. The deployed Railway service ignores this file and uses Railway Variables instead. Start from `backend/env.example` when setting up a new local env file.

```bash
# Database
DATABASE_URL=postgresql://user:pass@host/db?sslmode=require

# Authentication
JWT_SECRET=your-secret-key

# OpenAI
OPENAI_API_KEY=sk-...

# Stripe
STRIPE_SECRET_KEY=sk_...
STRIPE_WEBHOOK_SECRET=whsec_...

# RevenueCat
REVENUECAT_SECRET_KEY=...

# Email (Microsoft Graph)
MICROSOFT_GRAPH_CLIENT_ID=...
MICROSOFT_GRAPH_CLIENT_SECRET=...
MICROSOFT_GRAPH_TENANT_ID=...
MS_GRAPH_SENDER_EMAIL=...

# Calibration (Phase 2)
CALIBRATION_CURVES_ENABLED=true

# Adaptive Calibration (Phase 3) - Ship Dark
CALIBRATION_ADAPTIVE_ENABLED=false
```

### Frontend (`frontend/.env`)

For local development, point this to your local backend. If you test on a physical device, replace `localhost` with your machine's LAN IP. Start from `frontend/env.example` when setting up a new local env file.

```bash
EXPO_PUBLIC_API_BASE_URL=http://localhost:8001
EXPO_PUBLIC_BACKEND_URL=http://localhost:8001
EXPO_PUBLIC_REVENUECAT_IOS_API_KEY=...
EXPO_PUBLIC_REVENUECAT_ANDROID_API_KEY=...
```

---

## 🎯 Confidence Calibration System

Iron Stag features a sophisticated 3-phase confidence calibration system that ensures AI confidence scores are **honest and actionable**.

### Phase 1: Heuristic Calibration
- Region-aware confidence adjustments
- Age-specific difficulty factors
- Uncertainty gating for low-confidence predictions

### Phase 2: Empirical Calibration
- Data-driven calibration curves built from labeled outcomes
- Per-region and global curve support
- Admin endpoints for curve management

### Phase 3: Adaptive Monitoring (Ship Dark)
- Continuous drift detection
- Region maturity scoring
- Automated recommendation generation
- **Advisory only** - no automatic changes

### 🟢 When to Enable Phase 3 (Admin Guidance)

Phase 3 is **disabled by default** and should be enabled manually by an admin.  
It is not tied to releases — it is tied to **data readiness**.

#### ✅ Enable Phase 3 When:

- You have accumulated **meaningful labeled data** in `scan_labels`
  - ~100+ labeled scans globally → early signal
  - 300–500+ labeled scans → reliable signal
  - Region-level labels → strongest value
- You are seeing questions or inconsistencies around confidence or age estimates
- You are preparing to:
  - Rebuild calibration curves (Phase 2)
  - Adjust uncertainty thresholds
  - Evaluate whether retraining is justified
- You want **evidence-based insight** before making model changes

#### ❌ Do NOT Enable Phase 3 When:

- Immediately at public launch
- You have little or no labeled data
- You are still validating basic product-market fit
- You are not prepared to review and act on admin-only recommendations

#### 🔐 How Phase 3 Is Used

- Phase 3 is **advisory only**
- It **never** changes predictions, confidence, or calibration automatically
- It produces **signals and recommendations**, not actions
- A quiet Phase 3 system indicates healthy, stable confidence

#### ▶️ Enabling Phase 3

When ready, enable via environment variable:

```bash
CALIBRATION_ADAPTIVE_ENABLED=true
```

Restart the backend and use the Phase 3 CLI tool to run analysis jobs in **dry-run mode first**.

> **One-Line Rule of Thumb:**  
> Enable Phase 3 when you want **evidence** — not curiosity — to drive model decisions.

### Phase 3 CLI Tool

```bash
cd backend

# Check system status
python cli/phase3_admin.py status

# View drift events
python cli/phase3_admin.py drift

# Run all jobs (dry run)
python cli/phase3_admin.py run-all

# Run and save results
python cli/phase3_admin.py run-all --execute
```

---

## 📡 API Endpoints

### Authentication
| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/auth/register` | Register new user |
| POST | `/api/auth/login` | Login |
| GET | `/api/auth/me` | Get current user |
| PUT | `/api/auth/profile` | Update profile |

### Scans
| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/analyze` | Analyze deer photo |
| GET | `/api/scans` | Get user's scan history |
| GET | `/api/scans/{id}` | Get single scan |
| GET | `/api/scans/stats` | Get scan statistics |

### Subscriptions
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/subscription/status` | Get subscription status |
| POST | `/api/subscription/checkout` | Create Stripe checkout |
| POST | `/api/subscription/webhook` | Stripe webhook |

### Admin (Calibration)
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/admin/calibration/status` | Calibration status |
| GET | `/api/admin/calibration/curves` | List curves |
| POST | `/api/admin/calibration/build-curves` | Build curves |
| POST | `/api/admin/calibration/phase3/run-drift` | Run drift detection |

---

## 📱 Building for Production

### iOS

```bash
cd frontend

# Build for App Store
eas build --platform ios --profile production

# Submit to App Store
eas submit --platform ios
```

### Android

```bash
cd frontend

# Build AAB for Play Store
eas build --platform android --profile production

# Submit to Play Store
eas submit --platform android
```

---

## 🔐 Security

- JWT-based authentication with secure token handling
- Password hashing with bcrypt
- Rate limiting on sensitive endpoints
- Secure environment variable management
- HTTPS enforced in production

---

## 📄 License

Private - © 2025 Asgard Solutions. All rights reserved.

---

## 👥 Team

- **Development**: Asgard Solutions
- **Contact**: pjacobsen@asgardsolution.io

---

## 🗺️ Roadmap

- [x] Phase 1: Heuristic Calibration
- [x] Phase 2: Empirical Calibration
- [x] Phase 3: Adaptive Monitoring
- [x] Phase 3 CLI Tool
- [ ] Admin Dashboard UI
- [ ] Apple Sign-In
- [ ] Social Sharing
- [ ] Offline Mode
