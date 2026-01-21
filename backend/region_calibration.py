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
"""

import os
import logging
from typing import Dict, Any, Optional, Tuple, List
from dataclasses import dataclass, field
from enum import Enum
from datetime import datetime

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
    REGION_MAPPING_VERSION: str = "v1"
    
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
REGION_UNCERTAINTY_THRESHOLDS: Dict[RegionKey, float] = {
    RegionKey.MIDWEST: 0.55,
    RegionKey.NORTHEAST: 0.60,
    RegionKey.PLAINS: 0.62,
    RegionKey.SOUTHEAST: 0.65,
    RegionKey.SOUTH_TEXAS: 0.70,
    RegionKey.NORTHERN: 0.62,
    RegionKey.UNKNOWN: 0.68,
}


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

def compute_age_confidence_with_region(
    raw_confidence: float,
    predicted_age: Optional[float],
    deer_sex: Optional[str],
    antler_points: Optional[int],
    antler_points_left: Optional[int],
    antler_points_right: Optional[int],
    region_key: RegionKey
) -> float:
    """
    Compute calibrated age confidence with region-specific adjustments.
    
    Returns confidence as 0-1 float.
    """
    config = RegionCalibrationConfig
    
    # Start with raw confidence (convert from 0-100 to 0-1)
    base_confidence = (raw_confidence or 0) / 100.0
    
    # Apply base scaling
    scaled_confidence = base_confidence * config.AGE_CONFIDENCE_BASE_SCALE
    
    # Penalty: No age predicted
    if predicted_age is None or predicted_age == 0:
        scaled_confidence *= (1 - config.NULL_AGE_PENALTY)
    
    # Penalty: Missing antler information
    has_antler_detail = (
        antler_points is not None and 
        antler_points_left is not None and 
        antler_points_right is not None
    )
    if not has_antler_detail:
        scaled_confidence *= (1 - config.LOW_ANTLER_INFO_PENALTY)
    
    # Penalty: Unknown sex
    if deer_sex is None or deer_sex.lower() == 'unknown':
        scaled_confidence *= (1 - config.UNKNOWN_SEX_PENALTY)
    
    # Apply region difficulty multiplier
    region_multiplier = REGION_DIFFICULTY_MULTIPLIERS.get(region_key, 0.88)
    scaled_confidence *= region_multiplier
    
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
    predicted_age: Optional[float]
) -> Tuple[bool, Optional[float]]:
    """
    Apply region-specific uncertainty threshold.
    
    If confidence below threshold, mark age as uncertain and null it out.
    
    Returns:
        Tuple of (age_uncertain, adjusted_age)
    """
    threshold = REGION_UNCERTAINTY_THRESHOLDS.get(region_key, 0.68)
    
    if calibrated_age_confidence < threshold:
        return True, None
    
    return False, predicted_age


# ============================================================================
# MAIN CALIBRATION FUNCTION
# ============================================================================

def calibrate_with_region(input_data: RegionCalibrationInput, active_curves: Optional[Dict] = None) -> RegionCalibrationOutput:
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
    
    # Phase 2: Check for curve-based calibration
    if config.CALIBRATION_CURVES_ENABLED and active_curves:
        # Try region-specific age curve first
        region_age_key = ("region_age", region_key.value)
        global_age_key = ("global_age", None)
        
        region_rec_key = ("region_recommendation", region_key.value)
        global_rec_key = ("global_recommendation", None)
        
        # Age calibration via curves
        if region_age_key in active_curves:
            curve = active_curves[region_age_key]
            age_confidence = _apply_curve(input_data.raw_confidence, curve)
            calibration_strategy = CalibrationStrategy.CURVE_REGION
            calibration_version = curve.get("calibration_version", config.CALIBRATION_VERSION)
            logger.info(f"Using region age curve for {region_key.value}")
        elif global_age_key in active_curves:
            curve = active_curves[global_age_key]
            age_confidence = _apply_curve(input_data.raw_confidence, curve)
            calibration_strategy = CalibrationStrategy.CURVE_GLOBAL
            calibration_version = curve.get("calibration_version", config.CALIBRATION_VERSION)
            fallback_reason = "region_curve_missing"
            logger.info(f"Using global age curve (region {region_key.value} not available)")
        
        # Recommendation calibration via curves
        if region_rec_key in active_curves:
            curve = active_curves[region_rec_key]
            recommendation_confidence = _apply_curve(input_data.raw_confidence, curve)
        elif global_rec_key in active_curves:
            curve = active_curves[global_rec_key]
            recommendation_confidence = _apply_curve(input_data.raw_confidence, curve)
    
    # Fall back to heuristic if no curve calibration was applied
    if age_confidence is None:
        if config.CALIBRATION_CURVES_ENABLED:
            fallback_reason = fallback_reason or "no_active_curves"
        
        # Compute calibrated age confidence with heuristics
        if config.CALIBRATION_REGION_ENABLED:
            age_confidence = compute_age_confidence_with_region(
                raw_confidence=input_data.raw_confidence,
                predicted_age=input_data.predicted_age,
                deer_sex=input_data.deer_sex,
                antler_points=input_data.antler_points,
                antler_points_left=input_data.antler_points_left,
                antler_points_right=input_data.antler_points_right,
                region_key=region_key
            )
            calibration_strategy = CalibrationStrategy.HEURISTIC_REGION
        else:
            # Fall back to global heuristic (no region multiplier)
            calibration_strategy = CalibrationStrategy.HEURISTIC_GLOBAL
            age_confidence = compute_age_confidence_with_region(
                raw_confidence=input_data.raw_confidence,
                predicted_age=input_data.predicted_age,
                deer_sex=input_data.deer_sex,
                antler_points=input_data.antler_points,
                antler_points_left=input_data.antler_points_left,
                antler_points_right=input_data.antler_points_right,
                region_key=RegionKey.MIDWEST  # Use midwest (1.0 multiplier) for global
            )
            fallback_reason = fallback_reason or "region_calibration_disabled"
    
    if recommendation_confidence is None:
        # Compute calibrated recommendation confidence with heuristics
        recommendation_confidence = compute_recommendation_confidence_with_region(
            raw_confidence=input_data.raw_confidence,
            recommendation=input_data.recommendation,
            predicted_age=input_data.predicted_age,
            deer_sex=input_data.deer_sex,
            region_key=region_key
        )
    
    # Apply uncertainty gate
    age_uncertain, adjusted_age = apply_uncertainty_gate(
        calibrated_age_confidence=age_confidence,
        region_key=region_key,
        predicted_age=input_data.predicted_age
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
        raw_age_confidence=int(input_data.raw_age_confidence) if input_data.raw_age_confidence else None,
        raw_recommendation_confidence=int(input_data.raw_recommendation_confidence) if input_data.raw_recommendation_confidence else None
    )


def _apply_curve(raw_confidence: float, curve: Dict[str, Any]) -> float:
    """
    Apply curve-based calibration to a raw confidence value.
    
    Args:
        raw_confidence: Raw confidence (0-100 scale)
        curve: Curve data dict with bins
        
    Returns:
        Calibrated confidence as 0-1 float
    """
    bins = curve.get("bins", [])
    if not bins:
        # No bins, fall back to scaled raw
        return (raw_confidence or 0) / 100.0
    
    # Find the appropriate bin
    conf = raw_confidence or 0
    bin_idx = min(int(conf // 10), 9)  # 0-9
    
    if bin_idx < len(bins):
        bin_data = bins[bin_idx]
        sample_count = bin_data.get("sample_count", 0)
        
        # Use calibrated value if bin has enough samples
        min_bin_samples = int(os.environ.get('BIN_MIN_SAMPLES', '20'))
        if sample_count >= min_bin_samples:
            return bin_data.get("calibrated_confidence", conf / 100.0)
    
    # Fallback: return raw confidence scaled
    return conf / 100.0


def calibrate_from_dict_with_region(
    analysis: Dict[str, Any],
    state: Optional[str] = None,
    user_profile_state: Optional[str] = None
) -> Tuple[RegionCalibrationOutput, Dict[str, Any]]:
    """
    Convenience function to calibrate from a raw analysis dictionary.
    
    Args:
        analysis: Raw analysis dictionary from model
        state: Two-letter state from request
        user_profile_state: Two-letter state from user profile
        
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
        state=state,
        user_profile_state=user_profile_state
    )
    
    calibration_result = calibrate_with_region(input_data)
    
    # Create updated analysis dict with calibrated values
    updated_analysis = analysis.copy()
    
    # Core calibration fields (always set)
    updated_analysis["raw_confidence"] = int(calibration_result.raw_confidence)
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
    
    # Update legacy confidence field to use recommendation confidence
    updated_analysis["confidence"] = calibration_result.calibrated_recommendation_confidence
    
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
