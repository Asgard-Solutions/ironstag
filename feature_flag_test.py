#!/usr/bin/env python3
"""
Additional test to verify feature flag behavior for Phase 2 Empirical Calibration Admin APIs
"""

import requests
import json

# API Configuration
API_BASE_URL = "https://ai-confidence-boost.preview.emergentagent.com/api"

def test_feature_flag_behavior():
    """Test that endpoints work correctly when feature flag is enabled"""
    print("🔧 Testing Feature Flag Behavior")
    print("=" * 50)
    
    # Test that endpoints work when feature flag is enabled (current state)
    print("\n1. Testing with CALIBRATION_CURVES_ENABLED=true (current state)")
    
    # Test build-curves endpoint
    try:
        response = requests.post(
            f"{API_BASE_URL}/admin/calibration/build-curves",
            json={"dry_run": True},
            headers={"Content-Type": "application/json"}
        )
        
        if response.status_code == 200:
            print("✅ Build curves works with feature flag enabled")
        else:
            print(f"❌ Build curves failed: {response.status_code} - {response.text}")
    except Exception as e:
        print(f"❌ Build curves request failed: {e}")
    
    # Test activate-curve endpoint
    try:
        response = requests.post(
            f"{API_BASE_URL}/admin/calibration/activate-curve",
            json={"curve_id": "test-id"},
            headers={"Content-Type": "application/json"}
        )
        
        # Should return 400 because curve doesn't exist, not because feature is disabled
        if response.status_code == 400:
            data = response.json()
            if "not enabled" in data.get("detail", "").lower():
                print("❌ Activate curve shows feature disabled error (unexpected)")
            else:
                print("✅ Activate curve works with feature flag enabled (returns curve not found error)")
        else:
            print(f"❌ Activate curve unexpected response: {response.status_code} - {response.text}")
    except Exception as e:
        print(f"❌ Activate curve request failed: {e}")
    
    # Test recalibrate-scans endpoint
    try:
        response = requests.post(
            f"{API_BASE_URL}/admin/calibration/recalibrate-scans",
            json={"dry_run": True},
            headers={"Content-Type": "application/json"}
        )
        
        if response.status_code == 200:
            print("✅ Recalibrate scans works with feature flag enabled")
        else:
            print(f"❌ Recalibrate scans failed: {response.status_code} - {response.text}")
    except Exception as e:
        print(f"❌ Recalibrate scans request failed: {e}")
    
    print("\n📝 Note: To test feature flag disabled scenario:")
    print("   - Set CALIBRATION_CURVES_ENABLED=false in backend/.env")
    print("   - Restart backend service")
    print("   - All endpoints should return 400 'Empirical calibration curves are not enabled'")
    
    print("\n✅ Feature flag testing completed")

if __name__ == "__main__":
    test_feature_flag_behavior()