#!/usr/bin/env python3
"""
Iron Stag Backend API Testing - Phase 3 Adaptive Calibration
Testing the new Phase 3 Adaptive Calibration Admin API endpoints
"""

import requests
import json
import sys
from typing import Dict, Any

# API Configuration
API_BASE_URL = "https://ai-confidence-boost.preview.emergentagent.com/api"

class TestResults:
    def __init__(self):
        self.passed = 0
        self.failed = 0
        self.results = []
    
    def add_result(self, test_name: str, passed: bool, details: str = ""):
        self.results.append({
            "test": test_name,
            "passed": passed,
            "details": details
        })
        if passed:
            self.passed += 1
        else:
            self.failed += 1
    
    def print_summary(self):
        print(f"\n{'='*60}")
        print(f"TEST SUMMARY")
        print(f"{'='*60}")
        print(f"Total Tests: {self.passed + self.failed}")
        print(f"Passed: {self.passed}")
        print(f"Failed: {self.failed}")
        print(f"Success Rate: {(self.passed/(self.passed + self.failed)*100):.1f}%")
        
        if self.failed > 0:
            print(f"\n{'='*60}")
            print(f"FAILED TESTS:")
            print(f"{'='*60}")
            for result in self.results:
                if not result["passed"]:
                    print(f"❌ {result['test']}")
                    if result["details"]:
                        print(f"   Details: {result['details']}")

def test_phase3_status_endpoint(results: TestResults):
    """Test GET /api/admin/calibration/phase3/status - should always work"""
    print("\n🔍 Testing Phase 3 Status Endpoint...")
    
    try:
        response = requests.get(f"{API_BASE_URL}/admin/calibration/phase3/status")
        
        if response.status_code == 200:
            data = response.json()
            
            # Verify expected fields
            expected_fields = ["enabled", "jobs", "config"]
            missing_fields = [field for field in expected_fields if field not in data]
            
            if missing_fields:
                results.add_result(
                    "Phase3 Status - Response Structure", 
                    False, 
                    f"Missing fields: {missing_fields}"
                )
            else:
                results.add_result("Phase3 Status - Response Structure", True)
            
            # Verify enabled is false (ship dark mode)
            if data.get("enabled") == False:
                results.add_result("Phase3 Status - Enabled False", True)
                print(f"✅ Status endpoint working - enabled: {data.get('enabled')}")
            else:
                results.add_result(
                    "Phase3 Status - Enabled False", 
                    False, 
                    f"Expected enabled=false, got {data.get('enabled')}"
                )
            
            # Verify jobs structure
            jobs = data.get("jobs", {})
            expected_job_fields = ["drift_detection_running", "maturity_computation_running", "recommendation_generation_running"]
            missing_job_fields = [field for field in expected_job_fields if field not in jobs]
            
            if missing_job_fields:
                results.add_result(
                    "Phase3 Status - Jobs Structure", 
                    False, 
                    f"Missing job fields: {missing_job_fields}"
                )
            else:
                results.add_result("Phase3 Status - Jobs Structure", True)
            
            # Verify config structure
            config = data.get("config", {})
            if config:
                results.add_result("Phase3 Status - Config Present", True)
            else:
                results.add_result("Phase3 Status - Config Present", False, "Config object missing")
                
            print(f"Status Response: {json.dumps(data, indent=2)}")
                
        else:
            results.add_result(
                "Phase3 Status - Endpoint Access", 
                False, 
                f"Expected 200, got {response.status_code}: {response.text}"
            )
            
    except Exception as e:
        results.add_result("Phase3 Status - Endpoint Access", False, f"Exception: {str(e)}")

def test_flag_gated_endpoints(results: TestResults):
    """Test that flag-gated endpoints return 400 when CALIBRATION_ADAPTIVE_ENABLED=false"""
    print("\n🔍 Testing Flag-Gated Endpoints (should return 400)...")
    
    # GET endpoints that should be flag-gated
    get_endpoints = [
        "/admin/calibration/drift",
        "/admin/calibration/maturity", 
        "/admin/calibration/recommendations"
    ]
    
    for endpoint in get_endpoints:
        try:
            response = requests.get(f"{API_BASE_URL}{endpoint}")
            
            if response.status_code == 400:
                try:
                    error_data = response.json()
                    error_message = error_data.get("detail", "")
                    
                    if "Adaptive calibration is not enabled" in error_message:
                        results.add_result(f"Flag Gate - {endpoint}", True)
                        print(f"✅ {endpoint} correctly blocked with proper error message")
                    else:
                        results.add_result(
                            f"Flag Gate - {endpoint}", 
                            False, 
                            f"Wrong error message: {error_message}"
                        )
                except:
                    results.add_result(
                        f"Flag Gate - {endpoint}", 
                        False, 
                        f"400 status but invalid JSON response"
                    )
            else:
                results.add_result(
                    f"Flag Gate - {endpoint}", 
                    False, 
                    f"Expected 400, got {response.status_code}: {response.text}"
                )
                
        except Exception as e:
            results.add_result(f"Flag Gate - {endpoint}", False, f"Exception: {str(e)}")

def test_flag_gated_post_endpoints(results: TestResults):
    """Test POST endpoints that should be flag-gated"""
    print("\n🔍 Testing Flag-Gated POST Endpoints (should return 400)...")
    
    # POST endpoints with their required payloads
    post_endpoints = [
        {
            "endpoint": "/admin/calibration/phase3/run-drift",
            "payload": {"dry_run": True, "time_window_days": 30}
        },
        {
            "endpoint": "/admin/calibration/phase3/run-maturity", 
            "payload": {"dry_run": True}
        },
        {
            "endpoint": "/admin/calibration/phase3/run-recommendations",
            "payload": {"dry_run": True}
        }
    ]
    
    for endpoint_config in post_endpoints:
        endpoint = endpoint_config["endpoint"]
        payload = endpoint_config["payload"]
        
        try:
            response = requests.post(
                f"{API_BASE_URL}{endpoint}",
                json=payload,
                headers={"Content-Type": "application/json"}
            )
            
            if response.status_code == 400:
                try:
                    error_data = response.json()
                    error_message = error_data.get("detail", "")
                    
                    if "Adaptive calibration is not enabled" in error_message:
                        results.add_result(f"Flag Gate POST - {endpoint}", True)
                        print(f"✅ {endpoint} correctly blocked with proper error message")
                    else:
                        results.add_result(
                            f"Flag Gate POST - {endpoint}", 
                            False, 
                            f"Wrong error message: {error_message}"
                        )
                except:
                    results.add_result(
                        f"Flag Gate POST - {endpoint}", 
                        False, 
                        f"400 status but invalid JSON response"
                    )
            else:
                results.add_result(
                    f"Flag Gate POST - {endpoint}", 
                    False, 
                    f"Expected 400, got {response.status_code}: {response.text}"
                )
                
        except Exception as e:
            results.add_result(f"Flag Gate POST - {endpoint}", False, f"Exception: {str(e)}")

def test_endpoint_accessibility(results: TestResults):
    """Test that all endpoints are accessible (no 404s)"""
    print("\n🔍 Testing Endpoint Accessibility...")
    
    # Test that endpoints exist (should not return 404)
    all_endpoints = [
        "/admin/calibration/phase3/status",
        "/admin/calibration/drift",
        "/admin/calibration/maturity",
        "/admin/calibration/recommendations"
    ]
    
    for endpoint in all_endpoints:
        try:
            response = requests.get(f"{API_BASE_URL}{endpoint}")
            
            if response.status_code == 404:
                results.add_result(
                    f"Endpoint Exists - {endpoint}", 
                    False, 
                    "Endpoint not found (404)"
                )
            else:
                results.add_result(f"Endpoint Exists - {endpoint}", True)
                
        except Exception as e:
            results.add_result(f"Endpoint Exists - {endpoint}", False, f"Exception: {str(e)}")

def main():
    print("🚀 Starting Iron Stag Phase 3 Adaptive Calibration API Tests")
    print(f"🌐 Testing against: {API_BASE_URL}")
    print(f"📋 Expected: CALIBRATION_ADAPTIVE_ENABLED=false (ship dark mode)")
    
    results = TestResults()
    
    # Run all test suites
    test_endpoint_accessibility(results)
    test_phase3_status_endpoint(results)
    test_flag_gated_endpoints(results)
    test_flag_gated_post_endpoints(results)
    
    # Print detailed results
    print(f"\n{'='*60}")
    print(f"DETAILED TEST RESULTS")
    print(f"{'='*60}")
    
    for result in results.results:
        status = "✅" if result["passed"] else "❌"
        print(f"{status} {result['test']}")
        if result["details"] and not result["passed"]:
            print(f"   └─ {result['details']}")
    
    # Print summary
    results.print_summary()
    
    # Return appropriate exit code
    return 0 if results.failed == 0 else 1

if __name__ == "__main__":
    exit_code = main()
    sys.exit(exit_code)