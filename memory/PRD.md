# Iron Stag — Product Requirements Document

**Version**: 1.8.0  
**Last Updated**: July 2026

## Product Overview
Iron Stag is an AI-powered deer analysis mobile app for hunters and wildlife professionals. Users photograph deer and receive AI-estimated age, species identification, sex classification, antler analysis, management recommendations, and optional Boone & Crockett scoring.

## Core Features
- AI deer aging via OpenAI Vision (GPT-4o / GPT-4.1) with species-specific rubrics (v1.8.0)
- Region-aware confidence calibration (Midwest, Southeast, Northeast, Plains, South Texas, Northern)
- Season-aware prompt context (pre-rut, rut, post-rut, off-season)
- Selective multi-pass consensus for borderline cases with alternate age support
- Age quality gating (blocks unreliable estimates)
- Boone & Crockett unofficial scoring (typical/non-typical whitetail + mule deer)
- RevenueCat subscription management
- Apple Sign-In + email/password auth
- Scan history with favorites, tags, and cloud image sync (R2)
- Offline queue for field use
- Learn section for deer aging education

## Current AI Pipeline (v1.8.0)
- Prompt version: `age-v6-species-rubrics`
- Includes: Buck age rubric, Doe age rubric, Mule Deer rubric, Fawn identification guidance
- High-resolution image analysis (`detail: high`)
- max_output_tokens: 2000
- Consensus passes use temperature=0.2 for diverse perspectives
- Alternate ages leveraged in consensus merging
- confidence_reasoning field for transparency

## Security
- JWT_SECRET, ADMIN_SECRET required (fail-fast on startup)
- Admin endpoints protected via x-admin-secret header
- Rate limiting on auth endpoints (10/15min/IP)
- No secret keys in client builds
- RevenueCat webhook fails closed without secret

## Platform Requirements
- iOS 15.1+
- Android 7.0+ (API 24), targeting Android 16 (API 36)
- Expo SDK 54, React Native 0.81.x
