"""
Confidence Calibration Module for Deer Age Estimation

This module provides post-inference confidence calibration to align model outputs
with real-world accuracy. It separates age confidence from recommendation confidence
and implements uncertainty gating for unreliable age estimates.

Calibration Version: v1-heuristic
- Uses heuristic-based calibration without ground-truth labels
- Designed for future replacement with empirical calibration curves

Author: Iron Stag Development Team
"""

import os
import logging
from typing import Dict, Any, Optional, Tuple
from dataclasses import dataclass
from enum import Enum

logger = logging.getLogger(__name__)

# ============================================================================
# CONFIGURATION & FEATURE FLAGS
# ============================================================================

class CalibrationConfig:
    """Configuration for confidence calibration system."""
    
    # Feature flag - set via environment variable for flexibility
    CALIBRATION_ENABLED: bool = os.environ.get('CONFIDENCE_CALIBRATION_ENABLED', 'true').lower() == 'true'
    
    # Calibration version for tracking which algorithm produced the values
    CALIBRATION_VERSION: str = "v1-heuristic"
    
    # Minimum age confidence threshold - below this, age is marked uncertain
    AGE_CONFIDENCE_MIN: float = float(os.environ.get('AGE_CONFIDENCE_MIN', '0.60'))
    
    # Scaling factors for heuristic calibration
    # These can be tuned based on observed behavior
    AGE_CONFIDENCE_SCALE: float = float(os.environ.get('AGE_CONFIDENCE_SCALE', '0.75'))
    RECOMMENDATION_CONFIDENCE_SCALE: float = float(os.environ.get('RECOMMENDATION_CONFIDENCE_SCALE', '0.95'))
    
    # Penalty factors for uncertainty indicators
    NULL_AGE_PENALTY: float = 0.4  # Heavy penalty if model returns null age
    LOW_ANTLER_INFO_PENALTY: float = 0.1  # Penalty if antler data is incomplete
    UNKNOWN_SEX_PENALTY: float = 0.05  # Small penalty for unknown sex
    
    # Cap values to prevent overconfidence
    MAX_AGE_CONFIDENCE: float = 0.85  # Never claim >85% age confidence
    MAX_RECOMMENDATION_CONFIDENCE: float = 0.95  # Never claim >95% recommendation confidence


# ============================================================================
# DATA STRUCTURES
# ============================================================================

@dataclass
class CalibrationInput:
    """Input data for calibration computation."""
    raw_confidence: float  # Model's raw confidence (0-100 scale)
    predicted_age: Optional[float]  # Model's age prediction (can be null)
    recommendation: Optional[str]  # HARVEST or PASS
    deer_sex: Optional[str]  # Buck, Doe, or Unknown
    antler_points: Optional[int]  # Total points
    antler_points_left: Optional[int]  # Left antler points
    antler_points_right: Optional[int]  # Right antler points
    body_condition: Optional[str]  # Body condition assessment


@dataclass
class CalibrationOutput:
    """Output from calibration process."""
    # Original values (preserved for backward compatibility)
    raw_confidence: float
    original_age: Optional[float]
    
    # Calibrated values
    calibrated_age_confidence: float  # 0-100 scale
    calibrated_recommendation_confidence: float  # 0-100 scale
    
    # Uncertainty indicators
    age_uncertain: bool
    
    # Final adjusted age (null if uncertain)
    adjusted_age: Optional[float]
    
    # Metadata
    calibration_version: str
    calibration_applied: bool


# ============================================================================
# HEURISTIC CALIBRATION FUNCTIONS
# ============================================================================

def compute_age_confidence_heuristic(
    raw_confidence: float,
    predicted_age: Optional[float],
    deer_sex: Optional[str],
    antler_points: Optional[int],
    antler_points_left: Optional[int],
    antler_points_right: Optional[int]
) -> float:
    """
    Compute calibrated age confidence using heuristics.
    
    This is a placeholder for future empirical calibration.
    The heuristic penalizes cases where the model is likely unreliable:
    - Missing age prediction
    - Missing antler information
    - Unknown sex
    
    Returns confidence as 0-1 float.
    """
    # Start with raw confidence (convert from 0-100 to 0-1)
    base_confidence = (raw_confidence or 0) / 100.0
    
    # Apply base scaling - raw model confidence is generally overconfident for age
    scaled_confidence = base_confidence * CalibrationConfig.AGE_CONFIDENCE_SCALE
    
    # Penalty: No age predicted means very low confidence
    if predicted_age is None or predicted_age == 0:
        scaled_confidence *= (1 - CalibrationConfig.NULL_AGE_PENALTY)
    
    # Penalty: Missing antler information reduces confidence
    has_antler_detail = (
        antler_points is not None and 
        antler_points_left is not None and 
        antler_points_right is not None
    )
    if not has_antler_detail:
        scaled_confidence *= (1 - CalibrationConfig.LOW_ANTLER_INFO_PENALTY)
    
    # Penalty: Unknown sex suggests image quality issues
    if deer_sex is None or deer_sex.lower() == 'unknown':
        scaled_confidence *= (1 - CalibrationConfig.UNKNOWN_SEX_PENALTY)
    
    # Apply cap
    scaled_confidence = min(scaled_confidence, CalibrationConfig.MAX_AGE_CONFIDENCE)
    
    # Ensure non-negative
    scaled_confidence = max(0, scaled_confidence)
    
    return scaled_confidence


def compute_recommendation_confidence_heuristic(
    raw_confidence: float,
    recommendation: Optional[str],
    predicted_age: Optional[float],
    deer_sex: Optional[str]
) -> float:
    """
    Compute calibrated recommendation confidence using heuristics.
    
    Recommendation confidence is typically more reliable than age confidence
    because it's a binary decision based on multiple factors, not just age.
    
    Returns confidence as 0-1 float.
    """
    # Start with raw confidence (convert from 0-100 to 0-1)
    base_confidence = (raw_confidence or 0) / 100.0
    
    # Apply base scaling - recommendation is more reliable, scale less aggressively
    scaled_confidence = base_confidence * CalibrationConfig.RECOMMENDATION_CONFIDENCE_SCALE
    
    # Small penalty if age is unknown (recommendation still valuable but less certain)
    if predicted_age is None or predicted_age == 0:
        scaled_confidence *= 0.9  # 10% penalty
    
    # Penalty if recommendation is missing (shouldn't happen but defensive)
    if recommendation is None:
        scaled_confidence *= 0.5
    
    # Apply cap
    scaled_confidence = min(scaled_confidence, CalibrationConfig.MAX_RECOMMENDATION_CONFIDENCE)
    
    # Ensure non-negative
    scaled_confidence = max(0, scaled_confidence)
    
    return scaled_confidence


# ============================================================================
# MAIN CALIBRATION FUNCTION
# ============================================================================

def calibrate_confidence(input_data: CalibrationInput) -> CalibrationOutput:
    """
    Main entry point for confidence calibration.
    
    Takes raw model output and returns calibrated confidence values
    with uncertainty indicators.
    
    Args:
        input_data: CalibrationInput with raw model outputs
        
    Returns:
        CalibrationOutput with calibrated values and metadata
    """
    # Check if calibration is enabled
    if not CalibrationConfig.CALIBRATION_ENABLED:
        # Return passthrough values when calibration is disabled
        return CalibrationOutput(
            raw_confidence=input_data.raw_confidence,
            original_age=input_data.predicted_age,
            calibrated_age_confidence=input_data.raw_confidence,
            calibrated_recommendation_confidence=input_data.raw_confidence,
            age_uncertain=False,
            adjusted_age=input_data.predicted_age,
            calibration_version="disabled",
            calibration_applied=False
        )
    
    # Compute calibrated age confidence
    age_confidence = compute_age_confidence_heuristic(
        raw_confidence=input_data.raw_confidence,
        predicted_age=input_data.predicted_age,
        deer_sex=input_data.deer_sex,
        antler_points=input_data.antler_points,
        antler_points_left=input_data.antler_points_left,
        antler_points_right=input_data.antler_points_right
    )
    
    # Compute calibrated recommendation confidence
    recommendation_confidence = compute_recommendation_confidence_heuristic(
        raw_confidence=input_data.raw_confidence,
        recommendation=input_data.recommendation,
        predicted_age=input_data.predicted_age,
        deer_sex=input_data.deer_sex
    )
    
    # Apply uncertainty gate for age
    age_uncertain = age_confidence < CalibrationConfig.AGE_CONFIDENCE_MIN
    
    # Determine adjusted age (null if uncertain)
    adjusted_age = None if age_uncertain else input_data.predicted_age
    
    # Convert back to 0-100 scale for storage/display
    calibrated_age_confidence_pct = round(age_confidence * 100)
    calibrated_recommendation_confidence_pct = round(recommendation_confidence * 100)
    
    logger.info(
        f"Calibration applied: raw={input_data.raw_confidence}%, "
        f"age_conf={calibrated_age_confidence_pct}%, "
        f"rec_conf={calibrated_recommendation_confidence_pct}%, "
        f"age_uncertain={age_uncertain}"
    )
    
    return CalibrationOutput(
        raw_confidence=input_data.raw_confidence,
        original_age=input_data.predicted_age,
        calibrated_age_confidence=calibrated_age_confidence_pct,
        calibrated_recommendation_confidence=calibrated_recommendation_confidence_pct,
        age_uncertain=age_uncertain,
        adjusted_age=adjusted_age,
        calibration_version=CalibrationConfig.CALIBRATION_VERSION,
        calibration_applied=True
    )


def calibrate_from_dict(analysis: Dict[str, Any]) -> Tuple[CalibrationOutput, Dict[str, Any]]:
    """
    Convenience function to calibrate from a raw analysis dictionary.
    
    Returns both the CalibrationOutput and an updated dictionary
    with calibrated values merged in.
    
    Args:
        analysis: Raw analysis dictionary from model
        
    Returns:
        Tuple of (CalibrationOutput, updated analysis dict)
    """
    input_data = CalibrationInput(
        raw_confidence=analysis.get("confidence", 0) or 0,
        predicted_age=analysis.get("deer_age"),
        recommendation=analysis.get("recommendation"),
        deer_sex=analysis.get("deer_sex"),
        antler_points=analysis.get("antler_points"),
        antler_points_left=analysis.get("antler_points_left"),
        antler_points_right=analysis.get("antler_points_right"),
        body_condition=analysis.get("body_condition")
    )
    
    calibration_result = calibrate_confidence(input_data)
    
    # Create updated analysis dict with calibrated values
    updated_analysis = analysis.copy()
    updated_analysis["raw_confidence"] = calibration_result.raw_confidence
    updated_analysis["age_confidence"] = calibration_result.calibrated_age_confidence
    updated_analysis["recommendation_confidence"] = calibration_result.calibrated_recommendation_confidence
    updated_analysis["age_uncertain"] = calibration_result.age_uncertain
    updated_analysis["calibration_version"] = calibration_result.calibration_version
    
    # Apply uncertainty gate to age
    if calibration_result.age_uncertain:
        updated_analysis["deer_age"] = None
    
    # Update legacy confidence field to use recommendation confidence
    # (backward compatibility - existing clients expect this)
    updated_analysis["confidence"] = calibration_result.calibrated_recommendation_confidence
    
    return calibration_result, updated_analysis


# ============================================================================
# UTILITY FUNCTIONS FOR FUTURE EMPIRICAL CALIBRATION
# ============================================================================

def get_calibration_metadata() -> Dict[str, Any]:
    """
    Return metadata about current calibration configuration.
    Useful for debugging and tracking calibration versions.
    """
    return {
        "enabled": CalibrationConfig.CALIBRATION_ENABLED,
        "version": CalibrationConfig.CALIBRATION_VERSION,
        "thresholds": {
            "age_confidence_min": CalibrationConfig.AGE_CONFIDENCE_MIN,
            "max_age_confidence": CalibrationConfig.MAX_AGE_CONFIDENCE,
            "max_recommendation_confidence": CalibrationConfig.MAX_RECOMMENDATION_CONFIDENCE
        },
        "scaling": {
            "age_confidence_scale": CalibrationConfig.AGE_CONFIDENCE_SCALE,
            "recommendation_confidence_scale": CalibrationConfig.RECOMMENDATION_CONFIDENCE_SCALE
        },
        "penalties": {
            "null_age": CalibrationConfig.NULL_AGE_PENALTY,
            "low_antler_info": CalibrationConfig.LOW_ANTLER_INFO_PENALTY,
            "unknown_sex": CalibrationConfig.UNKNOWN_SEX_PENALTY
        }
    }


# Placeholder for future empirical calibration
# When ground-truth data is available, these functions can be implemented
# to replace the heuristic functions above

def load_empirical_calibration_curve(curve_path: str) -> None:
    """
    Placeholder: Load empirical calibration curve from file.
    
    Future implementation would load pre-computed calibration
    curves based on ground-truth validation data.
    """
    raise NotImplementedError("Empirical calibration not yet implemented")


def apply_isotonic_regression(raw_confidence: float, curve_data: Any) -> float:
    """
    Placeholder: Apply isotonic regression calibration.
    
    Future implementation would use sklearn's IsotonicRegression
    fitted on validation data.
    """
    raise NotImplementedError("Isotonic regression calibration not yet implemented")
