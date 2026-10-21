"""
Region-Specific Confidence Calibration Module

This module provides region-aware confidence calibration for deer age estimation.
It accounts for phenotype variance, terrain, and image quality differences across
geographic regions.

Calibration Version: v2-region-heuristic
- State → Region mapping with v1 lookup table
- Region-specific difficulty multipliers
- Region-specific uncertainty thresholds
- Fallback chain: region_curve → global_curve → heuristic → legacy

Author: Iron Stag Development Team

=============================================================================
IMPORTANT: EMPIRICAL CALIBRATION CURVES ARE INTENTIONALLY INACTIVE
=============================================================================
Calibration curves (Phase 2) are built but NOT activated until empirical
maturity gates are met. This prevents premature calibration on thin data.

Activation requires:
- Minimum sample counts per confidence bin
- Monotonicity validation
- No confidence inflation
- Human-gated approval via CLI

Do not manually enable curve-based calibration without validating maturity.
See: python -m cli.calibration status
=============================================================================
"""

import os
import logging
from typing import Dict, Any, Optional, Tuple, List
from dataclasses import dataclass, field
from enum import Enum
from datetime import datetime

from confidence_calibration import (
    HEURISTIC_TARGET,
    HEURISTIC_TARGET_DEFINITION,
    TARGETS,
    apply_artifact,
    check_compatibility,
    select_artifact,
)

logger = logging.getLogger(__name__)

# ============================================================================
# FEATURE FLAGS & CONFIGURATION
# ============================================================================

class RegionCalibrationConfig:
    """Configuration for region-specific confidence calibration."""
    
    # Master feature flags (environment-overridable)
    CALIBRATION_ENABLED: bool = os.environ.get('CALIBRATION_ENABLED', 'true').lower() == 'true'
    CALIBRATION_REGION_ENABLED: bool = os.environ.get('CALIBRATION_REGION_ENABLED', 'true').lower() == 'true'
    CALIBRATION_CURVES_ENABLED: bool = os.environ.get('CALIBRATION_CURVES_ENABLED', 'false').lower() == 'true'
    
    # Response field visibility (feature-flagged OFF by default)
    CALIBRATION_SHOW_REGION: bool = os.environ.get('CALIBRATION_SHOW_REGION', 'false').lower() == 'true'
    CALIBRATION_SHOW_STRATEGY: bool = os.environ.get('CALIBRATION_SHOW_STRATEGY', 'false').lower() == 'true'
    
    # Calibration version tracking
    CALIBRATION_VERSION: str = os.environ.get('CALIBRATION_VERSION', 'v2-region-heuristic')
    REGION_MAPPING_VERSION: str = os.environ.get('REGION_MAPPING_VERSION', 'v1')
    # Heuristic fallback version. v2 = production default (unchanged). v3 = de-duplicated candidate
    # (no antler penalty, one strongest visual penalty instead of stacked ones); shadow/benchmark it before switching.
    HEURISTIC_VERSION: str = os.environ.get('CALIBRATION_HEURISTIC_VERSION', 'v2')
    
    # Maturity gates for empirical calibration (Phase 2)
    GLOBAL_CURVE_MIN_SAMPLES: int = int(os.environ.get('GLOBAL_CURVE_MIN_SAMPLES', '500'))
    REGION_CURVE_MIN_SAMPLES: int = int(os.environ.get('REGION_CURVE_MIN_SAMPLES', '200'))
    
    # Base scaling factors
    AGE_CONFIDENCE_BASE_SCALE: float = float(os.environ.get('AGE_CONFIDENCE_BASE_SCALE', '0.75'))
    RECOMMENDATION_CONFIDENCE_BASE_SCALE: float = float(os.environ.get('RECOMMENDATION_CONFIDENCE_BASE_SCALE', '0.95'))
    
    # Global caps
    MAX_AGE_CONFIDENCE: float = float(os.environ.get('MAX_AGE_CONFIDENCE', '0.85'))
    MAX_RECOMMENDATION_CONFIDENCE: float = float(os.environ.get('MAX_RECOMMENDATION_CONFIDENCE', '0.95'))
    
    # Penalty factors
    NULL_AGE_PENALTY: float = float(os.environ.get('NULL_AGE_PENALTY', '0.4'))
    LOW_ANTLER_INFO_PENALTY: float = float(os.environ.get('LOW_ANTLER_INFO_PENALTY', '0.1'))
    UNKNOWN_SEX_PENALTY: float = float(os.environ.get('UNKNOWN_SEX_PENALTY', '0.05'))
    DOE_UNCERTAINTY_THRESHOLD_OFFSET: float = float(os.environ.get('DOE_UNCERTAINTY_THRESHOLD_OFFSET', '0.03'))


# ============================================================================
# REGION DEFINITIONS & MAPPING
# ============================================================================

class RegionKey(str, Enum):
    """Valid region keys for calibration."""
    MIDWEST = "midwest"
    SOUTHEAST = "southeast"
    NORTHEAST = "northeast"
    PLAINS = "plains"
    SOUTH_TEXAS = "south_texas"
    NORTHERN = "northern"
    UNKNOWN = "unknown"


class RegionSource(str, Enum):
    """How the region was determined."""
    SCAN_INPUT = "scan_input"
    USER_PROFILE = "user_profile"
    EXIF_GPS = "exif_gps"
    FALLBACK_UNKNOWN = "fallback_unknown"


class CalibrationStrategy(str, Enum):
    """Calibration strategy used."""
    LEGACY = "legacy"
    HEURISTIC_GLOBAL = "heuristic_global"
    HEURISTIC_REGION = "heuristic_region"
    CURVE_GLOBAL = "curve_global"
    CURVE_REGION = "curve_region"
    ARTIFACT = "validated_artifact"


# State → Region Mapping (v1)
# Intentionally coarse for error-clustering control, not wildlife biology precision
STATE_TO_REGION_V1: Dict[str, RegionKey] = {
    # South Texas (separate due to unique phenotype)
    "TX": RegionKey.SOUTH_TEXAS,
    
    # Midwest
    "IA": RegionKey.MIDWEST,
    "IL": RegionKey.MIDWEST,
    "IN": RegionKey.MIDWEST,
    "KS": RegionKey.MIDWEST,
    "MI": RegionKey.MIDWEST,
    "MN": RegionKey.MIDWEST,
    "MO": RegionKey.MIDWEST,
    "ND": RegionKey.MIDWEST,
    "NE": RegionKey.MIDWEST,
    "OH": RegionKey.MIDWEST,
    "SD": RegionKey.MIDWEST,
    "WI": RegionKey.MIDWEST,
    
    # Southeast
    "AL": RegionKey.SOUTHEAST,
    "AR": RegionKey.SOUTHEAST,
    "FL": RegionKey.SOUTHEAST,
    "GA": RegionKey.SOUTHEAST,
    "KY": RegionKey.SOUTHEAST,
    "LA": RegionKey.SOUTHEAST,
    "MS": RegionKey.SOUTHEAST,
    "NC": RegionKey.SOUTHEAST,
    "OK": RegionKey.SOUTHEAST,
    "SC": RegionKey.SOUTHEAST,
    "TN": RegionKey.SOUTHEAST,
    "VA": RegionKey.SOUTHEAST,
    "WV": RegionKey.SOUTHEAST,
    
    # Northeast
    "CT": RegionKey.NORTHEAST,
    "DE": RegionKey.NORTHEAST,
    "MA": RegionKey.NORTHEAST,
    "MD": RegionKey.NORTHEAST,
    "ME": RegionKey.NORTHEAST,
    "NH": RegionKey.NORTHEAST,
    "NJ": RegionKey.NORTHEAST,
    "NY": RegionKey.NORTHEAST,
    "PA": RegionKey.NORTHEAST,
    "RI": RegionKey.NORTHEAST,
    "VT": RegionKey.NORTHEAST,
    
    # Plains
    "CO": RegionKey.PLAINS,
    "MT": RegionKey.PLAINS,
    "NM": RegionKey.PLAINS,
    "WY": RegionKey.PLAINS,
    "UT": RegionKey.PLAINS,
    "ID": RegionKey.PLAINS,
    "NV": RegionKey.PLAINS,
    "AZ": RegionKey.PLAINS,
    
    # Northern
    "AK": RegionKey.NORTHERN,
    
    # West Coast (map to Plains for now)
    "WA": RegionKey.PLAINS,
    "OR": RegionKey.PLAINS,
    "CA": RegionKey.PLAINS,
    
    # Hawaii (unknown - minimal deer population)
    "HI": RegionKey.UNKNOWN,
}


# Region difficulty multipliers for age confidence (v1 defaults)
# Lower = harder to estimate age accurately in this region
REGION_DIFFICULTY_MULTIPLIERS: Dict[RegionKey, float] = {
    RegionKey.MIDWEST: 1.00,      # Best baseline
    RegionKey.NORTHEAST: 0.95,    # Slightly harder
    RegionKey.PLAINS: 0.90,       # Distance shots
    RegionKey.SOUTHEAST: 0.85,    # Body size variance
    RegionKey.SOUTH_TEXAS: 0.80,  # Unique phenotype
    RegionKey.NORTHERN: 0.90,     # Less data
    RegionKey.UNKNOWN: 0.88,      # Conservative default
}


# Region-specific uncertainty thresholds (v1 defaults)
# Higher = harder region requires higher confidence to avoid "uncertain"
# Region-specific uncertainty thresholds (FIXED - lowered to moderate range)
# Lower thresholds = only mark as uncertain for genuinely poor quality images
# These values represent the MINIMUM calibrated confidence needed to provide an age estimate
# Calibrated confidence is already scaled (max ~0.75), so thresholds should be proportionally lower
REGION_UNCERTAINTY_THRESHOLDS: Dict[RegionKey, float] = {
    RegionKey.MIDWEST: 0.35,       # Easiest region - only reject very low confidence
    RegionKey.NORTHEAST: 0.38,    # Slightly higher bar
    RegionKey.PLAINS: 0.40,       # Distance shots may have lower confidence
    RegionKey.SOUTHEAST: 0.42,    # Body size variance considered
    RegionKey.SOUTH_TEXAS: 0.45,  # Hardest region - still reasonable threshold
    RegionKey.NORTHERN: 0.40,     # Less data, moderate threshold
    RegionKey.UNKNOWN: 0.42,      # Conservative default for unknown regions
}


def _apply_region_threshold_env_overrides(
    defaults: Dict[RegionKey, float]
) -> Dict[RegionKey, float]:
    overridden = dict(defaults)
    for region, default in defaults.items():
        env_name = f"AGE_UNCERTAINTY_THRESHOLD_{region.value.upper()}"
        raw_value = os.environ.get(env_name)
        if raw_value is None:
            continue
        try:
            overridden[region] = max(0.0, min(1.0, float(raw_value)))
        except ValueError:
            logger.warning(
                "Invalid %s=%r; using default threshold %.2f",
                env_name,
                raw_value,
                default,
            )
    return overridden


REGION_UNCERTAINTY_THRESHOLDS = _apply_region_threshold_env_overrides(REGION_UNCERTAINTY_THRESHOLDS)


# ============================================================================
# DATA STRUCTURES
# ============================================================================

@dataclass
class RegionInfo:
    """Region assignment result."""
    region_key: RegionKey
    region_source: RegionSource
    region_state: Optional[str] = None


@dataclass
class RegionCalibrationInput:
    """Input data for region-aware calibration."""
    raw_confidence: float  # Model's raw confidence (0-100 scale)
    predicted_age: Optional[float] = None
    recommendation: Optional[str] = None
    deer_sex: Optional[str] = None
    antler_points: Optional[int] = None
    antler_points_left: Optional[int] = None
    antler_points_right: Optional[int] = None
    body_condition: Optional[str] = None
    image_quality_bucket: Optional[str] = None
    posture_bucket: Optional[str] = None
    quality_factors: Optional[Dict[str, Any]] = None
    # Region info
    state: Optional[str] = None  # Two-letter state from request
    user_profile_state: Optional[str] = None  # Fallback from user profile
    # Raw separate confidences (if model provides them)
    raw_age_confidence: Optional[float] = None
    raw_recommendation_confidence: Optional[float] = None


@dataclass
class RegionCalibrationOutput:
    """Output from region-aware calibration."""
    # Original values
    raw_confidence: float
    original_age: Optional[float]
    
    # Region assignment
    region_key: str
    region_source: str
    region_state: Optional[str]
    
    # Calibrated values (0-100 scale)
    calibrated_age_confidence: int
    calibrated_recommendation_confidence: int
    
    # Uncertainty
    age_uncertain: bool
    adjusted_age: Optional[float]
    
    # Metadata
    calibration_version: str
    calibration_strategy: str
    calibration_fallback_reason: Optional[str] = None
    
    # Raw values preserved for analysis
    raw_age_confidence: Optional[int] = None
    raw_recommendation_confidence: Optional[int] = None
    # What the displayed age_confidence means (traceability)
    age_confidence_target: str = "heuristic_reliability_score"
    age_confidence_method: str = "heuristic"
    shadow: Optional[List[Dict[str, Any]]] = None
    range_coverage: Optional[Dict[str, Any]] = None


# ============================================================================
# REGION ASSIGNMENT FUNCTIONS
# ============================================================================

def get_region_from_state(state: Optional[str]) -> RegionKey:
    """
    Map a two-letter state code to a region key.
    
    Args:
        state: Two-letter state code (e.g., 'IA', 'TX')
        
    Returns:
        RegionKey enum value
    """
    if not state:
        return RegionKey.UNKNOWN
    
    state_upper = state.upper().strip()
    # Mapping v2 (opt-in via REGION_MAPPING_VERSION=v2): a state-level "TX" is too coarse to imply the
    # South Texas phenotype, so it stays UNKNOWN (uncertainty preserved) instead of being forced to south_texas.
    if state_upper == "TX" and RegionCalibrationConfig.REGION_MAPPING_VERSION == "v2":
        return RegionKey.UNKNOWN
    return STATE_TO_REGION_V1.get(state_upper, RegionKey.UNKNOWN)


def determine_region(
    scan_state: Optional[str],
    user_profile_state: Optional[str]
) -> RegionInfo:
    """
    Determine region using priority chain:
    1. scan_state (from request)
    2. user_profile_state (fallback)
    3. unknown (final fallback)
    
    EXIF GPS is NOT implemented in this version.
    
    Args:
        scan_state: State from scan request
        user_profile_state: State from user profile
        
    Returns:
        RegionInfo with region_key, region_source, and region_state
    """
    # Priority 1: Scan input state
    if scan_state:
        state_clean = scan_state.upper().strip()
        if len(state_clean) == 2:
            region_key = get_region_from_state(state_clean)
            return RegionInfo(
                region_key=region_key,
                region_source=RegionSource.SCAN_INPUT,
                region_state=state_clean
            )
    
    # Priority 2: User profile state
    if user_profile_state:
        state_clean = user_profile_state.upper().strip()
        if len(state_clean) == 2:
            region_key = get_region_from_state(state_clean)
            return RegionInfo(
                region_key=region_key,
                region_source=RegionSource.USER_PROFILE,
                region_state=state_clean
            )
    
    # Priority 3: Unknown fallback
    return RegionInfo(
        region_key=RegionKey.UNKNOWN,
        region_source=RegionSource.FALLBACK_UNKNOWN,
        region_state=None
    )


# ============================================================================
# HEURISTIC CALIBRATION FUNCTIONS
# ============================================================================

def _heuristic_v3(scaled, predicted_age, deer_sex, region_key, quality_bucket, posture, qf) -> float:
    """De-duplicated candidate heuristic (opt-in). Each piece of evidence is counted once:
    - The pre-calibration stage already deducts for camera-angle/distance risk, alternate-age disagreement,
      consensus spread and multi-photo conflicts, so none of those are repeated here.
    - Image quality bucket, blur, occlusion, body/head visibility and posture all describe the same
      "can the age cues be seen" evidence: only the single strongest of those penalties applies.
    - No blanket missing-antler penalty: antlers are a weak secondary cue by design.
    - No bonuses are added.
    """
    config = RegionCalibrationConfig
    sex = (deer_sex or "").strip().lower()
    if predicted_age is None or predicted_age == 0:
        scaled *= (1 - config.NULL_AGE_PENALTY)
    if not sex or sex == "unknown":
        scaled *= (1 - config.UNKNOWN_SEX_PENALTY)
    visual = [1.0,
              {"fair": 0.95, "poor": 0.80}.get(quality_bucket, 1.0),
              {"head_down": 0.90, "frontal": 0.88, "rear": 0.88, "unknown": 0.88}.get(posture, 1.0),
              {"low": 0.86, "medium": 0.96}.get(qf.get("body_visibility"), 1.0),
              {"low": 0.92, "medium": 0.98}.get(qf.get("head_visibility"), 1.0),
              {"high": 0.82, "medium": 0.94}.get(qf.get("occlusion"), 1.0),
              {"high": 0.86, "medium": 0.95}.get(qf.get("blur"), 1.0)]
    scaled *= min(visual)
    scaled *= REGION_DIFFICULTY_MULTIPLIERS.get(region_key, 0.88)
    return max(0.0, min(scaled, config.MAX_AGE_CONFIDENCE))


def compute_age_confidence_with_region(
    raw_confidence: float,
    predicted_age: Optional[float],
    deer_sex: Optional[str],
    antler_points: Optional[int],
    antler_points_left: Optional[int],
    antler_points_right: Optional[int],
    region_key: RegionKey,
    image_quality_bucket: Optional[str] = None,
    posture_bucket: Optional[str] = None,
    quality_factors: Optional[Dict[str, Any]] = None,
) -> float:
    """
    Compute calibrated age confidence with region-specific adjustments.
    
    Returns confidence as 0-1 float.
    """
    config = RegionCalibrationConfig
    deer_sex_normalized = (deer_sex or "").strip().lower()
    is_buck = deer_sex_normalized == "buck"
    is_doe = deer_sex_normalized == "doe"
    
    # Start with raw confidence (convert from 0-100 to 0-1)
    base_confidence = (raw_confidence or 0) / 100.0
    
    # Apply base scaling
    scaled_confidence = base_confidence * config.AGE_CONFIDENCE_BASE_SCALE

    if config.HEURISTIC_VERSION == "v3":
        return _heuristic_v3(scaled_confidence, predicted_age, deer_sex, region_key,
                             image_quality_bucket, posture_bucket, quality_factors or {})
    
    # Penalty: No age predicted
    if predicted_age is None or predicted_age == 0:
        scaled_confidence *= (1 - config.NULL_AGE_PENALTY)
    
    # Penalty: Missing antler information
    has_antler_detail = (
        antler_points is not None and 
        antler_points_left is not None and 
        antler_points_right is not None
    )
    if is_buck and not has_antler_detail:
        scaled_confidence *= (1 - config.LOW_ANTLER_INFO_PENALTY)
    
    # Penalty: Unknown sex
    if deer_sex is None or deer_sex_normalized == 'unknown':
        scaled_confidence *= (1 - config.UNKNOWN_SEX_PENALTY)

    # Penalty: Lower-quality images reduce age reliability quickly.
    if image_quality_bucket == "fair":
        scaled_confidence *= 0.95
    elif image_quality_bucket == "poor":
        scaled_confidence *= 0.80

    # Penalty: Non-profile postures hide core age cues.
    if posture_bucket == "head_down":
        scaled_confidence *= 0.90
    elif posture_bucket in {"frontal", "rear", "unknown"}:
        scaled_confidence *= 0.88

    # Penalty: Explicit visibility issues from the model's quality rubric.
    quality_factors = quality_factors or {}
    if quality_factors.get("body_visibility") == "low":
        scaled_confidence *= 0.86
    elif quality_factors.get("body_visibility") == "medium":
        scaled_confidence *= 0.96

    if quality_factors.get("head_visibility") == "low":
        scaled_confidence *= 0.92
    elif quality_factors.get("head_visibility") == "medium":
        scaled_confidence *= 0.98

    if quality_factors.get("occlusion") == "high":
        scaled_confidence *= 0.82
    elif quality_factors.get("occlusion") == "medium":
        scaled_confidence *= 0.94

    if quality_factors.get("blur") == "high":
        scaled_confidence *= 0.86
    elif quality_factors.get("blur") == "medium":
        scaled_confidence *= 0.95
    
    # Apply region difficulty multiplier
    region_multiplier = REGION_DIFFICULTY_MULTIPLIERS.get(region_key, 0.88)
    scaled_confidence *= region_multiplier

    # Does are aged from body profile only, so avoid over-suppressing valid doe estimates.
    if is_doe and predicted_age is not None:
        scaled_confidence = min(config.MAX_AGE_CONFIDENCE, scaled_confidence * 1.05)
    
    # Apply global cap
    scaled_confidence = min(scaled_confidence, config.MAX_AGE_CONFIDENCE)
    
    # Ensure non-negative
    return max(0, scaled_confidence)


def compute_recommendation_confidence_with_region(
    raw_confidence: float,
    recommendation: Optional[str],
    predicted_age: Optional[float],
    deer_sex: Optional[str],
    region_key: RegionKey
) -> float:
    """
    Compute calibrated recommendation confidence.
    Recommendation is more robust to regional variance than age.
    
    Returns confidence as 0-1 float.
    """
    config = RegionCalibrationConfig
    
    # Start with raw confidence (convert from 0-100 to 0-1)
    base_confidence = (raw_confidence or 0) / 100.0
    
    # Apply base scaling (less aggressive than age)
    scaled_confidence = base_confidence * config.RECOMMENDATION_CONFIDENCE_BASE_SCALE
    
    # Small penalty if age is unknown
    if predicted_age is None or predicted_age == 0:
        scaled_confidence *= 0.90  # 10% penalty
    
    # Penalty if recommendation is missing
    if recommendation is None:
        scaled_confidence *= 0.5
    
    # Apply global cap
    scaled_confidence = min(scaled_confidence, config.MAX_RECOMMENDATION_CONFIDENCE)
    
    # Note: No region multiplier for recommendation - it's more stable across regions
    
    return max(0, scaled_confidence)


def apply_uncertainty_gate(
    calibrated_age_confidence: float,
    region_key: RegionKey,
    predicted_age: Optional[float],
    deer_sex: Optional[str] = None,
) -> Tuple[bool, Optional[float]]:
    """
    Apply region-specific uncertainty threshold.
    
    If confidence below threshold, mark age as uncertain and null it out.
    
    Returns:
        Tuple of (age_uncertain, adjusted_age)
    """
    threshold = REGION_UNCERTAINTY_THRESHOLDS.get(region_key, 0.68)
    deer_sex_normalized = (deer_sex or "").strip().lower()

    # The model returning a numeric age is not evidence that the age is reliable, so it never lowers the bar.
    if deer_sex_normalized == "doe" and predicted_age is not None:
        threshold = max(0.12, threshold - RegionCalibrationConfig.DOE_UNCERTAINTY_THRESHOLD_OFFSET)

    age_uncertain = calibrated_age_confidence < threshold
    logger.info(
        "Age uncertainty gate: region=%s predicted_age=%s deer_sex=%s calibrated_age_confidence=%.3f "
        "threshold=%.3f age_uncertain=%s",
        region_key.value,
        predicted_age,
        deer_sex,
        calibrated_age_confidence,
        threshold,
        age_uncertain,
    )

    if age_uncertain:
        return True, None
    
    return False, predicted_age


# ============================================================================
# MAIN CALIBRATION FUNCTION
# ============================================================================

def calibrate_with_region(
    input_data: RegionCalibrationInput,
    active_curves: Optional[Dict] = None,
    artifacts: Optional[List[Dict[str, Any]]] = None,
    runtime: Optional[Dict[str, Any]] = None,
) -> RegionCalibrationOutput:
    """
    Main entry point for region-aware confidence calibration.
    
    Implements fallback chain:
    1. curve_region (if enabled and mature curve exists)
    2. curve_global (if enabled and mature curve exists)
    3. heuristic_region (default)
    4. legacy (passthrough if all else fails)
    
    Args:
        input_data: RegionCalibrationInput with all scan data
        active_curves: Optional dict of active curves from database
                       Key: (curve_type, region_key), Value: curve data dict
        
    Returns:
        RegionCalibrationOutput with calibrated values
    """
    config = RegionCalibrationConfig
    
    # Check if calibration is enabled at all
    if not config.CALIBRATION_ENABLED:
        return RegionCalibrationOutput(
            raw_confidence=input_data.raw_confidence,
            original_age=input_data.predicted_age,
            region_key=RegionKey.UNKNOWN.value,
            region_source=RegionSource.FALLBACK_UNKNOWN.value,
            region_state=None,
            calibrated_age_confidence=int(input_data.raw_confidence or 0),
            calibrated_recommendation_confidence=int(input_data.raw_confidence or 0),
            age_uncertain=False,
            adjusted_age=input_data.predicted_age,
            calibration_version="disabled",
            calibration_strategy=CalibrationStrategy.LEGACY.value,
            calibration_fallback_reason="calibration_disabled"
        )
    
    # Determine region
    region_info = determine_region(
        scan_state=input_data.state,
        user_profile_state=input_data.user_profile_state
    )
    
    region_key = region_info.region_key
    
    # Determine calibration strategy (fallback chain)
    calibration_strategy = CalibrationStrategy.HEURISTIC_REGION
    fallback_reason = None
    age_confidence = None
    recommendation_confidence = None
    calibration_version = config.CALIBRATION_VERSION
    age_raw_confidence = input_data.raw_age_confidence if input_data.raw_age_confidence is not None else input_data.raw_confidence
    recommendation_raw_confidence = (
        input_data.raw_recommendation_confidence
        if input_data.raw_recommendation_confidence is not None
        else input_data.raw_confidence
    )
    
    # Phase 2 legacy curves: they carry no prediction target and no model/prompt/preprocessing
    # compatibility, so they are never applied (an unversioned curve cannot give a percentage a meaning).
    if config.CALIBRATION_CURVES_ENABLED and active_curves:
        fallback_reason = "legacy_curves_unversioned_ignored"
    age_target = HEURISTIC_TARGET
    age_method = f"heuristic_{config.HEURISTIC_VERSION}"
    shadow_results: List[Dict[str, Any]] = []
    range_coverage: Optional[Dict[str, Any]] = None

    # Validated, versioned artifacts (active ones drive the score; shadow ones are only recorded)
    runtime = runtime or {}
    if artifacts:
        # Only this scan's region artifacts (first), then global ones; never another region's curve.
        artifacts = select_artifact(artifacts, region_key.value)
        for art in artifacts:
            entry = {"artifact_id": art.get("artifact_id"), "status": art.get("_status"), "target": art.get("target")}
            reasons = check_compatibility(art, model=runtime.get("model"), prompt_version=runtime.get("prompt_version"),
                                          preprocessing_version=runtime.get("preprocessing_version"))
            if reasons:
                entry.update(value=None, fallback_reason="incompatible:" + ";".join(reasons))
            else:
                value, reason = apply_artifact(art, age_raw_confidence)
                entry.update(value=round(value * 100) if value is not None else None, fallback_reason=reason)
            if art.get("_status") == "shadow":
                shadow_results.append(entry)
            elif art.get("target") == "age_range_coverage":
                # Range coverage is a different meaning: it never replaces the exact-age score.
                if entry["value"] is not None and range_coverage is None:
                    range_coverage = {"value": entry["value"], "artifact_id": art["artifact_id"]}
            elif age_confidence is None and entry["value"] is not None:
                age_confidence = entry["value"] / 100.0
                calibration_strategy = CalibrationStrategy.ARTIFACT
                calibration_version = art["artifact_id"]
                age_target, age_method = art["target"], art["method"]
            elif age_confidence is None:
                fallback_reason = f"active_artifact_unusable:{entry['fallback_reason']}"
    # Fall back to heuristic if no curve calibration was applied
    if age_confidence is None:
        if artifacts is not None:
            fallback_reason = fallback_reason or "no_active_artifact"
        
        # Compute calibrated age confidence with heuristics
        if config.CALIBRATION_REGION_ENABLED:
            age_confidence = compute_age_confidence_with_region(
                raw_confidence=age_raw_confidence,
                predicted_age=input_data.predicted_age,
                deer_sex=input_data.deer_sex,
                antler_points=input_data.antler_points,
                antler_points_left=input_data.antler_points_left,
                antler_points_right=input_data.antler_points_right,
                region_key=region_key,
                image_quality_bucket=input_data.image_quality_bucket,
                posture_bucket=input_data.posture_bucket,
                quality_factors=input_data.quality_factors,
            )
            calibration_strategy = CalibrationStrategy.HEURISTIC_REGION
        else:
            # Fall back to global heuristic (no region multiplier)
            calibration_strategy = CalibrationStrategy.HEURISTIC_GLOBAL
            age_confidence = compute_age_confidence_with_region(
                raw_confidence=age_raw_confidence,
                predicted_age=input_data.predicted_age,
                deer_sex=input_data.deer_sex,
                antler_points=input_data.antler_points,
                antler_points_left=input_data.antler_points_left,
                antler_points_right=input_data.antler_points_right,
                region_key=RegionKey.MIDWEST,  # Use midwest (1.0 multiplier) for global
                image_quality_bucket=input_data.image_quality_bucket,
                posture_bucket=input_data.posture_bucket,
                quality_factors=input_data.quality_factors,
            )
            fallback_reason = fallback_reason or "region_calibration_disabled"
    
    if recommendation_confidence is None:
        # Compute calibrated recommendation confidence with heuristics
        recommendation_confidence = compute_recommendation_confidence_with_region(
            raw_confidence=recommendation_raw_confidence,
            recommendation=input_data.recommendation,
            predicted_age=input_data.predicted_age,
            deer_sex=input_data.deer_sex,
            region_key=region_key
        )
    
    # Apply uncertainty gate
    age_uncertain, adjusted_age = apply_uncertainty_gate(
        calibrated_age_confidence=age_confidence,
        region_key=region_key,
        predicted_age=input_data.predicted_age,
        deer_sex=input_data.deer_sex,
    )
    
    # Convert to 0-100 scale for storage
    calibrated_age_confidence_pct = round(age_confidence * 100)
    calibrated_recommendation_confidence_pct = round(recommendation_confidence * 100)
    
    logger.info(
        f"Region calibration: region={region_key.value}, source={region_info.region_source.value}, "
        f"raw={input_data.raw_confidence}%, age_conf={calibrated_age_confidence_pct}%, "
        f"rec_conf={calibrated_recommendation_confidence_pct}%, age_uncertain={age_uncertain}, "
        f"strategy={calibration_strategy.value}"
    )
    
    return RegionCalibrationOutput(
        raw_confidence=input_data.raw_confidence,
        original_age=input_data.predicted_age,
        region_key=region_key.value,
        region_source=region_info.region_source.value,
        region_state=region_info.region_state,
        calibrated_age_confidence=calibrated_age_confidence_pct,
        calibrated_recommendation_confidence=calibrated_recommendation_confidence_pct,
        age_uncertain=age_uncertain,
        adjusted_age=adjusted_age,
        calibration_version=calibration_version,
        calibration_strategy=calibration_strategy.value,
        calibration_fallback_reason=fallback_reason,
        raw_age_confidence=int(input_data.raw_age_confidence) if input_data.raw_age_confidence is not None else None,
        raw_recommendation_confidence=(
            int(input_data.raw_recommendation_confidence)
            if input_data.raw_recommendation_confidence is not None
            else None
        ),
        age_confidence_target=age_target,
        age_confidence_method=age_method,
        shadow=shadow_results or None,
        range_coverage=range_coverage,
    )


def calibrate_from_dict_with_region(
    analysis: Dict[str, Any],
    state: Optional[str] = None,
    user_profile_state: Optional[str] = None,
    active_curves: Optional[Dict[Tuple[str, Optional[str]], Dict[str, Any]]] = None,
    artifacts: Optional[List[Dict[str, Any]]] = None,
    preprocessing_version: Optional[str] = None,
) -> Tuple[RegionCalibrationOutput, Dict[str, Any]]:
    """
    Convenience function to calibrate from a raw analysis dictionary.
    
    Args:
        analysis: Raw analysis dictionary from model
        state: Two-letter state from request
        user_profile_state: Two-letter state from user profile
        active_curves: Optional dict of active empirical calibration curves
        
    Returns:
        Tuple of (RegionCalibrationOutput, updated analysis dict)
    """
    input_data = RegionCalibrationInput(
        raw_confidence=analysis.get("confidence", 0) or 0,
        predicted_age=analysis.get("deer_age"),
        recommendation=analysis.get("recommendation"),
        deer_sex=analysis.get("deer_sex"),
        antler_points=analysis.get("antler_points"),
        antler_points_left=analysis.get("antler_points_left"),
        antler_points_right=analysis.get("antler_points_right"),
        body_condition=analysis.get("body_condition"),
        image_quality_bucket=analysis.get("image_quality_bucket"),
        posture_bucket=analysis.get("posture_bucket"),
        quality_factors=analysis.get("quality_factors"),
        state=state,
        user_profile_state=user_profile_state,
        raw_age_confidence=analysis.get("raw_age_confidence"),
        raw_recommendation_confidence=analysis.get("raw_recommendation_confidence"),
    )
    
    runtime = {
        "model": analysis.get("analysis_model"),
        "prompt_version": analysis.get("analysis_prompt_version"),
        "preprocessing_version": preprocessing_version,
    }
    calibration_result = calibrate_with_region(
        input_data, active_curves=active_curves, artifacts=artifacts, runtime=runtime,
    )
    
    # Create updated analysis dict with calibrated values
    updated_analysis = analysis.copy()
    
    # Core calibration fields (always set)
    updated_analysis["raw_confidence"] = int(calibration_result.raw_confidence)
    updated_analysis["raw_age_confidence"] = calibration_result.raw_age_confidence
    updated_analysis["raw_recommendation_confidence"] = calibration_result.raw_recommendation_confidence
    updated_analysis["age_confidence"] = calibration_result.calibrated_age_confidence
    updated_analysis["recommendation_confidence"] = calibration_result.calibrated_recommendation_confidence
    updated_analysis["age_uncertain"] = calibration_result.age_uncertain
    updated_analysis["calibration_version"] = calibration_result.calibration_version
    
    # Region fields (always persist internally)
    updated_analysis["region_key"] = calibration_result.region_key
    updated_analysis["region_source"] = calibration_result.region_source
    updated_analysis["region_state"] = calibration_result.region_state
    updated_analysis["calibration_strategy"] = calibration_result.calibration_strategy
    updated_analysis["calibration_fallback_reason"] = calibration_result.calibration_fallback_reason
    
    # Apply uncertainty gate to age
    if calibration_result.age_uncertain:
        updated_analysis["deer_age"] = None
        updated_analysis["age_bucket"] = None
        updated_analysis["age_range"] = None
        updated_analysis["buck_age_class"] = None
        if not updated_analysis.get("retake_reason"):
            updated_analysis["reasoning"] = (
                "Visible body cues suggest a possible age class, but confidence calibration "
                "was too low to keep a defensible numeric age estimate."
            )

    # Update legacy confidence field to use recommendation confidence
    updated_analysis["confidence"] = calibration_result.calibrated_recommendation_confidence

    # ── Build structured score_audit ──
    pre_calibration_steps = updated_analysis.pop("_pre_calibration_audit_steps", [])
    calibration_audit_step = {
        "step": "calibration",
        "strategy": calibration_result.calibration_strategy,
        "version": calibration_result.calibration_version,
        "region": calibration_result.region_key,
        "adjustments": [
            {
                "field": "age_confidence",
                "before": calibration_result.raw_age_confidence,
                "after": calibration_result.calibrated_age_confidence,
            },
            {
                "field": "recommendation_confidence",
                "before": calibration_result.raw_recommendation_confidence,
                "after": calibration_result.calibrated_recommendation_confidence,
            },
        ],
    }
    if calibration_result.calibration_fallback_reason:
        calibration_audit_step["fallback_reason"] = calibration_result.calibration_fallback_reason

    uncertainty_step = {
        "step": "uncertainty_gate",
        "age_uncertain": calibration_result.age_uncertain,
    }

    all_steps = pre_calibration_steps + [calibration_audit_step, uncertainty_step]

    # Handle consensus audit if present
    consensus_data = updated_analysis.get("consensus")
    if consensus_data and isinstance(consensus_data, dict):
        consensus_step = {
            "step": "consensus",
            "runs": consensus_data.get("total_runs"),
            "agreement": consensus_data.get("age_agreement_rate"),
        }
        final_age_conf = consensus_data.get("final_age_confidence")
        final_rec_conf = consensus_data.get("final_recommendation_confidence")
        if final_age_conf is not None or final_rec_conf is not None:
            consensus_step["adjustments"] = []
            if final_age_conf is not None:
                consensus_step["adjustments"].append({
                    "field": "age_confidence",
                    "after": final_age_conf,
                    "reason": "consensus_override",
                })
            if final_rec_conf is not None:
                consensus_step["adjustments"].append({
                    "field": "recommendation_confidence",
                    "after": final_rec_conf,
                    "reason": "consensus_override",
                })
        all_steps.append(consensus_step)

    displayed_score = {
        "field": "age_confidence",
        "value": calibration_result.calibrated_age_confidence,
        "method": calibration_result.age_confidence_method,
        "method_version": calibration_result.calibration_version,
        "target": calibration_result.age_confidence_target,
        "target_definition": TARGETS.get(calibration_result.age_confidence_target, HEURISTIC_TARGET_DEFINITION),
        "fallback_reason": calibration_result.calibration_fallback_reason,
        "region_mapping_version": RegionCalibrationConfig.REGION_MAPPING_VERSION,
    }
    updated_analysis["age_confidence_target"] = calibration_result.age_confidence_target
    if calibration_result.range_coverage and updated_analysis.get("age_range"):
        updated_analysis["range_coverage_confidence"] = calibration_result.range_coverage["value"]
        updated_analysis["range_status"] = "calibrated"
        displayed_score["range_coverage"] = calibration_result.range_coverage
    updated_analysis["score_audit"] = {
        "version": "1.1",
        "displayed_score": displayed_score,
        "shadow_calibration": calibration_result.shadow,
        "preprocessing_version": preprocessing_version,
        "model": updated_analysis.get("analysis_model"),
        "prompt_version": updated_analysis.get("analysis_prompt_version"),
        "calibration_strategy": calibration_result.calibration_strategy,
        "calibration_version": calibration_result.calibration_version,
        "steps": all_steps,
        "final_scores": {
            "age_confidence": calibration_result.calibrated_age_confidence,
            "recommendation_confidence": calibration_result.calibrated_recommendation_confidence,
            "legacy_confidence": calibration_result.calibrated_recommendation_confidence,
        },
    }
    
    return calibration_result, updated_analysis


# ============================================================================
# ADMIN & DIAGNOSTICS FUNCTIONS
# ============================================================================

def get_region_calibration_metadata() -> Dict[str, Any]:
    """
    Return comprehensive metadata about region calibration configuration.
    """
    config = RegionCalibrationConfig
    
    return {
        "enabled": config.CALIBRATION_ENABLED,
        "region_enabled": config.CALIBRATION_REGION_ENABLED,
        "curves_enabled": config.CALIBRATION_CURVES_ENABLED,
        "version": config.CALIBRATION_VERSION,
        "region_mapping_version": config.REGION_MAPPING_VERSION,
        "feature_flags": {
            "show_region": config.CALIBRATION_SHOW_REGION,
            "show_strategy": config.CALIBRATION_SHOW_STRATEGY
        },
        "maturity_gates": {
            "global_curve_min_samples": config.GLOBAL_CURVE_MIN_SAMPLES,
            "region_curve_min_samples": config.REGION_CURVE_MIN_SAMPLES
        },
        "scaling": {
            "age_confidence_base_scale": config.AGE_CONFIDENCE_BASE_SCALE,
            "recommendation_confidence_base_scale": config.RECOMMENDATION_CONFIDENCE_BASE_SCALE
        },
        "caps": {
            "max_age_confidence": config.MAX_AGE_CONFIDENCE,
            "max_recommendation_confidence": config.MAX_RECOMMENDATION_CONFIDENCE
        },
        "penalties": {
            "null_age": config.NULL_AGE_PENALTY,
            "low_antler_info": config.LOW_ANTLER_INFO_PENALTY,
            "unknown_sex": config.UNKNOWN_SEX_PENALTY
        },
        "sex_specific": {
            "doe_uncertainty_threshold_offset": config.DOE_UNCERTAINTY_THRESHOLD_OFFSET
        },
        "regions": {
            region.value: {
                "difficulty_multiplier": REGION_DIFFICULTY_MULTIPLIERS.get(region, 0.88),
                "uncertainty_threshold": REGION_UNCERTAINTY_THRESHOLDS.get(region, 0.68)
            }
            for region in RegionKey
        },
        "state_mapping_sample": {
            "TX": "south_texas",
            "IA": "midwest",
            "GA": "southeast",
            "NY": "northeast",
            "MT": "plains",
            "AK": "northern"
        }
    }


def get_calibration_status() -> Dict[str, Any]:
    """
    Get calibration system status for admin diagnostics.
    """
    return {
        "status": "operational",
        "active_version": RegionCalibrationConfig.CALIBRATION_VERSION,
        "strategies_available": [s.value for s in CalibrationStrategy],
        "regions_configured": len(RegionKey),
        "states_mapped": len(STATE_TO_REGION_V1),
        "curves": {
            "global_age": {"available": False, "mature": False, "sample_count": 0},
            "global_recommendation": {"available": False, "mature": False, "sample_count": 0},
            "region_curves": {}  # Will be populated when curves are implemented
        },
        "feature_flags": {
            "calibration_enabled": RegionCalibrationConfig.CALIBRATION_ENABLED,
            "region_enabled": RegionCalibrationConfig.CALIBRATION_REGION_ENABLED,
            "curves_enabled": RegionCalibrationConfig.CALIBRATION_CURVES_ENABLED
        }
    }


def get_all_regions() -> List[Dict[str, Any]]:
    """Get all configured regions with their settings."""
    return [
        {
            "key": region.value,
            "difficulty_multiplier": REGION_DIFFICULTY_MULTIPLIERS.get(region, 0.88),
            "uncertainty_threshold": REGION_UNCERTAINTY_THRESHOLDS.get(region, 0.68),
            "states": [
                state for state, r in STATE_TO_REGION_V1.items() 
                if r == region
            ]
        }
        for region in RegionKey
    ]
