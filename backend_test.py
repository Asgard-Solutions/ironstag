#!/usr/bin/env python3
"""
Backend API Testing for Iron Stag - Confidence Separation & Score Audit Trail
Tests the following requirements:
1. API Response Structure (confidence, confidence_breakdown, score_audit)
2. confidence_breakdown values (age can be null, recommendation is 0-100)
3. Legacy backward compatibility (confidence field still present)
4. score_audit column exists in DB
5. Auth endpoints rate limiting (429 after 10+ attempts)
6. Admin endpoint protection (X-Admin-Secret header required)
"""

import requests
import json
import time
from typing import Dict, Any, Optional

# Backend URL
BASE_URL = "http://localhost:8001/api"
ADMIN_SECRET = "dev-admin-secret-change-me"

# Test credentials - newly registered user for testing
TEST_EMAIL = "confidence_test@test.com"
TEST_PASSWORD = "TestPass123!"

# Test results tracking
test_results = {
    "passed": [],
    "failed": [],
    "warnings": []
}

def log_test(test_name: str, passed: bool, message: str = ""):
    """Log test result"""
    if passed:
        test_results["passed"].append(f"✅ {test_name}: {message}")
        print(f"✅ {test_name}: {message}")
    else:
        test_results["failed"].append(f"❌ {test_name}: {message}")
        print(f"❌ {test_name}: {message}")

def log_warning(test_name: str, message: str):
    """Log warning"""
    test_results["warnings"].append(f"⚠️  {test_name}: {message}")
    print(f"⚠️  {test_name}: {message}")

def login(email: str, password: str) -> Optional[str]:
    """Login and return JWT token"""
    try:
        response = requests.post(
            f"{BASE_URL}/auth/login",
            json={"email": email, "password": password}
        )
        if response.status_code == 200:
            data = response.json()
            # Try both "token" and "access_token" for compatibility
            return data.get("token") or data.get("access_token")
        else:
            print(f"Login failed: {response.status_code} - {response.text}")
            return None
    except Exception as e:
        print(f"Login error: {e}")
        return None

def test_api_response_structure(token: str):
    """Test 1: Verify API response structure for GET /api/scans/{scan_id}"""
    print("\n" + "="*80)
    print("TEST 1: API Response Structure")
    print("="*80)
    
    # First, get list of scans
    headers = {"Authorization": f"Bearer {token}"}
    response = requests.get(f"{BASE_URL}/scans", headers=headers)
    
    if response.status_code != 200:
        log_test("Get scans list", False, f"Failed to get scans: {response.status_code}")
        return
    
    scans = response.json()
    if not scans or len(scans) == 0:
        log_warning("Get scans list", "No scans found for user. Creating a test scan would require image upload.")
        return
    
    # Test with first scan
    scan_id = scans[0]["id"]
    response = requests.get(f"{BASE_URL}/scans/{scan_id}", headers=headers)
    
    if response.status_code != 200:
        log_test("Get scan by ID", False, f"Failed to get scan: {response.status_code}")
        return
    
    scan = response.json()
    
    # Check for required fields
    has_confidence = "confidence" in scan
    has_confidence_breakdown = "confidence_breakdown" in scan
    has_score_audit = "score_audit" in scan
    
    log_test("API Response - confidence field", has_confidence, 
             f"confidence field present: {scan.get('confidence')}")
    log_test("API Response - confidence_breakdown field", has_confidence_breakdown,
             f"confidence_breakdown present: {scan.get('confidence_breakdown')}")
    log_test("API Response - score_audit field", has_score_audit,
             f"score_audit present: {scan.get('score_audit') is not None}")
    
    # Verify confidence_breakdown structure if present
    if has_confidence_breakdown and scan.get("confidence_breakdown") is not None:
        breakdown = scan["confidence_breakdown"]
        has_age = "age" in breakdown
        has_recommendation = "recommendation" in breakdown
        
        log_test("confidence_breakdown structure", has_age and has_recommendation,
                 f"Has age and recommendation keys: age={breakdown.get('age')}, recommendation={breakdown.get('recommendation')}")
        
        # Check that age can be null
        age_value = breakdown.get("age")
        if age_value is None:
            log_test("confidence_breakdown.age can be null", True, "age is null (expected for unavailable age confidence)")
        elif isinstance(age_value, int) and 0 <= age_value <= 100:
            log_test("confidence_breakdown.age value", True, f"age={age_value} (valid 0-100 range)")
        else:
            log_test("confidence_breakdown.age value", False, f"age={age_value} (invalid value)")
        
        # Check recommendation is 0-100
        rec_value = breakdown.get("recommendation")
        if isinstance(rec_value, int) and 0 <= rec_value <= 100:
            log_test("confidence_breakdown.recommendation value", True, f"recommendation={rec_value} (valid 0-100 range)")
        else:
            log_test("confidence_breakdown.recommendation value", False, f"recommendation={rec_value} (invalid value)")
    elif scan.get("confidence_breakdown") is None:
        log_warning("confidence_breakdown", "confidence_breakdown is null (legacy scan without calibration data)")
    
    # Verify score_audit structure if present
    if has_score_audit and scan.get("score_audit") is not None:
        audit = scan["score_audit"]
        has_version = "version" in audit
        has_steps = "steps" in audit
        has_final_scores = "final_scores" in audit
        
        log_test("score_audit structure", has_version and has_steps and has_final_scores,
                 f"Has version, steps, and final_scores keys")
        
        if has_steps and isinstance(audit.get("steps"), list):
            log_test("score_audit.steps", True, f"steps is a list with {len(audit['steps'])} entries")
        
        if has_final_scores and isinstance(audit.get("final_scores"), dict):
            final = audit["final_scores"]
            log_test("score_audit.final_scores", True, 
                     f"final_scores: age_confidence={final.get('age_confidence')}, recommendation_confidence={final.get('recommendation_confidence')}")
    elif scan.get("score_audit") is None:
        log_warning("score_audit", "score_audit is null (legacy scan without audit trail)")
    
    # Test legacy backward compatibility
    confidence_value = scan.get("confidence")
    if confidence_value is not None:
        log_test("Legacy compatibility - confidence field", True, 
                 f"confidence field contains value: {confidence_value}")
        
        # Verify confidence matches recommendation_confidence from breakdown
        if scan.get("confidence_breakdown") and scan["confidence_breakdown"].get("recommendation") is not None:
            rec_conf = scan["confidence_breakdown"]["recommendation"]
            if confidence_value == rec_conf:
                log_test("Legacy compatibility - confidence value", True,
                         f"confidence ({confidence_value}) matches recommendation_confidence ({rec_conf})")
            else:
                log_test("Legacy compatibility - confidence value", False,
                         f"confidence ({confidence_value}) does NOT match recommendation_confidence ({rec_conf})")

def test_database_score_audit_column():
    """Test 4: Verify score_audit column exists in database"""
    print("\n" + "="*80)
    print("TEST 4: Database Schema - score_audit Column")
    print("="*80)
    
    try:
        import os
        from dotenv import load_dotenv
        import asyncio
        from databases import Database
        
        # Load environment
        load_dotenv('/app/backend/.env')
        DATABASE_URL = os.environ.get('DATABASE_URL', '')
        
        async def check_column():
            database = Database(DATABASE_URL)
            await database.connect()
            
            query = """
            SELECT column_name, data_type 
            FROM information_schema.columns 
            WHERE table_name='scans' AND column_name='score_audit'
            """
            result = await database.fetch_one(query)
            
            await database.disconnect()
            return result
        
        result = asyncio.run(check_column())
        
        if result:
            log_test("Database - score_audit column", True, 
                     f"Column exists with type: {result[1]}")
        else:
            log_test("Database - score_audit column", False, 
                     "Column does not exist in scans table")
    
    except Exception as e:
        log_test("Database - score_audit column", False, f"Error checking database: {e}")

def test_auth_rate_limiting():
    """Test 5: Auth endpoints rate limiting (429 after 10+ attempts)"""
    print("\n" + "="*80)
    print("TEST 5: Auth Rate Limiting")
    print("="*80)
    
    # Try to login with wrong credentials multiple times
    wrong_email = f"ratelimit_test_{int(time.time())}@test.com"
    wrong_password = "wrongpassword123"
    
    attempt_count = 0
    rate_limited = False
    
    print(f"Attempting 12 rapid login attempts with wrong credentials...")
    
    for i in range(12):
        try:
            response = requests.post(
                f"{BASE_URL}/auth/login",
                json={"email": wrong_email, "password": wrong_password},
                timeout=5
            )
            attempt_count += 1
            
            if response.status_code == 429:
                rate_limited = True
                log_test("Rate limiting - 429 response", True, 
                         f"Rate limited after {attempt_count} attempts")
                break
            elif response.status_code == 400:
                # Expected for wrong credentials
                pass
            else:
                print(f"  Attempt {i+1}: Status {response.status_code}")
        
        except Exception as e:
            log_test("Rate limiting test", False, f"Error during test: {e}")
            return
    
    if not rate_limited:
        log_test("Rate limiting - 429 response", False, 
                 f"Did not receive 429 after {attempt_count} attempts")
    
    # Verify rate limit is per-IP (same IP should still be limited)
    try:
        response = requests.post(
            f"{BASE_URL}/auth/login",
            json={"email": wrong_email, "password": wrong_password},
            timeout=5
        )
        
        if response.status_code == 429:
            log_test("Rate limiting - per-IP enforcement", True, 
                     "Rate limit persists for same IP")
        else:
            log_test("Rate limiting - per-IP enforcement", False, 
                     f"Expected 429, got {response.status_code}")
    except Exception as e:
        log_test("Rate limiting - per-IP enforcement", False, f"Error: {e}")

def test_admin_endpoint_protection():
    """Test 6: Admin endpoint protection (X-Admin-Secret header required)"""
    print("\n" + "="*80)
    print("TEST 6: Admin Endpoint Protection")
    print("="*80)
    
    # Test without header
    response = requests.get(f"{BASE_URL}/admin/calibration/labels/stats")
    
    if response.status_code in [403, 503]:
        log_test("Admin protection - no header", True, 
                 f"Correctly rejected with {response.status_code}: {response.json().get('detail', '')}")
    else:
        log_test("Admin protection - no header", False, 
                 f"Expected 403/503, got {response.status_code}")
    
    # Test with wrong header
    response = requests.get(
        f"{BASE_URL}/admin/calibration/labels/stats",
        headers={"X-Admin-Secret": "wrong-secret"}
    )
    
    if response.status_code == 403:
        log_test("Admin protection - wrong header", True, 
                 f"Correctly rejected with 403: {response.json().get('detail', '')}")
    else:
        log_test("Admin protection - wrong header", False, 
                 f"Expected 403, got {response.status_code}")
    
    # Test with correct header
    response = requests.get(
        f"{BASE_URL}/admin/calibration/labels/stats",
        headers={"X-Admin-Secret": ADMIN_SECRET}
    )
    
    if response.status_code == 200:
        log_test("Admin protection - correct header", True, 
                 f"Successfully accessed with correct header")
        
        # Verify response structure
        data = response.json()
        if "total_labels" in data:
            log_test("Admin endpoint response", True, 
                     f"Response contains expected data: total_labels={data.get('total_labels')}")
    else:
        log_test("Admin protection - correct header", False, 
                 f"Expected 200, got {response.status_code}: {response.text}")

def print_summary():
    """Print test summary"""
    print("\n" + "="*80)
    print("TEST SUMMARY")
    print("="*80)
    
    print(f"\n✅ PASSED: {len(test_results['passed'])}")
    for result in test_results['passed']:
        print(f"  {result}")
    
    if test_results['warnings']:
        print(f"\n⚠️  WARNINGS: {len(test_results['warnings'])}")
        for result in test_results['warnings']:
            print(f"  {result}")
    
    if test_results['failed']:
        print(f"\n❌ FAILED: {len(test_results['failed'])}")
        for result in test_results['failed']:
            print(f"  {result}")
    
    print("\n" + "="*80)
    total_tests = len(test_results['passed']) + len(test_results['failed'])
    success_rate = (len(test_results['passed']) / total_tests * 100) if total_tests > 0 else 0
    print(f"SUCCESS RATE: {success_rate:.1f}% ({len(test_results['passed'])}/{total_tests})")
    print("="*80)

def main():
    print("="*80)
    print("Iron Stag Backend Testing - Confidence Separation & Score Audit Trail")
    print("="*80)
    
    # Login
    print("\nLogging in...")
    token = login(TEST_EMAIL, TEST_PASSWORD)
    
    if not token:
        print("❌ Failed to login. Cannot proceed with tests.")
        return
    
    print(f"✅ Login successful")
    
    # Run tests
    test_api_response_structure(token)
    test_database_score_audit_column()
    test_auth_rate_limiting()
    test_admin_endpoint_protection()
    
    # Print summary
    print_summary()
    
    # Exit with appropriate code
    if test_results['failed']:
        exit(1)
    else:
        exit(0)

if __name__ == "__main__":
    main()
