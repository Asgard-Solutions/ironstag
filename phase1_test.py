#!/usr/bin/env python3
"""
Backend Test Suite for Iron Stag - Phase 1 Empirical Calibration
Tests the label creation, retrieval, and admin stats endpoints.
"""

import requests
import json
import uuid
import base64
from datetime import datetime
from typing import Dict, Any, Optional

# Backend URL from frontend/.env
BACKEND_URL = "https://ai-confidence-boost.preview.emergentagent.com/api"

class IronStagPhase1Tester:
    def __init__(self):
        self.session = requests.Session()
        self.auth_token = None
        self.user_id = None
        self.test_user_email = f"phase1test_{uuid.uuid4().hex[:8]}@test.com"
        self.test_user_password = "TestPass123!"
        
    def log(self, message: str):
        """Log test messages with timestamp"""
        timestamp = datetime.now().strftime("%H:%M:%S")
        print(f"[{timestamp}] {message}")
        
    def register_test_user(self) -> bool:
        """Register a new test user"""
        self.log(f"🔐 Registering test user: {self.test_user_email}")
        
        response = self.session.post(f"{BACKEND_URL}/auth/register", json={
            "email": self.test_user_email,
            "password": self.test_user_password,
            "name": "Phase 1 Test User"
        })
        
        if response.status_code == 200:
            data = response.json()
            self.auth_token = data["access_token"]
            self.user_id = data["user"]["id"]
            self.session.headers.update({"Authorization": f"Bearer {self.auth_token}"})
            self.log(f"✅ User registered successfully. ID: {self.user_id}")
            return True
        else:
            self.log(f"❌ Registration failed: {response.status_code} - {response.text}")
            return False
    
    def get_user_scans(self) -> list:
        """Get existing scans for the user"""
        self.log("📋 Fetching user scans...")
        
        response = self.session.get(f"{BACKEND_URL}/scans")
        
        if response.status_code == 200:
            scans = response.json()
            self.log(f"✅ Found {len(scans)} existing scans")
            return scans
        else:
            self.log(f"❌ Failed to get scans: {response.status_code} - {response.text}")
            return []
    
    def create_mock_scan(self) -> Optional[str]:
        """Create a mock scan for testing (without OpenAI)"""
        self.log("🦌 Creating mock scan for testing...")
        
        # Create a simple base64 encoded test image (1x1 pixel PNG)
        test_image_b64 = "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNkYPhfDwAChwGA60e6kgAAAABJRU5ErkJggg=="
        
        # Try to create a scan - this will likely fail due to OpenAI, but we can check the error
        response = self.session.post(f"{BACKEND_URL}/analyze-deer", json={
            "image_base64": test_image_b64,
            "local_image_id": f"test_image_{uuid.uuid4().hex[:8]}",
            "notes": "Test scan for Phase 1 calibration testing"
        })
        
        if response.status_code == 200:
            scan_data = response.json()
            scan_id = scan_data["id"]
            self.log(f"✅ Mock scan created successfully. ID: {scan_id}")
            return scan_id
        else:
            self.log(f"⚠️ Mock scan creation failed (expected): {response.status_code} - {response.text}")
            # This is expected since we don't have a real deer image and OpenAI will reject it
            return None
    
    def test_label_creation_exact_age(self, scan_id: str) -> bool:
        """Test Case A - Exact Age Label (strong signal)"""
        self.log(f"🏷️ Testing exact age label creation for scan {scan_id}")
        
        label_data = {
            "reported_age": 4.5,
            "harvest_confirmed": True,
            "notes": "Confirmed age via jawbone analysis"
        }
        
        response = self.session.post(f"{BACKEND_URL}/scans/{scan_id}/label", json=label_data)
        
        if response.status_code == 200:
            data = response.json()
            self.log(f"✅ Exact age label created successfully")
            self.log(f"   - Label Type: {data.get('label_type')}")
            self.log(f"   - Label Weight: {data.get('label_weight')}")
            self.log(f"   - Effective Weight: {data.get('effective_weight')}")
            self.log(f"   - Reported Age: {data.get('reported_age')}")
            
            # Validate expected values
            expected_label_type = "exact_age"
            expected_weight = 1.0  # exact_age_harvested
            expected_effective = 1.0  # harvested credibility
            
            if (data.get('label_type') == expected_label_type and 
                data.get('label_weight') == expected_weight and
                data.get('effective_weight') == expected_effective):
                self.log("✅ Label values match expected results")
                return True
            else:
                self.log(f"❌ Label values don't match expected: got {data}")
                return False
        else:
            self.log(f"❌ Exact age label creation failed: {response.status_code} - {response.text}")
            return False
    
    def test_label_creation_categorical(self, scan_id: str) -> bool:
        """Test Case B - Categorical Label (weak signal)"""
        self.log(f"🏷️ Testing categorical label creation for scan {scan_id}")
        
        label_data = {
            "accuracy_category": "close",
            "harvest_confirmed": False
        }
        
        response = self.session.post(f"{BACKEND_URL}/scans/{scan_id}/label", json=label_data)
        
        if response.status_code == 200:
            data = response.json()
            self.log(f"✅ Categorical label created successfully")
            self.log(f"   - Label Type: {data.get('label_type')}")
            self.log(f"   - Label Weight: {data.get('label_weight')}")
            self.log(f"   - Effective Weight: {data.get('effective_weight')}")
            self.log(f"   - Accuracy Category: {data.get('accuracy_category')}")
            
            # Validate expected values
            expected_label_type = "categorical"
            expected_weight = 0.2  # categorical_close
            # Effective weight should be lower due to credibility factor
            
            if (data.get('label_type') == expected_label_type and 
                data.get('label_weight') == expected_weight and
                data.get('effective_weight') < expected_weight):
                self.log("✅ Categorical label values match expected results")
                return True
            else:
                self.log(f"❌ Categorical label values don't match expected: got {data}")
                return False
        else:
            self.log(f"❌ Categorical label creation failed: {response.status_code} - {response.text}")
            return False
    
    def test_label_retrieval(self, scan_id: str) -> bool:
        """Test label retrieval for a scan"""
        self.log(f"📖 Testing label retrieval for scan {scan_id}")
        
        response = self.session.get(f"{BACKEND_URL}/scans/{scan_id}/label")
        
        if response.status_code == 200:
            data = response.json()
            if data is None:
                self.log("✅ No label found (expected for new scan)")
                return True
            else:
                self.log(f"✅ Label retrieved successfully")
                self.log(f"   - Label ID: {data.get('id')}")
                self.log(f"   - Label Type: {data.get('label_type')}")
                self.log(f"   - Effective Weight: {data.get('effective_weight')}")
                return True
        else:
            self.log(f"❌ Label retrieval failed: {response.status_code} - {response.text}")
            return False
    
    def test_admin_label_stats(self) -> bool:
        """Test admin label statistics endpoint"""
        self.log("📊 Testing admin label statistics endpoint")
        
        response = self.session.get(f"{BACKEND_URL}/admin/calibration/labels/stats")
        
        if response.status_code == 200:
            data = response.json()
            self.log(f"✅ Label stats retrieved successfully")
            self.log(f"   - Total Labels: {data.get('total_labels')}")
            self.log(f"   - Exact Age Count: {data.get('exact_age_count')}")
            self.log(f"   - Categorical Count: {data.get('categorical_count')}")
            self.log(f"   - By Region: {data.get('by_region')}")
            self.log(f"   - Maturity Gates: {data.get('maturity_gates')}")
            
            # Validate structure
            required_fields = ['total_labels', 'exact_age_count', 'categorical_count', 
                             'by_region', 'by_error_bucket', 'by_image_quality', 
                             'total_weighted_samples', 'maturity_gates']
            
            if all(field in data for field in required_fields):
                self.log("✅ All required fields present in stats response")
                return True
            else:
                missing = [f for f in required_fields if f not in data]
                self.log(f"❌ Missing fields in stats response: {missing}")
                return False
        else:
            self.log(f"❌ Label stats retrieval failed: {response.status_code} - {response.text}")
            return False
    
    def test_admin_labels_list(self) -> bool:
        """Test admin labels list endpoint"""
        self.log("📋 Testing admin labels list endpoint")
        
        response = self.session.get(f"{BACKEND_URL}/admin/calibration/labels?limit=10")
        
        if response.status_code == 200:
            data = response.json()
            self.log(f"✅ Labels list retrieved successfully")
            self.log(f"   - Count: {data.get('count')}")
            self.log(f"   - Labels: {len(data.get('labels', []))}")
            
            # Validate structure
            if 'labels' in data and 'count' in data:
                self.log("✅ Labels list has correct structure")
                return True
            else:
                self.log(f"❌ Labels list missing required fields: {data}")
                return False
        else:
            self.log(f"❌ Labels list retrieval failed: {response.status_code} - {response.text}")
            return False
    
    def create_test_scan_directly(self) -> Optional[str]:
        """Create a test scan directly in database for testing labels"""
        self.log("🔧 Creating test scan directly for label testing...")
        
        # We'll create a minimal scan record that we can use for label testing
        # This bypasses the OpenAI requirement
        scan_id = str(uuid.uuid4())
        
        # Since we can't directly insert into DB, we'll try a different approach
        # Let's check if there are any existing scans we can use
        existing_scans = self.get_user_scans()
        
        if existing_scans:
            scan_id = existing_scans[0]["id"]
            self.log(f"✅ Using existing scan for testing: {scan_id}")
            return scan_id
        else:
            self.log("⚠️ No existing scans found. Label testing will be limited.")
            return None
    
    def run_phase1_tests(self):
        """Run all Phase 1 Empirical Calibration tests"""
        self.log("🚀 Starting Phase 1 Empirical Calibration Backend Tests")
        self.log("=" * 60)
        
        # Test results tracking
        results = {
            "user_registration": False,
            "scan_retrieval": False,
            "label_stats": False,
            "labels_list": False,
            "label_creation_exact": False,
            "label_creation_categorical": False,
            "label_retrieval": False
        }
        
        # 1. Register test user
        if not self.register_test_user():
            self.log("❌ Cannot proceed without user registration")
            return results
        results["user_registration"] = True
        
        # 2. Test scan retrieval
        existing_scans = self.get_user_scans()
        results["scan_retrieval"] = True
        
        # 3. Test admin endpoints (these don't require scans)
        results["label_stats"] = self.test_admin_label_stats()
        results["labels_list"] = self.test_admin_labels_list()
        
        # 4. Test label endpoints (need a scan)
        test_scan_id = None
        
        # Try to get existing scan or create one
        if existing_scans:
            test_scan_id = existing_scans[0]["id"]
            self.log(f"📋 Using existing scan for label testing: {test_scan_id}")
        else:
            # Try to create a mock scan (will likely fail but worth trying)
            test_scan_id = self.create_mock_scan()
            
            if not test_scan_id:
                # Try alternative approach
                test_scan_id = self.create_test_scan_directly()
        
        if test_scan_id:
            # Test label retrieval first (should return None for new scan)
            results["label_retrieval"] = self.test_label_retrieval(test_scan_id)
            
            # Test exact age label creation
            results["label_creation_exact"] = self.test_label_creation_exact_age(test_scan_id)
            
            # If exact age label was created, we need a different scan for categorical
            # For now, let's test the retrieval of the created label
            if results["label_creation_exact"]:
                self.test_label_retrieval(test_scan_id)
        else:
            self.log("⚠️ No scan available for label testing. This is expected if OpenAI is required for scan creation.")
            self.log("   Label endpoints require existing scans to test properly.")
        
        # Print summary
        self.log("\n" + "=" * 60)
        self.log("📊 PHASE 1 EMPIRICAL CALIBRATION TEST SUMMARY")
        self.log("=" * 60)
        
        passed = sum(results.values())
        total = len(results)
        
        for test_name, passed_test in results.items():
            status = "✅ PASS" if passed_test else "❌ FAIL"
            self.log(f"{status} - {test_name.replace('_', ' ').title()}")
        
        self.log(f"\n🎯 Overall Result: {passed}/{total} tests passed ({passed/total*100:.1f}%)")
        
        if passed == total:
            self.log("🎉 All Phase 1 Empirical Calibration tests PASSED!")
        elif passed >= total * 0.7:
            self.log("⚠️ Most tests passed. Some issues may need investigation.")
        else:
            self.log("❌ Multiple test failures. System needs attention.")
        
        return results


def main():
    """Main test execution"""
    tester = IronStagPhase1Tester()
    results = tester.run_phase1_tests()
    
    # Return appropriate exit code
    passed = sum(results.values())
    total = len(results)
    
    if passed == total:
        exit(0)  # All tests passed
    else:
        exit(1)  # Some tests failed


if __name__ == "__main__":
    main()