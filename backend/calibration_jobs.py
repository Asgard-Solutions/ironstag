"""
Calibration Jobs Module - Phase 2 Empirical Calibration

This module provides:
1. Curve building from labeled data (scan_labels)
2. Curve activation management
3. Recalibration of existing scans
4. Job locking and idempotency

Calibration Version: v2-curve-*
"""

import os
import json
import logging
from typing import Dict, Any, Optional, List, Tuple
from dataclasses import dataclass, asdict
from datetime import datetime
from enum import Enum
import asyncio

logger = logging.getLogger(__name__)

# ============================================================================
# CONFIGURATION
# ============================================================================

class CalibrationJobConfig:
    """Configuration for calibration jobs."""
    
    # Feature flags
    CALIBRATION_CURVES_ENABLED: bool = os.environ.get('CALIBRATION_CURVES_ENABLED', 'false').lower() == 'true'
    CALIBRATION_CURVE_SCHEDULE_ENABLED: bool = os.environ.get('CALIBRATION_CURVE_SCHEDULE_ENABLED', 'false').lower() == 'true'
    
    # Maturity gates
    GLOBAL_CURVE_MIN_SAMPLES: int = int(os.environ.get('GLOBAL_CURVE_MIN_SAMPLES', '500'))
    REGION_CURVE_MIN_SAMPLES: int = int(os.environ.get('REGION_CURVE_MIN_SAMPLES', '200'))
    BIN_MIN_SAMPLES: int = int(os.environ.get('BIN_MIN_SAMPLES', '20'))
    
    # Bin configuration (10 bins from 0-100)
    CONFIDENCE_BINS: List[Tuple[int, int]] = [
        (0, 10), (10, 20), (20, 30), (30, 40), (40, 50),
        (50, 60), (60, 70), (70, 80), (80, 90), (90, 100)
    ]
    
    # Recalibration batch size
    RECALIBRATION_BATCH_SIZE: int = int(os.environ.get('RECALIBRATION_BATCH_SIZE', '100'))


# ============================================================================
# DATA STRUCTURES
# ============================================================================

class CurveType(str, Enum):
    """Types of calibration curves."""
    GLOBAL_AGE = "global_age"
    GLOBAL_RECOMMENDATION = "global_recommendation"
    REGION_AGE = "region_age"
    REGION_RECOMMENDATION = "region_recommendation"


@dataclass
class CalibrationBin:
    """Single confidence bin with calibration data."""
    min_confidence: int  # 0-100
    max_confidence: int  # 0-100
    sample_count: int
    correct_count: int
    calibrated_confidence: float  # 0.0-1.0
    
    @property
    def is_mature(self) -> bool:
        return self.sample_count >= CalibrationJobConfig.BIN_MIN_SAMPLES


@dataclass
class CalibrationCurve:
    """Complete calibration curve with bins and metadata."""
    id: str
    calibration_version: str
    curve_type: str
    region_key: Optional[str]
    method: str
    bins: List[CalibrationBin]
    total_samples: int
    is_active: bool
    is_mature: bool
    created_at: datetime
    
    def to_db_dict(self) -> Dict[str, Any]:
        """Convert to database-friendly dictionary."""
        return {
            "id": self.id,
            "calibration_version": self.calibration_version,
            "curve_type": self.curve_type,
            "region_key": self.region_key,
            "method": self.method,
            "bins": json.dumps([asdict(b) for b in self.bins]),
            "sample_count": self.total_samples,
            "is_active": self.is_active,
            "min_samples_required": (
                CalibrationJobConfig.REGION_CURVE_MIN_SAMPLES 
                if self.region_key 
                else CalibrationJobConfig.GLOBAL_CURVE_MIN_SAMPLES
            ),
            "created_at": self.created_at,
            "updated_at": datetime.utcnow()
        }


@dataclass
class CurveBuildResult:
    """Result of a curve build operation."""
    curves_built: int
    curves_mature: int
    curves_immature: int
    total_labels_processed: int
    regions_processed: List[str]
    errors: List[str]
    dry_run: bool
    version: str
    duration_seconds: float


@dataclass
class RecalibrationResult:
    """Result of a recalibration job."""
    scans_processed: int
    scans_updated: int
    scans_skipped: int
    errors: List[str]
    dry_run: bool
    curve_version: str
    duration_seconds: float


# ============================================================================
# JOB LOCK MANAGEMENT
# ============================================================================

# In-memory lock for simplicity (use Redis/DB for distributed systems)
_job_locks: Dict[str, datetime] = {}
_LOCK_TIMEOUT_SECONDS = 3600  # 1 hour


def acquire_job_lock(job_name: str) -> bool:
    """
    Acquire a lock for a job. Returns True if lock acquired.
    Uses timestamp-based expiration for safety.
    """
    global _job_locks
    now = datetime.utcnow()
    
    if job_name in _job_locks:
        lock_time = _job_locks[job_name]
        elapsed = (now - lock_time).total_seconds()
        if elapsed < _LOCK_TIMEOUT_SECONDS:
            logger.warning(f"Job {job_name} is already running (started {elapsed:.0f}s ago)")
            return False
        else:
            logger.info(f"Releasing stale lock for {job_name}")
    
    _job_locks[job_name] = now
    logger.info(f"Acquired lock for job: {job_name}")
    return True


def release_job_lock(job_name: str):
    """Release a job lock."""
    global _job_locks
    if job_name in _job_locks:
        del _job_locks[job_name]
        logger.info(f"Released lock for job: {job_name}")


def is_job_running(job_name: str) -> bool:
    """Check if a job is currently running."""
    if job_name not in _job_locks:
        return False
    
    lock_time = _job_locks[job_name]
    elapsed = (datetime.utcnow() - lock_time).total_seconds()
    return elapsed < _LOCK_TIMEOUT_SECONDS


# ============================================================================
# CURVE BUILDING LOGIC
# ============================================================================

def generate_curve_version() -> str:
    """Generate a unique curve version string."""
    timestamp = datetime.utcnow().strftime("%Y%m%d-%H%M%S")
    return f"v2-curve-{timestamp}"


def compute_bin_index(confidence: int) -> int:
    """Get the bin index for a confidence value (0-100)."""
    # Clamp to valid range
    confidence = max(0, min(100, confidence))
    # Map to bin index (0-9)
    return min(confidence // 10, 9)


def build_empty_bins() -> List[Dict[str, Any]]:
    """Create empty bin structure."""
    bins = []
    for min_conf, max_conf in CalibrationJobConfig.CONFIDENCE_BINS:
        bins.append({
            "min_confidence": min_conf,
            "max_confidence": max_conf,
            "sample_count": 0,
            "correct_count": 0,
            "calibrated_confidence": 0.5  # Default to 50% when no data
        })
    return bins


async def build_curves_from_labels(
    database,
    scans_table,
    scan_labels_table,
    calibration_curves_table,
    dry_run: bool = False
) -> CurveBuildResult:
    """
    Build calibration curves from labeled scan data.
    
    Process:
    1. Join scans with scan_labels
    2. Group by curve_type and region
    3. Bin by raw confidence
    4. Compute empirical correctness per bin
    5. Store curves (inactive by default)
    
    Args:
        database: Database connection
        scans_table: SQLAlchemy table for scans
        scan_labels_table: SQLAlchemy table for labels
        calibration_curves_table: SQLAlchemy table for curves
        dry_run: If True, don't write to database
        
    Returns:
        CurveBuildResult with statistics
    """
    import uuid
    from sqlalchemy import select, func, and_
    
    start_time = datetime.utcnow()
    version = generate_curve_version()
    
    result = CurveBuildResult(
        curves_built=0,
        curves_mature=0,
        curves_immature=0,
        total_labels_processed=0,
        regions_processed=[],
        errors=[],
        dry_run=dry_run,
        version=version,
        duration_seconds=0
    )
    
    try:
        # Query: Join scans with labels
        query = select(
            scans_table.c.id,
            scans_table.c.raw_confidence,
            scans_table.c.confidence,
            scans_table.c.region_key,
            scan_labels_table.c.age_correct,
            scan_labels_table.c.recommendation_correct
        ).select_from(
            scans_table.join(
                scan_labels_table,
                scans_table.c.id == scan_labels_table.c.scan_id
            )
        )
        
        rows = await database.fetch_all(query)
        result.total_labels_processed = len(rows)
        
        if not rows:
            logger.info("No labeled data found for curve building")
            return result
        
        # Aggregate data by curve type and region
        # Structure: {(curve_type, region_key): {bin_index: {samples, correct}}}
        aggregates: Dict[Tuple[str, Optional[str]], Dict[int, Dict[str, int]]] = {}
        
        for row in rows:
            raw_conf = row["raw_confidence"] or row["confidence"] or 50
            region = row["region_key"]
            age_correct = row["age_correct"]
            rec_correct = row["recommendation_correct"]
            
            bin_idx = compute_bin_index(raw_conf)
            
            # Track regions processed
            if region and region not in result.regions_processed:
                result.regions_processed.append(region)
            
            # Global age curve
            if age_correct is not None:
                key = (CurveType.GLOBAL_AGE.value, None)
                if key not in aggregates:
                    aggregates[key] = {i: {"samples": 0, "correct": 0} for i in range(10)}
                aggregates[key][bin_idx]["samples"] += 1
                if age_correct:
                    aggregates[key][bin_idx]["correct"] += 1
                
                # Region-specific age curve
                if region:
                    key = (CurveType.REGION_AGE.value, region)
                    if key not in aggregates:
                        aggregates[key] = {i: {"samples": 0, "correct": 0} for i in range(10)}
                    aggregates[key][bin_idx]["samples"] += 1
                    if age_correct:
                        aggregates[key][bin_idx]["correct"] += 1
            
            # Global recommendation curve
            if rec_correct is not None:
                key = (CurveType.GLOBAL_RECOMMENDATION.value, None)
                if key not in aggregates:
                    aggregates[key] = {i: {"samples": 0, "correct": 0} for i in range(10)}
                aggregates[key][bin_idx]["samples"] += 1
                if rec_correct:
                    aggregates[key][bin_idx]["correct"] += 1
                
                # Region-specific recommendation curve
                if region:
                    key = (CurveType.REGION_RECOMMENDATION.value, region)
                    if key not in aggregates:
                        aggregates[key] = {i: {"samples": 0, "correct": 0} for i in range(10)}
                    aggregates[key][bin_idx]["samples"] += 1
                    if rec_correct:
                        aggregates[key][bin_idx]["correct"] += 1
        
        # Build curves from aggregates
        curves_to_insert = []
        
        for (curve_type, region_key), bin_data in aggregates.items():
            total_samples = sum(b["samples"] for b in bin_data.values())
            
            # Determine maturity threshold
            min_samples = (
                CalibrationJobConfig.REGION_CURVE_MIN_SAMPLES 
                if region_key 
                else CalibrationJobConfig.GLOBAL_CURVE_MIN_SAMPLES
            )
            is_mature = total_samples >= min_samples
            
            # Build bins
            bins = []
            for i, (min_conf, max_conf) in enumerate(CalibrationJobConfig.CONFIDENCE_BINS):
                data = bin_data[i]
                samples = data["samples"]
                correct = data["correct"]
                
                # Calculate calibrated confidence
                if samples >= CalibrationJobConfig.BIN_MIN_SAMPLES:
                    calibrated = correct / samples
                else:
                    # Fallback for under-sampled bins: use midpoint
                    calibrated = (min_conf + max_conf) / 200.0
                
                bins.append({
                    "min_confidence": min_conf,
                    "max_confidence": max_conf,
                    "sample_count": samples,
                    "correct_count": correct,
                    "calibrated_confidence": round(calibrated, 4)
                })
            
            curve_id = str(uuid.uuid4())
            curve_data = {
                "id": curve_id,
                "calibration_version": version,
                "curve_type": curve_type,
                "region_key": region_key,
                "method": "binning",
                "bins": json.dumps(bins),
                "sample_count": total_samples,
                "min_samples_required": min_samples,
                "is_active": False,  # Always inactive until explicitly activated
                "created_at": datetime.utcnow(),
                "updated_at": datetime.utcnow()
            }
            
            curves_to_insert.append(curve_data)
            result.curves_built += 1
            
            if is_mature:
                result.curves_mature += 1
            else:
                result.curves_immature += 1
            
            logger.info(
                f"Built curve: {curve_type} region={region_key} "
                f"samples={total_samples} mature={is_mature}"
            )
        
        # Insert curves if not dry run
        if not dry_run and curves_to_insert:
            for curve in curves_to_insert:
                query = calibration_curves_table.insert().values(**curve)
                await database.execute(query)
            logger.info(f"Inserted {len(curves_to_insert)} curves to database")
        
    except Exception as e:
        logger.error(f"Curve building error: {e}")
        result.errors.append(str(e))
    
    result.duration_seconds = (datetime.utcnow() - start_time).total_seconds()
    return result


async def activate_curve(
    database,
    calibration_curves_table,
    curve_id: str,
    deactivate_others: bool = True
) -> Dict[str, Any]:
    """
    Activate a calibration curve.
    
    Args:
        database: Database connection
        calibration_curves_table: SQLAlchemy table
        curve_id: ID of curve to activate
        deactivate_others: If True, deactivate other curves of same type/region
        
    Returns:
        Status dict with activation result
    """
    from sqlalchemy import select, update, and_
    
    # Fetch the curve
    query = select(calibration_curves_table).where(
        calibration_curves_table.c.id == curve_id
    )
    curve = await database.fetch_one(query)
    
    if not curve:
        return {"success": False, "error": "Curve not found"}
    
    curve_type = curve["curve_type"]
    region_key = curve["region_key"]
    sample_count = curve["sample_count"]
    min_samples = curve["min_samples_required"]
    
    # Check maturity
    if sample_count < min_samples:
        return {
            "success": False, 
            "error": f"Curve not mature: {sample_count} < {min_samples} samples",
            "sample_count": sample_count,
            "min_samples_required": min_samples
        }
    
    # Deactivate other curves of same type/region if requested
    if deactivate_others:
        if region_key:
            deactivate_query = update(calibration_curves_table).where(
                and_(
                    calibration_curves_table.c.curve_type == curve_type,
                    calibration_curves_table.c.region_key == region_key,
                    calibration_curves_table.c.id != curve_id
                )
            ).values(is_active=False, updated_at=datetime.utcnow())
        else:
            deactivate_query = update(calibration_curves_table).where(
                and_(
                    calibration_curves_table.c.curve_type == curve_type,
                    calibration_curves_table.c.region_key.is_(None),
                    calibration_curves_table.c.id != curve_id
                )
            ).values(is_active=False, updated_at=datetime.utcnow())
        
        await database.execute(deactivate_query)
    
    # Activate this curve
    activate_query = update(calibration_curves_table).where(
        calibration_curves_table.c.id == curve_id
    ).values(is_active=True, updated_at=datetime.utcnow())
    
    await database.execute(activate_query)
    
    logger.info(f"Activated curve: {curve_id} ({curve_type}, region={region_key})")
    
    return {
        "success": True,
        "curve_id": curve_id,
        "curve_type": curve_type,
        "region_key": region_key,
        "calibration_version": curve["calibration_version"]
    }


async def deactivate_curve(
    database,
    calibration_curves_table,
    curve_id: str
) -> Dict[str, Any]:
    """Deactivate a calibration curve."""
    from sqlalchemy import update
    
    query = update(calibration_curves_table).where(
        calibration_curves_table.c.id == curve_id
    ).values(is_active=False, updated_at=datetime.utcnow())
    
    result = await database.execute(query)
    
    return {"success": True, "curve_id": curve_id}


# ============================================================================
# CURVE LOADING & APPLICATION
# ============================================================================

async def load_active_curves(
    database,
    calibration_curves_table
) -> Dict[Tuple[str, Optional[str]], Dict[str, Any]]:
    """
    Load all active calibration curves.
    
    Returns:
        Dict mapping (curve_type, region_key) to curve data
    """
    from sqlalchemy import select
    
    query = select(calibration_curves_table).where(
        calibration_curves_table.c.is_active == True
    )
    
    rows = await database.fetch_all(query)
    
    curves = {}
    for row in rows:
        key = (row["curve_type"], row["region_key"])
        curves[key] = {
            "id": row["id"],
            "calibration_version": row["calibration_version"],
            "curve_type": row["curve_type"],
            "region_key": row["region_key"],
            "method": row["method"],
            "bins": json.loads(row["bins"]) if row["bins"] else [],
            "sample_count": row["sample_count"],
            "is_active": row["is_active"]
        }
    
    return curves


def apply_curve_calibration(
    raw_confidence: int,
    curve: Dict[str, Any]
) -> Tuple[float, bool]:
    """
    Apply curve-based calibration to a raw confidence value.
    
    Args:
        raw_confidence: Raw confidence value (0-100)
        curve: Curve data dict with bins
        
    Returns:
        Tuple of (calibrated_confidence, used_fallback)
    """
    bins = curve.get("bins", [])
    if not bins:
        return raw_confidence / 100.0, True
    
    bin_idx = compute_bin_index(raw_confidence)
    
    if bin_idx < len(bins):
        bin_data = bins[bin_idx]
        sample_count = bin_data.get("sample_count", 0)
        
        if sample_count >= CalibrationJobConfig.BIN_MIN_SAMPLES:
            return bin_data["calibrated_confidence"], False
    
    # Fallback: return raw confidence scaled
    return raw_confidence / 100.0, True


# ============================================================================
# RECALIBRATION JOB
# ============================================================================

async def recalibrate_scans(
    database,
    scans_table,
    calibration_curves_table,
    curve_version: Optional[str] = None,
    since: Optional[datetime] = None,
    region: Optional[str] = None,
    dry_run: bool = False
) -> RecalibrationResult:
    """
    Recalibrate existing scans using active curves.
    
    This job:
    - Does NOT re-run ML inference
    - Only recomputes calibrated confidence values
    - Updates calibration metadata
    
    Args:
        database: Database connection
        scans_table: SQLAlchemy table for scans
        calibration_curves_table: SQLAlchemy table for curves
        curve_version: Optional specific curve version to use
        since: Only recalibrate scans created after this date
        region: Only recalibrate scans in this region
        dry_run: If True, don't update database
        
    Returns:
        RecalibrationResult with statistics
    """
    from sqlalchemy import select, update, and_
    from region_calibration import (
        REGION_UNCERTAINTY_THRESHOLDS,
        RegionKey
    )
    
    start_time = datetime.utcnow()
    
    result = RecalibrationResult(
        scans_processed=0,
        scans_updated=0,
        scans_skipped=0,
        errors=[],
        dry_run=dry_run,
        curve_version=curve_version or "active",
        duration_seconds=0
    )
    
    try:
        # Load active curves
        curves = await load_active_curves(database, calibration_curves_table)
        
        if not curves:
            result.errors.append("No active curves found")
            return result
        
        # Build query for scans to recalibrate
        conditions = []
        if since:
            conditions.append(scans_table.c.created_at >= since)
        if region:
            conditions.append(scans_table.c.region_key == region)
        
        query = select(scans_table)
        if conditions:
            query = query.where(and_(*conditions))
        
        # Process in batches
        batch_size = CalibrationJobConfig.RECALIBRATION_BATCH_SIZE
        offset = 0
        
        while True:
            batch_query = query.limit(batch_size).offset(offset)
            scans = await database.fetch_all(batch_query)
            
            if not scans:
                break
            
            for scan in scans:
                result.scans_processed += 1
                
                scan_id = scan["id"]
                raw_conf = scan["raw_confidence"] or scan["confidence"] or 50
                scan_region = scan["region_key"] or "unknown"
                
                # Determine which curves to use
                age_curve = None
                rec_curve = None
                age_strategy = "heuristic_region"
                rec_strategy = "heuristic_region"
                age_fallback_reason = None
                rec_fallback_reason = None
                
                # Try region-specific age curve
                region_age_key = (CurveType.REGION_AGE.value, scan_region)
                if region_age_key in curves:
                    age_curve = curves[region_age_key]
                    age_strategy = "curve_region"
                else:
                    # Try global age curve
                    global_age_key = (CurveType.GLOBAL_AGE.value, None)
                    if global_age_key in curves:
                        age_curve = curves[global_age_key]
                        age_strategy = "curve_global"
                        age_fallback_reason = "region_curve_missing"
                
                # Try region-specific recommendation curve
                region_rec_key = (CurveType.REGION_RECOMMENDATION.value, scan_region)
                if region_rec_key in curves:
                    rec_curve = curves[region_rec_key]
                    rec_strategy = "curve_region"
                else:
                    # Try global recommendation curve
                    global_rec_key = (CurveType.GLOBAL_RECOMMENDATION.value, None)
                    if global_rec_key in curves:
                        rec_curve = curves[global_rec_key]
                        rec_strategy = "curve_global"
                        rec_fallback_reason = "region_curve_missing"
                
                # Apply calibration
                if age_curve:
                    cal_age_conf, age_used_fallback = apply_curve_calibration(raw_conf, age_curve)
                    if age_used_fallback:
                        age_fallback_reason = "bin_under_sampled"
                else:
                    cal_age_conf = raw_conf / 100.0 * 0.75  # Heuristic fallback
                    age_fallback_reason = "no_curve_available"
                
                if rec_curve:
                    cal_rec_conf, rec_used_fallback = apply_curve_calibration(raw_conf, rec_curve)
                    if rec_used_fallback:
                        rec_fallback_reason = "bin_under_sampled"
                else:
                    cal_rec_conf = raw_conf / 100.0 * 0.95  # Heuristic fallback
                    rec_fallback_reason = "no_curve_available"
                
                # Apply uncertainty gate
                try:
                    region_enum = RegionKey(scan_region)
                except ValueError:
                    region_enum = RegionKey.UNKNOWN
                
                threshold = REGION_UNCERTAINTY_THRESHOLDS.get(region_enum, 0.68)
                age_uncertain = cal_age_conf < threshold
                
                # Convert to 0-100 scale
                cal_age_conf_pct = round(cal_age_conf * 100)
                cal_rec_conf_pct = round(cal_rec_conf * 100)
                
                # Determine final calibration version
                final_version = curve_version
                if age_curve:
                    final_version = age_curve.get("calibration_version", curve_version)
                
                # Determine deer_age (null if uncertain)
                new_deer_age = None if age_uncertain else scan["deer_age"]
                
                # Skip if nothing changed
                if (scan["age_confidence"] == cal_age_conf_pct and
                    scan["recommendation_confidence"] == cal_rec_conf_pct and
                    scan["age_uncertain"] == age_uncertain):
                    result.scans_skipped += 1
                    continue
                
                # Update scan if not dry run
                if not dry_run:
                    update_query = update(scans_table).where(
                        scans_table.c.id == scan_id
                    ).values(
                        deer_age=new_deer_age,
                        age_confidence=cal_age_conf_pct,
                        recommendation_confidence=cal_rec_conf_pct,
                        confidence=cal_rec_conf_pct,  # Legacy field
                        age_uncertain=age_uncertain,
                        calibration_version=final_version,
                        calibration_strategy=age_strategy,
                        calibration_fallback_reason=age_fallback_reason
                    )
                    await database.execute(update_query)
                
                result.scans_updated += 1
            
            offset += batch_size
            
            # Safety check: don't process forever
            if offset > 1000000:
                result.errors.append("Safety limit reached (1M scans)")
                break
        
    except Exception as e:
        logger.error(f"Recalibration error: {e}")
        result.errors.append(str(e))
    
    result.duration_seconds = (datetime.utcnow() - start_time).total_seconds()
    return result


# ============================================================================
# ADMIN UTILITIES
# ============================================================================

async def get_curves_summary(
    database,
    calibration_curves_table
) -> Dict[str, Any]:
    """Get summary of all calibration curves."""
    from sqlalchemy import select, func
    
    query = select(calibration_curves_table).order_by(
        calibration_curves_table.c.created_at.desc()
    )
    
    rows = await database.fetch_all(query)
    
    curves = []
    active_count = 0
    mature_count = 0
    
    for row in rows:
        is_mature = row["sample_count"] >= row["min_samples_required"]
        if row["is_active"]:
            active_count += 1
        if is_mature:
            mature_count += 1
        
        curves.append({
            "id": row["id"],
            "calibration_version": row["calibration_version"],
            "curve_type": row["curve_type"],
            "region_key": row["region_key"],
            "method": row["method"],
            "sample_count": row["sample_count"],
            "min_samples_required": row["min_samples_required"],
            "is_active": row["is_active"],
            "is_mature": is_mature,
            "created_at": row["created_at"].isoformat() if row["created_at"] else None
        })
    
    return {
        "total_curves": len(curves),
        "active_curves": active_count,
        "mature_curves": mature_count,
        "curves": curves
    }


async def get_curve_details(
    database,
    calibration_curves_table,
    curve_id: str
) -> Optional[Dict[str, Any]]:
    """Get detailed information about a specific curve."""
    from sqlalchemy import select
    
    query = select(calibration_curves_table).where(
        calibration_curves_table.c.id == curve_id
    )
    
    row = await database.fetch_one(query)
    
    if not row:
        return None
    
    bins = json.loads(row["bins"]) if row["bins"] else []
    
    return {
        "id": row["id"],
        "calibration_version": row["calibration_version"],
        "curve_type": row["curve_type"],
        "region_key": row["region_key"],
        "method": row["method"],
        "sample_count": row["sample_count"],
        "min_samples_required": row["min_samples_required"],
        "is_active": row["is_active"],
        "is_mature": row["sample_count"] >= row["min_samples_required"],
        "created_at": row["created_at"].isoformat() if row["created_at"] else None,
        "updated_at": row["updated_at"].isoformat() if row["updated_at"] else None,
        "bins": bins,
        "bin_stats": {
            "total_bins": len(bins),
            "mature_bins": sum(1 for b in bins if b.get("sample_count", 0) >= CalibrationJobConfig.BIN_MIN_SAMPLES),
            "total_samples_in_bins": sum(b.get("sample_count", 0) for b in bins)
        }
    }


def get_job_status() -> Dict[str, Any]:
    """Get status of calibration jobs."""
    return {
        "build_curves_running": is_job_running("build_curves"),
        "recalibrate_scans_running": is_job_running("recalibrate_scans"),
        "config": {
            "curves_enabled": CalibrationJobConfig.CALIBRATION_CURVES_ENABLED,
            "schedule_enabled": CalibrationJobConfig.CALIBRATION_CURVE_SCHEDULE_ENABLED,
            "global_min_samples": CalibrationJobConfig.GLOBAL_CURVE_MIN_SAMPLES,
            "region_min_samples": CalibrationJobConfig.REGION_CURVE_MIN_SAMPLES,
            "bin_min_samples": CalibrationJobConfig.BIN_MIN_SAMPLES,
            "recalibration_batch_size": CalibrationJobConfig.RECALIBRATION_BATCH_SIZE
        }
    }
