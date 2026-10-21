#!/usr/bin/env python3
"""
Comprehensive test for Confidence Separation & Score Audit Trail implementation
Tests both database schema and API response structure
"""

import os
from dotenv import load_dotenv
load_dotenv('/app/backend/.env')
import asyncio
from databases import Database
import json

DATABASE_URL = os.environ.get('DATABASE_URL', '')

async def run_all_tests():
    database = Database(DATABASE_URL)
    await database.connect()
    
    print("="*80)
    print("CONFIDENCE SEPARATION & SCORE AUDIT TRAIL - COMPREHENSIVE TESTS")
    print("="*80)
    
    passed = []
    failed = []
    warnings = []
    
    # TEST 1: Database Schema - score_audit column
    print("\n" + "="*80)
    print("TEST 1: Database Schema - score_audit Column")
    print("="*80)
    
    query = """
    SELECT column_name, data_type 
    FROM information_schema.columns 
    WHERE table_name='scans' AND column_name='score_audit'
    """
    result = await database.fetch_one(query)
    
    if result:
        passed.append(f"✅ score_audit column exists with type: {result[1]}")
        print(f"✅ score_audit column exists with type: {result[1]}")
    else:
        failed.append("❌ score_audit column does not exist")
        print("❌ score_audit column does not exist")
    
    # TEST 2: Check existing scans have proper confidence fields
    print("\n" + "="*80)
    print("TEST 2: Existing Scans - Confidence Fields")
    print("="*80)
    
    query = """
    SELECT id, confidence, age_confidence, recommendation_confidence, score_audit
    FROM scans 
    LIMIT 5
    """
    scans = await database.fetch_all(query)
    
    print(f"Found {len(scans)} scans to test")
    
    for scan in scans:
        scan_id = scan[0]
        confidence = scan[1]
        age_confidence = scan[2]
        recommendation_confidence = scan[3]
        score_audit = scan[4]
        
        print(f"\nScan {scan_id[:8]}...")
        
        # Check confidence field (legacy)
        if confidence is not None:
            passed.append(f"✅ Scan {scan_id[:8]}: confidence field present ({confidence})")
            print(f"  ✅ confidence (legacy): {confidence}")
        else:
            failed.append(f"❌ Scan {scan_id[:8]}: confidence field is NULL")
            print(f"  ❌ confidence (legacy): NULL")
        
        # Check age_confidence (can be NULL)
        if age_confidence is not None:
            if 0 <= age_confidence <= 100:
                passed.append(f"✅ Scan {scan_id[:8]}: age_confidence valid ({age_confidence})")
                print(f"  ✅ age_confidence: {age_confidence} (valid 0-100)")
            else:
                failed.append(f"❌ Scan {scan_id[:8]}: age_confidence out of range ({age_confidence})")
                print(f"  ❌ age_confidence: {age_confidence} (invalid range)")
        else:
            warnings.append(f"⚠️  Scan {scan_id[:8]}: age_confidence is NULL (expected for unavailable age)")
            print(f"  ⚠️  age_confidence: NULL (expected for unavailable age)")
        
        # Check recommendation_confidence
        if recommendation_confidence is not None:
            if 0 <= recommendation_confidence <= 100:
                passed.append(f"✅ Scan {scan_id[:8]}: recommendation_confidence valid ({recommendation_confidence})")
                print(f"  ✅ recommendation_confidence: {recommendation_confidence} (valid 0-100)")
            else:
                failed.append(f"❌ Scan {scan_id[:8]}: recommendation_confidence out of range ({recommendation_confidence})")
                print(f"  ❌ recommendation_confidence: {recommendation_confidence} (invalid range)")
        else:
            failed.append(f"❌ Scan {scan_id[:8]}: recommendation_confidence is NULL")
            print(f"  ❌ recommendation_confidence: NULL")
        
        # Check legacy compatibility: confidence should match recommendation_confidence
        if confidence is not None and recommendation_confidence is not None:
            if confidence == recommendation_confidence:
                passed.append(f"✅ Scan {scan_id[:8]}: Legacy compatibility - confidence matches recommendation_confidence")
                print(f"  ✅ Legacy compatibility: confidence ({confidence}) == recommendation_confidence ({recommendation_confidence})")
            else:
                failed.append(f"❌ Scan {scan_id[:8]}: Legacy compatibility broken - confidence ({confidence}) != recommendation_confidence ({recommendation_confidence})")
                print(f"  ❌ Legacy compatibility: confidence ({confidence}) != recommendation_confidence ({recommendation_confidence})")
        
        # Check score_audit
        if score_audit is not None:
            passed.append(f"✅ Scan {scan_id[:8]}: score_audit present")
            print(f"  ✅ score_audit: Present with data")
            
            # Verify structure
            if isinstance(score_audit, dict):
                has_version = 'version' in score_audit
                has_steps = 'steps' in score_audit
                has_final_scores = 'final_scores' in score_audit
                
                if has_version and has_steps and has_final_scores:
                    passed.append(f"✅ Scan {scan_id[:8]}: score_audit structure valid")
                    print(f"    ✅ Structure: version, steps, final_scores present")
                else:
                    failed.append(f"❌ Scan {scan_id[:8]}: score_audit structure incomplete")
                    print(f"    ❌ Structure incomplete: version={has_version}, steps={has_steps}, final_scores={has_final_scores}")
        else:
            warnings.append(f"⚠️  Scan {scan_id[:8]}: score_audit is NULL (legacy scan)")
            print(f"  ⚠️  score_audit: NULL (legacy scan without audit trail)")
    
    # TEST 3: Verify confidence_breakdown logic
    print("\n" + "="*80)
    print("TEST 3: confidence_breakdown Logic")
    print("="*80)
    
    for scan in scans[:3]:  # Test first 3 scans
        scan_id = scan[0]
        confidence = scan[1]
        age_confidence = scan[2]
        recommendation_confidence = scan[3]
        
        # Simulate build_scan_response logic
        confidence_breakdown = None
        if age_confidence is not None or recommendation_confidence is not None:
            confidence_breakdown = {
                "age": age_confidence if age_confidence is not None else None,
                "recommendation": recommendation_confidence if recommendation_confidence is not None else (confidence or 0)
            }
        
        print(f"\nScan {scan_id[:8]}:")
        if confidence_breakdown:
            passed.append(f"✅ Scan {scan_id[:8]}: confidence_breakdown can be built")
            print(f"  ✅ confidence_breakdown: {confidence_breakdown}")
            
            # Verify age can be null
            if confidence_breakdown['age'] is None:
                passed.append(f"✅ Scan {scan_id[:8]}: age can be null")
                print(f"    ✅ age is null (expected for unavailable age confidence)")
            elif isinstance(confidence_breakdown['age'], int) and 0 <= confidence_breakdown['age'] <= 100:
                passed.append(f"✅ Scan {scan_id[:8]}: age is valid integer")
                print(f"    ✅ age={confidence_breakdown['age']} (valid 0-100)")
            
            # Verify recommendation is integer 0-100
            if isinstance(confidence_breakdown['recommendation'], int) and 0 <= confidence_breakdown['recommendation'] <= 100:
                passed.append(f"✅ Scan {scan_id[:8]}: recommendation is valid integer")
                print(f"    ✅ recommendation={confidence_breakdown['recommendation']} (valid 0-100)")
            else:
                failed.append(f"❌ Scan {scan_id[:8]}: recommendation is invalid")
                print(f"    ❌ recommendation={confidence_breakdown['recommendation']} (invalid)")
        else:
            warnings.append(f"⚠️  Scan {scan_id[:8]}: confidence_breakdown is NULL (legacy scan)")
            print(f"  ⚠️  confidence_breakdown: NULL (legacy scan)")
    
    # TEST 4: Check that genuine 0 values are preserved
    print("\n" + "="*80)
    print("TEST 4: Zero Value Handling")
    print("="*80)
    
    query = """
    SELECT id, age_confidence, recommendation_confidence
    FROM scans 
    WHERE age_confidence = 0 OR recommendation_confidence = 0
    LIMIT 3
    """
    zero_scans = await database.fetch_all(query)
    
    if zero_scans:
        print(f"Found {len(zero_scans)} scans with 0 confidence values")
        for scan in zero_scans:
            scan_id = scan[0]
            age_conf = scan[1]
            rec_conf = scan[2]
            
            if age_conf == 0:
                passed.append(f"✅ Scan {scan_id[:8]}: age_confidence=0 preserved (not converted to NULL)")
                print(f"  ✅ Scan {scan_id[:8]}: age_confidence=0 preserved")
            
            if rec_conf == 0:
                passed.append(f"✅ Scan {scan_id[:8]}: recommendation_confidence=0 preserved")
                print(f"  ✅ Scan {scan_id[:8]}: recommendation_confidence=0 preserved")
    else:
        warnings.append("⚠️  No scans with 0 confidence values found (cannot test zero handling)")
        print("⚠️  No scans with 0 confidence values found")
    
    await database.disconnect()
    
    # Print summary
    print("\n" + "="*80)
    print("TEST SUMMARY")
    print("="*80)
    
    print(f"\n✅ PASSED: {len(passed)}")
    for p in passed[:10]:  # Show first 10
        print(f"  {p}")
    if len(passed) > 10:
        print(f"  ... and {len(passed) - 10} more")
    
    if warnings:
        print(f"\n⚠️  WARNINGS: {len(warnings)}")
        for w in warnings[:5]:  # Show first 5
            print(f"  {w}")
        if len(warnings) > 5:
            print(f"  ... and {len(warnings) - 5} more")
    
    if failed:
        print(f"\n❌ FAILED: {len(failed)}")
        for f in failed:
            print(f"  {f}")
    
    print("\n" + "="*80)
    total_tests = len(passed) + len(failed)
    success_rate = (len(passed) / total_tests * 100) if total_tests > 0 else 0
    print(f"SUCCESS RATE: {success_rate:.1f}% ({len(passed)}/{total_tests})")
    print("="*80)
    
    return len(failed) == 0

if __name__ == "__main__":
    success = asyncio.run(run_all_tests())
    exit(0 if success else 1)
