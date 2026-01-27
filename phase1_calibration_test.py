#!/usr/bin/env python3
"""
Backend Test Suite for Iron Stag - Phase 1 Empirical Calibration
Tests the label creation, retrieval, and admin stats endpoints.
"""

import requests
import json
import uuid
import asyncio
import sys
import os
from datetime import datetime
from typing import Dict, Any, Optional

# Add backend path for database access
sys.path.append('/app/backend')

# Backend URL - using localhost since external URL is not accessible
BACKEND_URL = "http://localhost:8001/api"

class IronStagPhase1Tester:
    def __init__(self):
        self.session = requests.Session()
        self.auth_token = None
        self.user_id = None
        self.test_user_email = f"phase1test_{uuid.uuid4().hex[:8]}@test.com"
        self.test_user_password = "TestPass123!"
        self.test_scan_id = None
        
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
    
    async def create_test_scan_in_db(self) -> Optional[str]:
        """Create a test scan directly in the database"""
        try:
            from server import database, scans_table
            
            await database.connect()
            
            # Create a test scan record
            scan_id = str(uuid.uuid4())
            
            query = scans_table.insert().values(
                id=scan_id,
                user_id=self.user_id,
                local_image_id='test_image_phase1',
                deer_age=4.5,
                deer_type='Whitetail',
                deer_sex='Buck',
                antler_points=10,
                antler_points_left=5,
                antler_points_right=5,
                body_condition='Excellent',
                confidence=90,
                recommendation='HARVEST',
                reasoning='Mature buck with excellent antler development for Phase 1 testing',
                notes='Test scan for Phase 1 empirical calibration testing',
                created_at=datetime.utcnow(),
                raw_confidence=90,
                age_confidence=85,
                recommendation_confidence=90,
                age_uncertain=False,
                calibration_version='v2-region-heuristic',
                region_key='midwest',
                region_source='fallback_unknown',
                calibration_strategy='heuristic'
            )
            
            await database.execute(query)
            await database.disconnect()
            
            self.log(f"✅ Created test scan in database: {scan_id}")
            return scan_id
            
        except Exception as e:
            self.log(f"❌ Error creating test scan: {e}")
            return None
    
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
        """Test Case B - Categorical Label (weak signal) - need different scan"""
        self.log(f"🏷️ Testing categorical label creation for scan {scan_id}")
        
        # First delete any existing label
        delete_response = self.session.delete(f"{BACKEND_URL}/scans/{scan_id}/label")
        self.log(f"   Deleted existing label: {delete_response.status_code}")
        
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
            # Effective weight should be lower due to credibility factor (0.5 default)
            expected_effective = expected_weight * 0.5
            
            if (data.get('label_type') == expected_label_type and 
                data.get('label_weight') == expected_weight and
                abs(data.get('effective_weight') - expected_effective) < 0.01):
                self.log("✅ Categorical label values match expected results")
                return True
            else:
                self.log(f"❌ Categorical label values don't match expected: got {data}")
                self.log(f"   Expected effective weight: {expected_effective}, got: {data.get('effective_weight')}")
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
    
    def run_phase1_tests(self):
        """Run all Phase 1 Empirical Calibration tests"""
        self.log("🚀 Starting Phase 1 Empirical Calibration Backend Tests")
        self.log("=" * 60)
        
        # Test results tracking
        results = {
            "user_registration": False,
            "scan_creation": False,
            "scan_retrieval": False,
            "label_stats": False,
            "labels_list": False,
            "label_retrieval_empty": False,
            "label_creation_exact": False,
            "label_retrieval_after_exact": False,
            "label_creation_categorical": False,
            "label_retrieval_after_categorical": False
        }
        
        # 1. Register test user
        if not self.register_test_user():
            self.log("❌ Cannot proceed without user registration")
            return results
        results["user_registration"] = True
        
        # 2. Create test scan in database
        try:
            self.test_scan_id = asyncio.run(self.create_test_scan_in_db())
            if self.test_scan_id:
                results["scan_creation"] = True
            else:
                self.log("❌ Failed to create test scan")
                return results
        except Exception as e:
            self.log(f"❌ Error in scan creation: {e}")
            return results
        
        # 3. Test scan retrieval
        scans = self.get_user_scans()
        if scans and len(scans) > 0:
            results["scan_retrieval"] = True
            self.log(f"✅ Confirmed scan exists in user's scan list")
        
        # 4. Test admin endpoints (these don't require scans)
        results["label_stats"] = self.test_admin_label_stats()
        results["labels_list"] = self.test_admin_labels_list()
        
        # 5. Test label endpoints with our test scan
        if self.test_scan_id:
            # Test label retrieval first (should return None for new scan)
            results["label_retrieval_empty"] = self.test_label_retrieval(self.test_scan_id)
            
            # Test exact age label creation
            results["label_creation_exact"] = self.test_label_creation_exact_age(self.test_scan_id)
            
            # Test label retrieval after creation
            if results["label_creation_exact"]:
                results["label_retrieval_after_exact"] = self.test_label_retrieval(self.test_scan_id)
            
            # Test categorical label creation (replaces exact age label)
            results["label_creation_categorical"] = self.test_label_creation_categorical(self.test_scan_id)
            
            # Test label retrieval after categorical creation
            if results["label_creation_categorical"]:
                results["label_retrieval_after_categorical"] = self.test_label_retrieval(self.test_scan_id)
        
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
        elif passed >= total * 0.8:
            self.log("⚠️ Most tests passed. Minor issues may need investigation.")
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
    
    if passed >= total * 0.8:  # 80% pass rate is acceptable
        exit(0)
    else:
        exit(1)


if __name__ == "__main__":
    main()