# Iron Stag - Data Sources & Connections

## Overview
This article explains what data Iron Stag uses and how your data flows through the app during analysis.

## Key Information
- **Data collected:** Email, name, home state, scan results, device info (local only).
- **Deer photos:** Uploaded for analysis, processed, and stored locally; optional cloud copy if enabled.
- **Server storage:** Scan metadata is stored; optional cloud image storage via R2 if configured.
- **Manual score data:** Harvest-confirmed buck records can store user-entered unofficial B&C measurements and totals.
- **External services used:**
  - OpenAI (multimodal deer analysis)
  - Neon/PostgreSQL (primary database)
  - RevenueCat (in-app purchase entitlement sync)
  - Stripe (web checkout/portal)
  - Microsoft Graph (password reset email)
  - Cloudflare R2 (optional image storage)

## Step-by-Step
1. Upload or capture a deer photo in the app.
2. The image is sent securely to the server for AI analysis.
3. The analysis results, calibration metadata, and visible age cues are stored for scan history.
4. The original image is stored locally on your device (and may be stored in cloud if enabled).
5. If you mark a buck as harvested, you can optionally save manual unofficial B&C measurements on that record.

## Common Questions
**Q: Do you store my photos on your servers?**
A: Photos are stored locally. If cloud image storage is enabled, a compressed copy may be stored for cross-device access.

**Q: Does the AI calculate Boone & Crockett scores from photos?**
A: No. B&C scores in Iron Stag are user-entered only and saved as harvested-buck record data.

**Q: Can Iron Stag connect to my database or CRM?**
A: The current Iron Stag documentation does not list any external database or CRM connections.

## Contact Support
For issues not covered here, email support@asgardsolution.io
