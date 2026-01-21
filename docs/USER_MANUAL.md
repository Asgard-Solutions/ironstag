# Iron Stag - User Manual

![Iron Stag Logo](../frontend/assets/images/iron_stag_logo.png)

**Version 1.1.0**  
**Last Updated: January 2026**

---

## Table of Contents

1. [Introduction](#1-introduction)
2. [Getting Started](#2-getting-started)
3. [Account Management](#3-account-management)
4. [Biometric Login](#4-biometric-login)
5. [Home State & Regional Calibration](#5-home-state--regional-calibration)
6. [Scanning Deer](#6-scanning-deer)
7. [Scan Results](#7-scan-results)
8. [Scan History](#8-scan-history)
9. [Learn Section](#9-learn-section)
10. [Profile & Settings](#10-profile--settings)
11. [Subscription Plans](#11-subscription-plans)
12. [Data & Privacy](#12-data--privacy)
13. [Troubleshooting](#13-troubleshooting)
14. [FAQ](#14-faq)
15. [Contact & Support](#15-contact--support)

---

## 1. Introduction

### What is Iron Stag?

Iron Stag is an AI-powered deer analysis application designed for hunters, wildlife enthusiasts, and deer management professionals. Using advanced artificial intelligence and machine learning, Iron Stag analyzes photos of deer to provide:

- **Age Estimation** - Estimated age of the deer in years
- **Sex Identification** - Buck or Doe classification
- **Species Type** - Whitetail or Mule Deer identification
- **Antler Analysis** - Point count (left and right antlers separately)
- **Body Condition Assessment** - Overall health evaluation
- **Harvest Recommendation** - AI-powered HARVEST or PASS recommendation
- **Confidence Score** - How certain the AI is about its analysis
- **Regional Calibration** - Confidence adjusted for your hunting region

### Supported Deer Species

Iron Stag is specifically designed for:
- ✅ **Whitetail Deer**
- ✅ **Mule Deer**

The app will **not** analyze:
- ❌ Elk
- ❌ Moose
- ❌ Other wildlife (hogs, turkey, etc.)
- ❌ Non-animal images

If you upload an image that isn't a Whitetail or Mule Deer, the app will notify you and no scan will be used.

---

## 2. Getting Started

### System Requirements

**iOS:**
- iOS 13.0 or later
- iPhone 8 or newer recommended
- Camera access for photo capture
- Internet connection required for AI analysis

**Android:**
- Android 10 (API 29) or later
- Android 15 Edge-to-Edge compliant
- Android 16 Large Screen / Foldable ready
- 4GB RAM recommended
- Camera access for photo capture
- Internet connection required for AI analysis

### Installation

#### App Store (iOS)
1. Open the App Store on your iPhone
2. Search for "Iron Stag"
3. Tap "Get" to download
4. Open the app once installed

#### Google Play Store (Android)
1. Open Google Play Store
2. Search for "Iron Stag"
3. Tap "Install"
4. Open the app once installed

### First Launch

When you first open Iron Stag:

1. **Welcome Screen** - View the app introduction
2. **Account Creation** - Create an account or sign in
3. **Legal Disclaimer** - Accept the terms of use
4. **Permissions** - Grant camera and photo library access
5. **Set Home State** - Configure your hunting region for better accuracy
6. **Ready to Scan** - Start analyzing deer!

---

## 3. Account Management

### Creating an Account

#### Email Registration
1. Tap "Sign Up" on the welcome screen
2. Enter your information:
   - **First Name** (required)
   - **Last Name** (required)
   - **Username** (required, unique)
   - **Email Address** (required, unique)
   - **Password** (required, minimum 6 characters)
3. Tap "Create Account"
4. Accept the legal disclaimer
5. You're ready to start scanning!

### Signing In

You can sign in using:
- **Email Address** + Password
- **Username** + Password

### Forgot Password

1. Tap "Forgot Password?" on the login screen
2. Enter your registered email address
3. Tap "Send Reset Code"
4. Check your email for the 6-digit code
5. Enter the code and your new password
6. Tap "Reset Password"

**Note:** Reset codes expire after 15 minutes.

### Editing Your Profile

1. Go to the **Profile** tab
2. Tap "Edit Profile" (pencil icon)
3. You can update:
   - First Name
   - Last Name
   - Username
4. Tap "Save" to confirm changes

### Signing Out

1. Go to the **Profile** tab
2. Scroll to the bottom
3. Tap "Sign Out"
4. Confirm when prompted

---

## 4. Biometric Login

### Overview

Iron Stag supports biometric authentication for quick, secure login using:
- **Face ID** (iPhone X and newer, iPad Pro)
- **Touch ID** (iPhone 5S-8, older iPads)
- **Fingerprint** (Android devices with fingerprint sensors)
- **Face Unlock** (Android devices with face recognition)

### Enabling Biometric Login

1. **Sign in** with your email/username and password first
2. Go to the **Profile** tab
3. Scroll to the **Security** section
4. Tap **"Face ID Login"** or **"Fingerprint Login"** toggle
5. Authenticate with your biometric to confirm
6. Biometric login is now enabled!

### Using Biometric Login

Once enabled, the next time you open Iron Stag:

1. On the login screen, you'll see a **"Login with Face ID"** or **"Login with Fingerprint"** button
2. Tap the button
3. Authenticate with your face or fingerprint
4. You're instantly logged in!

### Disabling Biometric Login

1. Go to **Profile** → **Security**
2. Tap the biometric toggle to turn it **off**
3. Biometric login is now disabled

### Important Notes

| Note | Details |
|------|---------|
| **First login required** | You must log in with password at least once before enabling biometric |
| **Token expiration** | If your session expires (30 days), you'll need to re-enter your password |
| **Device-specific** | Biometric is tied to your device; set up again on new devices |
| **Security** | Your password is NOT stored; only a secure token is saved |
| **Fallback** | You can always use your password if biometric fails |

### Troubleshooting Biometric

**"Biometric not available"**
- Ensure your device has Face ID/Touch ID/Fingerprint hardware
- Check that biometrics are set up in your device settings
- Some older devices may not support biometric authentication

**"Please login with password"**
- Your stored token has expired
- Log in with your password and re-enable biometric

**Biometric doesn't appear on login screen**
- You haven't enabled it yet; go to Profile → Security first
- Only appears on iOS/Android native apps (not Expo Go)

---

## 5. Home State & Regional Calibration

### Why Set Your Home State?

Deer vary significantly by region. A 3.5-year-old buck in Texas looks different from one in Wisconsin. By setting your **Home State**, Iron Stag calibrates its confidence scores specifically for your region's deer population.

### Benefits of Regional Calibration

- **More Accurate Confidence Scores** - Calibrated for your region's deer characteristics
- **Better Age Estimates** - Accounts for regional body size variations
- **Honest Uncertainty** - When the AI is unsure, it tells you clearly

### Setting Your Home State

Your Home State is prominently displayed in your Profile:

1. Go to the **Profile** tab
2. Find the **Home State** card (near the top)
3. Tap to open the state selector
4. Scroll or search for your state
5. Tap your state to select it
6. Your selection is saved automatically

### Regional Calibration Zones

Iron Stag groups states into calibration regions:

| Region | States |
|--------|--------|
| **Midwest** | IA, IL, IN, KS, MI, MN, MO, NE, ND, OH, SD, WI |
| **Southeast** | AL, AR, FL, GA, KY, LA, MS, NC, SC, TN, VA, WV |
| **Northeast** | CT, DE, MA, MD, ME, NH, NJ, NY, PA, RI, VT |
| **Plains** | CO, MT, NM, OK, WY |
| **South Texas** | TX (southern region) |
| **Northern** | AK, ID, OR, WA |

### Per-Scan Location Override

If you're hunting in a different state than your home state:

1. On the **Scan** screen, look for "Hunting Location"
2. Tap to select the state where you're currently hunting
3. This overrides your home state for this scan only
4. Your home state remains unchanged for future scans

---

## 6. Scanning Deer

### How to Scan

Navigate to the **Scan** tab (center icon) to analyze a deer.

#### Method 1: Take a Photo
1. Tap "Scan Deer" or "Open Camera"
2. Point your camera at the deer
3. Tap the capture button
4. Review the photo
5. Optionally set a different hunting location
6. Tap "Analyze" to process

#### Method 2: Upload from Gallery
1. Tap "Choose from Library"
2. Select a deer photo from your device
3. Optionally set a different hunting location
4. Tap "Analyze" to process

### Best Practices for Accurate Results

For the most accurate analysis:

#### ✅ DO:
- Use clear, well-lit photos
- Capture the deer from the side (broadside view)
- Include the full body if possible
- Ensure the deer is in focus
- Take photos during daylight or with good artificial lighting
- Set your home state for calibrated results

#### ❌ DON'T:
- Use blurry or out-of-focus images
- Upload extremely dark photos
- Use images where the deer is too far away
- Submit photos with multiple deer (AI may get confused)
- Upload photos of mounted/taxidermy deer

### Scan Limits

**Free Users (Tracker Tier):**
- 3 free scans total
- Scans do not refresh
- Upgrade to Master Stag for unlimited scans

**Premium Users (Master Stag Tier):**
- Unlimited scans
- No restrictions

### What Happens During Analysis

1. Your image is securely uploaded
2. AI processes the image (typically 5-15 seconds)
3. Regional calibration is applied based on your location
4. Results are displayed on the Scan Result screen
5. Data is saved to your Scan History
6. Image is stored locally on your device

---

## 7. Scan Results

### Understanding Your Results

After a successful scan, you'll see:

#### Primary Information
| Field | Description |
|-------|-------------|
| **Deer Type** | Whitetail or Mule Deer |
| **Sex** | Buck, Doe, or Unknown |
| **Estimated Age** | Age in years (e.g., 3.5 years) |
| **Recommendation** | HARVEST (green) or PASS (red) |
| **Confidence** | AI certainty percentage (0-100%) |

#### Understanding Confidence Scores

Iron Stag uses a sophisticated confidence calibration system:

- **High Confidence (70%+)** - The AI is confident in its assessment
- **Moderate Confidence (50-70%)** - Reasonable certainty, but some uncertainty
- **Low Confidence (<50%)** - The AI is uncertain; consider this a rough estimate

**Age Uncertain Indicator:** When confidence is low, you may see "Age Uncertain" displayed. This means the AI acknowledges it's not sure about the age estimate.

#### Antler Details (Bucks Only)
| Field | Description |
|-------|-------------|
| **Total Points** | Combined antler points |
| **Left Antler** | Points on left side |
| **Right Antler** | Points on right side |

#### Additional Information
| Field | Description |
|-------|-------------|
| **Body Condition** | Health assessment (Excellent, Good, Fair, Poor) |
| **Reasoning** | AI's explanation for the recommendation |
| **Region** | The calibration region used for this scan |

### Editing Scan Results

If you believe the AI made an error, you can edit and re-analyze:

1. Tap the **Edit** button (pencil icon) on the scan result
2. Modify any of the following:
   - Sex (Buck/Doe)
   - Deer Type (Whitetail/Mule Deer)
   - Left Antler Points
   - Right Antler Points
3. Tap "Re-Analyze"
4. The AI will recalculate using your corrections

### Adding Notes

1. Tap the notes field at the bottom of the result
2. Enter any personal observations:
   - Location where the deer was spotted
   - Trail camera number
   - Weather conditions
   - Any other relevant details
3. Notes are saved automatically

---

## 8. Scan History

### Viewing History

1. Navigate to the **History** tab
2. View all your past scans in a scrollable list
3. Each entry shows:
   - Thumbnail image
   - Deer type and sex
   - Age and point count
   - HARVEST/PASS recommendation
   - Confidence score
   - Date scanned

### Searching & Filtering

#### Search Bar
Type to search by:
- Deer type ("Whitetail", "Mule")
- Sex ("Buck", "Doe")
- Age ("4 yrs")
- Points ("8 points")
- Recommendation ("HARVEST", "PASS")
- Date ("Jan 2026")
- Notes content

#### Quick Filters
Tap the filter dropdown buttons:

**Sex Filter:**
- All
- Buck
- Doe

**Recommendation Filter:**
- All
- HARVEST
- PASS

### Viewing Scan Details

1. Tap any scan in the history list
2. View the full scan result page
3. Edit, add notes, or delete as needed

### Deleting Individual Scans

1. Open the scan you want to delete
2. Tap the delete/trash icon
3. Confirm deletion
4. The scan is permanently removed

---

## 9. Learn Section

### Educational Content

The **Learn** tab provides educational resources about:

- **Deer Aging Techniques** - How to estimate deer age by body characteristics
- **Antler Development** - Understanding antler growth patterns
- **Body Condition Indicators** - What to look for in healthy deer
- **Regional Variations** - How deer differ by geography
- **Best Practices** - Tips for better photos and analysis

### Content Categories

- Beginner guides
- Advanced techniques
- Seasonal tips
- Deer management principles

---

## 10. Profile & Settings

### Profile Overview

Your profile displays:
- Name and username
- Email address
- Member since date
- Current subscription tier
- Home State setting

### Home State

Prominently displayed at the top of your profile:
- Shows your currently selected state
- Shows "Calibrated for your region" when set
- Tap to change your home state

### Subscription Status

View your current plan:
- **Tracker** (Free) - 3 scans
- **Master Stag** (Premium) - Unlimited scans

### Storage Management

Iron Stag stores scan images locally on your device.

#### Cleanup Settings
Set a cleanup interval:
1. Go to Profile → Local Storage
2. Select cleanup interval:
   - 30 days
   - 60 days
   - 90 days (recommended)
   - 180 days
3. Images older than the interval can be cleaned up

#### Manual Cleanup

**Clean Up Old Images:**
1. Tap "Clean Up Old Images"
2. Images older than your set interval are deleted
3. Associated scan history is also removed

**Clear All Local Images:**
1. Tap "Clear All"
2. Confirm (destructive action)
3. ALL local images AND scan history are deleted

⚠️ **Warning:** Clearing images also deletes all your scan history from the database. This cannot be undone.

### About Iron Stag

View app information including:
- Current app version
- Check for updates
- Legal information

### Restore Purchases

If your subscription isn't showing:

1. Go to Profile
2. Tap "Restore Purchases"
3. Wait for verification with Apple/Google
4. Your subscription status will update

Use this when:
- You reinstalled the app
- You switched to a new device
- Your subscription isn't being recognized

### Delete Account

⚠️ **Permanent Action - Cannot be undone!**

1. Scroll to bottom of Profile
2. Tap "Delete Account" (red button)
3. Confirm first warning
4. Confirm second warning
5. Your account is permanently deleted:
   - All scan history removed
   - Local images cleared
   - Account credentials deleted
   - You are signed out

---

## 11. Subscription Plans

### Tracker (Free)

**Price:** Free

**Features:**
- 3 lifetime scans
- Full AI analysis with regional calibration
- Scan history
- Local image storage

**Limitations:**
- Scans do not refresh
- Once 3 scans are used, must upgrade

### Master Stag (Premium)

**Price:** $9.99/month or $89.99/year (Save $30!)

**Features:**
- ✅ Unlimited scans
- ✅ Full AI analysis with detailed reasoning
- ✅ Regional calibration for accurate confidence
- ✅ Scan history with search/filter
- ✅ Edit and re-analyze scans
- ✅ Priority support
- ✅ All future features included

### How to Subscribe

1. Use all 3 free scans, OR
2. Go to Profile → tap subscription card
3. Select Monthly ($9.99/mo) or Annual ($89.99/yr)
4. Complete purchase through App Store/Play Store
5. Subscription activates immediately

### Managing Your Subscription

**iOS:**
1. Open Settings → Your Name → Subscriptions
2. Tap "Iron Stag"
3. Manage or cancel

**Android:**
1. Open Play Store → Menu → Subscriptions
2. Tap "Iron Stag"
3. Manage or cancel

### Cancellation Policy

- Cancel anytime
- Access continues until end of billing period
- No refunds for partial periods
- Can re-subscribe at any time

---

## 12. Data & Privacy

### What Data We Collect

| Data Type | Purpose | Storage |
|-----------|---------|----------|
| Email | Account identification | Server |
| Name | Personalization | Server |
| Home State | Regional calibration | Server |
| Deer Photos | AI analysis | Processed, not stored on server |
| Scan Results | History feature | Server |
| Device Info | App functionality | Local only |

### Image Handling

1. **Upload:** Your image is sent to our secure server
2. **Analysis:** AI processes the image with regional calibration
3. **Storage:** Image is stored locally on YOUR device only
4. **Server:** We do NOT store your original images on our servers

### Data Security

- All data transmitted via HTTPS/TLS encryption
- Passwords are hashed (never stored in plain text)
- JWT tokens for secure authentication
- Regular security audits

### Your Rights

- **Access:** View all your data in the app
- **Delete:** Remove all your data via Delete Account
- **Opt-out:** Cancel subscription anytime

### Privacy Policy

View our full privacy policy at:
- In-app: Profile → Privacy Policy
- Web: https://asgardsolution.io/iron-stag/privacy

---

## 13. Troubleshooting

### Common Issues

#### "Analysis Failed"
**Possible causes:**
- Poor internet connection
- Image too large
- Server temporarily unavailable

**Solutions:**
1. Check your internet connection
2. Try a smaller/compressed image
3. Wait a moment and try again

#### "Not a Deer" Message
**Cause:** The AI detected something other than a Whitetail or Mule Deer.

**Solution:** Only upload photos of Whitetail or Mule Deer. Elk, Moose, and other animals are not supported.

#### Login Failed
**Possible causes:**
- Incorrect email/username or password
- Account doesn't exist
- Network issues

**Solutions:**
1. Verify your email/username spelling
2. Use "Forgot Password" to reset
3. Check your internet connection

#### Subscription Not Showing
**Solutions:**
1. Tap "Restore Purchases" in Profile
2. Ensure you're signed into the same Apple ID/Google account
3. Wait a few minutes and try again
4. Contact support if issue persists

#### Camera Not Working
**Solutions:**
1. Check app permissions in device settings
2. Restart the app
3. Restart your device

#### Images Not Loading in History
**Cause:** Local images may have been cleared.

**Note:** If you cleared local images, the scan data remains but images won't display. This is expected behavior.

### Error Codes

| Code | Meaning | Solution |
|------|---------|----------|
| 401 | Not authenticated | Sign in again |
| 403 | Scan limit reached | Upgrade to Master Stag |
| 400 | Invalid request | Check image format |
| 500 | Server error | Try again later |

---

## 14. FAQ

### General

**Q: Is Iron Stag accurate?**
A: Our AI achieves approximately 85-95% accuracy depending on image quality. The confidence score tells you how certain the AI is. Results should be used as a guide, not definitive determination.

**Q: Does it work offline?**
A: No. Internet connection is required for AI analysis.

**Q: Can I use trail camera photos?**
A: Yes! Trail camera photos work well, especially if they're clear and well-lit.

**Q: Why should I set my home state?**
A: Setting your home state enables regional calibration, making confidence scores more accurate for deer in your area.

### Scanning

**Q: Why was my scan rejected?**
A: The AI only analyzes Whitetail and Mule Deer. Photos of other animals or non-animal images will be rejected.

**Q: How long does analysis take?**
A: Typically 5-15 seconds depending on your connection speed.

**Q: Can I scan the same deer twice?**
A: Yes, each scan uses one of your scan credits.

**Q: What does "Age Uncertain" mean?**
A: When the AI's confidence is low, it honestly tells you it's uncertain about the age estimate. Use such results as rough guidance.

### Subscription

**Q: Do free scans refresh?**
A: No. Free users get 3 lifetime scans. Once used, upgrade is required.

**Q: Can I get a refund?**
A: Refunds are handled by Apple/Google according to their policies.

**Q: What happens if I cancel?**
A: You keep access until the end of your billing period, then revert to Tracker tier.

**Q: What's the difference between monthly and annual?**
A: Annual ($89.99/yr) saves you $30 compared to monthly ($9.99/mo × 12 = $119.88/yr).

### Privacy

**Q: Do you store my photos?**
A: No. Photos are processed and then stored only on your local device.

**Q: Can I delete all my data?**
A: Yes. Use "Delete Account" to permanently remove all data.

### Biometric Login

**Q: How do I enable fingerprint/Face ID login?**
A: First login with your password, then go to Profile → Security and toggle on biometric login.

**Q: Why isn't biometric showing on my login screen?**
A: You must enable it first from Profile → Security. It also requires a native build (not Expo Go).

**Q: Is biometric login secure?**
A: Yes. We store a secure encrypted token, not your password. Only your biometric can unlock it.

---

## 15. Contact & Support

### Customer Support

**Email:** support@asgardsolution.io

**Response Time:** Within 24-48 hours

### Bug Reports

To report a bug:
1. Email support@asgardsolution.io
2. Include:
   - Device model
   - OS version
   - App version
   - Steps to reproduce
   - Screenshots if applicable

### Feature Requests

We love hearing from our users! Email your suggestions to:
support@asgardsolution.io

### Social Media

- Website: https://asgardsolution.io
- Instagram: @ironstagapp
- Facebook: Iron Stag App

### Legal

- **Terms of Service:** https://asgardsolution.io/iron-stag/terms
- **Privacy Policy:** https://asgardsolution.io/iron-stag/privacy

---

## Appendix A: Supported Image Formats

| Format | Supported |
|--------|-----------|
| JPEG/JPG | ✅ Yes |
| PNG | ✅ Yes |
| HEIC | ✅ Yes (iOS) |
| WebP | ✅ Yes |
| GIF | ❌ No |
| BMP | ❌ No |
| RAW | ❌ No |

**Maximum file size:** 20MB

---

## Appendix B: Age Estimation Guide

The AI considers multiple factors:

| Age | Typical Characteristics |
|-----|------------------------|
| 1.5 yrs | Slender body, thin neck, spike or small antlers |
| 2.5 yrs | Athletic build, slight neck swelling during rut |
| 3.5 yrs | Muscular, developed chest, full antler potential |
| 4.5 yrs | Heavy body, thick neck, may have belly sag |
| 5.5+ yrs | Swayed back, loose skin, pot belly, thick body |

---

## Appendix C: Regional Calibration Zones

| Region | Characteristics | States |
|--------|-----------------|--------|
| **Midwest** | Large-bodied deer, consistent conditions | IA, IL, IN, KS, MI, MN, MO, NE, ND, OH, SD, WI |
| **Southeast** | Varied terrain, longer seasons | AL, AR, FL, GA, KY, LA, MS, NC, SC, TN, VA, WV |
| **Northeast** | Dense cover, cold winters | CT, DE, MA, MD, ME, NH, NJ, NY, PA, RI, VT |
| **Plains** | Open country, mule deer mix | CO, MT, NM, OK, WY |
| **South Texas** | Late rut, unique genetics | TX |
| **Northern** | Short seasons, large deer | AK, ID, OR, WA |

---

**Thank you for using Iron Stag!**

*Happy Hunting! 🦌*

---

© 2026 Asgard Solutions. All rights reserved.
