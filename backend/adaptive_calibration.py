"""
Phase 3 - Adaptive Confidence & Trust System

This module provides:
1. Label trust weighting for analytics
2. Continuous drift detection
3. Seasonal/temporal awareness
4. Region maturity scoring
5. Calibration vs retraining recommendations

KEY GUARDRAILS:
- ADVISORY ONLY - No automatic behavior changes
- Ship dark - CALIBRATION_ADAPTIVE_ENABLED=false by default
- Zero impact on Phase 1-2 outputs
- All outputs are diagnostic and recommendatory

Calibration Version: v3-adaptive
"""

import os
import json
import logging
from typing import Dict, Any, Optional, List, Tuple
from dataclasses import dataclass, asdict
from datetime import datetime, timedelta
from enum import Enum
from pathlib import Path
import uuid

logger = logging.getLogger(__name__)

# ============================================================================
# CONFIGURATION
# ============================================================================

class AdaptiveCalibrationConfig:
    """Configuration for Phase 3 Adaptive Calibration."""
    
    @staticmethod
    def is_enabled() -> bool:
        """Check if adaptive calibration is enabled."""
        return os.environ.get('CALIBRATION_ADAPTIVE_ENABLED', 'false').lower() == 'true'
    
    # Drift thresholds (configurable via env)
    DRIFT_WARNING_THRESHOLD: float = float(os.environ.get('DRIFT_WARNING_THRESHOLD', '0.08'))  # 8%
    DRIFT_CRITICAL_THRESHOLD: float = float(os.environ.get('DRIFT_CRITICAL_THRESHOLD', '0.12'))  # 12%
    
    # Rolling window options (days)
    DRIFT_WINDOW_OPTIONS: List[int] = [30, 60, 90]
    
    # Minimum samples for drift detection
    DRIFT_MIN_SAMPLES: int = int(os.environ.get('DRIFT_MIN_SAMPLES', '50'))
    
    # Region maturity thresholds
    MATURITY_LOW_THRESHOLD: int = int(os.environ.get('MATURITY_LOW_THRESHOLD', '100'))
    MATURITY_MEDIUM_THRESHOLD: int = int(os.environ.get('MATURITY_MEDIUM_THRESHOLD', '300'))
    MATURITY_HIGH_THRESHOLD: int = int(os.environ.get('MATURITY_HIGH_THRESHOLD', '500'))
    
    # Label trust weights (default values)
    DEFAULT_TRUST_WEIGHTS: Dict[str, float] = {
        'expert': 0.9,
        'admin': 0.8,
        'trusted_user': 0.7,
        'self_reported': 0.6,
        'unknown': 0.5
    }


# ============================================================================
# ENUMS
# ============================================================================

class TrustSource(str, Enum):
    """Sources for label trust weighting."""
    EXPERT = 'expert'
    ADMIN = 'admin'
    TRUSTED_USER = 'trusted_user'
    SELF_REPORTED = 'self_reported'
    UNKNOWN = 'unknown'


class DriftSeverity(str, Enum):
    """Severity levels for drift detection."""
    NONE = 'none'
    WARNING = 'warning'
    CRITICAL = 'critical'


class MaturityLevel(str, Enum):
    """Region data maturity levels."""
    LOW = 'low'
    MEDIUM = 'medium'
    HIGH = 'high'


class RecommendationType(str, Enum):
    """Types of model/calibration recommendations."""
    REBUILD_CALIBRATION = 'rebuild_calibration'
    TIGHTEN_UNCERTAINTY = 'tighten_uncertainty'
    INVESTIGATE_DATA = 'investigate_data'
    CONSIDER_RETRAINING = 'consider_retraining'
    REGION_CURVE_UPDATE = 'region_curve_update'
    NO_ACTION = 'no_action'


class ConfidenceType(str, Enum):
    """Types of confidence being measured."""
    AGE = 'age'
    RECOMMENDATION = 'recommendation'


class SeasonBucket(str, Enum):
    """Deer hunting season buckets."""
    PRE_RUT = 'pre_rut'
    RUT = 'rut'
    POST_RUT = 'post_rut'
    LATE_SEASON = 'late_season'
    OFF_SEASON = 'off_season'


# ============================================================================
# DATA STRUCTURES
# ============================================================================

@dataclass
class DriftEvent:
    """Represents a detected calibration drift event."""
    id: str
    region_key: str
    model_version: str
    calibration_version: str
    confidence_type: str
    expected_accuracy: float
    observed_accuracy: float
    drift_percentage: float
    severity: str
    sample_size: int
    time_window_days: int
    season_bucket: Optional[str]
    created_at: datetime
    
    def to_db_dict(self) -> Dict[str, Any]:
        return {
            'id': self.id,
            'region_key': self.region_key,
            'model_version': self.model_version,
            'calibration_version': self.calibration_version,
            'confidence_type': self.confidence_type,
            'expected_accuracy': self.expected_accuracy,
            'observed_accuracy': self.observed_accuracy,
            'drift_percentage': self.drift_percentage,
            'severity': self.severity,
            'sample_size': self.sample_size,
            'time_window_days': self.time_window_days,
            'season_bucket': self.season_bucket,
            'created_at': self.created_at
        }


@dataclass
class RegionMaturity:
    """Represents region data maturity assessment."""
    region_key: str
    maturity_level: str
    labeled_sample_count: int
    label_source_diversity_score: float
    stability_score: float
    last_computed_at: datetime
    
    def to_db_dict(self) -> Dict[str, Any]:
        return {
            'region_key': self.region_key,
            'maturity_level': self.maturity_level,
            'labeled_sample_count': self.labeled_sample_count,
            'label_source_diversity_score': self.label_source_diversity_score,
            'stability_score': self.stability_score,
            'last_computed_at': self.last_computed_at
        }


@dataclass
class ModelRecommendation:
    """Represents a model/calibration action recommendation."""
    id: str
    region_key: Optional[str]
    model_version: str
    confidence_type: str
    recommendation_type: str
    supporting_metrics: Dict[str, Any]
    severity: str
    created_at: datetime
    
    def to_db_dict(self) -> Dict[str, Any]:
        return {
            'id': self.id,
            'region_key': self.region_key,
            'model_version': self.model_version,
            'confidence_type': self.confidence_type,
            'recommendation_type': self.recommendation_type,
            'supporting_metrics': json.dumps(self.supporting_metrics),
            'severity': self.severity,
            'created_at': self.created_at
        }


@dataclass
class DriftDetectionResult:
    """Result of drift detection job."""
    events_detected: int
    warnings: int
    criticals: int
    regions_analyzed: List[str]
    time_windows_used: List[int]
    errors: List[str]
    dry_run: bool
    duration_seconds: float


@dataclass
class MaturityComputeResult:
    """Result of maturity computation job."""
    regions_computed: int
    low_maturity: int
    medium_maturity: int
    high_maturity: int
    errors: List[str]
    dry_run: bool
    duration_seconds: float


@dataclass
class RecommendationResult:
    """Result of recommendation generation job."""
    recommendations_generated: int
    by_type: Dict[str, int]
    errors: List[str]
    dry_run: bool
    duration_seconds: float


# ============================================================================
# SEASON MAPPING
# ============================================================================

_season_mapping_cache: Optional[Dict[str, Any]] = None

def load_season_mapping() -> Dict[str, Any]:
    """Load season mapping configuration."""
    global _season_mapping_cache
    
    if _season_mapping_cache is not None:
        return _season_mapping_cache
    
    config_path = Path(__file__).parent / 'config' / 'season_mapping.json'
    
    try:
        with open(config_path, 'r') as f:
            _season_mapping_cache = json.load(f)
            return _season_mapping_cache
    except FileNotFoundError:
        logger.warning(f"Season mapping config not found at {config_path}, using defaults")
        _season_mapping_cache = {'default': {}}
        return _season_mapping_cache
    except json.JSONDecodeError as e:
        logger.error(f"Invalid season mapping JSON: {e}")
        _season_mapping_cache = {'default': {}}
        return _season_mapping_cache


def get_season_bucket(scan_date: datetime, region_key: str) -> str:
    """
    Determine the season bucket for a scan based on date and region.
    
    Args:
        scan_date: DateTime of the scan
        region_key: Region key (e.g., 'midwest', 'southeast')
        
    Returns:
        Season bucket string
    """
    mapping = load_season_mapping()
    
    # Get region-specific mapping or fall back to default
    region_seasons = mapping.get(region_key, mapping.get('default', {}))
    if not region_seasons:
        return SeasonBucket.OFF_SEASON.value
    
    month = scan_date.month
    day = scan_date.day
    
    for season_name, dates in region_seasons.items():
        if season_name.startswith('_'):
            continue  # Skip metadata fields
            
        start_month = dates.get('start_month', 1)
        start_day = dates.get('start_day', 1)
        end_month = dates.get('end_month', 12)
        end_day = dates.get('end_day', 31)
        
        # Handle year wrap-around (e.g., late_season Dec-Jan)
        if start_month <= end_month:
            # Normal case: within same year
            if (month > start_month or (month == start_month and day >= start_day)) and \
               (month < end_month or (month == end_month and day <= end_day)):
                return season_name
        else:
            # Year wrap-around case
            if (month > start_month or (month == start_month and day >= start_day)) or \
               (month < end_month or (month == end_month and day <= end_day)):
                return season_name
    
    return SeasonBucket.OFF_SEASON.value


# ============================================================================
# LABEL TRUST WEIGHTING
# ============================================================================

def get_trust_weight(trust_source: Optional[str]) -> float:
    """
    Get the trust weight for a label source.
    
    Args:
        trust_source: Source of the label (expert, admin, etc.)
        
    Returns:
        Trust weight (0-1)
    """
    if not trust_source:
        return AdaptiveCalibrationConfig.DEFAULT_TRUST_WEIGHTS['unknown']
    
    return AdaptiveCalibrationConfig.DEFAULT_TRUST_WEIGHTS.get(
        trust_source.lower(),
        AdaptiveCalibrationConfig.DEFAULT_TRUST_WEIGHTS['unknown']
    )


def compute_weighted_accuracy(labels: List[Dict[str, Any]], correct_field: str = 'age_correct') -> Tuple[float, int]:
    """
    Compute weighted accuracy from labels.
    
    effective_correct = sum(correct * trust_weight) / sum(trust_weight)
    
    Args:
        labels: List of label dicts with correct_field and trust_weight
        correct_field: Field name for correctness (age_correct or recommendation_correct)
        
    Returns:
        Tuple of (weighted_accuracy, sample_count)
    """
    if not labels:
        return 0.0, 0
    
    total_weight = 0.0
    weighted_correct = 0.0
    
    for label in labels:
        correct = label.get(correct_field)
        if correct is None:
            continue
            
        trust_weight = label.get('trust_weight', get_trust_weight(label.get('trust_source')))
        total_weight += trust_weight
        
        if correct:
            weighted_correct += trust_weight
    
    if total_weight == 0:
        return 0.0, 0
    
    return weighted_correct / total_weight, len(labels)


# ============================================================================
# DRIFT DETECTION
# ============================================================================

def classify_drift_severity(drift_percentage: float) -> str:
    """
    Classify drift severity based on percentage.
    
    Args:
        drift_percentage: Drift as decimal (e.g., 0.08 for 8%)
        
    Returns:
        Severity string
    """
    abs_drift = abs(drift_percentage)
    
    if abs_drift >= AdaptiveCalibrationConfig.DRIFT_CRITICAL_THRESHOLD:
        return DriftSeverity.CRITICAL.value
    elif abs_drift >= AdaptiveCalibrationConfig.DRIFT_WARNING_THRESHOLD:
        return DriftSeverity.WARNING.value
    else:
        return DriftSeverity.NONE.value


async def detect_calibration_drift(
    database,
    scans_table,
    scan_labels_table,
    calibration_curves_table,
    drift_events_table,
    time_window_days: int = 30,
    include_seasons: bool = True,
    dry_run: bool = True
) -> DriftDetectionResult:
    """
    Detect calibration drift by comparing expected vs observed accuracy.
    
    ADVISORY ONLY - Does not modify calibration behavior.
    
    Args:
        database: Database connection
        scans_table: Scans SQLAlchemy table
        scan_labels_table: Labels SQLAlchemy table
        calibration_curves_table: Curves SQLAlchemy table
        drift_events_table: Drift events SQLAlchemy table
        time_window_days: Rolling window in days
        include_seasons: Whether to segment by season
        dry_run: If True, don't persist events
        
    Returns:
        DriftDetectionResult with statistics
    """
    from sqlalchemy import select, func, and_
    
    start_time = datetime.utcnow()
    config = AdaptiveCalibrationConfig
    
    result = DriftDetectionResult(
        events_detected=0,
        warnings=0,
        criticals=0,
        regions_analyzed=[],
        time_windows_used=[time_window_days],
        errors=[],
        dry_run=dry_run,
        duration_seconds=0
    )
    
    if not config.is_enabled():
        result.errors.append("Adaptive calibration is disabled")
        return result
    
    try:
        # Calculate cutoff date
        cutoff_date = datetime.utcnow() - timedelta(days=time_window_days)
        
        # Join scans with labels to get recent labeled data
        query = select(
            scans_table.c.id,
            scans_table.c.region_key,
            scans_table.c.calibration_version,
            scans_table.c.raw_confidence,
            scans_table.c.age_confidence,
            scans_table.c.recommendation_confidence,
            scans_table.c.created_at,
            scan_labels_table.c.age_correct,
            scan_labels_table.c.recommendation_correct,
            scan_labels_table.c.trust_source,
            scan_labels_table.c.trust_weight
        ).select_from(
            scans_table.join(
                scan_labels_table,
                scans_table.c.id == scan_labels_table.c.scan_id
            )
        ).where(
            scans_table.c.created_at >= cutoff_date
        )
        
        rows = await database.fetch_all(query)
        
        if not rows:
            logger.info(f"No labeled data found in {time_window_days}-day window")
            return result
        
        # Group by region, calibration_version, and optionally season
        # Structure: {(region, cal_version, season): [labels]}
        grouped_data: Dict[Tuple[str, str, Optional[str]], List[Dict]] = {}
        
        for row in rows:
            region = row['region_key'] or 'unknown'
            cal_version = row['calibration_version'] or 'unknown'
            
            season = None
            if include_seasons and row['created_at']:
                season = get_season_bucket(row['created_at'], region)
            
            key = (region, cal_version, season)
            if key not in grouped_data:
                grouped_data[key] = []
            
            grouped_data[key].append(dict(row))
            
            if region not in result.regions_analyzed:
                result.regions_analyzed.append(region)
        
        # Load active curves to get expected accuracy
        curves_query = select(calibration_curves_table).where(
            calibration_curves_table.c.is_active == True
        )
        active_curves = await database.fetch_all(curves_query)
        
        # Build lookup for expected accuracy
        # For simplicity, use bin midpoints as expected accuracy
        curve_lookup = {}
        for curve in active_curves:
            curve_key = (curve['curve_type'], curve['region_key'])
            bins = json.loads(curve['bins']) if curve['bins'] else []
            curve_lookup[curve_key] = bins
        
        # Process each group
        events_to_insert = []
        
        for (region, cal_version, season), labels in grouped_data.items():
            if len(labels) < config.DRIFT_MIN_SAMPLES:
                continue
            
            # Compute observed weighted accuracy for age
            age_labels = [l for l in labels if l.get('age_correct') is not None]
            if age_labels:
                observed_age_accuracy, age_count = compute_weighted_accuracy(age_labels, 'age_correct')
                
                # Get expected accuracy (from calibration curve or default)
                # For now, use 0.7 as baseline expected accuracy
                expected_age_accuracy = 0.70
                
                # Look up in curve if available
                for curve_type in [('region_age', region), ('global_age', None)]:
                    if curve_type in curve_lookup:
                        bins = curve_lookup[curve_type]
                        if bins:
                            # Use average of calibrated_confidence across bins
                            avg_expected = sum(b.get('calibrated_confidence', 0.7) for b in bins) / len(bins)
                            expected_age_accuracy = avg_expected
                            break
                
                drift = observed_age_accuracy - expected_age_accuracy
                severity = classify_drift_severity(drift)
                
                if severity != DriftSeverity.NONE.value:
                    event = DriftEvent(
                        id=str(uuid.uuid4()),
                        region_key=region,
                        model_version='gpt-4o',  # Current model
                        calibration_version=cal_version,
                        confidence_type=ConfidenceType.AGE.value,
                        expected_accuracy=round(expected_age_accuracy, 4),
                        observed_accuracy=round(observed_age_accuracy, 4),
                        drift_percentage=round(drift, 4),
                        severity=severity,
                        sample_size=age_count,
                        time_window_days=time_window_days,
                        season_bucket=season,
                        created_at=datetime.utcnow()
                    )
                    events_to_insert.append(event)
                    result.events_detected += 1
                    
                    if severity == DriftSeverity.WARNING.value:
                        result.warnings += 1
                    elif severity == DriftSeverity.CRITICAL.value:
                        result.criticals += 1
                    
                    logger.info(
                        f"Drift detected: region={region}, type=age, "
                        f"expected={expected_age_accuracy:.2%}, observed={observed_age_accuracy:.2%}, "
                        f"drift={drift:.2%}, severity={severity}"
                    )
            
            # Compute observed weighted accuracy for recommendation
            rec_labels = [l for l in labels if l.get('recommendation_correct') is not None]
            if rec_labels:
                observed_rec_accuracy, rec_count = compute_weighted_accuracy(rec_labels, 'recommendation_correct')
                expected_rec_accuracy = 0.85  # Higher baseline for recommendations
                
                drift = observed_rec_accuracy - expected_rec_accuracy
                severity = classify_drift_severity(drift)
                
                if severity != DriftSeverity.NONE.value:
                    event = DriftEvent(
                        id=str(uuid.uuid4()),
                        region_key=region,
                        model_version='gpt-4o',
                        calibration_version=cal_version,
                        confidence_type=ConfidenceType.RECOMMENDATION.value,
                        expected_accuracy=round(expected_rec_accuracy, 4),
                        observed_accuracy=round(observed_rec_accuracy, 4),
                        drift_percentage=round(drift, 4),
                        severity=severity,
                        sample_size=rec_count,
                        time_window_days=time_window_days,
                        season_bucket=season,
                        created_at=datetime.utcnow()
                    )
                    events_to_insert.append(event)
                    result.events_detected += 1
                    
                    if severity == DriftSeverity.WARNING.value:
                        result.warnings += 1
                    elif severity == DriftSeverity.CRITICAL.value:
                        result.criticals += 1
        
        # Persist events if not dry run
        if not dry_run and events_to_insert:
            for event in events_to_insert:
                insert_query = drift_events_table.insert().values(**event.to_db_dict())
                await database.execute(insert_query)
            logger.info(f"Persisted {len(events_to_insert)} drift events")
        
    except Exception as e:
        logger.error(f"Drift detection error: {e}")
        result.errors.append(str(e))
    
    result.duration_seconds = (datetime.utcnow() - start_time).total_seconds()
    return result


# ============================================================================
# REGION MATURITY SCORING
# ============================================================================

def compute_maturity_level(sample_count: int) -> str:
    """
    Compute maturity level based on sample count.
    
    Args:
        sample_count: Number of labeled samples
        
    Returns:
        Maturity level string
    """
    config = AdaptiveCalibrationConfig
    
    if sample_count >= config.MATURITY_HIGH_THRESHOLD:
        return MaturityLevel.HIGH.value
    elif sample_count >= config.MATURITY_MEDIUM_THRESHOLD:
        return MaturityLevel.MEDIUM.value
    else:
        return MaturityLevel.LOW.value


def compute_source_diversity_score(labels: List[Dict[str, Any]]) -> float:
    """
    Compute label source diversity score (0-1).
    Higher score = more diverse sources = more trustworthy data.
    
    Args:
        labels: List of labels with trust_source field
        
    Returns:
        Diversity score (0-1)
    """
    if not labels:
        return 0.0
    
    # Count labels by source
    source_counts = {}
    for label in labels:
        source = label.get('trust_source', 'unknown')
        source_counts[source] = source_counts.get(source, 0) + 1
    
    # Shannon diversity index normalized to 0-1
    import math
    total = sum(source_counts.values())
    if total == 0:
        return 0.0
    
    max_sources = len(TrustSource)
    
    # Calculate entropy
    entropy = 0.0
    for count in source_counts.values():
        if count > 0:
            p = count / total
            entropy -= p * math.log(p)
    
    # Normalize to 0-1 (max entropy is log of number of sources)
    max_entropy = math.log(max_sources) if max_sources > 1 else 1
    diversity_score = entropy / max_entropy if max_entropy > 0 else 0
    
    # Bonus for having expert labels
    if 'expert' in source_counts:
        diversity_score = min(1.0, diversity_score + 0.1)
    
    return round(diversity_score, 4)


async def compute_region_maturity(
    database,
    scans_table,
    scan_labels_table,
    drift_events_table,
    region_maturity_table,
    dry_run: bool = True
) -> MaturityComputeResult:
    """
    Compute data maturity scores for all regions.
    
    ADVISORY ONLY - Does not affect calibration behavior.
    
    Inputs:
    - Labeled sample count
    - Label source diversity
    - Stability of drift metrics over time
    - (Future: curve rebuild frequency)
    
    Args:
        database: Database connection
        scans_table: Scans SQLAlchemy table
        scan_labels_table: Labels SQLAlchemy table
        drift_events_table: Drift events SQLAlchemy table
        region_maturity_table: Region maturity SQLAlchemy table
        dry_run: If True, don't persist results
        
    Returns:
        MaturityComputeResult with statistics
    """
    from sqlalchemy import select, func, and_, distinct
    
    start_time = datetime.utcnow()
    config = AdaptiveCalibrationConfig
    
    result = MaturityComputeResult(
        regions_computed=0,
        low_maturity=0,
        medium_maturity=0,
        high_maturity=0,
        errors=[],
        dry_run=dry_run,
        duration_seconds=0
    )
    
    if not config.is_enabled():
        result.errors.append("Adaptive calibration is disabled")
        return result
    
    try:
        # Get all regions with labeled data
        regions_query = select(
            distinct(scans_table.c.region_key)
        ).select_from(
            scans_table.join(
                scan_labels_table,
                scans_table.c.id == scan_labels_table.c.scan_id
            )
        ).where(
            scans_table.c.region_key.isnot(None)
        )
        
        region_rows = await database.fetch_all(regions_query)
        regions = [r[0] for r in region_rows if r[0]]
        
        if not regions:
            logger.info("No regions with labeled data found")
            return result
        
        maturity_records = []
        
        for region in regions:
            # Get all labels for this region
            labels_query = select(
                scan_labels_table.c.id,
                scan_labels_table.c.trust_source,
                scan_labels_table.c.age_correct,
                scan_labels_table.c.recommendation_correct
            ).select_from(
                scans_table.join(
                    scan_labels_table,
                    scans_table.c.id == scan_labels_table.c.scan_id
                )
            ).where(
                scans_table.c.region_key == region
            )
            
            labels = await database.fetch_all(labels_query)
            labels_list = [dict(l) for l in labels]
            
            sample_count = len(labels_list)
            maturity_level = compute_maturity_level(sample_count)
            diversity_score = compute_source_diversity_score(labels_list)
            
            # Compute stability score based on recent drift events
            # Lower drift variance = higher stability
            drift_query = select(
                drift_events_table.c.drift_percentage
            ).where(
                and_(
                    drift_events_table.c.region_key == region,
                    drift_events_table.c.created_at >= datetime.utcnow() - timedelta(days=90)
                )
            )
            
            drift_rows = await database.fetch_all(drift_query)
            
            if drift_rows and len(drift_rows) >= 2:
                drifts = [abs(r[0]) for r in drift_rows]
                avg_drift = sum(drifts) / len(drifts)
                # Stability = 1 - normalized average drift
                stability_score = max(0, 1 - (avg_drift / 0.20))  # Normalize to 20% max
            else:
                stability_score = 0.5  # Default when insufficient data
            
            maturity_record = RegionMaturity(
                region_key=region,
                maturity_level=maturity_level,
                labeled_sample_count=sample_count,
                label_source_diversity_score=diversity_score,
                stability_score=round(stability_score, 4),
                last_computed_at=datetime.utcnow()
            )
            
            maturity_records.append(maturity_record)
            result.regions_computed += 1
            
            if maturity_level == MaturityLevel.LOW.value:
                result.low_maturity += 1
            elif maturity_level == MaturityLevel.MEDIUM.value:
                result.medium_maturity += 1
            else:
                result.high_maturity += 1
            
            logger.info(
                f"Region maturity: {region} = {maturity_level} "
                f"(samples={sample_count}, diversity={diversity_score:.2f}, stability={stability_score:.2f})"
            )
        
        # Persist if not dry run (upsert)
        if not dry_run and maturity_records:
            for record in maturity_records:
                # Try update first, then insert
                update_query = region_maturity_table.update().where(
                    region_maturity_table.c.region_key == record.region_key
                ).values(**record.to_db_dict())
                
                await database.execute(update_query)
                
                # If no rows updated, insert
                # Note: This is a simple approach; production would use UPSERT
                try:
                    insert_query = region_maturity_table.insert().values(**record.to_db_dict())
                    await database.execute(insert_query)
                except Exception:
                    pass  # Already exists, update succeeded
            
            logger.info(f"Persisted maturity for {len(maturity_records)} regions")
        
    except Exception as e:
        logger.error(f"Maturity computation error: {e}")
        result.errors.append(str(e))
    
    result.duration_seconds = (datetime.utcnow() - start_time).total_seconds()
    return result


# ============================================================================
# RECOMMENDATION GENERATION
# ============================================================================

async def generate_model_recommendations(
    database,
    drift_events_table,
    region_maturity_table,
    recommendations_table,
    dry_run: bool = True
) -> RecommendationResult:
    """
    Generate advisory recommendations based on drift patterns.
    
    ADVISORY ONLY - Does not take any automatic action.
    
    Decision heuristics:
    - Drift high, accuracy stable -> rebuild_calibration
    - Accuracy declining, confidence stable -> consider_retraining
    - Both drifting -> investigate_data
    - Region-only drift -> region_curve_update
    
    Args:
        database: Database connection
        drift_events_table: Drift events SQLAlchemy table
        region_maturity_table: Region maturity SQLAlchemy table
        recommendations_table: Recommendations SQLAlchemy table
        dry_run: If True, don't persist recommendations
        
    Returns:
        RecommendationResult with statistics
    """
    from sqlalchemy import select, func, and_, desc
    
    start_time = datetime.utcnow()
    config = AdaptiveCalibrationConfig
    
    result = RecommendationResult(
        recommendations_generated=0,
        by_type={},
        errors=[],
        dry_run=dry_run,
        duration_seconds=0
    )
    
    if not config.is_enabled():
        result.errors.append("Adaptive calibration is disabled")
        return result
    
    try:
        # Get recent drift events (last 30 days)
        recent_cutoff = datetime.utcnow() - timedelta(days=30)
        
        drift_query = select(drift_events_table).where(
            drift_events_table.c.created_at >= recent_cutoff
        ).order_by(desc(drift_events_table.c.created_at))
        
        drift_events = await database.fetch_all(drift_query)
        
        if not drift_events:
            logger.info("No recent drift events to analyze")
            return result
        
        # Group drift by region
        region_drift: Dict[str, List[Dict]] = {}
        global_drift: List[Dict] = []
        
        for event in drift_events:
            event_dict = dict(event)
            region = event_dict.get('region_key', 'unknown')
            region_drift.setdefault(region, []).append(event_dict)
            global_drift.append(event_dict)
        
        recommendations_to_insert = []
        
        # Analyze global patterns first
        critical_count = sum(1 for e in global_drift if e.get('severity') == 'critical')
        warning_count = sum(1 for e in global_drift if e.get('severity') == 'warning')
        
        # Global recommendation logic
        if critical_count >= 3:
            # Multiple critical drifts -> investigate data quality
            rec = ModelRecommendation(
                id=str(uuid.uuid4()),
                region_key=None,  # Global
                model_version='gpt-4o',
                confidence_type='both',
                recommendation_type=RecommendationType.INVESTIGATE_DATA.value,
                supporting_metrics={
                    'critical_drift_events': critical_count,
                    'warning_drift_events': warning_count,
                    'total_events': len(global_drift),
                    'time_period_days': 30
                },
                severity='critical',
                created_at=datetime.utcnow()
            )
            recommendations_to_insert.append(rec)
            result.by_type['investigate_data'] = result.by_type.get('investigate_data', 0) + 1
        
        elif critical_count >= 1 or warning_count >= 5:
            # Moderate drift -> suggest calibration rebuild
            rec = ModelRecommendation(
                id=str(uuid.uuid4()),
                region_key=None,
                model_version='gpt-4o',
                confidence_type='both',
                recommendation_type=RecommendationType.REBUILD_CALIBRATION.value,
                supporting_metrics={
                    'critical_drift_events': critical_count,
                    'warning_drift_events': warning_count,
                    'average_drift': sum(abs(e.get('drift_percentage', 0)) for e in global_drift) / len(global_drift) if global_drift else 0
                },
                severity='warning',
                created_at=datetime.utcnow()
            )
            recommendations_to_insert.append(rec)
            result.by_type['rebuild_calibration'] = result.by_type.get('rebuild_calibration', 0) + 1
        
        # Region-specific recommendations
        for region, events in region_drift.items():
            if region == 'unknown':
                continue
                
            region_critical = sum(1 for e in events if e.get('severity') == 'critical')
            region_warning = sum(1 for e in events if e.get('severity') == 'warning')
            
            if region_critical >= 1 or region_warning >= 3:
                # Region-specific drift -> recommend region curve update
                avg_drift = sum(e.get('drift_percentage', 0) for e in events) / len(events)
                
                rec = ModelRecommendation(
                    id=str(uuid.uuid4()),
                    region_key=region,
                    model_version='gpt-4o',
                    confidence_type='age',  # Most common issue
                    recommendation_type=RecommendationType.REGION_CURVE_UPDATE.value,
                    supporting_metrics={
                        'region': region,
                        'critical_events': region_critical,
                        'warning_events': region_warning,
                        'average_drift_percentage': round(avg_drift, 4),
                        'sample_events': len(events)
                    },
                    severity='critical' if region_critical >= 1 else 'warning',
                    created_at=datetime.utcnow()
                )
                recommendations_to_insert.append(rec)
                result.by_type['region_curve_update'] = result.by_type.get('region_curve_update', 0) + 1
        
        result.recommendations_generated = len(recommendations_to_insert)
        
        # Persist if not dry run
        if not dry_run and recommendations_to_insert:
            for rec in recommendations_to_insert:
                insert_query = recommendations_table.insert().values(**rec.to_db_dict())
                await database.execute(insert_query)
            logger.info(f"Persisted {len(recommendations_to_insert)} recommendations")
        
    except Exception as e:
        logger.error(f"Recommendation generation error: {e}")
        result.errors.append(str(e))
    
    result.duration_seconds = (datetime.utcnow() - start_time).total_seconds()
    return result


# ============================================================================
# JOB LOCK MANAGEMENT (REUSE FROM CALIBRATION_JOBS)
# ============================================================================

_phase3_job_locks: Dict[str, datetime] = {}
_PHASE3_LOCK_TIMEOUT_SECONDS = 3600


def acquire_phase3_lock(job_name: str) -> bool:
    """Acquire a lock for a Phase 3 job."""
    global _phase3_job_locks
    now = datetime.utcnow()
    
    if job_name in _phase3_job_locks:
        lock_time = _phase3_job_locks[job_name]
        elapsed = (now - lock_time).total_seconds()
        if elapsed < _PHASE3_LOCK_TIMEOUT_SECONDS:
            logger.warning(f"Phase 3 job {job_name} is already running")
            return False
    
    _phase3_job_locks[job_name] = now
    logger.info(f"Acquired Phase 3 lock for: {job_name}")
    return True


def release_phase3_lock(job_name: str):
    """Release a Phase 3 job lock."""
    global _phase3_job_locks
    if job_name in _phase3_job_locks:
        del _phase3_job_locks[job_name]
        logger.info(f"Released Phase 3 lock for: {job_name}")


def is_phase3_job_running(job_name: str) -> bool:
    """Check if a Phase 3 job is running."""
    if job_name not in _phase3_job_locks:
        return False
    
    lock_time = _phase3_job_locks[job_name]
    elapsed = (datetime.utcnow() - lock_time).total_seconds()
    return elapsed < _PHASE3_LOCK_TIMEOUT_SECONDS


# ============================================================================
# ADMIN UTILITIES
# ============================================================================

def get_phase3_status() -> Dict[str, Any]:
    """Get Phase 3 system status."""
    config = AdaptiveCalibrationConfig
    
    return {
        'enabled': config.is_enabled(),
        'jobs': {
            'drift_detection_running': is_phase3_job_running('drift_detection'),
            'maturity_computation_running': is_phase3_job_running('maturity_computation'),
            'recommendation_generation_running': is_phase3_job_running('recommendation_generation')
        },
        'config': {
            'drift_warning_threshold': config.DRIFT_WARNING_THRESHOLD,
            'drift_critical_threshold': config.DRIFT_CRITICAL_THRESHOLD,
            'drift_min_samples': config.DRIFT_MIN_SAMPLES,
            'drift_window_options': config.DRIFT_WINDOW_OPTIONS,
            'maturity_thresholds': {
                'low': config.MATURITY_LOW_THRESHOLD,
                'medium': config.MATURITY_MEDIUM_THRESHOLD,
                'high': config.MATURITY_HIGH_THRESHOLD
            },
            'trust_weights': config.DEFAULT_TRUST_WEIGHTS
        }
    }


async def get_drift_summary(
    database,
    drift_events_table,
    days: int = 30
) -> Dict[str, Any]:
    """Get summary of drift events."""
    from sqlalchemy import select, func, desc
    
    cutoff = datetime.utcnow() - timedelta(days=days)
    
    query = select(drift_events_table).where(
        drift_events_table.c.created_at >= cutoff
    ).order_by(desc(drift_events_table.c.created_at))
    
    rows = await database.fetch_all(query)
    
    events = []
    by_severity = {'warning': 0, 'critical': 0}
    by_region = {}
    
    for row in rows:
        event = dict(row)
        event['created_at'] = event['created_at'].isoformat() if event['created_at'] else None
        events.append(event)
        
        severity = event.get('severity', 'none')
        if severity in by_severity:
            by_severity[severity] += 1
        
        region = event.get('region_key', 'unknown')
        by_region[region] = by_region.get(region, 0) + 1
    
    return {
        'time_period_days': days,
        'total_events': len(events),
        'by_severity': by_severity,
        'by_region': by_region,
        'events': events[:50]  # Limit to recent 50
    }


async def get_maturity_summary(
    database,
    region_maturity_table
) -> Dict[str, Any]:
    """Get summary of region maturity."""
    from sqlalchemy import select
    
    query = select(region_maturity_table)
    rows = await database.fetch_all(query)
    
    regions = []
    by_level = {'low': 0, 'medium': 0, 'high': 0}
    
    for row in rows:
        record = dict(row)
        record['last_computed_at'] = record['last_computed_at'].isoformat() if record.get('last_computed_at') else None
        regions.append(record)
        
        level = record.get('maturity_level', 'low')
        if level in by_level:
            by_level[level] += 1
    
    return {
        'total_regions': len(regions),
        'by_level': by_level,
        'regions': regions
    }


async def get_recommendations_summary(
    database,
    recommendations_table,
    days: int = 30
) -> Dict[str, Any]:
    """Get summary of recommendations."""
    from sqlalchemy import select, desc
    
    cutoff = datetime.utcnow() - timedelta(days=days)
    
    query = select(recommendations_table).where(
        recommendations_table.c.created_at >= cutoff
    ).order_by(desc(recommendations_table.c.created_at))
    
    rows = await database.fetch_all(query)
    
    recommendations = []
    by_type = {}
    by_severity = {'warning': 0, 'critical': 0}
    
    for row in rows:
        rec = dict(row)
        rec['created_at'] = rec['created_at'].isoformat() if rec['created_at'] else None
        rec['supporting_metrics'] = json.loads(rec['supporting_metrics']) if rec.get('supporting_metrics') else {}
        recommendations.append(rec)
        
        rec_type = rec.get('recommendation_type', 'unknown')
        by_type[rec_type] = by_type.get(rec_type, 0) + 1
        
        severity = rec.get('severity', 'warning')
        if severity in by_severity:
            by_severity[severity] += 1
    
    return {
        'time_period_days': days,
        'total_recommendations': len(recommendations),
        'by_type': by_type,
        'by_severity': by_severity,
        'recommendations': recommendations[:50]  # Limit to recent 50
    }
