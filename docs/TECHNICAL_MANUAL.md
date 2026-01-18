# Iron Stag - Technical Manual

**Version 1.0.0**  
**Last Updated: January 2026**

---

## Table of Contents

1. [System Architecture](#1-system-architecture)
2. [Technology Stack](#2-technology-stack)
3. [Backend API Reference](#3-backend-api-reference)
4. [Database Schema](#4-database-schema)
5. [Authentication System](#5-authentication-system)
6. [AI Integration](#6-ai-integration)
7. [Payment & Subscription System](#7-payment--subscription-system)
8. [Frontend Architecture](#8-frontend-architecture)
9. [State Management](#9-state-management)
10. [Local Storage & Caching](#10-local-storage--caching)
11. [Build & Deployment](#11-build--deployment)
12. [Environment Configuration](#12-environment-configuration)
13. [Security Considerations](#13-security-considerations)
14. [Error Handling](#14-error-handling)
15. [Testing](#15-testing)
16. [Monitoring & Logging](#16-monitoring--logging)
17. [Troubleshooting Guide](#17-troubleshooting-guide)
18. [API Rate Limits](#18-api-rate-limits)
19. [Future Roadmap](#19-future-roadmap)

---

## 1. System Architecture

### High-Level Overview

```
┌─────────────────────────────────────────────────────────────────┐
│                        CLIENT LAYER                              │
├─────────────────────────────────────────────────────────────────┤
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐           │
│  │   iOS App    │  │ Android App  │  │   Web App    │           │
│  │  (Expo/RN)   │  │  (Expo/RN)   │  │  (Expo Web)  │           │
│  └──────────────┘  └──────────────┘  └──────────────┘           │
└─────────────────────────────────────────────────────────────────┘
                              │
                              │ HTTPS/REST
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                        API LAYER                                 │
├─────────────────────────────────────────────────────────────────┤
│  ┌──────────────────────────────────────────────────────────┐   │
│  │              FastAPI Backend (Python 3.11+)               │   │
│  │  ┌────────────┐ ┌────────────┐ ┌────────────────────┐    │   │
│  │  │    Auth    │ │   Scans    │ │   Subscriptions    │    │   │
│  │  │   Module   │ │   Module   │ │      Module        │    │   │
│  │  └────────────┘ └────────────┘ └────────────────────┘    │   │
│  └──────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────┘
                              │
              ┌───────────────┼───────────────┐
              │               │               │
              ▼               ▼               ▼
┌──────────────────┐ ┌──────────────┐ ┌──────────────────┐
│    PostgreSQL    │ │   OpenAI     │ │   RevenueCat     │
│    (Neon DB)     │ │   GPT-4o     │ │   (Payments)     │
│                  │ │   Vision     │ │                  │
└──────────────────┘ └──────────────┘ └──────────────────┘
```

### Request Flow

```
User Action → Expo App → API Gateway → FastAPI → Service Layer → Database/External APIs
     ↑                                                                      │
     └──────────────────────── Response ────────────────────────────────────┘
```

---

## 2. Technology Stack

### Frontend

| Technology | Version | Purpose |
|------------|---------|----------|
| React Native | 0.81.x | Cross-platform mobile framework |
| Expo | SDK 54 | Development and build tooling |
| Expo Router | 4.x | File-based navigation |
| TypeScript | 5.x | Type safety |
| Zustand | 4.x | State management |
| Axios | 1.x | HTTP client |
| React Native Reanimated | 4.x | Animations |
| Expo Camera | 16.x | Camera access |
| Expo Image Picker | 16.x | Gallery access |
| Expo Secure Store | 14.x | Secure credential storage |
| Expo Local Authentication | 15.x | Biometric authentication (Face ID/Fingerprint) |
| Expo File System | 18.x | Local file management |
| react-native-purchases | 8.x | RevenueCat SDK |

### Backend

| Technology | Version | Purpose |
|------------|---------|----------|
| Python | 3.11+ | Runtime |
| FastAPI | 0.100+ | Web framework |
| SQLAlchemy | 2.x | ORM |
| databases | 0.9+ | Async database driver |
| asyncpg | 0.29+ | PostgreSQL async adapter |
| python-jose | 3.x | JWT handling |
| passlib | 1.7+ | Password hashing |
| bcrypt | 4.x | Bcrypt algorithm |
| openai | 1.x | GPT-4 Vision API |
| httpx | 0.27+ | Async HTTP client |
| python-dotenv | 1.x | Environment management |
| msal | 1.x | Microsoft Graph (email) |

### Database

| Technology | Purpose |
|------------|---------|
| PostgreSQL 15+ | Primary database |
| Neon | Serverless PostgreSQL hosting |

### External Services

| Service | Purpose |
|---------|---------|
| OpenAI GPT-4o Vision | AI deer analysis |
| RevenueCat | In-app purchase management |
| Microsoft Graph | Email delivery (password reset) |
| Expo EAS | Build and deployment |

---

## 3. Backend API Reference

### Base URL

```
Production: https://ironstag-production.up.railway.app/api
Local: http://localhost:8001/api
```

### Authentication Endpoints

#### POST /auth/register

Register a new user account.

**Request Body:**
```json
{
  "email": "user@example.com",
  "password": "securepassword",
  "first_name": "John",
  "last_name": "Doe",
  "username": "johndoe"
}
```

**Response (200):**
```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIs...",
  "token_type": "bearer",
  "user": {
    "id": "uuid-string",
    "email": "user@example.com",
    "name": "John Doe",
    "first_name": "John",
    "last_name": "Doe",
    "username": "johndoe",
    "subscription_tier": "tracker",
    "scans_remaining": 3,
    "total_scans_used": 0,
    "disclaimer_accepted": false
  }
}
```

**Error Responses:**
- `400`: Email or username already registered
- `422`: Validation error

---

#### POST /auth/login

Authenticate user with email/username and password.

**Request Body:**
```json
{
  "email": "user@example.com",  // or username
  "password": "securepassword"
}
```

**Response (200):**
```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIs...",
  "token_type": "bearer",
  "user": { ... }
}
```

**Error Responses:**
- `401`: Invalid credentials

---

#### POST /auth/apple

Authenticate via Sign in with Apple.

**Request Body:**
```json
{
  "identity_token": "apple_identity_token",
  "user_identifier": "apple_user_id",
  "email": "user@privaterelay.appleid.com",
  "full_name": {
    "given_name": "John",
    "family_name": "Doe"
  }
}
```

**Response (200):**
```json
{
  "access_token": "...",
  "token_type": "bearer",
  "user": { ... }
}
```

---

#### GET /auth/me

Get current authenticated user profile.

**Headers:**
```
Authorization: Bearer <access_token>
```

**Response (200):**
```json
{
  "id": "uuid",
  "email": "user@example.com",
  "name": "John Doe",
  "first_name": "John",
  "last_name": "Doe",
  "username": "johndoe",
  "subscription_tier": "tracker",
  "scans_remaining": 3,
  "total_scans_used": 0,
  "disclaimer_accepted": true
}
```

---

#### PUT /auth/profile

Update user profile.

**Headers:**
```
Authorization: Bearer <access_token>
```

**Request Body:**
```json
{
  "first_name": "John",
  "last_name": "Smith",
  "username": "johnsmith"
}
```

**Response (200):** Updated user object

---

#### DELETE /auth/account

Permanently delete user account and all data.

**Headers:**
```
Authorization: Bearer <access_token>
```

**Response (200):**
```json
{
  "message": "Account deleted successfully"
}
```

---

#### POST /auth/request-password-reset

Request password reset code via email.

**Request Body:**
```json
{
  "email": "user@example.com"
}
```

**Response (200):**
```json
{
  "message": "If email exists, reset code sent"
}
```

---

#### POST /auth/verify-password-reset

Verify reset code and set new password.

**Request Body:**
```json
{
  "email": "user@example.com",
  "code": "123456",
  "new_password": "newpassword123"
}
```

**Response (200):**
```json
{
  "message": "Password reset successful"
}
```

**Error Responses:**
- `400`: Invalid or expired code

---

#### POST /auth/accept-disclaimer

Accept the legal disclaimer.

**Headers:**
```
Authorization: Bearer <access_token>
```

**Request Body:**
```json
{
  "accepted": true
}
```

**Response (200):** Updated user object with `disclaimer_accepted: true`

---

### Scan Endpoints

#### POST /analyze-deer

Analyze a deer image using AI.

**Headers:**
```
Authorization: Bearer <access_token>
```

**Request Body:**
```json
{
  "image_base64": "data:image/jpeg;base64,/9j/4AAQ...",
  "local_image_id": "uuid-for-local-storage"
}
```

**Response (200):**
```json
{
  "id": "scan-uuid",
  "user_id": "user-uuid",
  "local_image_id": "local-uuid",
  "deer_age": 3.5,
  "deer_type": "Whitetail",
  "deer_sex": "Buck",
  "antler_points": 8,
  "antler_points_left": 4,
  "antler_points_right": 4,
  "body_condition": "Good",
  "confidence": 87,
  "recommendation": "HARVEST",
  "reasoning": "This buck appears to be 3.5 years old based on...",
  "created_at": "2026-01-16T12:00:00Z"
}
```

**Error Responses:**
- `400` (NOT_A_DEER): Image doesn't contain a Whitetail or Mule Deer
- `403` (FREE_LIMIT_REACHED): Free scan limit exceeded
- `401`: Not authenticated

---

#### GET /scans

Get user's scan history.

**Headers:**
```
Authorization: Bearer <access_token>
```

**Query Parameters:**
- `limit` (optional): Number of results (default: 100)
- `offset` (optional): Pagination offset (default: 0)

**Response (200):**
```json
[
  {
    "id": "scan-uuid",
    "deer_age": 3.5,
    "deer_type": "Whitetail",
    "deer_sex": "Buck",
    "antler_points": 8,
    "recommendation": "HARVEST",
    "created_at": "2026-01-16T12:00:00Z"
  },
  ...
]
```

---

#### GET /scans/stats/summary

Get scan statistics summary.

**Headers:**
```
Authorization: Bearer <access_token>
```

**Response (200):**
```json
{
  "total_scans": 15,
  "harvest_count": 8,
  "pass_count": 7
}
```

---

#### GET /scans/{scan_id}

Get a specific scan by ID.

**Response (200):** Full scan object

**Error Responses:**
- `404`: Scan not found

---

#### PUT /scans/{scan_id}

Update scan notes.

**Request Body:**
```json
{
  "notes": "Spotted near the creek on trail cam #3"
}
```

**Response (200):** Updated scan object

---

#### POST /scans/{scan_id}/edit

Edit scan details and re-run AI analysis.

**Request Body:**
```json
{
  "deer_sex": "Buck",
  "deer_type": "Whitetail",
  "antler_points_left": 5,
  "antler_points_right": 4,
  "image_base64": "data:image/jpeg;base64,..."  // optional
}
```

**Response (200):** Updated scan with new AI analysis

---

#### DELETE /scans/{scan_id}

Delete a specific scan.

**Response (200):**
```json
{
  "message": "Scan deleted"
}
```

---

#### DELETE /scans/all

Delete ALL scans for the current user.

**Response (200):**
```json
{
  "deleted_count": 15,
  "message": "Deleted all 15 scan(s)"
}
```

---

#### POST /scans/delete-by-local-ids

Delete scans by their local image IDs.

**Request Body:**
```json
{
  "local_image_ids": ["uuid1", "uuid2", "uuid3"]
}
```

**Response (200):**
```json
{
  "deleted_count": 3,
  "message": "Deleted 3 scan(s)"
}
```

---

### Subscription Endpoints

#### GET /subscription/status

Get user's subscription status.

**Response (200):**
```json
{
  "tier": "master_stag",
  "is_premium": true,
  "scans_remaining": -1,
  "cancel_at_period_end": false
}
```

---

#### GET /subscription/scan-eligibility

Check if user can perform a scan.

**Response (200):**
```json
{
  "can_scan": true,
  "reason": "premium",
  "scans_remaining": -1
}
```

**Response (403):**
```json
{
  "can_scan": false,
  "reason": "limit_reached",
  "scans_remaining": 0
}
```

---

#### POST /subscription/verify-revenuecat

Verify RevenueCat subscription status.

**Request Body:**
```json
{
  "app_user_id": "revenuecat_user_id"
}
```

**Response (200):**
```json
{
  "is_premium": true,
  "tier": "master_stag"
}
```

---

### Other Endpoints

#### GET /learn/content

Get educational content for the Learn section.

**Response (200):**
```json
{
  "sections": [
    {
      "title": "Aging Whitetail Deer",
      "content": "...",
      "category": "beginner"
    },
    ...
  ]
}
```

---

#### GET /health

Health check endpoint.

**Response (200):**
```json
{
  "status": "healthy",
  "database": "postgresql",
  "timestamp": "2026-01-16T12:00:00Z"
}
```

---

## 4. Database Schema

### Entity Relationship Diagram

```
┌─────────────────────────────────────────────────────────────┐
│                          users                               │
├─────────────────────────────────────────────────────────────┤
│ id (PK)              │ VARCHAR(36)  │ UUID                  │
│ email                │ VARCHAR(255) │ UNIQUE, NOT NULL      │
│ password             │ TEXT         │ NOT NULL (hashed)     │
│ name                 │ VARCHAR(255) │ Display name          │
│ first_name           │ VARCHAR(100) │                       │
│ last_name            │ VARCHAR(100) │                       │
│ username             │ VARCHAR(100) │ UNIQUE                │
│ created_at           │ DATETIME     │ DEFAULT NOW()         │
│ subscription_tier    │ VARCHAR(50)  │ DEFAULT 'tracker'     │
│ scans_remaining      │ INTEGER      │ DEFAULT 3             │
│ total_scans_used     │ INTEGER      │ DEFAULT 0             │
│ disclaimer_accepted  │ BOOLEAN      │ DEFAULT FALSE         │
│ disclaimer_accepted_at│ DATETIME    │ NULLABLE              │
│ stripe_customer_id   │ VARCHAR(100) │ NULLABLE              │
│ stripe_subscription_id│ VARCHAR(100)│ NULLABLE              │
│ subscription_cancel_at_period_end │ BOOLEAN │ DEFAULT FALSE │
│ revenuecat_id        │ VARCHAR(100) │ NULLABLE              │
│ subscription_expires_at │ DATETIME  │ NULLABLE              │
│ apple_user_id        │ VARCHAR(100) │ NULLABLE              │
└─────────────────────────────────────────────────────────────┘
                              │
                              │ 1:N
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                          scans                               │
├─────────────────────────────────────────────────────────────┤
│ id (PK)              │ VARCHAR(36)  │ UUID                  │
│ user_id (FK)         │ VARCHAR(36)  │ NOT NULL              │
│ local_image_id       │ VARCHAR(100) │ Links to local storage│
│ deer_age             │ FLOAT        │ Estimated age in years│
│ deer_type            │ VARCHAR(100) │ Whitetail/Mule Deer   │
│ deer_sex             │ VARCHAR(50)  │ Buck/Doe/Unknown      │
│ antler_points        │ INTEGER      │ Total points          │
│ antler_points_left   │ INTEGER      │ Left antler points    │
│ antler_points_right  │ INTEGER      │ Right antler points   │
│ body_condition       │ VARCHAR(50)  │ Health assessment     │
│ confidence           │ INTEGER      │ 0-100 percentage      │
│ recommendation       │ VARCHAR(50)  │ HARVEST/PASS          │
│ reasoning            │ TEXT         │ AI explanation        │
│ notes                │ TEXT         │ User notes            │
│ raw_response         │ JSON         │ Full AI response      │
│ created_at           │ DATETIME     │ DEFAULT NOW()         │
└─────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────┐
│                   password_reset_codes                       │
├─────────────────────────────────────────────────────────────┤
│ id (PK)              │ VARCHAR(36)  │ UUID                  │
│ email                │ VARCHAR(255) │ NOT NULL              │
│ code                 │ VARCHAR(10)  │ 6-digit code          │
│ created_at           │ DATETIME     │ DEFAULT NOW()         │
│ used                 │ BOOLEAN      │ DEFAULT FALSE         │
└─────────────────────────────────────────────────────────────┘
```

### Subscription Tiers

| Tier | Name | Scans Remaining | Description |
|------|------|-----------------|-------------|
| `tracker` | Free | 3 (then 0) | Default free tier |
| `master_stag` | Premium | -1 (unlimited) | Paid subscription |

**Note:** `scans_remaining = -1` indicates unlimited scans.

---

## 5. Authentication System

### JWT Token Structure

```json
{
  "sub": "user-uuid",
  "email": "user@example.com",
  "exp": 1705420800,
  "iat": 1705334400
}
```

**Token Expiry:** 30 days

### Password Hashing

- **Algorithm:** bcrypt
- **Rounds:** 12 (via passlib)
- **Storage:** Only hash stored, never plaintext

### Sign in with Apple Flow

```
1. User taps "Sign in with Apple"
2. App receives identity_token from Apple
3. Frontend sends token to /auth/apple
4. Backend decodes JWT (without verification for now)
5. Backend creates/retrieves user by apple_user_id
6. Backend returns app JWT token
7. User is authenticated
```

### Token Storage (Frontend)

- **Location:** Expo SecureStore
- **Key:** `auth_token`
- **Encryption:** Platform-provided secure storage

### Biometric Authentication

Iron Stag supports biometric authentication (Face ID, Touch ID, Fingerprint) for quick login.

#### Supported Biometric Types

| Type | Platform | Detection |
|------|----------|-----------|
| Face ID | iOS (iPhone X+) | `AuthenticationType.FACIAL_RECOGNITION` |
| Touch ID | iOS (iPhone 5S-8) | `AuthenticationType.FINGERPRINT` |
| Fingerprint | Android | `AuthenticationType.FINGERPRINT` |
| Face Unlock | Android | `AuthenticationType.FACIAL_RECOGNITION` |

#### Implementation Flow

```
Enable Biometric:
1. User logged in with password (has valid token)
2. User taps "Enable Face ID/Fingerprint" in Profile → Security
3. App calls LocalAuthentication.authenticateAsync() to verify identity
4. On success, token stored in SecureStore with key 'biometric_auth_token'
5. Flag 'biometric_enabled' set to 'true' in SecureStore

Login with Biometric:
1. App checks if biometric is enabled and available
2. User taps "Login with Face ID/Fingerprint"
3. App calls LocalAuthentication.authenticateAsync()
4. On success, retrieve token from SecureStore
5. Validate token with backend (/auth/me)
6. If valid, user is logged in
7. If expired, prompt for password login
```

#### Storage Keys

| Key | Purpose | Value |
|-----|---------|-------|
| `auth_token` | Current session token | JWT string |
| `biometric_auth_token` | Token for biometric login | JWT string |
| `biometric_enabled` | User preference | 'true' or 'false' |

#### AuthStore Methods

```typescript
interface AuthState {
  biometric: {
    isAvailable: boolean;    // Device has biometric hardware
    isEnabled: boolean;      // User has enabled biometric login
    biometricType: 'fingerprint' | 'facial' | 'iris' | 'none';
  };
  
  // Check device capabilities
  checkBiometricAvailability: () => Promise<void>;
  
  // Enable biometric (stores token after auth)
  enableBiometric: () => Promise<boolean>;
  
  // Disable biometric (removes stored token)
  disableBiometric: () => Promise<void>;
  
  // Authenticate and return stored token
  authenticateWithBiometric: () => Promise<{
    success: boolean;
    token?: string;
    error?: string;
  }>;
}
```

#### Security Considerations

- **No password storage:** Only the JWT token is stored, never the password
- **Secure storage:** Token encrypted using platform-native secure storage
- **Token expiration:** If token expires, user must re-authenticate with password
- **Device binding:** Biometric setup is device-specific, not synced across devices
- **Fallback:** Password login always available if biometric fails

#### iOS Configuration (app.json)

```json
{
  "expo": {
    "ios": {
      "infoPlist": {
        "NSFaceIDUsageDescription": "Enable Face ID for quick, secure login to Iron Stag."
      }
    },
    "plugins": [
      "expo-local-authentication"
    ]
  }
}
```

---

## 6. AI Integration

### OpenAI GPT-4o Vision

#### Configuration

```python
MODEL = "gpt-4o"
MAX_TOKENS = 1000
```

#### System Prompt

The AI receives a detailed system prompt that instructs it to:

1. **First identify** what's in the image
2. **Reject non-deer** images (Elk, Moose, other animals, objects)
3. **Only accept** Whitetail and Mule Deer
4. **Analyze valid deer** for age, sex, points, condition, recommendation

#### Response Format

**Invalid (Not a Deer):**
```json
{
  "is_valid_deer": false,
  "detected_subject": "Elk",
  "message": "This app is designed for Whitetail and Mule Deer only."
}
```

**Valid Deer:**
```json
{
  "is_valid_deer": true,
  "deer_age": 3.5,
  "deer_type": "Whitetail",
  "deer_sex": "Buck",
  "antler_points": 8,
  "antler_points_left": 4,
  "antler_points_right": 4,
  "body_condition": "Good",
  "confidence": 87,
  "recommendation": "HARVEST",
  "reasoning": "This buck appears to be..."
}
```

#### Image Handling

1. Frontend converts image to base64
2. Prepends `data:image/jpeg;base64,` if missing
3. Sends to OpenAI via API
4. Response parsed and stored

---

## 7. Payment & Subscription System

### RevenueCat Integration

#### Configuration

```typescript
// iOS
REVENUECAT_IOS_API_KEY=sk_mhkZTJXJjpUcNrCYVRyMYAPDOgKgV

// Android
REVENUECAT_ANDROID_API_KEY=goog_MZUtDk1KjnEPjVZDnQWAiYxPQAV
```

#### Flow

```
1. User taps "Subscribe"
2. RevenueCat SDK shows paywall
3. User completes purchase in App Store/Play Store
4. RevenueCat notifies app of success
5. App calls /subscription/verify-revenuecat
6. Backend updates user tier to "master_stag"
7. User has unlimited scans
```

#### Restore Purchases

```typescript
const restore = async () => {
  const customerInfo = await Purchases.restorePurchases();
  // Check entitlements
  if (customerInfo.entitlements.active['master_stag']) {
    // User is premium
  }
};
```

### Expo Go Mocking

In Expo Go (development), native purchases aren't available. The `RevenueCatService` provides mock functionality:

```typescript
if (isExpoGo) {
  return {
    offerings: mockOfferings,
    purchase: mockPurchase,
    restore: mockRestore
  };
}
```

---

## 8. Frontend Architecture

### Directory Structure

```
frontend/
├── app/                      # Expo Router screens
│   ├── (auth)/               # Auth group (no tabs)
│   │   ├── _layout.tsx       # Auth stack layout
│   │   ├── login.tsx         # Login screen
│   │   ├── signup.tsx        # Registration screen
│   │   ├── forgot-password.tsx
│   │   ├── disclaimer.tsx
│   │   ├── onboarding.tsx
│   │   └── privacy.tsx
│   ├── (tabs)/               # Main app (with tabs)
│   │   ├── _layout.tsx       # Tab navigator
│   │   ├── index.tsx         # Home tab
│   │   ├── scan.tsx          # Scan tab
│   │   ├── history.tsx       # History tab
│   │   ├── learn.tsx         # Learn tab
│   │   └── profile.tsx       # Profile tab
│   ├── scan-result/
│   │   └── [id].tsx          # Dynamic scan result
│   ├── _layout.tsx           # Root layout
│   ├── index.tsx             # Entry point
│   └── splash.tsx            # Splash screen
├── assets/
│   └── images/               # App images
├── components/               # Reusable components
├── constants/
│   └── theme.ts              # Design tokens
├── services/
│   ├── LocalImageService.ts  # Image storage
│   └── RevenueCatService.ts  # Payments
├── stores/
│   ├── authStore.ts          # Auth state
│   └── imageStore.ts         # Image state
├── utils/
│   └── api.ts                # API client
├── app.json                  # Expo config
├── eas.json                  # EAS Build config
└── package.json
```

### Navigation Structure

```
Root Stack
├── Splash Screen
├── Auth Stack (not authenticated)
│   ├── Login
│   ├── Signup
│   ├── Forgot Password
│   └── Onboarding
└── Tab Navigator (authenticated)
    ├── Home
    ├── Learn
    ├── Scan
    ├── History
    └── Profile
```

### Component Architecture

```
Screen (Page)
├── Layout Components (SafeAreaView, ScrollView)
├── Header Component
├── Content Components
│   ├── UI Components (Button, Input, Card)
│   └── Business Components (ScanCard, HistoryItem)
└── Modal Components
```

---

## 9. State Management

### Zustand Stores

#### authStore

```typescript
interface AuthState {
  user: User | null;
  token: string | null;
  isAuthenticated: boolean;
  isLoading: boolean;
  
  // Actions
  login: (email: string, password: string) => Promise<void>;
  register: (data: RegisterData) => Promise<void>;
  logout: () => Promise<void>;
  updateUser: (data: Partial<User>) => void;
  loadStoredAuth: () => Promise<void>;
}
```

#### imageStore

```typescript
interface ImageState {
  stats: StorageStats;
  cleanupInterval: number;
  
  // Actions
  initialize: () => Promise<void>;
  saveImage: (base64: string) => Promise<string>;
  getImage: (id: string) => Promise<string | null>;
  deleteImage: (id: string) => Promise<void>;
  cleanupOldImages: () => Promise<number>;
  clearAllImages: () => Promise<number>;
  setCleanupInterval: (days: number) => Promise<void>;
}
```

### Data Flow

```
User Action → Zustand Action → API Call → Update Store → Re-render
```

---

## 10. Local Storage & Caching

### Image Storage (LocalImageService)

#### Storage Location

```typescript
// Base directory
const BASE_DIR = FileSystem.documentDirectory + 'deer_images/';

// Metadata file
const METADATA_FILE = FileSystem.documentDirectory + 'image_metadata.json';

// Settings file  
const SETTINGS_FILE = FileSystem.documentDirectory + 'storage_settings.json';
```

#### Metadata Structure

```typescript
interface ImageMetadata {
  id: string;           // UUID
  createdAt: number;    // Unix timestamp
  size: number;         // Bytes
  path: string;         // Full file path
}
```

#### Cleanup Logic

```typescript
const cleanup = async (maxAgeDays: number) => {
  const cutoff = Date.now() - (maxAgeDays * 24 * 60 * 60 * 1000);
  const oldImages = metadata.filter(m => m.createdAt < cutoff);
  // Delete old images and their database records
};
```

### Auth Token Storage

```typescript
import * as SecureStore from 'expo-secure-store';

// Store
await SecureStore.setItemAsync('auth_token', token);

// Retrieve
const token = await SecureStore.getItemAsync('auth_token');

// Delete
await SecureStore.deleteItemAsync('auth_token');
```

---

## 11. Build & Deployment

### EAS Build Configuration

#### eas.json

```json
{
  "cli": {
    "version": ">= 10.0.0",
    "appVersionSource": "local"
  },
  "build": {
    "base": {
      "env": {
        "EXPO_PUBLIC_API_BASE_URL": "https://ironstag-production.up.railway.app",
        "EXPO_NO_DOCTOR": "1"
      }
    },
    "development": {
      "extends": "base",
      "developmentClient": true,
      "distribution": "internal",
      "prebuildCommand": "npx expo prebuild --clean"
    },
    "preview": {
      "extends": "base",
      "distribution": "internal",
      "prebuildCommand": "npx expo prebuild --clean",
      "android": { "buildType": "apk" }
    },
    "production": {
      "extends": "base",
      "autoIncrement": true,
      "prebuildCommand": "npx expo prebuild --clean",
      "android": { "buildType": "app-bundle" }
    }
  }
}
```

### Build Commands

```bash
# Development build (internal testing)
eas build --platform android --profile development
eas build --platform ios --profile development

# Preview build (APK for testers)
eas build --platform android --profile preview

# Production build (store submission)
eas build --platform android --profile production
eas build --platform ios --profile production
```

### CNG (Continuous Native Generation)

This project uses Expo's CNG workflow:

- Native folders (`android/`, `ios/`) are **not committed** to git
- `npx expo prebuild --clean` generates them during build
- All native config is in `app.json` via plugins

---

## 12. Environment Configuration

### Backend (.env)

```env
# Database
DATABASE_URL=postgresql://user:pass@host/db?sslmode=require

# Authentication
SECRET_KEY=your-jwt-secret-key

# AI
EMERGENT_LLM_KEY=your-openai-compatible-key

# Email (Microsoft Graph)
MS_GRAPH_CLIENT_ID=azure-app-client-id
MS_GRAPH_CLIENT_SECRET=azure-app-secret
MS_GRAPH_TENANT_ID=azure-tenant-id
MS_GRAPH_SENDER_EMAIL=support@domain.com
```

### Frontend (.env)

```env
# API
EXPO_PUBLIC_API_BASE_URL=https://ironstag-production.up.railway.app
EXPO_PUBLIC_BACKEND_URL=https://ironstag-production.up.railway.app/api

# RevenueCat
EXPO_PUBLIC_REVENUECAT_IOS_API_KEY=sk_xxx
EXPO_PUBLIC_REVENUECAT_ANDROID_API_KEY=goog_xxx
```

---

## 13. Security Considerations

### Authentication
- JWT tokens expire after 30 days
- Passwords hashed with bcrypt (12 rounds)
- Tokens stored in platform secure storage

### API Security
- All endpoints require authentication (except health, login, register)
- User can only access their own data
- Rate limiting recommended for production

### Data Privacy
- Images are NOT stored on server
- Only analysis results are stored
- User can delete all data via Delete Account

### HTTPS
- All API communication over HTTPS
- TLS 1.2+ required

---

## 14. Error Handling

### HTTP Status Codes

| Code | Meaning | When Used |
|------|---------|----------|
| 200 | Success | Successful request |
| 400 | Bad Request | Invalid input, validation error |
| 401 | Unauthorized | Missing/invalid token |
| 403 | Forbidden | Scan limit reached, insufficient permissions |
| 404 | Not Found | Resource doesn't exist |
| 422 | Unprocessable | Validation failed |
| 500 | Server Error | Unexpected error |

### Error Response Format

```json
{
  "detail": "Error message"
}
```

Or structured:

```json
{
  "detail": {
    "code": "ERROR_CODE",
    "message": "Human readable message",
    "field": "optional_field_name"
  }
}
```

### Frontend Error Handling

```typescript
try {
  const response = await api.post('/endpoint', data);
} catch (error) {
  if (error.response?.status === 403) {
    // Handle forbidden (e.g., show upgrade modal)
  } else if (error.response?.status === 400) {
    // Handle bad request (e.g., show validation error)
  } else {
    // Generic error handling
    Alert.alert('Error', 'Something went wrong');
  }
}
```

---

## 15. Testing

### Backend Testing

```bash
# Run tests
cd backend
pytest

# With coverage
pytest --cov=server
```

### Frontend Testing

```bash
# Run tests
cd frontend
yarn test

# With coverage
yarn test --coverage
```

### Manual API Testing

```bash
# Health check
curl http://localhost:8001/api/health

# Login
curl -X POST http://localhost:8001/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email": "user@test.com", "password": "password"}'
```

---

## 16. Monitoring & Logging

### Backend Logging

```python
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Usage
logger.info("User logged in", extra={"user_id": user_id})
logger.error("Failed to process", exc_info=True)
```

### Log Locations

```bash
# Backend logs
/var/log/supervisor/backend.out.log
/var/log/supervisor/backend.err.log

# Frontend logs
/var/log/supervisor/expo.out.log
/var/log/supervisor/expo.err.log
```

### Key Metrics to Monitor

- API response times
- Error rates
- Scan success/failure ratio
- Active users
- Subscription conversions

---

## 17. Troubleshooting Guide

### Common Issues

#### Database Connection Failed
```
Error: Connection refused
```
**Solution:** Check DATABASE_URL, ensure database is running

#### JWT Decode Error
```
Error: Signature verification failed
```
**Solution:** Check SECRET_KEY matches between auth and verification

#### OpenAI API Error
```
Error: Rate limit exceeded
```
**Solution:** Implement retry logic, check API key quota

#### Image Analysis Timeout
```
Error: Request timeout
```
**Solution:** Reduce image size, check network connectivity

### Debug Commands

```bash
# Check backend status
sudo supervisorctl status backend

# Restart backend
sudo supervisorctl restart backend

# Check frontend status
sudo supervisorctl status expo

# View real-time logs
tail -f /var/log/supervisor/backend.err.log
```

---

## 18. API Rate Limits

### Recommended Limits (Production)

| Endpoint | Limit | Window |
|----------|-------|--------|
| /auth/login | 10 | 1 minute |
| /auth/register | 5 | 1 minute |
| /analyze-deer | 20 | 1 hour |
| /scans | 100 | 1 minute |
| General | 1000 | 1 hour |

### Implementation

```python
from slowapi import Limiter
from slowapi.util import get_remote_address

limiter = Limiter(key_func=get_remote_address)

@app.post("/api/auth/login")
@limiter.limit("10/minute")
async def login(...):
    ...
```

---

## 19. Future Roadmap

### Planned Features

- [ ] Offline mode with cached AI
- [ ] Social sharing of scans
- [ ] Multi-user hunting groups
- [ ] Advanced analytics dashboard
- [ ] Trail camera integration
- [ ] Weather data correlation
- [ ] Export to PDF/CSV
- [ ] Push notifications
- [ ] Dark/Light theme toggle
- [ ] Multiple language support

### Technical Improvements

- [ ] GraphQL API option
- [ ] WebSocket for real-time updates
- [ ] Redis caching layer
- [ ] Horizontal scaling
- [ ] CI/CD pipeline
- [ ] Automated testing suite
- [ ] Performance monitoring
- [ ] A/B testing framework

---

## Appendix A: Complete API Reference Table

| Method | Endpoint | Auth | Description |
|--------|----------|------|-------------|
| POST | /auth/register | No | Register new user |
| POST | /auth/login | No | Login user |
| POST | /auth/apple | No | Apple Sign-in |
| GET | /auth/me | Yes | Get current user |
| PUT | /auth/profile | Yes | Update profile |
| DELETE | /auth/account | Yes | Delete account |
| POST | /auth/request-password-reset | No | Request reset code |
| POST | /auth/verify-password-reset | No | Reset password |
| POST | /auth/accept-disclaimer | Yes | Accept disclaimer |
| POST | /analyze-deer | Yes | Analyze deer image |
| GET | /scans | Yes | List scans |
| GET | /scans/stats/summary | Yes | Get scan stats |
| GET | /scans/{id} | Yes | Get specific scan |
| PUT | /scans/{id} | Yes | Update scan notes |
| POST | /scans/{id}/edit | Yes | Edit and re-analyze |
| DELETE | /scans/{id} | Yes | Delete scan |
| DELETE | /scans/all | Yes | Delete all scans |
| POST | /scans/delete-by-local-ids | Yes | Bulk delete by local IDs |
| GET | /subscription/status | Yes | Get subscription |
| GET | /subscription/scan-eligibility | Yes | Check scan eligibility |
| POST | /subscription/verify-revenuecat | Yes | Verify purchase |
| GET | /learn/content | No | Get learn content |
| GET | /health | No | Health check |

---

## Appendix B: Database Migrations

### Adding New Column

```python
# In server.py startup
async def migrate_database():
    # Add new column if not exists
    await database.execute("""
        ALTER TABLE users 
        ADD COLUMN IF NOT EXISTS new_field VARCHAR(100)
    """)
```

### Running Migrations

Migrations run automatically on server startup in the `lifespan` context manager.

---

## Appendix C: Development Setup

### Prerequisites

- Node.js 20+
- Python 3.11+
- PostgreSQL 15+
- Yarn 1.22+

### Quick Start

```bash
# Clone repository
git clone https://github.com/Asgard-Solutions/ironstag.git
cd ironstag

# Backend setup
cd backend
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
# Edit .env with your credentials
uvicorn server:app --reload --port 8001

# Frontend setup (new terminal)
cd frontend
yarn install
cp .env.example .env
# Edit .env
yarn start
```

---

**Iron Stag Technical Manual**

© 2026 Asgard Solutions. All rights reserved.
