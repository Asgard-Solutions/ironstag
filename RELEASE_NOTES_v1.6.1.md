# Iron Stag v1.6.1 Release Notes
**Version 1.6.1**  
April 15, 2026

## Featured
**iOS, Android**
- Bug Fix
- Security Enhancement
- Improvement

---

## 🐛 Bug Fixes

### Critical Fixes
- **Fixed authentication security vulnerability** – Added protection against brute force login attempts
- **Resolved scan processing errors** – Fixed crashes when processing photos with invalid date information
- **Fixed offline queue sync issues** – Scans now properly sync when returning to cell service
- **Corrected in-app purchase errors** – Resolved subscription purchase failures on some devices

### App Stability
- **Enhanced error recovery** – App now gracefully handles unexpected errors with a "Try Again" option
- **Improved crash reporting** – Better error tracking to help us identify and fix issues faster
- **Fixed network transition handling** – Smoother experience when moving between WiFi and cellular
- **Resolved confidence calculation issues** – Age confidence now displays more accurately

---

## 🔒 Security Enhancements

### Account Protection
- **Rate limiting on login attempts** – Temporary lockout after multiple failed login attempts
- **Enhanced admin endpoint security** – Better protection for administrative functions
- **Improved error data privacy** – Crash reports now exclude sensitive information

---

## ✨ Improvements

### Reliability & Performance
- **Better offline-to-online transitions** – Automatic scan sync when network is restored
- **Enhanced age estimation accuracy** – Improved confidence calculations for borderline cases
- **More robust date handling** – Better processing of photo timestamps and hunting dates
- **Optimized database performance** – Faster loading of scan history and calibration data

### User Experience
- **Improved error messages** – Clearer explanations when something goes wrong
- **Better subscription handling** – More reliable premium feature activation
- **Enhanced update detection** – Improved checking for new app versions
- **Smoother navigation** – Fixed several edge cases causing navigation issues

### Regional Analysis
- **Better state recognition** – Improved handling of location names and abbreviations
- **Enhanced season detection** – More accurate rut timing for regional analysis
- **Improved calibration accuracy** – Better age estimates based on your hunting region

---

## 🔧 Technical Improvements

### Backend Stability
- **Improved error handling** – Better recovery from temporary service issues
- **Enhanced logging** – More detailed error tracking for faster issue resolution
- **Better resource management** – Optimized memory usage and performance
- **Improved API reliability** – More robust handling of network requests

### Configuration Management
- **Better feature flag handling** – Improved management of experimental features
- **Enhanced environment configuration** – More flexible deployment options
- **Improved calibration controls** – Better management of AI model updates

---

## 🚀 Performance Optimizations

- Faster scan processing for photos with complex metadata
- Improved memory usage during offline queue operations
- Optimized database queries for scan history loading
- Better caching of user preferences and settings
- Reduced network overhead for subscription status checks

---

## 📋 Requirements

- **iOS**: 13.0 or later
- **Android**: 10.0 (API level 29) or later
- Internet connection for analysis (improved offline capabilities)
- Camera access for deer scanning
- Location access for regional calibration (optional)

---

## 🔄 Update Information

This is a **recommended update** that improves app stability and fixes several important issues. The update is backward compatible with v1.6.0 - no data migration required.

### What to Expect:
- Existing scans and data remain unchanged
- Premium subscriptions continue uninterrupted  
- Offline queued scans will sync properly after update
- All existing tags and favorites are preserved

---

## 🏆 Coming Soon

We're continuing to work on exciting new features for the next major release:
- Enhanced photo analysis capabilities
- Additional scoring system options
- More detailed regional customization
- Advanced filtering and search options

---

## 💬 Support & Feedback

Found a bug or have suggestions? We're here to help:

- **Email**: support@ironstag.com
- **In-App Support**: Settings → Help & Support
- **FAQ**: Available in app and at [ironstag.com/faq](https://ironstag.com/faq)

---

## 🙏 Thank You

This patch release addresses feedback from our hunting community. Your reports help us make Iron Stag better for everyone.

**Happy Hunting!** 🦌

*The Iron Stag Team*

---

## Version History
- **v1.6.1** (April 15, 2026) - Bug fixes and security improvements
- **v1.6.0** (April 15, 2026) - Boone & Crockett Scoring, Learn Section, Enhanced UI
- **v1.2.0** (January 30, 2026) - Cloud sync, offline scanning, doe aging improvements