from fastapi import FastAPI, APIRouter, HTTPException, Depends, Header, UploadFile, File, Request
from dotenv import load_dotenv
from starlette.middleware.cors import CORSMiddleware
import os
import logging
import hashlib
from pathlib import Path
from pydantic import BaseModel, Field, EmailStr
from typing import Callable, List, Optional, Dict, Any, Tuple
import uuid
from datetime import datetime, timedelta, timezone
import jwt
from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError
import openai
import httpx
import base64
import json
import random
import string
import msal
from databases import Database
import sqlalchemy
from sqlalchemy import MetaData, Table, Column, String, Integer, Float, Boolean, DateTime, Text, JSON

# Import region-aware confidence calibration module (replaces basic calibration)
from region_calibration import (
    calibrate_from_dict_with_region,
    get_region_calibration_metadata,
    get_calibration_status,
    get_all_regions,
    RegionCalibrationConfig,
    determine_region,
)

# Import calibration jobs module for Phase 2 empirical calibration
from calibration_jobs import (
    build_curves_from_labels,
    activate_curve,
    deactivate_curve,
    load_active_curves,
    recalibrate_scans,
    get_curves_summary,
    get_curve_details,
    get_job_status,
    acquire_job_lock,
    release_job_lock,
    is_job_running,
    CalibrationJobConfig
)

# Import R2 storage for cloud image storage
from r2_storage import upload_scan_image, delete_scan_image, R2_ENABLED

# Import Phase 3 adaptive calibration module
from adaptive_calibration import (
    AdaptiveCalibrationConfig,
    detect_calibration_drift,
    compute_region_maturity,
    generate_model_recommendations,
    get_phase3_status,
    get_drift_summary,
    get_maturity_summary,
    get_recommendations_summary,
    acquire_phase3_lock,
    release_phase3_lock,
    TrustSource,
    DriftSeverity,
    MaturityLevel,
    RecommendationType,
    get_season_bucket,
)
from bc_typical_whitetail import (
    build_bc_score_record,
    get_bc_score_type_label,
    is_bc_score_type_allowed_for_scan,
    is_supported_bc_score_type,
    normalize_bc_score_entry,
    normalize_saved_bc_score,
)
from analysis_consensus import (
    merge_consensus_analyses,
    should_trigger_selective_consensus,
)

ROOT_DIR = Path(__file__).parent
if os.getenv("RAILWAY_ENVIRONMENT") is None:
    load_dotenv(ROOT_DIR / ".env")

# PostgreSQL connection (Neon DB)
DATABASE_URL = os.environ.get('DATABASE_URL', '')
database = Database(DATABASE_URL)
metadata = MetaData()

# Define tables
users_table = Table(
    "users",
    metadata,
    Column("id", String(36), primary_key=True),
    Column("email", String(255), unique=True, nullable=False),
    Column("password", Text, nullable=False),
    Column("name", String(255)),
    Column("first_name", String(100)),
    Column("last_name", String(100)),
    Column("username", String(100), unique=True),
    Column("created_at", DateTime, default=datetime.utcnow),
    Column("subscription_tier", String(50), default="tracker"),
    Column("scans_remaining", Integer, default=3),
    Column("total_scans_used", Integer, default=0),
    Column("disclaimer_accepted", Boolean, default=False),
    Column("disclaimer_accepted_at", DateTime, nullable=True),
    Column("stripe_customer_id", String(100)),
    Column("stripe_subscription_id", String(100)),
    Column("subscription_cancel_at_period_end", Boolean, default=False),
    Column("revenuecat_id", String(100)),
    Column("subscription_expires_at", DateTime),
    Column("apple_user_id", String(100), nullable=True),
    # User profile state for region fallback
    Column("state", String(2), nullable=True),  # Two-letter state code (e.g., IA, TX)
)

scans_table = Table(
    "scans",
    metadata,
    Column("id", String(36), primary_key=True),
    Column("user_id", String(36), nullable=False),
    Column("local_image_id", String(100)),
    Column("image_url", String, nullable=True),  # Cloud image URL (R2)
    Column("deer_age", Float),
    Column("age_bucket", String(50), nullable=True),
    Column("age_range", String(50), nullable=True),
    Column("buck_age_class", String(10), nullable=True),
    Column("age_evidence", JSON, nullable=True),
    Column("deer_type", String(100)),
    Column("deer_sex", String(50)),
    Column("antler_points", Integer),
    Column("antler_points_left", Integer),
    Column("antler_points_right", Integer),
    Column("body_condition", String(50)),
    Column("confidence", Integer),  # Legacy field - now holds recommendation_confidence
    Column("recommendation", String(50)),
    Column("reasoning", Text),
    Column("notes", Text),
    Column("raw_response", JSON),
    Column("created_at", DateTime, default=datetime.utcnow),
    # Confidence calibration fields
    Column("raw_confidence", Integer),  # Original model confidence (preserved for analysis)
    Column("age_confidence", Integer),  # Calibrated age estimation confidence
    Column("recommendation_confidence", Integer),  # Calibrated recommendation confidence
    Column("age_uncertain", Boolean, default=False),  # True if age confidence below threshold
    Column("calibration_version", String(50)),  # e.g., "v2-region-heuristic"
    # Region-specific calibration fields
    Column("region_key", String(50)),  # e.g., midwest, southeast, south_texas
    Column("region_source", String(50)),  # scan_input, user_profile, fallback_unknown
    Column("region_state", String(2)),  # Two-letter state code when available
    Column("raw_age_confidence", Integer),  # Raw age confidence from model (if separate)
    Column("raw_recommendation_confidence", Integer),  # Raw recommendation confidence from model
    Column("calibration_strategy", String(50)),  # heuristic, global_curve, region_curve
    Column("calibration_fallback_reason", String(100)),  # Why fallback was used
    Column("season_bucket", String(50), nullable=True),  # Prompt-time seasonal context
    Column("analysis_prompt_version", String(50), nullable=True),
    Column("analysis_model", String(100), nullable=True),
    Column("age_estimation_allowed", Boolean, nullable=True),
    Column("retake_reason", Text, nullable=True),
    Column("visible_age_cues", JSON, nullable=True),
    # Image quality fields
    Column("image_quality_bucket", String(20), nullable=True),  # Image quality assessment
    Column("quality_factors", JSON, nullable=True),  # Detailed quality factors
    # User organization fields
    Column("is_favorite", Boolean, default=False),  # User favorite
    Column("tags", JSON, nullable=True),  # User tags for organization
    Column("posture_bucket", String(20), nullable=True),  # Future: posture analysis
    # Harvest + unofficial score fields
    Column("harvest_confirmed", Boolean, default=False),
    Column("harvested_at", DateTime, nullable=True),
    Column("boone_crockett_score", JSON, nullable=True),
    Column("boone_crockett_gross", Float, nullable=True),
    Column("boone_crockett_net", Float, nullable=True),
    Column("boone_crockett_final_score", Float, nullable=True),
    Column("boone_crockett_status", String(20), nullable=True),
    Column("boone_crockett_calculated_at", DateTime, nullable=True),
    Column("boone_crockett_updated_at", DateTime, nullable=True),
)

# Scan labels table for empirical calibration (Phase 2) and trust weighting (Phase 3)
scan_labels_table = Table(
    "scan_labels",
    metadata,
    Column("id", String(36), primary_key=True),
    Column("scan_id", String(36), nullable=False),
    Column("user_id", String(36), nullable=True),
    Column("label_type", String(20), nullable=True),
    Column("label_weight", Float, nullable=True),
    Column("reported_age", Float, nullable=True),
    Column("accuracy_category", String(20), nullable=True),
    Column("prediction_error", Float, nullable=True),
    Column("error_bucket", String(20), nullable=True),
    Column("harvest_confirmed", Boolean, nullable=True),
    Column("credibility_factor", Float, nullable=True),
    Column("effective_weight", Float, nullable=True),
    Column("notes", Text, nullable=True),
    Column("labeled_at", DateTime, nullable=True),
    Column("age_source", String(50), nullable=True),
    Column("labeler_role", String(50), nullable=True),
    Column("label_source", String(50)),  # expert, user_self_report, admin_review
    Column("true_age_bucket", String(20)),  # Age range bucket
    Column("age_correct", Boolean),  # Was age estimation correct
    Column("recommendation_correct", Boolean),  # Was recommendation correct
    Column("created_at", DateTime, default=datetime.utcnow),
    # Phase 3: Trust weighting fields
    Column("trust_source", String(50)),  # expert, admin, trusted_user, self_reported, unknown
    Column("trust_weight", Float),  # 0-1 trust weight
)

# Calibration curves table for future empirical calibration (Phase 2)
calibration_curves_table = Table(
    "calibration_curves",
    metadata,
    Column("id", String(36), primary_key=True),
    Column("calibration_version", String(50), nullable=False),  # e.g., v2-curve
    Column("curve_type", String(50), nullable=False),  # global_age, global_reco, region_age, region_reco
    Column("region_key", String(50)),  # nullable for global curves
    Column("method", String(50)),  # binning, isotonic, platt
    Column("bins", JSON),  # Bin data for binning method
    Column("min_samples_required", Integer, default=200),
    Column("sample_count", Integer, default=0),
    Column("is_active", Boolean, default=False),
    Column("created_at", DateTime, default=datetime.utcnow),
    Column("updated_at", DateTime, default=datetime.utcnow),
)

# Phase 3: Calibration drift events table
calibration_drift_events_table = Table(
    "calibration_drift_events",
    metadata,
    Column("id", String(36), primary_key=True),
    Column("region_key", String(50)),
    Column("model_version", String(50)),
    Column("calibration_version", String(50)),
    Column("confidence_type", String(50)),  # age, recommendation
    Column("expected_accuracy", Float),
    Column("observed_accuracy", Float),
    Column("drift_percentage", Float),
    Column("severity", String(20)),  # warning, critical
    Column("sample_size", Integer),
    Column("time_window_days", Integer),
    Column("season_bucket", String(50)),  # pre_rut, rut, post_rut, late_season, off_season
    Column("created_at", DateTime, default=datetime.utcnow),
)

# Phase 3: Region maturity table
region_maturity_table = Table(
    "region_maturity",
    metadata,
    Column("region_key", String(50), primary_key=True),
    Column("maturity_level", String(20)),  # low, medium, high
    Column("labeled_sample_count", Integer),
    Column("label_source_diversity_score", Float),
    Column("stability_score", Float),
    Column("last_computed_at", DateTime, default=datetime.utcnow),
)

# Phase 3: Model action recommendations table
model_action_recommendations_table = Table(
    "model_action_recommendations",
    metadata,
    Column("id", String(36), primary_key=True),
    Column("region_key", String(50)),  # nullable for global recommendations
    Column("model_version", String(50)),
    Column("confidence_type", String(50)),
    Column("recommendation_type", String(50)),  # rebuild_calibration, consider_retraining, etc.
    Column("supporting_metrics", JSON),
    Column("severity", String(20)),
    Column("created_at", DateTime, default=datetime.utcnow),
)

password_reset_codes_table = Table(
    "password_reset_codes",
    metadata,
    Column("id", String(36), primary_key=True),
    Column("email", String(255), nullable=False),
    Column("code", String(10), nullable=False),
    Column("created_at", DateTime, default=datetime.utcnow),
    Column("used", Boolean, default=False),
)

# API Keys
OPENAI_API_KEY = os.environ.get('OPENAI_API_KEY', '')
OPENAI_ANALYSIS_MODEL = os.environ.get('OPENAI_ANALYSIS_MODEL', 'gpt-4o').strip() or 'gpt-4o'
OPENAI_REANALYSIS_MODEL = os.environ.get('OPENAI_REANALYSIS_MODEL', '').strip() or OPENAI_ANALYSIS_MODEL
OPENAI_MODEL_AB_TEST_CANDIDATE = os.environ.get('OPENAI_MODEL_AB_TEST_CANDIDATE', 'gpt-4.1').strip() or 'gpt-4.1'
REVENUECAT_SECRET_KEY = os.environ.get('REVENUECAT_SECRET_KEY', '')
JWT_SECRET = os.environ.get('JWT_SECRET', 'iron-stag-secret-key-2025')
JWT_ALGORITHM = 'HS256'

# Apple IAP Configuration
APPLE_IAP_SHARED_SECRET = os.environ.get('APPLE_IAP_SHARED_SECRET', '')
APPLE_BUNDLE_ID = 'io.asgardsolution.ironstag'

# Google Play Configuration  
GOOGLE_SERVICE_ACCOUNT_JSON = os.environ.get('GOOGLE_SERVICE_ACCOUNT_JSON', '')

# Microsoft Graph Configuration
MS_GRAPH_CLIENT_ID = os.environ.get('MICROSOFT_GRAPH_CLIENT_ID', '')
MS_GRAPH_CLIENT_SECRET = os.environ.get('MICROSOFT_GRAPH_CLIENT_SECRET', '')
MS_GRAPH_TENANT_ID = os.environ.get('MICROSOFT_GRAPH_TENANT_ID', '')
MS_GRAPH_SENDER_EMAIL = os.environ.get('MS_GRAPH_SENDER_EMAIL', 'support@asgardsolution.io')

# Initialize clients
openai_client = openai.OpenAI(api_key=OPENAI_API_KEY)

# Password hasher
ph = PasswordHasher()

# Create the main app
app = FastAPI(title="Iron Stag API", version="1.0.0")

# Create router with /api prefix
api_router = APIRouter(prefix="/api")

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def get_bool_env(name: str, default: bool = False) -> bool:
    value = os.environ.get(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def get_int_env(name: str, default: int) -> int:
    value = os.environ.get(name)
    if value is None:
        return default
    try:
        return int(value.strip())
    except (TypeError, ValueError):
        return default


def get_float_env(name: str, default: float) -> float:
    value = os.environ.get(name)
    if value is None:
        return default
    try:
        return float(value.strip())
    except (TypeError, ValueError):
        return default


SELECTIVE_CONSENSUS_ENABLED = get_bool_env("SELECTIVE_CONSENSUS_ENABLED", True)
SELECTIVE_CONSENSUS_TOTAL_PASSES = max(1, get_int_env("SELECTIVE_CONSENSUS_TOTAL_PASSES", 3))
SELECTIVE_CONSENSUS_TRIGGER_MAX_AGE_CONFIDENCE = max(
    0,
    min(100, get_int_env("SELECTIVE_CONSENSUS_TRIGGER_MAX_AGE_CONFIDENCE", 78)),
)
SELECTIVE_CONSENSUS_TRIGGER_MAX_RECOMMENDATION_CONFIDENCE = max(
    0,
    min(100, get_int_env("SELECTIVE_CONSENSUS_TRIGGER_MAX_RECOMMENDATION_CONFIDENCE", 80)),
)
SELECTIVE_CONSENSUS_TRIGGER_HARVEST_WINDOW = max(
    0.0,
    get_float_env("SELECTIVE_CONSENSUS_TRIGGER_HARVEST_WINDOW", 0.5),
)
SELECTIVE_CONSENSUS_AGE_SPREAD_PENALTY_PER_HALF_YEAR = max(
    0,
    get_int_env("SELECTIVE_CONSENSUS_AGE_SPREAD_PENALTY_PER_HALF_YEAR", 8),
)
SELECTIVE_CONSENSUS_DISAGREEMENT_PENALTY = max(
    0,
    get_int_env("SELECTIVE_CONSENSUS_DISAGREEMENT_PENALTY", 12),
)


def model_uses_max_completion_tokens(model_name: Optional[str]) -> bool:
    normalized = str(model_name or "").strip().lower()
    return normalized.startswith("gpt-5")


def build_chat_completion_request(
    *,
    model: str,
    messages: List[Dict[str, Any]],
    max_output_tokens: int,
    temperature: float = 0,
) -> Dict[str, Any]:
    request: Dict[str, Any] = {
        "model": model,
        "messages": messages,
        "temperature": temperature,
    }
    if model_uses_max_completion_tokens(model):
        request["max_completion_tokens"] = max_output_tokens
        request["reasoning_effort"] = "none"
    else:
        request["max_tokens"] = max_output_tokens
    return request


def run_model_analysis_pass(
    *,
    model: str,
    system_prompt: str,
    user_content: List[Dict[str, Any]],
    max_output_tokens: int,
    prompt_version: str,
    context: Dict[str, Any],
    post_parse: Optional[Callable[[Dict[str, Any]], Dict[str, Any]]] = None,
) -> Optional[Dict[str, Any]]:
    response = openai_client.chat.completions.create(
        **build_chat_completion_request(
            model=model,
            messages=[
                {
                    "role": "system",
                    "content": system_prompt,
                },
                {
                    "role": "user",
                    "content": user_content,
                },
            ],
            max_output_tokens=max_output_tokens,
            temperature=0,
        )
    )
    response_text = response.choices[0].message.content or ""
    try:
        parsed_analysis = parse_json_response(response_text)
    except (json.JSONDecodeError, ValueError):
        return None
    if post_parse is not None:
        parsed_analysis = post_parse(parsed_analysis)
    parsed_analysis["analysis_model"] = model
    return normalize_model_analysis(
        parsed_analysis,
        prompt_version=prompt_version,
        context=context,
    )


def maybe_apply_selective_consensus(
    *,
    initial_analysis: Dict[str, Any],
    total_passes: int,
    pass_builder: Callable[[], Optional[Dict[str, Any]]],
) -> Dict[str, Any]:
    if not should_trigger_selective_consensus(
        initial_analysis,
        enabled=SELECTIVE_CONSENSUS_ENABLED,
        max_age_confidence=SELECTIVE_CONSENSUS_TRIGGER_MAX_AGE_CONFIDENCE,
        max_recommendation_confidence=SELECTIVE_CONSENSUS_TRIGGER_MAX_RECOMMENDATION_CONFIDENCE,
        harvest_window=SELECTIVE_CONSENSUS_TRIGGER_HARVEST_WINDOW,
        harvest_threshold=HARVEST_RECOMMENDATION_MIN_AGE,
    ):
        return initial_analysis

    analyses: List[Dict[str, Any]] = [initial_analysis]
    target_passes = max(2, total_passes)
    for _ in range(target_passes - 1):
        extra_analysis = pass_builder()
        if extra_analysis is not None:
            analyses.append(extra_analysis)

    if len(analyses) < 2:
        return initial_analysis

    merged_analysis, consensus_meta = merge_consensus_analyses(
        analyses,
        age_spread_penalty_per_half_year=SELECTIVE_CONSENSUS_AGE_SPREAD_PENALTY_PER_HALF_YEAR,
        disagreement_penalty=SELECTIVE_CONSENSUS_DISAGREEMENT_PENALTY,
    )
    if not merged_analysis:
        return initial_analysis

    merged_analysis["consensus"] = consensus_meta
    return merged_analysis


OPENAI_MODEL_AB_TEST_ENABLED = get_bool_env('OPENAI_MODEL_AB_TEST_ENABLED', False)
OPENAI_MODEL_AB_TEST_PERCENT = max(0, min(100, get_int_env('OPENAI_MODEL_AB_TEST_PERCENT', 50)))
OPENAI_MODEL_AB_TEST_SALT = os.environ.get('OPENAI_MODEL_AB_TEST_SALT', 'ironstag-model-ab-v1').strip() or 'ironstag-model-ab-v1'
LIVE_CALIBRATION_CURVE_CACHE_TTL_SECONDS = max(0, get_int_env('LIVE_CALIBRATION_CURVE_CACHE_TTL_SECONDS', 60))

# Cache active empirical curves so live scans can use them without a DB read on every request.
live_active_curve_cache: Dict[Tuple[str, Optional[str]], Dict[str, Any]] = {}
live_active_curve_cache_loaded_at: Optional[datetime] = None


def invalidate_live_curve_cache(reason: str) -> None:
    global live_active_curve_cache
    global live_active_curve_cache_loaded_at

    live_active_curve_cache = {}
    live_active_curve_cache_loaded_at = None
    logger.info("Invalidated live calibration curve cache (%s)", reason)


async def get_live_active_curves(force_refresh: bool = False) -> Dict[Tuple[str, Optional[str]], Dict[str, Any]]:
    global live_active_curve_cache
    global live_active_curve_cache_loaded_at

    if not RegionCalibrationConfig.CALIBRATION_ENABLED:
        return {}
    if not RegionCalibrationConfig.CALIBRATION_CURVES_ENABLED:
        return {}

    now = datetime.utcnow()
    if (
        not force_refresh
        and live_active_curve_cache_loaded_at is not None
        and LIVE_CALIBRATION_CURVE_CACHE_TTL_SECONDS > 0
        and (now - live_active_curve_cache_loaded_at).total_seconds() < LIVE_CALIBRATION_CURVE_CACHE_TTL_SECONDS
    ):
        return live_active_curve_cache

    try:
        live_active_curve_cache = await load_active_curves(database, calibration_curves_table)
        live_active_curve_cache_loaded_at = now
        logger.info(
            "Loaded %s active calibration curves for live inference",
            len(live_active_curve_cache),
        )
    except Exception as exc:
        if live_active_curve_cache_loaded_at is None:
            logger.warning("Failed to load active calibration curves: %s", exc)
            return {}

        logger.warning(
            "Failed to refresh active calibration curves; reusing %s cached curves: %s",
            len(live_active_curve_cache),
            exc,
        )

    return live_active_curve_cache


def get_live_curve_cache_metadata() -> Dict[str, Any]:
    curve_types: Dict[str, int] = {}
    for (curve_type, _), curve in live_active_curve_cache.items():
        key = curve_type or str(curve.get("curve_type") or "unknown")
        curve_types[key] = curve_types.get(key, 0) + 1

    return {
        "enabled": RegionCalibrationConfig.CALIBRATION_CURVES_ENABLED,
        "active_count": len(live_active_curve_cache),
        "last_loaded_at": live_active_curve_cache_loaded_at.isoformat() if live_active_curve_cache_loaded_at else None,
        "cache_ttl_seconds": LIVE_CALIBRATION_CURVE_CACHE_TTL_SECONDS,
        "by_curve_type": curve_types,
    }

# ============ PYDANTIC MODELS ============

class UserRegister(BaseModel):
    email: EmailStr
    password: str
    name: Optional[str] = None
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    username: Optional[str] = None

class UserLogin(BaseModel):
    email: str  # Can be email or username
    password: str

class UserResponse(BaseModel):
    id: str
    email: str
    name: str
    username: Optional[str] = None
    created_at: datetime
    subscription_tier: str = "tracker"
    scans_remaining: int = 3
    total_scans_used: int = 0
    disclaimer_accepted: bool = False
    disclaimer_accepted_at: Optional[datetime] = None
    state: Optional[str] = None  # Two-letter state code for region calibration

class TokenResponse(BaseModel):
    access_token: str
    user: UserResponse

class ProfileUpdate(BaseModel):
    name: Optional[str] = None
    username: Optional[str] = None
    email: Optional[str] = None
    current_password: Optional[str] = None
    new_password: Optional[str] = None
    state: Optional[str] = None  # Two-letter state code for region calibration

class DisclaimerAccept(BaseModel):
    accepted: bool

class AppleSignInRequest(BaseModel):
    identity_token: str
    authorization_code: str
    user: str
    email: Optional[str] = None
    full_name: Optional[str] = None

class SubscriptionStatus(BaseModel):
    tier: str
    scans_remaining: int
    total_scans_used: int = 0
    is_premium: bool
    expires_at: Optional[datetime] = None

class CheckoutRequest(BaseModel):
    plan: str = "monthly"

class DeerAnalysisRequest(BaseModel):
    image_base64: str
    local_image_id: str
    notes: Optional[str] = None
    # Optional state for region-specific calibration (two-letter code)
    state: Optional[str] = None  # e.g., "TX", "IA", "GA"

class DeerAnalysisResponse(BaseModel):
    id: str
    user_id: str
    local_image_id: str
    deer_age: Optional[float] = None
    age_bucket: Optional[str] = None
    age_range: Optional[str] = None
    buck_age_class: Optional[str] = None
    age_evidence: Optional[List[Dict[str, str]]] = None
    cue_checklist: Optional[Dict[str, str]] = None
    alternate_age: Optional[float] = None
    why_not_primary: Optional[str] = None
    abstain_reason: Optional[str] = None
    foreshortening_risk: Optional[str] = None
    camera_angle_risk: Optional[str] = None
    distance_risk: Optional[str] = None
    deer_type: Optional[str] = None
    deer_sex: Optional[str] = None
    antler_points: Optional[int] = None
    antler_points_left: Optional[int] = None
    antler_points_right: Optional[int] = None
    body_condition: Optional[str] = None
    confidence: Optional[int] = None  # Legacy field - holds recommendation_confidence for backward compat
    recommendation: Optional[str] = None
    reasoning: Optional[str] = None
    notes: Optional[str] = None
    created_at: datetime
    # Calibration fields
    age_uncertain: Optional[bool] = None
    confidence_breakdown: Optional[Dict[str, int]] = None  # {"age": X, "recommendation": Y}
    calibration_version: Optional[str] = None
    # Region fields (feature-flagged in response, always persisted)
    region_key: Optional[str] = None
    calibration_strategy: Optional[str] = None
    calibration_fallback_reason: Optional[str] = None
    image_quality_bucket: Optional[str] = None
    quality_factors: Optional[Dict[str, Any]] = None
    posture_bucket: Optional[str] = None
    analysis_prompt_version: Optional[str] = None
    analysis_model: Optional[str] = None
    age_estimation_allowed: Optional[bool] = None
    retake_reason: Optional[str] = None
    visible_age_cues: Optional[List[str]] = None
    consensus: Optional[Dict[str, Any]] = None
    # Cloud image storage (R2) - for cross-device image access
    image_url: Optional[str] = None
    # Favorites and Tags
    is_favorite: Optional[bool] = False
    tags: Optional[List[str]] = None
    # Harvest + unofficial score
    harvest_confirmed: Optional[bool] = False
    harvested_at: Optional[datetime] = None
    boone_crockett_score: Optional[Dict[str, Any]] = None
    boone_crockett_gross: Optional[float] = None
    boone_crockett_net: Optional[float] = None
    boone_crockett_final_score: Optional[float] = None
    boone_crockett_status: Optional[str] = None
    boone_crockett_calculated_at: Optional[datetime] = None
    boone_crockett_updated_at: Optional[datetime] = None

class ScanUpdate(BaseModel):
    notes: Optional[str] = None
    harvest_confirmed: Optional[bool] = None
    boone_crockett_measurements: Optional[Dict[str, Any]] = None
    boone_crockett_disclaimer_accepted: Optional[bool] = None

class ScanEditRequest(BaseModel):
    """Request model for editing scan details and re-analyzing with LLM"""
    deer_sex: Optional[str] = None
    deer_type: Optional[str] = None
    antler_points_left: Optional[int] = None
    antler_points_right: Optional[int] = None
    image_base64: Optional[str] = None  # Required if re-analyzing with LLM


# ============ SCAN LABEL MODELS (Phase 2 Empirical Calibration) ============

class ScanLabelRequest(BaseModel):
    """Request to add a label to a scan for empirical calibration.
    
    Two modes:
    1. Exact age (strong signal): User provides reported_age after harvest
    2. Categorical (weak signal): User says 'exact', 'close', or 'off'
    """
    # Exact age label (strong signal)
    reported_age: Optional[float] = Field(None, description="Actual age if known (e.g., after harvest)")
    
    # Categorical label (weak signal)
    accuracy_category: Optional[str] = Field(None, description="'exact' | 'close' | 'off'")
    
    # Was this deer harvested? (affects credibility)
    harvest_confirmed: bool = Field(False, description="True if user harvested this deer")

    # Exact-age evidence metadata
    age_source: Optional[str] = Field(None, description="'jawbone' | 'tooth_wear' | 'taxidermist' | 'biologist_assessment' | 'hunter_best_estimate' | 'other' | 'unknown'")
    labeler_role: Optional[str] = Field(None, description="'self' | 'guide' | 'biologist' | 'admin' | 'taxidermist' | 'processor' | 'unknown'")
    
    # Optional notes
    notes: Optional[str] = None


class ScanLabelResponse(BaseModel):
    """Response after creating a scan label."""
    id: str
    scan_id: str
    label_type: str  # 'exact_age' | 'categorical'
    label_weight: float
    effective_weight: float  # After credibility adjustment
    reported_age: Optional[float] = None
    accuracy_category: Optional[str] = None
    error_bucket: Optional[str] = None  # 'exact' | 'within_half' | 'within_one' | 'off'
    prediction_error: Optional[float] = None
    harvest_confirmed: bool
    age_source: Optional[str] = None
    labeler_role: Optional[str] = None
    trust_source: Optional[str] = None
    created_at: datetime


class ScanWithLabel(DeerAnalysisResponse):
    """Scan response extended with label data if present."""
    label: Optional[ScanLabelResponse] = None


class LabelStatsResponse(BaseModel):
    """Statistics about labels in the system."""
    total_labels: int
    exact_age_count: int  # Strong signals
    categorical_count: int  # Weak signals
    by_region: Dict[str, int]
    by_error_bucket: Dict[str, int]
    by_image_quality: Dict[str, int]
    by_season_bucket: Dict[str, int] = Field(default_factory=dict)
    by_posture_bucket: Dict[str, int] = Field(default_factory=dict)
    by_age_estimation_allowed: Dict[str, int] = Field(default_factory=dict)
    by_age_source: Dict[str, int] = Field(default_factory=dict)
    by_labeler_role: Dict[str, int] = Field(default_factory=dict)
    total_weighted_samples: float  # Sum of effective weights
    maturity_gates: Dict[str, bool]  # Which gates are met
    exact_age_mae: Optional[float] = None
    exact_age_within_half_accuracy: Optional[float] = None
    exact_age_coverage: Optional[float] = None
    by_prompt_version: Dict[str, int] = Field(default_factory=dict)
    exact_age_mae_by_prompt_version: Dict[str, float] = Field(default_factory=dict)
    exact_age_within_half_by_prompt_version: Dict[str, float] = Field(default_factory=dict)
    exact_age_coverage_by_prompt_version: Dict[str, float] = Field(default_factory=dict)
    by_analysis_model: Dict[str, int] = Field(default_factory=dict)
    exact_age_mae_by_analysis_model: Dict[str, float] = Field(default_factory=dict)
    exact_age_within_half_by_analysis_model: Dict[str, float] = Field(default_factory=dict)
    exact_age_coverage_by_analysis_model: Dict[str, float] = Field(default_factory=dict)
    exact_age_mae_by_region: Dict[str, float] = Field(default_factory=dict)
    exact_age_within_half_by_region: Dict[str, float] = Field(default_factory=dict)
    exact_age_coverage_by_region: Dict[str, float] = Field(default_factory=dict)
    exact_age_mae_by_season_bucket: Dict[str, float] = Field(default_factory=dict)
    exact_age_within_half_by_season_bucket: Dict[str, float] = Field(default_factory=dict)
    exact_age_coverage_by_season_bucket: Dict[str, float] = Field(default_factory=dict)
    exact_age_mae_by_image_quality: Dict[str, float] = Field(default_factory=dict)
    exact_age_within_half_by_image_quality: Dict[str, float] = Field(default_factory=dict)
    exact_age_coverage_by_image_quality: Dict[str, float] = Field(default_factory=dict)
    exact_age_mae_by_posture_bucket: Dict[str, float] = Field(default_factory=dict)
    exact_age_within_half_by_posture_bucket: Dict[str, float] = Field(default_factory=dict)
    exact_age_coverage_by_posture_bucket: Dict[str, float] = Field(default_factory=dict)


class PasswordResetRequest(BaseModel):
    email: EmailStr

class PasswordResetVerify(BaseModel):
    email: EmailStr
    code: str
    new_password: str

# ============ APP VERSION CHECK MODELS ============

class VersionCheckRequest(BaseModel):
    platform: str  # 'ios' or 'android'
    current_version: str  # e.g., "1.0.0"
    build_number: Optional[str] = None  # iOS build number or Android versionCode

class PlatformVersionInfo(BaseModel):
    latest_version: str
    min_supported_version: str
    store_url: str

class VersionCheckResponse(BaseModel):
    update_available: bool
    update_mode: str  # 'none', 'soft', 'force'
    latest_version: str
    min_supported_version: str
    release_notes: Optional[str] = None
    store_url: str
    message: Optional[str] = None

# ============ DATABASE INITIALIZATION ============

@app.on_event("startup")
async def startup():
    await database.connect()
    # Create tables if they don't exist
    engine = sqlalchemy.create_engine(DATABASE_URL.replace("postgresql://", "postgresql+psycopg2://") if "postgresql://" in DATABASE_URL else DATABASE_URL)
    metadata.create_all(engine)
    
    # Run migrations for new columns
    try:
        # User profile state for region fallback
        await database.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS state VARCHAR(2)")
        
        # Add antler_points_left column if it doesn't exist
        await database.execute("ALTER TABLE scans ADD COLUMN IF NOT EXISTS antler_points_left INTEGER")
        # Add antler_points_right column if it doesn't exist
        await database.execute("ALTER TABLE scans ADD COLUMN IF NOT EXISTS antler_points_right INTEGER")
        await database.execute("ALTER TABLE scans ADD COLUMN IF NOT EXISTS age_bucket VARCHAR(50)")
        await database.execute("ALTER TABLE scans ADD COLUMN IF NOT EXISTS age_range VARCHAR(50)")
        await database.execute("ALTER TABLE scans ADD COLUMN IF NOT EXISTS buck_age_class VARCHAR(10)")
        await database.execute("ALTER TABLE scans ADD COLUMN IF NOT EXISTS age_evidence JSON")
        
        # Confidence calibration columns (added for v1-heuristic calibration)
        await database.execute("ALTER TABLE scans ADD COLUMN IF NOT EXISTS raw_confidence INTEGER")
        await database.execute("ALTER TABLE scans ADD COLUMN IF NOT EXISTS age_confidence INTEGER")
        await database.execute("ALTER TABLE scans ADD COLUMN IF NOT EXISTS recommendation_confidence INTEGER")
        await database.execute("ALTER TABLE scans ADD COLUMN IF NOT EXISTS age_uncertain BOOLEAN DEFAULT FALSE")
        await database.execute("ALTER TABLE scans ADD COLUMN IF NOT EXISTS calibration_version VARCHAR(50)")
        
        # Region-specific calibration columns (v2)
        await database.execute("ALTER TABLE scans ADD COLUMN IF NOT EXISTS region_key VARCHAR(50)")
        await database.execute("ALTER TABLE scans ADD COLUMN IF NOT EXISTS region_source VARCHAR(50)")
        await database.execute("ALTER TABLE scans ADD COLUMN IF NOT EXISTS region_state VARCHAR(2)")
        await database.execute("ALTER TABLE scans ADD COLUMN IF NOT EXISTS raw_age_confidence INTEGER")
        await database.execute("ALTER TABLE scans ADD COLUMN IF NOT EXISTS raw_recommendation_confidence INTEGER")
        await database.execute("ALTER TABLE scans ADD COLUMN IF NOT EXISTS calibration_strategy VARCHAR(50)")
        await database.execute("ALTER TABLE scans ADD COLUMN IF NOT EXISTS calibration_fallback_reason VARCHAR(100)")
        await database.execute("ALTER TABLE scans ADD COLUMN IF NOT EXISTS season_bucket VARCHAR(50)")
        await database.execute("ALTER TABLE scans ADD COLUMN IF NOT EXISTS analysis_prompt_version VARCHAR(50)")
        await database.execute("ALTER TABLE scans ADD COLUMN IF NOT EXISTS analysis_model VARCHAR(100)")
        await database.execute("ALTER TABLE scans ADD COLUMN IF NOT EXISTS age_estimation_allowed BOOLEAN")
        await database.execute("ALTER TABLE scans ADD COLUMN IF NOT EXISTS retake_reason TEXT")
        await database.execute("ALTER TABLE scans ADD COLUMN IF NOT EXISTS visible_age_cues JSON")
        
        # Create indexes for region calibration queries
        await database.execute("CREATE INDEX IF NOT EXISTS idx_scans_region_key ON scans(region_key)")
        await database.execute("CREATE INDEX IF NOT EXISTS idx_scans_calibration_version ON scans(calibration_version)")
        await database.execute("CREATE INDEX IF NOT EXISTS idx_scans_age_uncertain ON scans(age_uncertain)")
        await database.execute("CREATE INDEX IF NOT EXISTS idx_scans_analysis_model ON scans(analysis_model)")
        await database.execute("CREATE INDEX IF NOT EXISTS idx_scans_age_estimation_allowed ON scans(age_estimation_allowed)")
        
        # Phase 2: Create scan_labels table for empirical calibration
        await database.execute("""
            CREATE TABLE IF NOT EXISTS scan_labels (
                id VARCHAR(36) PRIMARY KEY,
                scan_id VARCHAR(36) NOT NULL,
                label_source VARCHAR(50),
                true_age_bucket VARCHAR(20),
                age_correct BOOLEAN,
                recommendation_correct BOOLEAN,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        await database.execute("CREATE INDEX IF NOT EXISTS idx_scan_labels_scan_id ON scan_labels(scan_id)")
        
        # Phase 2 Enhanced: Add new columns to scan_labels for weighted empirical calibration
        await database.execute("ALTER TABLE scan_labels ADD COLUMN IF NOT EXISTS user_id VARCHAR(36)")
        await database.execute("ALTER TABLE scan_labels ADD COLUMN IF NOT EXISTS label_type VARCHAR(20)")  # 'exact_age' | 'categorical'
        await database.execute("ALTER TABLE scan_labels ADD COLUMN IF NOT EXISTS label_weight FLOAT DEFAULT 1.0")
        await database.execute("ALTER TABLE scan_labels ADD COLUMN IF NOT EXISTS reported_age FLOAT")  # User-entered actual age
        await database.execute("ALTER TABLE scan_labels ADD COLUMN IF NOT EXISTS accuracy_category VARCHAR(20)")  # 'exact' | 'close' | 'off'
        await database.execute("ALTER TABLE scan_labels ADD COLUMN IF NOT EXISTS prediction_error FLOAT")  # |predicted - actual|
        await database.execute("ALTER TABLE scan_labels ADD COLUMN IF NOT EXISTS error_bucket VARCHAR(20)")  # 'exact' | 'within_half' | 'within_one' | 'off'
        await database.execute("ALTER TABLE scan_labels ADD COLUMN IF NOT EXISTS harvest_confirmed BOOLEAN DEFAULT FALSE")
        await database.execute("ALTER TABLE scan_labels ADD COLUMN IF NOT EXISTS credibility_factor FLOAT DEFAULT 0.5")
        await database.execute("ALTER TABLE scan_labels ADD COLUMN IF NOT EXISTS effective_weight FLOAT")  # label_weight * credibility_factor
        await database.execute("ALTER TABLE scan_labels ADD COLUMN IF NOT EXISTS notes TEXT")
        await database.execute("ALTER TABLE scan_labels ADD COLUMN IF NOT EXISTS labeled_at TIMESTAMP")
        await database.execute("ALTER TABLE scan_labels ADD COLUMN IF NOT EXISTS age_source VARCHAR(50)")
        await database.execute("ALTER TABLE scan_labels ADD COLUMN IF NOT EXISTS labeler_role VARCHAR(50)")
        
        # Phase 2 Enhanced: Add image quality and posture columns to scans
        await database.execute("ALTER TABLE scans ADD COLUMN IF NOT EXISTS image_quality_bucket VARCHAR(20)")  # 'excellent' | 'good' | 'fair' | 'poor'
        await database.execute("ALTER TABLE scans ADD COLUMN IF NOT EXISTS quality_factors JSON")  # {blur_score, lighting, distance_estimate, occlusion}
        await database.execute("ALTER TABLE scans ADD COLUMN IF NOT EXISTS posture_bucket VARCHAR(20)")  # 'broadside' | 'angled' | 'head_down' | 'unknown'
        
        # Cloud image storage (R2) - for cross-device image access
        await database.execute("ALTER TABLE scans ADD COLUMN IF NOT EXISTS image_url VARCHAR(500)")  # R2 public URL
        
        # Favorites and Tags for organizing scans
        await database.execute("ALTER TABLE scans ADD COLUMN IF NOT EXISTS is_favorite BOOLEAN DEFAULT FALSE")
        await database.execute("ALTER TABLE scans ADD COLUMN IF NOT EXISTS tags JSON")  # Array of tag strings
        await database.execute("CREATE INDEX IF NOT EXISTS idx_scans_is_favorite ON scans(is_favorite)")

        # Harvest + unofficial score fields
        await database.execute("ALTER TABLE scans ADD COLUMN IF NOT EXISTS harvest_confirmed BOOLEAN DEFAULT FALSE")
        await database.execute("ALTER TABLE scans ADD COLUMN IF NOT EXISTS harvested_at TIMESTAMP")
        await database.execute("ALTER TABLE scans ADD COLUMN IF NOT EXISTS boone_crockett_score JSON")
        await database.execute("ALTER TABLE scans ADD COLUMN IF NOT EXISTS boone_crockett_gross FLOAT")
        await database.execute("ALTER TABLE scans ADD COLUMN IF NOT EXISTS boone_crockett_net FLOAT")
        await database.execute("ALTER TABLE scans ADD COLUMN IF NOT EXISTS boone_crockett_final_score FLOAT")
        await database.execute("ALTER TABLE scans ADD COLUMN IF NOT EXISTS boone_crockett_status VARCHAR(20)")
        await database.execute("ALTER TABLE scans ADD COLUMN IF NOT EXISTS boone_crockett_calculated_at TIMESTAMP")
        await database.execute("ALTER TABLE scans ADD COLUMN IF NOT EXISTS boone_crockett_updated_at TIMESTAMP")
        await database.execute("CREATE INDEX IF NOT EXISTS idx_scans_harvest_confirmed ON scans(harvest_confirmed)")
        
        # Label versioning for safe weight recomputation in future
        await database.execute("ALTER TABLE scan_labels ADD COLUMN IF NOT EXISTS label_version INTEGER DEFAULT 1")
        
        # Create indexes for label queries
        await database.execute("CREATE INDEX IF NOT EXISTS idx_scan_labels_user_id ON scan_labels(user_id)")
        await database.execute("CREATE INDEX IF NOT EXISTS idx_scan_labels_label_type ON scan_labels(label_type)")
        await database.execute("CREATE INDEX IF NOT EXISTS idx_scan_labels_error_bucket ON scan_labels(error_bucket)")
        await database.execute("CREATE INDEX IF NOT EXISTS idx_scan_labels_created_at ON scan_labels(created_at)")
        await database.execute("CREATE INDEX IF NOT EXISTS idx_scan_labels_version ON scan_labels(label_version)")
        await database.execute("CREATE INDEX IF NOT EXISTS idx_scan_labels_age_source ON scan_labels(age_source)")
        await database.execute("CREATE INDEX IF NOT EXISTS idx_scan_labels_labeler_role ON scan_labels(labeler_role)")
        
        # Phase 2: Create calibration_curves table for empirical calibration
        await database.execute("""
            CREATE TABLE IF NOT EXISTS calibration_curves (
                id VARCHAR(36) PRIMARY KEY,
                calibration_version VARCHAR(50) NOT NULL,
                curve_type VARCHAR(50) NOT NULL,
                region_key VARCHAR(50),
                method VARCHAR(50),
                bins JSON,
                min_samples_required INTEGER DEFAULT 200,
                sample_count INTEGER DEFAULT 0,
                is_active BOOLEAN DEFAULT FALSE,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        await database.execute("CREATE INDEX IF NOT EXISTS idx_calibration_curves_active ON calibration_curves(is_active)")
        await database.execute("CREATE INDEX IF NOT EXISTS idx_calibration_curves_type_region ON calibration_curves(curve_type, region_key)")
        
        # Phase 3: Add trust weighting columns to scan_labels
        await database.execute("ALTER TABLE scan_labels ADD COLUMN IF NOT EXISTS trust_source VARCHAR(50)")
        await database.execute("ALTER TABLE scan_labels ADD COLUMN IF NOT EXISTS trust_weight FLOAT")
        
        # Phase 3: Create calibration_drift_events table
        await database.execute("""
            CREATE TABLE IF NOT EXISTS calibration_drift_events (
                id VARCHAR(36) PRIMARY KEY,
                region_key VARCHAR(50),
                model_version VARCHAR(50),
                calibration_version VARCHAR(50),
                confidence_type VARCHAR(50),
                expected_accuracy FLOAT,
                observed_accuracy FLOAT,
                drift_percentage FLOAT,
                severity VARCHAR(20),
                sample_size INTEGER,
                time_window_days INTEGER,
                season_bucket VARCHAR(50),
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        await database.execute("CREATE INDEX IF NOT EXISTS idx_drift_events_region ON calibration_drift_events(region_key, confidence_type)")
        await database.execute("CREATE INDEX IF NOT EXISTS idx_drift_events_model ON calibration_drift_events(model_version)")
        await database.execute("CREATE INDEX IF NOT EXISTS idx_drift_events_severity ON calibration_drift_events(severity)")
        
        # Phase 3: Create region_maturity table
        await database.execute("""
            CREATE TABLE IF NOT EXISTS region_maturity (
                region_key VARCHAR(50) PRIMARY KEY,
                maturity_level VARCHAR(20),
                labeled_sample_count INTEGER,
                label_source_diversity_score FLOAT,
                stability_score FLOAT,
                last_computed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # Phase 3: Create model_action_recommendations table
        await database.execute("""
            CREATE TABLE IF NOT EXISTS model_action_recommendations (
                id VARCHAR(36) PRIMARY KEY,
                region_key VARCHAR(50),
                model_version VARCHAR(50),
                confidence_type VARCHAR(50),
                recommendation_type VARCHAR(50),
                supporting_metrics JSON,
                severity VARCHAR(20),
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        await database.execute("CREATE INDEX IF NOT EXISTS idx_recommendations_type ON model_action_recommendations(recommendation_type)")
        await database.execute("CREATE INDEX IF NOT EXISTS idx_recommendations_created ON model_action_recommendations(created_at)")
        
        logger.info("Database migrations completed")
    except Exception as e:
        logger.warning(f"Migration note: {e}")

    await get_live_active_curves(force_refresh=True)
    
    logger.info("Database connected and tables created")

@app.on_event("shutdown")
async def shutdown():
    invalidate_live_curve_cache("shutdown")
    await database.disconnect()
    logger.info("Database disconnected")

# ============ AUTH HELPERS ============

def create_token(user_id: str) -> str:
    payload = {
        "sub": user_id,
        "exp": datetime.utcnow() + timedelta(days=30)
    }
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)

def verify_token(token: str) -> str:
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
        return payload["sub"]
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token expired")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Invalid token")


ANALYSIS_PROMPT_VERSION = "age-v5-structured-checklist"
REANALYSIS_PROMPT_VERSION = "age-v5-structured-checklist-reanalysis"

REGION_PROMPT_HINTS = {
    "midwest": "Large-bodied deer are common. Use body maturity more than antler spread.",
    "northeast": "Be conservative with mass-based aging when winter coats and terrain hide proportions.",
    "plains": "Distance and open-country images often flatten depth. Favor visible body proportions over antlers.",
    "southeast": "Smaller-bodied deer are common. Do not over-age based on antler count alone.",
    "south_texas": "South Texas bucks can carry mature antlers on smaller frames. Body cues must dominate age.",
    "northern": "Heavy coats can exaggerate bulk. Use chest, belly, and leg-to-body ratio carefully.",
    "unknown": "Regional context is limited. Use only visible body evidence."
}

SEASON_PROMPT_HINTS = {
    "pre_rut": "Necks may begin to swell. Do not over-age based on early rut mass alone.",
    "rut": "Rut can inflate neck thickness and posture. Body frame, chest, belly, and face should dominate age.",
    "post_rut": "Post-rut bucks may look run down. Separate fatigue from true old age.",
    "late_season": "Winter coats and weight loss can distort condition. Use proportions more than fat cover.",
    "off_season": "Antlers and body condition can be atypical. Stay conservative if cues are weak."
}

BODY_CONDITION_VALUES = {"poor": "Poor", "fair": "Fair", "good": "Good", "excellent": "Excellent", "unknown": "Unknown"}
QUALITY_BUCKET_VALUES = {"excellent", "good", "fair", "poor"}
POSTURE_BUCKET_VALUES = {"broadside", "angled", "head_down", "frontal", "rear", "unknown"}
QUALITY_FACTOR_VALUES = {
    "body_visibility": {"high", "medium", "low"},
    "head_visibility": {"high", "medium", "low"},
    "lighting": {"good", "mixed", "poor", "unknown"},
    "occlusion": {"low", "medium", "high", "unknown"},
    "distance_estimate": {"close", "medium", "far", "unknown"},
    "blur": {"low", "medium", "high", "unknown"},
}
AGE_EVIDENCE_IMPACTS = {"older", "younger", "neutral", "unknown"}
VISIBLE_AGE_CUE_VALUES = {
    "chest_depth",
    "belly_sag",
    "backline",
    "leg_to_body_ratio",
    "leg_apparent_length",
    "face_length",
    "neck_brisket",
    "neck_to_face_ratio",
    "body_mass",
    "hindquarters",
    "chest_vs_hindquarters",
    "waistline",
    "head_blockiness",
    "forehead_muzzle",
    "tarsal_staining",
}
CRITICAL_AGE_CUE_VALUES = {
    "chest_depth",
    "belly_sag",
    "backline",
    "leg_to_body_ratio",
    "face_length",
    "body_mass",
}
REQUIRED_CUE_CHECKLIST_KEYS = {
    "chest_depth",
    "belly_sag",
    "backline",
    "leg_to_body_ratio",
    "face_length",
    "neck_brisket",
    "body_mass",
    "chest_vs_hindquarters",
    "head_blockiness",
}
MIN_VISIBLE_CRITICAL_AGE_CUES = max(1, get_int_env("MIN_VISIBLE_CRITICAL_AGE_CUES", 3))
CHECKLIST_VISIBILITY_VALUES = {"visible", "not_visible", "unclear"}
RISK_LEVEL_VALUES = {"low", "medium", "high"}
ABSTAIN_REASON_VALUES = {
    "insufficient_profile",
    "heavy_occlusion",
    "low_resolution_or_blur",
    "distance_or_perspective",
    "pose_not_supported",
    "mixed_or_conflicting_cues",
    "insufficient_visible_age_cues",
    "other",
}
BUCK_AGE_CLASS_VALUES = {"1.5", "2.5", "3.5", "4.5", "5.5", "6.5+"}
BUCK_AGE_CLASS_TO_AGE = {
    "1.5": 1.5,
    "2.5": 2.5,
    "3.5": 3.5,
    "4.5": 4.5,
    "5.5": 5.5,
    "6.5+": 6.5,
}
BUCK_AGE_CLASS_PROMPT_GUIDANCE = """
Buck age-class rubric:
- 1.5: doe-like body, long-looking legs, thin neck, narrow chest, little muscle definition
- 2.5: lean waist and shoulders, hindquarters larger than chest, flat belly/back, minimal neck swelling
- 3.5: chest and shoulders now heavier than hindquarters, athletic and tight frame, neck wider than face during rut
- 4.5: neck blends into shoulders, deeper chest, waistline has dropped, fully mature frame
- 5.5: shoulder and neck mass look heavy, belly rounds or sags, head appears blockier, legs look short for the body
- 6.5+: very heavy body, obvious belly/back sag, loose skin in face/brisket, darker or grayer forehead/muzzle
"""
AGE_QUALITY_GATE_MESSAGES = {
    "poor_image_quality": "The image quality is too poor for a reliable age estimate.",
    "body_visibility_low": "Too little of the body is visible to judge chest, belly, and frame proportions.",
    "occlusion_high": "Heavy occlusion is hiding the main body-aging cues.",
    "blur_high": "The image is too blurry to read body proportions confidently.",
    "profile_not_visible": "A frontal or rear pose does not show the body profile needed for accurate aging.",
    "model_insufficient_evidence": "Visible body cues are too limited for a defensible age estimate.",
    "insufficient_visible_age_cues": "There are not enough visible age cues to support a numeric age.",
    "critical_cues_missing": "Critical body-aging cues are not visible enough for a reliable age call.",
    "incomplete_cue_checklist": "The required cue checklist is incomplete, so a reliable age cannot be provided.",
}
AGE_SOURCE_VALUES = {
    "jawbone",
    "tooth_wear",
    "taxidermist",
    "biologist_assessment",
    "hunter_best_estimate",
    "other",
    "unknown",
}
LABELER_ROLE_VALUES = {
    "self",
    "guide",
    "biologist",
    "admin",
    "taxidermist",
    "processor",
    "unknown",
}
AGE_SOURCE_RELIABILITY = {
    "jawbone": 1.0,
    "tooth_wear": 0.88,
    "taxidermist": 0.84,
    "biologist_assessment": 0.96,
    "hunter_best_estimate": 0.60,
    "other": 0.72,
    "unknown": 0.55,
}
LABELER_ROLE_RELIABILITY = {
    "self": 1.0,
    "guide": 0.82,
    "biologist": 1.0,
    "admin": 0.95,
    "taxidermist": 0.88,
    "processor": 0.82,
    "unknown": 0.65,
}
AGE_RETAKE_TIP = "Retake tip: use a full-body broadside photo with the deer centered, in focus, and unobstructed."


def stable_percent_bucket(value: str) -> int:
    digest = hashlib.sha256(value.encode("utf-8")).hexdigest()
    return int(digest[:8], 16) % 100


def select_analysis_model(
    *,
    user_id: str,
    local_image_id: Optional[str],
    default_model: Optional[str] = None,
) -> Tuple[str, str]:
    control_model = (default_model or OPENAI_ANALYSIS_MODEL).strip() or OPENAI_ANALYSIS_MODEL

    if (
        not OPENAI_MODEL_AB_TEST_ENABLED
        or OPENAI_MODEL_AB_TEST_PERCENT <= 0
        or OPENAI_MODEL_AB_TEST_CANDIDATE == control_model
    ):
        return control_model, "control"

    if OPENAI_MODEL_AB_TEST_PERCENT >= 100:
        return OPENAI_MODEL_AB_TEST_CANDIDATE, "candidate"

    assignment_key = f"{OPENAI_MODEL_AB_TEST_SALT}:{user_id}:{local_image_id or 'unknown'}"
    if stable_percent_bucket(assignment_key) < OPENAI_MODEL_AB_TEST_PERCENT:
        return OPENAI_MODEL_AB_TEST_CANDIDATE, "candidate"
    return control_model, "control"


def resolve_reanalysis_model(scan: Dict[str, Any], user_id: str) -> Tuple[str, str]:
    persisted_model = str(scan.get("analysis_model") or "").strip()
    if persisted_model:
        return persisted_model, "persisted"

    return select_analysis_model(
        user_id=user_id,
        local_image_id=scan.get("local_image_id") or scan.get("id"),
        default_model=OPENAI_REANALYSIS_MODEL,
    )


def clamp_confidence(value: Any) -> Optional[int]:
    """Clamp model-provided confidence values to the API's 0-100 range."""
    if value is None or value == "":
        return None
    try:
        return max(0, min(100, int(round(float(value)))))
    except (TypeError, ValueError):
        return None


def normalize_estimated_age(value: Any) -> Optional[float]:
    """Normalize free-form model ages into the app's half-year hunting convention."""
    if value is None or value == "":
        return None
    try:
        age = float(value)
    except (TypeError, ValueError):
        return None

    if age <= 0:
        return None

    age = max(0.5, min(15.5, age))
    normalized = round(age - 0.5) + 0.5
    normalized = max(0.5, min(15.5, normalized))
    return float(f"{normalized:.1f}")


def derive_age_bucket(age: Optional[float]) -> Optional[str]:
    if age is None:
        return None
    if age < 1.0:
        return "fawn"
    if age < 2.0:
        return "yearling"
    if age < 4.0:
        return "young_adult"
    if age < 6.0:
        return "mature"
    return "older"


def derive_age_range(age: Optional[float]) -> Optional[str]:
    if age is None:
        return None
    if age < 1.0:
        return "0.5"
    if age < 2.0:
        return "1.5"
    if age < 4.0:
        return "2.5-3.5"
    if age < 6.0:
        return "4.5-5.5"
    return "6.5+"


HARVEST_RECOMMENDATION_MIN_AGE = 3.5


def is_mature_harvest_age(age: Optional[float]) -> bool:
    return age is not None and age >= HARVEST_RECOMMENDATION_MIN_AGE


def derive_management_recommendation(
    value: Any,
    deer_age: Optional[float],
    age_estimation_allowed: Optional[bool],
) -> Optional[str]:
    cleaned = str(value or "").strip().upper()
    if cleaned in {"HARVEST", "PASS"}:
        return cleaned
    if age_estimation_allowed is False or deer_age is None:
        return None
    return "HARVEST" if is_mature_harvest_age(deer_age) else "PASS"


def normalize_buck_age_class(value: Any) -> Optional[str]:
    if value is None or value == "":
        return None

    cleaned = str(value).strip().lower()
    cleaned = (
        cleaned
        .replace("years old", "")
        .replace("year old", "")
        .replace("years-old", "")
        .replace("year-old", "")
        .replace("years", "")
        .replace("year", "")
        .replace("bucks", "")
        .replace("buck", "")
        .replace("½", ".5")
        .replace("plus", "+")
        .replace(" ", "")
    )

    if cleaned in {"6.5+", "6.5andup", "6.5_up", "6.5orolder"}:
        return "6.5+"

    try:
        age = float(cleaned.rstrip("+"))
    except (TypeError, ValueError):
        return None

    if age >= 6.5 or cleaned.endswith("+"):
        return "6.5+"

    class_age = normalize_estimated_age(age)
    if class_age is None:
        return None

    normalized = f"{class_age:.1f}"
    return normalized if normalized in BUCK_AGE_CLASS_VALUES else None


def derive_buck_age_class(age: Optional[float], deer_sex: Optional[str]) -> Optional[str]:
    if deer_sex != "Buck" or age is None:
        return None
    if age < 2.0:
        return "1.5"
    if age < 3.0:
        return "2.5"
    if age < 4.0:
        return "3.5"
    if age < 5.0:
        return "4.5"
    if age < 6.0:
        return "5.5"
    return "6.5+"


def resolve_buck_age_from_class(age: Optional[float], buck_age_class: Optional[str]) -> Optional[float]:
    if buck_age_class is None:
        return age

    class_age = BUCK_AGE_CLASS_TO_AGE[buck_age_class]
    if age is None:
        return class_age

    if buck_age_class == "6.5+":
        return age if age >= 6.5 else 6.5

    return age if abs(age - class_age) <= 0.5 else class_age


def normalize_deer_type(value: Any) -> Optional[str]:
    if value is None:
        return None
    cleaned = str(value).strip().lower()
    if cleaned in {"whitetail", "white-tailed deer", "white tailed deer", "whitetail deer"}:
        return "Whitetail"
    if cleaned in {"mule deer", "mule"}:
        return "Mule Deer"
    return str(value).strip() or None


def normalize_deer_sex(value: Any) -> Optional[str]:
    if value is None:
        return None
    cleaned = str(value).strip().lower()
    if cleaned == "buck":
        return "Buck"
    if cleaned == "doe":
        return "Doe"
    if cleaned == "unknown":
        return "Unknown"
    return str(value).strip() or None


def normalize_body_condition(value: Any) -> Optional[str]:
    if value is None:
        return None
    cleaned = str(value).strip().lower()
    return BODY_CONDITION_VALUES.get(cleaned, str(value).strip() or None)


def normalize_quality_bucket(value: Any) -> Optional[str]:
    if value is None:
        return None
    cleaned = str(value).strip().lower().replace(" ", "_")
    return cleaned if cleaned in QUALITY_BUCKET_VALUES else None


def normalize_posture_bucket(value: Any) -> Optional[str]:
    if value is None:
        return None
    cleaned = str(value).strip().lower().replace(" ", "_")
    return cleaned if cleaned in POSTURE_BUCKET_VALUES else None


def normalize_antler_points(value: Any) -> Optional[int]:
    if value is None or value == "":
        return None
    try:
        points = int(round(float(value)))
    except (TypeError, ValueError):
        return None
    return max(0, points)


def normalize_quality_factors(value: Any) -> Dict[str, str]:
    if not isinstance(value, dict):
        return {}

    normalized: Dict[str, str] = {}
    for key, allowed_values in QUALITY_FACTOR_VALUES.items():
        raw = value.get(key)
        if raw is None:
            continue
        cleaned = str(raw).strip().lower().replace(" ", "_")
        if cleaned in allowed_values:
            normalized[key] = cleaned
    return normalized


def normalize_age_evidence(value: Any) -> List[Dict[str, str]]:
    if not isinstance(value, list):
        return []

    evidence: List[Dict[str, str]] = []
    for item in value[:8]:
        if not isinstance(item, dict):
            continue
        feature = str(item.get("feature", "")).strip()
        observation = str(item.get("observation", "")).strip()
        impact = str(item.get("impact", "unknown")).strip().lower()
        if not feature or not observation:
            continue
        if impact not in AGE_EVIDENCE_IMPACTS:
            impact = "unknown"
        evidence.append(
            {
                "feature": feature[:80],
                "observation": observation[:240],
                "impact": impact,
            }
        )
    return evidence


def normalize_optional_bool(value: Any) -> Optional[bool]:
    if value is None or value == "":
        return None
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return bool(value)
    cleaned = str(value).strip().lower()
    if cleaned in {"true", "yes", "1"}:
        return True
    if cleaned in {"false", "no", "0"}:
        return False
    return None


def normalize_visible_age_cues(value: Any) -> List[str]:
    if not isinstance(value, list):
        return []

    cues: List[str] = []
    seen = set()
    for item in value[:8]:
        raw = item
        if isinstance(item, dict):
            raw = item.get("cue") or item.get("feature")
        cleaned = str(raw or "").strip().lower().replace(" ", "_").replace("-", "_")
        if cleaned in VISIBLE_AGE_CUE_VALUES and cleaned not in seen:
            cues.append(cleaned)
            seen.add(cleaned)
    return cues


def normalize_cue_checklist(value: Any) -> Dict[str, str]:
    checklist: Dict[str, str] = {}

    if isinstance(value, list):
        items = value
    elif isinstance(value, dict):
        items = [{"cue": key, "visibility": raw} for key, raw in value.items()]
    else:
        return checklist

    for item in items[:24]:
        if not isinstance(item, dict):
            continue
        cue = item.get("cue") or item.get("feature")
        cleaned_cue = str(cue or "").strip().lower().replace(" ", "_").replace("-", "_")
        if cleaned_cue not in VISIBLE_AGE_CUE_VALUES:
            continue
        visibility = item.get("visibility")
        if visibility is None and "visible" in item:
            visibility = "visible" if bool(item.get("visible")) else "not_visible"
        cleaned_visibility = str(visibility or "").strip().lower().replace(" ", "_").replace("-", "_")
        if cleaned_visibility in CHECKLIST_VISIBILITY_VALUES:
            checklist[cleaned_cue] = cleaned_visibility
    return checklist


def normalize_risk_level(value: Any) -> Optional[str]:
    if value is None or value == "":
        return None
    cleaned = str(value).strip().lower().replace(" ", "_").replace("-", "_")
    return cleaned if cleaned in RISK_LEVEL_VALUES else None


def normalize_abstain_reason(value: Any) -> Optional[str]:
    if value is None or value == "":
        return None
    cleaned = str(value).strip().lower().replace(" ", "_").replace("-", "_")
    if cleaned in ABSTAIN_REASON_VALUES:
        return cleaned
    return "other"


def derive_visible_age_cues_from_evidence(evidence: List[Dict[str, str]]) -> List[str]:
    cues: List[str] = []
    seen = set()
    for item in evidence:
        cleaned = str(item.get("feature") or "").strip().lower().replace(" ", "_").replace("-", "_")
        if cleaned in VISIBLE_AGE_CUE_VALUES and cleaned not in seen:
            cues.append(cleaned)
            seen.add(cleaned)
    return cues


def normalize_age_source(value: Any) -> Optional[str]:
    if value is None or value == "":
        return None
    cleaned = str(value).strip().lower().replace(" ", "_").replace("-", "_")
    return cleaned if cleaned in AGE_SOURCE_VALUES else "other"


def normalize_labeler_role(value: Any) -> Optional[str]:
    if value is None or value == "":
        return None
    cleaned = str(value).strip().lower().replace(" ", "_").replace("-", "_")
    return cleaned if cleaned in LABELER_ROLE_VALUES else "unknown"


def compute_age_source_multiplier(age_source: Optional[str]) -> float:
    return AGE_SOURCE_RELIABILITY.get(age_source or "unknown", AGE_SOURCE_RELIABILITY["unknown"])


def compute_labeler_role_multiplier(labeler_role: Optional[str]) -> float:
    return LABELER_ROLE_RELIABILITY.get(labeler_role or "unknown", LABELER_ROLE_RELIABILITY["unknown"])


def derive_label_trust_source(
    *,
    age_source: Optional[str],
    labeler_role: Optional[str],
    harvest_confirmed: bool,
) -> str:
    if labeler_role == "admin":
        return TrustSource.ADMIN.value
    if labeler_role in {"biologist", "taxidermist"} or age_source in {"taxidermist", "biologist_assessment"}:
        return TrustSource.EXPERT.value
    if harvest_confirmed or labeler_role == "guide" or age_source in {"jawbone", "tooth_wear"}:
        return TrustSource.TRUSTED_USER.value
    return TrustSource.SELF_REPORTED.value


def derive_label_source(age_source: Optional[str], labeler_role: Optional[str], harvest_confirmed: bool) -> str:
    if labeler_role == "admin":
        return "admin_review"
    if labeler_role in {"biologist", "taxidermist"} or age_source in {"taxidermist", "biologist_assessment"}:
        return "expert_review"
    if harvest_confirmed and age_source in {"jawbone", "tooth_wear"}:
        return "harvest_measurement"
    return "user_self_report"


def build_age_quality_gate_reason(blockers: List[str], model_reason: Optional[str] = None) -> str:
    reasons: List[str] = []
    seen = set()

    for blocker in blockers:
        message = AGE_QUALITY_GATE_MESSAGES.get(blocker)
        if message and message not in seen:
            reasons.append(message)
            seen.add(message)

    cleaned_model_reason = str(model_reason or "").strip()
    if cleaned_model_reason:
        clipped = cleaned_model_reason[:220]
        if clipped not in seen:
            reasons.append(clipped)

    if not reasons:
        reasons.append("Visible body cues are too limited for a reliable age estimate.")

    reasons.append(AGE_RETAKE_TIP)
    return " ".join(reasons)


def derive_abstain_reason_from_blockers(blockers: List[str]) -> str:
    if "profile_not_visible" in blockers:
        return "pose_not_supported"
    if "occlusion_high" in blockers:
        return "heavy_occlusion"
    if "blur_high" in blockers or "poor_image_quality" in blockers:
        return "low_resolution_or_blur"
    if "critical_cues_missing" in blockers or "insufficient_visible_age_cues" in blockers:
        return "insufficient_visible_age_cues"
    return "insufficient_profile"


def apply_age_estimation_gate(normalized: Dict[str, Any]) -> Dict[str, Any]:
    quality_factors = normalized.get("quality_factors") or {}
    blockers: List[str] = []

    if normalized.get("image_quality_bucket") == "poor":
        blockers.append("poor_image_quality")
    if quality_factors.get("body_visibility") == "low":
        blockers.append("body_visibility_low")
    if quality_factors.get("occlusion") == "high":
        blockers.append("occlusion_high")
    if quality_factors.get("blur") == "high":
        blockers.append("blur_high")
    if normalized.get("posture_bucket") in {"frontal", "rear"}:
        blockers.append("profile_not_visible")

    if normalized.get("age_estimation_allowed") is False:
        blockers.append("model_insufficient_evidence")

    visible_age_cues = normalized.get("visible_age_cues") or []
    if not visible_age_cues:
        visible_age_cues = derive_visible_age_cues_from_evidence(normalized.get("age_evidence") or [])
        normalized["visible_age_cues"] = visible_age_cues

    cue_checklist = normalize_cue_checklist(normalized.get("cue_checklist"))
    normalized["cue_checklist"] = cue_checklist
    missing_required_checklist_keys = sorted(REQUIRED_CUE_CHECKLIST_KEYS.difference(cue_checklist.keys()))
    if missing_required_checklist_keys:
        blockers.append("incomplete_cue_checklist")

    if cue_checklist:
        visible_from_checklist = [cue for cue, state in cue_checklist.items() if state == "visible"]
        for cue in visible_from_checklist:
            if cue not in visible_age_cues:
                visible_age_cues.append(cue)
        normalized["visible_age_cues"] = visible_age_cues

    critical_visible_count = len([cue for cue in visible_age_cues if cue in CRITICAL_AGE_CUE_VALUES])
    if critical_visible_count < MIN_VISIBLE_CRITICAL_AGE_CUES:
        blockers.append("critical_cues_missing")

    if normalized.get("deer_age") is None and len(visible_age_cues) < 2:
        blockers.append("insufficient_visible_age_cues")

    blockers = list(dict.fromkeys(blockers))

    if blockers:
        normalized["age_estimation_allowed"] = False
        normalized["retake_reason"] = build_age_quality_gate_reason(blockers, normalized.get("retake_reason"))
        if normalized.get("abstain_reason") is None:
            normalized["abstain_reason"] = derive_abstain_reason_from_blockers(blockers)
        normalized["deer_age"] = None
        normalized["age_bucket"] = None
        normalized["age_range"] = None
        normalized["buck_age_class"] = None
        normalized["recommendation"] = None
        normalized["raw_age_confidence"] = 0
        normalized["raw_recommendation_confidence"] = 0
        normalized["confidence"] = 0
        normalized["reasoning"] = normalized["retake_reason"]
    else:
        normalized["age_estimation_allowed"] = True if normalized.get("age_estimation_allowed") is None else bool(normalized.get("age_estimation_allowed"))
        normalized["retake_reason"] = None
        normalized["abstain_reason"] = None

    return normalized


def build_scan_context(
    scan_state: Optional[str],
    user_profile_state: Optional[str],
    scan_datetime: datetime,
    notes: Optional[str] = None,
) -> Dict[str, Any]:
    region_info = determine_region(scan_state=scan_state, user_profile_state=user_profile_state)
    season_bucket = get_season_bucket(scan_datetime, region_info.region_key.value)
    clean_notes = notes.strip() if isinstance(notes, str) and notes.strip() else None

    return {
        "state": region_info.region_state,
        "region_key": region_info.region_key.value,
        "region_source": region_info.region_source.value,
        "season_bucket": season_bucket,
        "notes": clean_notes,
    }


def format_scan_context_for_prompt(context: Dict[str, Any]) -> str:
    region_key = context.get("region_key") or "unknown"
    season_bucket = context.get("season_bucket") or "unknown"
    lines = [
        "Field context:",
        f"- User-reported state: {context.get('state') or 'unknown'}",
        f"- Region profile: {region_key}",
        f"- Seasonal phase: {season_bucket}",
        f"- Regional caution: {REGION_PROMPT_HINTS.get(region_key, REGION_PROMPT_HINTS['unknown'])}",
        f"- Seasonal caution: {SEASON_PROMPT_HINTS.get(season_bucket, 'Use season only as supporting context, never as proof of age.')}",
    ]
    if context.get("notes"):
        lines.append(f"- Hunter notes (supplemental, not ground truth): {context['notes']}")
    return "\n".join(lines)


def parse_json_response(response_text: str) -> Dict[str, Any]:
    if not response_text:
        raise ValueError("Empty model response")

    if "```json" in response_text:
        json_str = response_text.split("```json", 1)[1].split("```", 1)[0]
    elif "```" in response_text:
        json_str = response_text.split("```", 1)[1].split("```", 1)[0]
    else:
        json_str = response_text

    parsed = json.loads(json_str.strip())
    if not isinstance(parsed, dict):
        raise ValueError("Model response was not a JSON object")
    return parsed


def normalize_model_analysis(
    analysis: Dict[str, Any],
    *,
    prompt_version: str,
    context: Dict[str, Any],
) -> Dict[str, Any]:
    """Normalize model output into stable fields used by storage and calibration."""
    normalized = dict(analysis)
    normalized["analysis_prompt_version"] = prompt_version
    normalized["analysis_context"] = {
        "state": context.get("state"),
        "region_key": context.get("region_key"),
        "region_source": context.get("region_source"),
        "season_bucket": context.get("season_bucket"),
    }

    if not normalized.get("is_valid_deer", False):
        normalized["detected_subject"] = str(normalized.get("detected_subject") or "Unknown").strip() or "Unknown"
        normalized["message"] = (
            str(normalized.get("message")).strip()
            if normalized.get("message")
            else "This app is designed for Whitetail and Mule Deer only."
        )
        return normalized

    stage_1 = normalized.get("stage_1_observations")
    if isinstance(stage_1, dict):
        if normalized.get("cue_checklist") is None and stage_1.get("cue_checklist") is not None:
            normalized["cue_checklist"] = stage_1.get("cue_checklist")

    stage_2 = normalized.get("stage_2_age_decision")
    if isinstance(stage_2, dict):
        if normalized.get("deer_age") is None and stage_2.get("primary_age") is not None:
            normalized["deer_age"] = stage_2.get("primary_age")
        if normalized.get("alternate_age") is None and stage_2.get("alternate_age") is not None:
            normalized["alternate_age"] = stage_2.get("alternate_age")
        if normalized.get("why_not_primary") is None and stage_2.get("why_not_primary") is not None:
            normalized["why_not_primary"] = stage_2.get("why_not_primary")
        if normalized.get("abstain_reason") is None and stage_2.get("abstain_reason") is not None:
            normalized["abstain_reason"] = stage_2.get("abstain_reason")

    normalized["deer_type"] = normalize_deer_type(normalized.get("deer_type"))
    normalized["deer_sex"] = normalize_deer_sex(normalized.get("deer_sex"))
    normalized["body_condition"] = normalize_body_condition(normalized.get("body_condition"))
    normalized["buck_age_class"] = normalize_buck_age_class(normalized.get("buck_age_class"))
    normalized["analysis_model"] = str(normalized.get("analysis_model") or "").strip() or None
    normalized["age_estimation_allowed"] = normalize_optional_bool(normalized.get("age_estimation_allowed"))
    normalized["retake_reason"] = str(normalized.get("retake_reason") or "").strip()[:280] or None
    normalized["abstain_reason"] = normalize_abstain_reason(normalized.get("abstain_reason"))
    normalized["visible_age_cues"] = normalize_visible_age_cues(normalized.get("visible_age_cues"))
    normalized["cue_checklist"] = normalize_cue_checklist(normalized.get("cue_checklist"))
    normalized["image_quality_bucket"] = normalize_quality_bucket(normalized.get("image_quality_bucket")) or "fair"
    normalized["posture_bucket"] = normalize_posture_bucket(normalized.get("posture_bucket")) or "unknown"
    foreshortening_risk = normalize_risk_level(
        normalized.get("foreshortening_risk") or normalized.get("camera_angle_risk")
    )
    normalized["foreshortening_risk"] = foreshortening_risk
    normalized["camera_angle_risk"] = foreshortening_risk
    normalized["distance_risk"] = normalize_risk_level(normalized.get("distance_risk"))
    normalized["quality_factors"] = normalize_quality_factors(normalized.get("quality_factors"))
    normalized["age_evidence"] = normalize_age_evidence(normalized.get("age_evidence"))

    antler_points_left = normalize_antler_points(normalized.get("antler_points_left"))
    antler_points_right = normalize_antler_points(normalized.get("antler_points_right"))
    antler_points_total = normalize_antler_points(normalized.get("antler_points"))

    if normalized.get("deer_sex") == "Doe":
        antler_points_left = None
        antler_points_right = None
        antler_points_total = None
    elif antler_points_left is not None and antler_points_right is not None:
        antler_points_total = antler_points_left + antler_points_right

    normalized["antler_points_left"] = antler_points_left
    normalized["antler_points_right"] = antler_points_right
    normalized["antler_points"] = antler_points_total

    age_confidence = clamp_confidence(normalized.get("age_confidence"))
    recommendation_confidence = clamp_confidence(normalized.get("recommendation_confidence"))
    legacy_confidence = clamp_confidence(normalized.get("confidence"))

    if age_confidence is None:
        age_confidence = legacy_confidence
    if recommendation_confidence is None:
        recommendation_confidence = legacy_confidence or age_confidence

    angle_risk = normalize_risk_level(
        normalized.get("foreshortening_risk") or normalized.get("camera_angle_risk")
    )
    distance_risk = normalize_risk_level(normalized.get("distance_risk"))
    risk_penalty = 0
    if angle_risk == "high":
        risk_penalty += 10
    elif angle_risk == "medium":
        risk_penalty += 5
    if distance_risk == "high":
        risk_penalty += 10
    elif distance_risk == "medium":
        risk_penalty += 5
    if risk_penalty:
        if age_confidence is not None:
            age_confidence = max(0, age_confidence - risk_penalty)
        if recommendation_confidence is not None:
            recommendation_confidence = max(0, recommendation_confidence - risk_penalty)

    normalized["raw_age_confidence"] = age_confidence
    normalized["raw_recommendation_confidence"] = recommendation_confidence
    normalized["confidence"] = recommendation_confidence or age_confidence or 0

    normalized.pop("age_confidence", None)
    normalized.pop("recommendation_confidence", None)

    deer_age = normalize_estimated_age(normalized.get("deer_age"))
    alternate_age = normalize_estimated_age(normalized.get("alternate_age"))
    buck_age_class = normalized.get("buck_age_class")

    if normalized.get("deer_sex") != "Buck":
        buck_age_class = None
    else:
        if buck_age_class is None:
            buck_age_class = derive_buck_age_class(deer_age, normalized.get("deer_sex"))
        deer_age = resolve_buck_age_from_class(deer_age, buck_age_class)

    normalized["deer_age"] = deer_age
    normalized["alternate_age"] = alternate_age
    normalized["age_bucket"] = derive_age_bucket(deer_age)
    normalized["age_range"] = derive_age_range(deer_age)
    normalized["buck_age_class"] = buck_age_class

    normalized["recommendation"] = derive_management_recommendation(
        normalized.get("recommendation"),
        deer_age,
        normalized.get("age_estimation_allowed"),
    )
    normalized["why_not_primary"] = str(normalized.get("why_not_primary") or "").strip()[:220] or None

    # Penalize confidence if the model's alternate age meaningfully disagrees.
    if deer_age is not None and alternate_age is not None and abs(deer_age - alternate_age) > 0.5:
        normalized["raw_age_confidence"] = max(0, int((normalized.get("raw_age_confidence") or 0) - 10))
        normalized["raw_recommendation_confidence"] = max(
            0,
            int((normalized.get("raw_recommendation_confidence") or 0) - 8),
        )
        normalized["confidence"] = normalized["raw_recommendation_confidence"] or normalized["raw_age_confidence"] or 0

    normalized["reasoning"] = str(normalized.get("reasoning") or "").strip() or None

    return apply_age_estimation_gate(normalized)


def build_analysis_system_prompt() -> str:
    return f"""You are an expert wildlife biologist specializing in deer identification and field-aging from photos.

Return ONLY valid JSON. Do not include markdown fences or commentary.

First determine whether the image contains a valid deer for this app. Only Whitetail and Mule Deer are valid.

If the image does NOT contain a valid deer, return:
{{
  "is_valid_deer": false,
  "detected_subject": "<what is in the image>",
  "message": "<friendly message explaining the app is for Whitetail and Mule Deer only>"
}}

If the image DOES contain a valid deer, return:
{{
  "is_valid_deer": true,
  "stage_1_observations": {{
    "summary": "<2-3 sentence body-profile summary>",
    "cue_checklist": [
      {{"cue": "<cue>", "visibility": "<visible|not_visible|unclear>"}}
    ]
  }},
  "stage_2_age_decision": {{
    "primary_age": <number or null>,
    "alternate_age": <number or null>,
    "why_not_primary": "<short explanation or null>",
    "abstain_reason": <"insufficient_profile" | "heavy_occlusion" | "low_resolution_or_blur" | "distance_or_perspective" | "pose_not_supported" | "mixed_or_conflicting_cues" | "insufficient_visible_age_cues" | "other" | null>
  }},
  "age_estimation_allowed": <true or false>,
  "retake_reason": <string or null>,
  "abstain_reason": <same enum or null>,
  "visible_age_cues": [
    <"chest_depth" | "belly_sag" | "backline" | "leg_to_body_ratio" | "leg_apparent_length" | "face_length" | "neck_brisket" | "neck_to_face_ratio" | "body_mass" | "hindquarters" | "chest_vs_hindquarters" | "waistline" | "head_blockiness" | "forehead_muzzle" | "tarsal_staining">
  ],
  "deer_age": <number or null>,
  "alternate_age": <number or null>,
  "why_not_primary": <string or null>,
  "age_bucket": <"fawn" | "yearling" | "young_adult" | "mature" | "older" | null>,
  "age_range": <"0.5" | "1.5" | "2.5-3.5" | "4.5-5.5" | "6.5+" | null>,
  "buck_age_class": <"1.5" | "2.5" | "3.5" | "4.5" | "5.5" | "6.5+" | null>,
  "age_confidence": <0-100>,
  "recommendation_confidence": <0-100>,
  "deer_type": <"Whitetail" or "Mule Deer">,
  "deer_sex": <"Buck" or "Doe" or "Unknown">,
  "antler_points": <integer or null>,
  "antler_points_left": <integer or null>,
  "antler_points_right": <integer or null>,
  "body_condition": <"Poor" | "Fair" | "Good" | "Excellent" | "Unknown">,
  "image_quality_bucket": <"excellent" | "good" | "fair" | "poor">,
  "posture_bucket": <"broadside" | "angled" | "head_down" | "frontal" | "rear" | "unknown">,
  "foreshortening_risk": <"low" | "medium" | "high">,
  "distance_risk": <"low" | "medium" | "high">,
  "cue_checklist": {{
    "<cue>": <"visible" | "not_visible" | "unclear">
  }},
  "quality_factors": {{
    "body_visibility": <"high" | "medium" | "low">,
    "head_visibility": <"high" | "medium" | "low">,
    "lighting": <"good" | "mixed" | "poor" | "unknown">,
    "occlusion": <"low" | "medium" | "high" | "unknown">,
    "distance_estimate": <"close" | "medium" | "far" | "unknown">,
    "blur": <"low" | "medium" | "high" | "unknown">
  }},
  "age_evidence": [
    {{"feature": "<cue>", "observation": "<what you observed>", "impact": "<older|younger|neutral|unknown>"}}
  ],
  "confidence": <0-100>,
  "recommendation": <"HARVEST" or "PASS" or null>,
  "reasoning": "<brief explanation>"
}}

Critical rules:
- Use a two-stage method: (1) observation checklist, (2) age decision.
- Fill `cue_checklist` for every major cue in this set: chest_depth, belly_sag, backline, leg_to_body_ratio, face_length, neck_brisket, body_mass, chest_vs_hindquarters, head_blockiness.
- `cue_checklist` must include every key cue listed above with visibility `visible`, `not_visible`, or `unclear`.
- If any required checklist key is missing, set `age_estimation_allowed` to false.
- Do not set `age_estimation_allowed` true unless at least {MIN_VISIBLE_CRITICAL_AGE_CUES} critical cues are marked visible.
- Body morphology is the primary basis for age. Antlers are only a weak secondary cue.
- Use visible cues such as chest depth, belly sag, backline, leg length, face length, neck/brisket, chest-vs-hindquarter balance, waistline, head blockiness, tarsal staining, and overall body mass.
- For bucks, first place the deer into the nearest buck age class, then make the numeric age align with that class.
{BUCK_AGE_CLASS_PROMPT_GUIDANCE.strip()}
- For does, age from body profile only. If chest depth, belly line, backline, leg-to-body ratio, face length, and overall body mass are clearly visible, provide the best half-year estimate instead of defaulting to null.
- For does, do not require antlers or buck-specific cues before giving an age estimate.
- Rut-swollen necks, coat thickness, and perspective can mislead. Stay conservative.
- `visible_age_cues` must only list cues that are clearly visible in the image.
- If image_quality_bucket is `poor`, or body_visibility is `low`, or occlusion is `high`, or blur is `high`, or posture is `frontal` or `rear`, set `age_estimation_allowed` to false.
- If key body cues are not clearly visible, set `age_estimation_allowed` to false.
- When `age_estimation_allowed` is false:
  - set `deer_age`, `age_bucket`, `age_range`, and `buck_age_class` to null
  - set `recommendation` to null
  - set `age_confidence`, `recommendation_confidence`, and `confidence` to 0
  - provide `abstain_reason` from the enum
  - provide a concise `retake_reason`
- When `age_estimation_allowed` is true, set `retake_reason` to null.
- When `age_estimation_allowed` is true, set `abstain_reason` to null.
- Provide both `deer_age` (primary) and `alternate_age` for borderline cases. If not borderline, set `alternate_age` to null.
- If `alternate_age` is provided, `why_not_primary` is required.
- When `age_estimation_allowed` is true and `deer_age` is not null, `recommendation` must be `HARVEST` or `PASS`, never null.
- If recommendation is otherwise uncertain, use this app baseline: `HARVEST` for deer_age >= 3.5 and `PASS` for deer_age < 3.5.
- If deer_age is not null, use the half-year hunting convention and keep it to a single estimate such as 0.5, 1.5, 2.5, 3.5, 4.5, 5.5, 6.5, 7.5, etc.
- age_bucket and age_range must align with deer_age. If deer_age is null, set both to null.
- For bucks, `buck_age_class` must align with `deer_age`, `age_bucket`, and `age_range`. For does or unknown sex, set `buck_age_class` to null.
- For does, do not force an age when evidence is weak.
- For bucks, antler count may refine the estimate but must never dominate it.
- Antler point count can never be a standalone basis for age.
- If the deer is a doe, antler fields must be null.
- Use `foreshortening_risk` and `distance_risk` to reflect perspective uncertainty.
- Set confidence equal to recommendation_confidence for backward compatibility.
- Provide 3 to 6 concise age_evidence items whenever possible."""


def build_reanalysis_system_prompt() -> str:
    return f"""You are an expert wildlife biologist specializing in deer aging and analysis.

The user corrected some scan details after seeing the deer in person. Treat those corrections as authoritative facts.

Return ONLY valid JSON. Do not include markdown fences or commentary.

Return:
{{
  "stage_1_observations": {{
    "summary": "<2-3 sentence body-profile summary>",
    "cue_checklist": [
      {{"cue": "<cue>", "visibility": "<visible|not_visible|unclear>"}}
    ]
  }},
  "stage_2_age_decision": {{
    "primary_age": <number or null>,
    "alternate_age": <number or null>,
    "why_not_primary": "<short explanation or null>",
    "abstain_reason": <"insufficient_profile" | "heavy_occlusion" | "low_resolution_or_blur" | "distance_or_perspective" | "pose_not_supported" | "mixed_or_conflicting_cues" | "insufficient_visible_age_cues" | "other" | null>
  }},
  "age_estimation_allowed": <true or false>,
  "retake_reason": <string or null>,
  "abstain_reason": <same enum or null>,
  "visible_age_cues": [
    <"chest_depth" | "belly_sag" | "backline" | "leg_to_body_ratio" | "leg_apparent_length" | "face_length" | "neck_brisket" | "neck_to_face_ratio" | "body_mass" | "hindquarters" | "chest_vs_hindquarters" | "waistline" | "head_blockiness" | "forehead_muzzle" | "tarsal_staining">
  ],
  "deer_age": <number or null>,
  "alternate_age": <number or null>,
  "why_not_primary": <string or null>,
  "age_bucket": <"fawn" | "yearling" | "young_adult" | "mature" | "older" | null>,
  "age_range": <"0.5" | "1.5" | "2.5-3.5" | "4.5-5.5" | "6.5+" | null>,
  "buck_age_class": <"1.5" | "2.5" | "3.5" | "4.5" | "5.5" | "6.5+" | null>,
  "age_confidence": <0-100>,
  "recommendation_confidence": <0-100>,
  "deer_type": <"Whitetail" or "Mule Deer">,
  "deer_sex": <"Buck" or "Doe" or "Unknown">,
  "antler_points": <integer or null>,
  "antler_points_left": <integer or null>,
  "antler_points_right": <integer or null>,
  "body_condition": <"Poor" | "Fair" | "Good" | "Excellent" | "Unknown">,
  "image_quality_bucket": <"excellent" | "good" | "fair" | "poor">,
  "posture_bucket": <"broadside" | "angled" | "head_down" | "frontal" | "rear" | "unknown">,
  "foreshortening_risk": <"low" | "medium" | "high">,
  "distance_risk": <"low" | "medium" | "high">,
  "cue_checklist": {{
    "<cue>": <"visible" | "not_visible" | "unclear">
  }},
  "quality_factors": {{
    "body_visibility": <"high" | "medium" | "low">,
    "head_visibility": <"high" | "medium" | "low">,
    "lighting": <"good" | "mixed" | "poor" | "unknown">,
    "occlusion": <"low" | "medium" | "high" | "unknown">,
    "distance_estimate": <"close" | "medium" | "far" | "unknown">,
    "blur": <"low" | "medium" | "high" | "unknown">
  }},
  "age_evidence": [
    {{"feature": "<cue>", "observation": "<what you observed>", "impact": "<older|younger|neutral|unknown>"}}
  ],
  "confidence": <0-100>,
  "recommendation": <"HARVEST" or "PASS" or null>,
  "reasoning": "<brief explanation>"
}}

Critical rules:
- Use user corrections as hard constraints.
- Do not use the previous AI age estimate as evidence.
- Use a two-stage method: (1) observation checklist, (2) age decision.
- Fill `cue_checklist` for every major cue in this set: chest_depth, belly_sag, backline, leg_to_body_ratio, face_length, neck_brisket, body_mass, chest_vs_hindquarters, head_blockiness.
- `cue_checklist` must include every key cue listed above with visibility `visible`, `not_visible`, or `unclear`.
- If any required checklist key is missing, set `age_estimation_allowed` to false.
- Do not set `age_estimation_allowed` true unless at least {MIN_VISIBLE_CRITICAL_AGE_CUES} critical cues are marked visible.
- Body morphology is the primary basis for age. Antlers are only a weak secondary cue.
- For bucks, first place the deer into the nearest buck age class, then make the numeric age align with that class.
{BUCK_AGE_CLASS_PROMPT_GUIDANCE.strip()}
- Corrected antler points may inform the analysis slightly, but they must not dominate age.
- If the corrected sex is Doe, all antler fields must be null.
- For does, age from body profile only and do not require antlers or buck-specific cues before giving an age estimate.
- `visible_age_cues` must only list cues that are clearly visible in the image.
- If image_quality_bucket is `poor`, or body_visibility is `low`, or occlusion is `high`, or blur is `high`, or posture is `frontal` or `rear`, set `age_estimation_allowed` to false.
- If key body cues remain unclear, set `age_estimation_allowed` to false instead of forcing a number.
- When `age_estimation_allowed` is false:
  - set `deer_age`, `age_bucket`, `age_range`, and `buck_age_class` to null
  - set `recommendation` to null
  - set `age_confidence`, `recommendation_confidence`, and `confidence` to 0
  - provide `abstain_reason` from the enum
  - provide a concise `retake_reason`
- When `age_estimation_allowed` is true, set `retake_reason` to null.
- When `age_estimation_allowed` is true, set `abstain_reason` to null.
- Provide both `deer_age` (primary) and `alternate_age` for borderline cases. If not borderline, set `alternate_age` to null.
- If `alternate_age` is provided, `why_not_primary` is required.
- When `age_estimation_allowed` is true and `deer_age` is not null, `recommendation` must be `HARVEST` or `PASS`, never null.
- If recommendation is otherwise uncertain, use this app baseline: `HARVEST` for deer_age >= 3.5 and `PASS` for deer_age < 3.5.
- Keep deer_age to the half-year hunting convention when not null.
- For bucks, `buck_age_class` must align with `deer_age`, `age_bucket`, and `age_range`. For does or unknown sex, set `buck_age_class` to null.
- For does, use visible body cues when they are available; only abstain when the photo truly lacks enough anatomy to age reliably.
- Antler point count can never be a standalone basis for age.
- Use `foreshortening_risk` and `distance_risk` to reflect perspective uncertainty.
- Set confidence equal to recommendation_confidence for backward compatibility."""

def build_scan_response(scan: dict) -> DeerAnalysisResponse:
    """
    Helper to build DeerAnalysisResponse with calibration and region fields.
    Handles both new scans (with calibration data) and legacy scans (without).
    
    Region fields are feature-flagged in response but always persisted internally.
    """
    config = RegionCalibrationConfig
    
    # Build confidence breakdown if we have calibration data
    confidence_breakdown = None
    if scan.get("age_confidence") is not None or scan.get("recommendation_confidence") is not None:
        confidence_breakdown = {
            "age": scan.get("age_confidence") or 0,
            "recommendation": scan.get("recommendation_confidence") or scan.get("confidence") or 0
        }
    
    # Region fields (feature-flagged)
    region_key = scan.get("region_key") if config.CALIBRATION_SHOW_REGION else None
    calibration_strategy = scan.get("calibration_strategy") if config.CALIBRATION_SHOW_STRATEGY else None
    calibration_fallback_reason = scan.get("calibration_fallback_reason") if config.CALIBRATION_SHOW_STRATEGY else None
    age_estimation_allowed = scan.get("age_estimation_allowed")
    if age_estimation_allowed is None:
        age_estimation_allowed = scan.get("retake_reason") is None
    normalized_bc_score = normalize_saved_bc_score(scan.get("boone_crockett_score"))
    raw_response = scan.get("raw_response") or {}
    boone_crockett_status = scan.get("boone_crockett_status")
    if boone_crockett_status is None and isinstance(normalized_bc_score, dict):
        boone_crockett_status = normalized_bc_score.get("status")
    boone_crockett_gross = scan.get("boone_crockett_gross")
    boone_crockett_net = scan.get("boone_crockett_net")
    boone_crockett_final_score = scan.get("boone_crockett_final_score")
    if isinstance(normalized_bc_score, dict):
        computed = normalized_bc_score.get("computed") or {}
        boone_crockett_gross = boone_crockett_gross if boone_crockett_gross is not None else computed.get("grossScore")
        boone_crockett_net = boone_crockett_net if boone_crockett_net is not None else computed.get("finalScore")
        boone_crockett_final_score = (
            boone_crockett_final_score
            if boone_crockett_final_score is not None
            else computed.get("finalScore")
        )

    return DeerAnalysisResponse(
        id=scan["id"],
        user_id=scan["user_id"],
        local_image_id=scan["local_image_id"],
        deer_age=scan["deer_age"],
        age_bucket=scan.get("age_bucket"),
        age_range=scan.get("age_range"),
        buck_age_class=scan.get("buck_age_class"),
        age_evidence=scan.get("age_evidence") or [],
        cue_checklist=raw_response.get("cue_checklist") if isinstance(raw_response.get("cue_checklist"), dict) else {},
        alternate_age=raw_response.get("alternate_age"),
        why_not_primary=raw_response.get("why_not_primary"),
        abstain_reason=raw_response.get("abstain_reason"),
        foreshortening_risk=raw_response.get("foreshortening_risk") or raw_response.get("camera_angle_risk"),
        camera_angle_risk=raw_response.get("camera_angle_risk") or raw_response.get("foreshortening_risk"),
        distance_risk=raw_response.get("distance_risk"),
        deer_type=scan["deer_type"],
        deer_sex=scan["deer_sex"],
        antler_points=scan["antler_points"],
        antler_points_left=scan.get("antler_points_left"),
        antler_points_right=scan.get("antler_points_right"),
        body_condition=scan["body_condition"],
        confidence=scan["confidence"],
        recommendation=scan["recommendation"],
        reasoning=scan["reasoning"],
        notes=scan["notes"],
        created_at=scan["created_at"],
        # Calibration fields
        age_uncertain=scan.get("age_uncertain"),
        confidence_breakdown=confidence_breakdown,
        calibration_version=scan.get("calibration_version"),
        # Region fields (feature-flagged)
        region_key=region_key,
        calibration_strategy=calibration_strategy,
        calibration_fallback_reason=calibration_fallback_reason,
        image_quality_bucket=scan.get("image_quality_bucket"),
        quality_factors=scan.get("quality_factors") or {},
        posture_bucket=scan.get("posture_bucket"),
        analysis_prompt_version=scan.get("analysis_prompt_version"),
        analysis_model=scan.get("analysis_model"),
        age_estimation_allowed=age_estimation_allowed,
        retake_reason=scan.get("retake_reason"),
        visible_age_cues=scan.get("visible_age_cues") or [],
        consensus=(scan.get("raw_response") or {}).get("consensus"),
        # Cloud image storage (R2) - for cross-device image access
        image_url=scan.get("image_url"),
        # Favorites and Tags
        is_favorite=scan.get("is_favorite") or False,
        tags=scan.get("tags") or [],
        harvest_confirmed=bool(scan.get("harvest_confirmed")) if scan.get("harvest_confirmed") is not None else False,
        harvested_at=scan.get("harvested_at"),
        boone_crockett_score=normalized_bc_score,
        boone_crockett_gross=boone_crockett_gross,
        boone_crockett_net=boone_crockett_net,
        boone_crockett_final_score=boone_crockett_final_score,
        boone_crockett_status=boone_crockett_status,
        boone_crockett_calculated_at=scan.get("boone_crockett_calculated_at"),
        boone_crockett_updated_at=scan.get("boone_crockett_updated_at"),
    )

async def get_current_user(authorization: str = Header(None)) -> dict:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Not authenticated")
    
    try:
        token = authorization.split(" ")[1]
        user_id = verify_token(token)
        query = users_table.select().where(users_table.c.id == user_id)
        user = await database.fetch_one(query)
        if not user:
            raise HTTPException(status_code=401, detail="User not found")
        return dict(user)
    except Exception:
        raise HTTPException(status_code=401, detail="Invalid authentication")

async def get_optional_user(authorization: str = Header(None)) -> Optional[dict]:
    if not authorization or not authorization.startswith("Bearer "):
        return None
    
    try:
        token = authorization.split(" ")[1]
        user_id = verify_token(token)
        query = users_table.select().where(users_table.c.id == user_id)
        user = await database.fetch_one(query)
        return dict(user) if user else None
    except Exception:
        return None

# ============ AUTH ROUTES ============

@api_router.post("/auth/register", response_model=TokenResponse)
async def register(data: UserRegister):
    # Check if email exists
    query = users_table.select().where(users_table.c.email == data.email.lower())
    existing = await database.fetch_one(query)
    if existing:
        raise HTTPException(status_code=400, detail="Email already registered")
    
    # Check if username exists
    if data.username:
        query = users_table.select().where(users_table.c.username == data.username.lower())
        existing = await database.fetch_one(query)
        if existing:
            raise HTTPException(status_code=400, detail="Username already taken")
    
    user_id = str(uuid.uuid4())
    hashed_password = ph.hash(data.password)
    
    name = data.name
    if not name and data.first_name and data.last_name:
        name = f"{data.first_name} {data.last_name}"
    elif not name and data.first_name:
        name = data.first_name
    elif not name:
        name = data.email.split('@')[0]
    
    query = users_table.insert().values(
        id=user_id,
        email=data.email.lower(),
        password=hashed_password,
        name=name,
        first_name=data.first_name,
        last_name=data.last_name,
        username=data.username.lower() if data.username else None,
        created_at=datetime.utcnow(),
        subscription_tier="tracker",
        scans_remaining=3,
        total_scans_used=0,
        disclaimer_accepted=False,
    )
    await database.execute(query)
    
    token = create_token(user_id)
    
    return TokenResponse(
        access_token=token,
        user=UserResponse(
            id=user_id,
            email=data.email.lower(),
            name=name,
            username=data.username.lower() if data.username else None,
            created_at=datetime.utcnow(),
            subscription_tier="tracker",
            scans_remaining=3,
            total_scans_used=0,
            disclaimer_accepted=False,
            state=None
        )
    )

@api_router.post("/auth/login", response_model=TokenResponse)
async def login(data: UserLogin):
    identifier = data.email.lower().strip()
    
    # Try email first
    query = users_table.select().where(users_table.c.email == identifier)
    user = await database.fetch_one(query)
    
    # Try username if email not found
    if not user:
        query = users_table.select().where(sqlalchemy.func.lower(users_table.c.username) == identifier)
        user = await database.fetch_one(query)
    
    if not user:
        raise HTTPException(status_code=401, detail="Invalid credentials")
    
    user = dict(user)
    
    try:
        ph.verify(user["password"], data.password)
    except VerifyMismatchError:
        raise HTTPException(status_code=401, detail="Invalid credentials")
    
    token = create_token(user["id"])
    
    return TokenResponse(
        access_token=token,
        user=UserResponse(
            id=user["id"],
            email=user["email"],
            name=user["name"] or user["email"],
            username=user.get("username"),
            created_at=user["created_at"],
            subscription_tier=user.get("subscription_tier", "tracker"),
            scans_remaining=user.get("scans_remaining", 3),
            total_scans_used=user.get("total_scans_used", 0),
            disclaimer_accepted=user.get("disclaimer_accepted", False),
            disclaimer_accepted_at=user.get("disclaimer_accepted_at"),
            state=user.get("state")
        )
    )

@api_router.post("/auth/apple", response_model=TokenResponse)
async def apple_sign_in(data: AppleSignInRequest):
    """Sign in with Apple - creates account if not exists"""
    # Check if user already exists by apple_user_id
    query = users_table.select().where(users_table.c.apple_user_id == data.user)
    user = await database.fetch_one(query)
    
    if user:
        # Existing user - return token
        user = dict(user)
        token = create_token(user["id"])
        return TokenResponse(
            access_token=token,
            user=UserResponse(
                id=user["id"],
                email=user["email"],
                name=user["name"] or user.get("email", "Apple User"),
                username=user.get("username"),
                created_at=user["created_at"],
                subscription_tier=user.get("subscription_tier", "tracker"),
                scans_remaining=user.get("scans_remaining", 3),
                total_scans_used=user.get("total_scans_used", 0),
                disclaimer_accepted=user.get("disclaimer_accepted", False),
                disclaimer_accepted_at=user.get("disclaimer_accepted_at"),
                state=user.get("state")
            )
        )
    
    # Check if email already exists (but not linked to Apple)
    if data.email:
        query = users_table.select().where(users_table.c.email == data.email.lower())
        existing_user = await database.fetch_one(query)
        if existing_user:
            # Link Apple ID to existing account
            existing_user = dict(existing_user)
            update_query = users_table.update().where(
                users_table.c.id == existing_user["id"]
            ).values(apple_user_id=data.user)
            await database.execute(update_query)
            
            token = create_token(existing_user["id"])
            return TokenResponse(
                access_token=token,
                user=UserResponse(
                    id=existing_user["id"],
                    email=existing_user["email"],
                    name=existing_user["name"] or existing_user.get("email", "Apple User"),
                    username=existing_user.get("username"),
                    created_at=existing_user["created_at"],
                    subscription_tier=existing_user.get("subscription_tier", "tracker"),
                    scans_remaining=existing_user.get("scans_remaining", 3),
                    total_scans_used=existing_user.get("total_scans_used", 0),
                    disclaimer_accepted=existing_user.get("disclaimer_accepted", False),
                    disclaimer_accepted_at=existing_user.get("disclaimer_accepted_at"),
                    state=existing_user.get("state")
                )
            )
    
    # Create new user
    user_id = str(uuid.uuid4())
    now = datetime.utcnow()
    
    # Use email from Apple or generate placeholder for private relay
    email = data.email.lower() if data.email else f"{data.user}@privaterelay.appleid.com"
    name = data.full_name or "Apple User"
    
    insert_query = users_table.insert().values(
        id=user_id,
        email=email,
        name=name,
        password=ph.hash(str(uuid.uuid4())),  # Random password since they'll use Apple Sign In
        created_at=now,
        subscription_tier="tracker",
        scans_remaining=3,
        total_scans_used=0,
        disclaimer_accepted=False,
        apple_user_id=data.user
    )
    await database.execute(insert_query)
    
    token = create_token(user_id)
    
    return TokenResponse(
        access_token=token,
        user=UserResponse(
            id=user_id,
            email=email,
            name=name,
            username=None,
            created_at=now,
            subscription_tier="tracker",
            scans_remaining=3,
            total_scans_used=0,
            disclaimer_accepted=False,
            disclaimer_accepted_at=None,
            state=None
        )
    )

@api_router.get("/auth/me", response_model=UserResponse)
async def get_me(user: dict = Depends(get_current_user)):
    return UserResponse(
        id=user["id"],
        email=user["email"],
        name=user["name"] or user["email"],
        username=user.get("username"),
        created_at=user["created_at"],
        subscription_tier=user.get("subscription_tier", "tracker"),
        scans_remaining=user.get("scans_remaining", 3),
        total_scans_used=user.get("total_scans_used", 0),
        disclaimer_accepted=user.get("disclaimer_accepted", False),
        disclaimer_accepted_at=user.get("disclaimer_accepted_at"),
        state=user.get("state")
    )

@api_router.put("/auth/profile", response_model=UserResponse)
async def update_profile(data: ProfileUpdate, user: dict = Depends(get_current_user)):
    updates = {}
    
    if data.name is not None:
        updates["name"] = data.name
    
    if data.username is not None:
        query = users_table.select().where(
            (users_table.c.username == data.username) & 
            (users_table.c.id != user["id"])
        )
        existing = await database.fetch_one(query)
        if existing:
            raise HTTPException(status_code=400, detail="Username already taken")
        updates["username"] = data.username
    
    if data.email is not None:
        query = users_table.select().where(
            (users_table.c.email == data.email.lower()) & 
            (users_table.c.id != user["id"])
        )
        existing = await database.fetch_one(query)
        if existing:
            raise HTTPException(status_code=400, detail="Email already in use")
        updates["email"] = data.email.lower()
    
    if data.new_password:
        if not data.current_password:
            raise HTTPException(status_code=400, detail="Current password required")
        try:
            ph.verify(user["password"], data.current_password)
        except VerifyMismatchError:
            raise HTTPException(status_code=400, detail="Current password is incorrect")
        updates["password"] = ph.hash(data.new_password)
    
    # Handle state update for region calibration
    if data.state is not None:
        # Validate state code (must be 2 letters or empty to clear)
        if data.state == "":
            updates["state"] = None
        elif len(data.state) == 2 and data.state.isalpha():
            updates["state"] = data.state.upper()
        else:
            raise HTTPException(status_code=400, detail="State must be a 2-letter code (e.g., TX, IA)")
    
    if updates:
        query = users_table.update().where(users_table.c.id == user["id"]).values(**updates)
        await database.execute(query)
        user.update(updates)
    
    return UserResponse(
        id=user["id"],
        email=user.get("email"),
        name=user.get("name", user["email"]),
        username=user.get("username"),
        created_at=user["created_at"],
        subscription_tier=user.get("subscription_tier", "tracker"),
        scans_remaining=user.get("scans_remaining", 3),
        total_scans_used=user.get("total_scans_used", 0),
        disclaimer_accepted=user.get("disclaimer_accepted", False),
        disclaimer_accepted_at=user.get("disclaimer_accepted_at"),
        state=user.get("state")
    )

# ============ ACCOUNT DELETION ============

@api_router.delete("/auth/account")
async def delete_account(user: dict = Depends(get_current_user)):
    """
    Permanently delete user account and all associated data.
    This action cannot be undone.
    """
    user_id = user["id"]
    user_email = user["email"]
    
    try:
        # Delete all user's scans first
        delete_scans_query = scans_table.delete().where(scans_table.c.user_id == user_id)
        await database.execute(delete_scans_query)
        logger.info(f"Deleted all scans for user {user_id}")
        
        # Delete any password reset codes (uses email, not user_id)
        delete_reset_codes_query = password_reset_codes_table.delete().where(
            password_reset_codes_table.c.email == user_email
        )
        await database.execute(delete_reset_codes_query)
        logger.info(f"Deleted password reset codes for {user_email}")
        
        # Delete the user account
        delete_user_query = users_table.delete().where(users_table.c.id == user_id)
        await database.execute(delete_user_query)
        logger.info(f"Deleted user account {user_id}")
        
        return {"message": "Account deleted successfully"}
    
    except Exception as e:
        logger.error(f"Failed to delete account for user {user_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to delete account")

# ============ PASSWORD RESET ============

async def send_email_via_graph(to_email: str, subject: str, body: str):
    """Send email using Microsoft Graph API"""
    try:
        msal_app = msal.ConfidentialClientApplication(
            MS_GRAPH_CLIENT_ID,
            authority=f"https://login.microsoftonline.com/{MS_GRAPH_TENANT_ID}",
            client_credential=MS_GRAPH_CLIENT_SECRET
        )
        
        result = msal_app.acquire_token_silent(
            ["https://graph.microsoft.com/.default"],
            account=None
        )
        
        if not result:
            result = msal_app.acquire_token_for_client(
                scopes=["https://graph.microsoft.com/.default"]
            )
        
        if "access_token" not in result:
            raise Exception("Could not acquire token")
        
        access_token = result["access_token"]
        
        email_data = {
            "message": {
                "subject": subject,
                "body": {
                    "contentType": "HTML",
                    "content": body
                },
                "toRecipients": [{"emailAddress": {"address": to_email}}]
            },
            "saveToSentItems": "false"
        }
        
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"https://graph.microsoft.com/v1.0/users/{MS_GRAPH_SENDER_EMAIL}/sendMail",
                headers={
                    "Authorization": f"Bearer {access_token}",
                    "Content-Type": "application/json"
                },
                json=email_data
            )
            
            if response.status_code not in [200, 202]:
                raise Exception(f"Email send failed: {response.text}")
                
        return True
    except Exception as e:
        logger.error(f"Email send error: {e}")
        raise

@api_router.post("/auth/request-password-reset")
async def request_password_reset(data: PasswordResetRequest):
    query = users_table.select().where(users_table.c.email == data.email.lower())
    user = await database.fetch_one(query)
    
    if not user:
        return {"message": "If email exists, reset code sent"}
    
    code = ''.join(random.choices(string.digits, k=6))
    
    query = password_reset_codes_table.insert().values(
        id=str(uuid.uuid4()),
        email=data.email.lower(),
        code=code,
        created_at=datetime.utcnow(),
        used=False
    )
    await database.execute(query)
    
    try:
        await send_email_via_graph(
            data.email,
            "Iron Stag - Password Reset Code",
            f"""
            <h2>Password Reset</h2>
            <p>Your verification code is: <strong>{code}</strong></p>
            <p>This code expires in 15 minutes.</p>
            <p>If you didn't request this, ignore this email.</p>
            """
        )
    except Exception as e:
        logger.error(f"Failed to send reset email: {e}")
    
    return {"message": "If email exists, reset code sent"}

@api_router.post("/auth/verify-password-reset")
async def verify_password_reset(data: PasswordResetVerify):
    cutoff = datetime.utcnow() - timedelta(minutes=15)
    
    query = password_reset_codes_table.select().where(
        (password_reset_codes_table.c.email == data.email.lower()) &
        (password_reset_codes_table.c.code == data.code) &
        (password_reset_codes_table.c.used == False) &
        (password_reset_codes_table.c.created_at > cutoff)
    )
    reset_code = await database.fetch_one(query)
    
    if not reset_code:
        raise HTTPException(status_code=400, detail="Invalid or expired code")
    
    hashed = ph.hash(data.new_password)
    
    query = users_table.update().where(
        users_table.c.email == data.email.lower()
    ).values(password=hashed)
    await database.execute(query)
    
    query = password_reset_codes_table.update().where(
        password_reset_codes_table.c.id == reset_code["id"]
    ).values(used=True)
    await database.execute(query)
    
    return {"message": "Password reset successful"}

# ============ DISCLAIMER ============

@api_router.post("/auth/accept-disclaimer", response_model=UserResponse)
async def accept_disclaimer(data: DisclaimerAccept, user: dict = Depends(get_current_user)):
    now = datetime.utcnow()
    query = users_table.update().where(
        users_table.c.id == user["id"]
    ).values(
        disclaimer_accepted=data.accepted,
        disclaimer_accepted_at=now if data.accepted else None
    )
    await database.execute(query)
    
    user["disclaimer_accepted"] = data.accepted
    user["disclaimer_accepted_at"] = now if data.accepted else None
    
    return UserResponse(
        id=user["id"],
        email=user["email"],
        name=user["name"],
        username=user.get("username"),
        created_at=user["created_at"],
        subscription_tier=user.get("subscription_tier", "tracker"),
        scans_remaining=user.get("scans_remaining", 3),
        total_scans_used=user.get("total_scans_used", 0),
        disclaimer_accepted=user["disclaimer_accepted"],
        disclaimer_accepted_at=user.get("disclaimer_accepted_at"),
        state=user.get("state")
    )

# ============ SUBSCRIPTION HELPERS ============

async def check_scan_eligibility(user: dict) -> dict:
    """Check if user can scan. Free tier: 3 lifetime, Premium: unlimited"""
    if user.get("subscription_tier") == "master_stag":
        return {"allowed": True, "scans_remaining": -1, "is_premium": True}
    
    scans_remaining = user.get("scans_remaining", 3)
    total_used = user.get("total_scans_used", 0)
    
    if scans_remaining <= 0:
        return {
            "allowed": False,
            "reason": "free_limit_reached",
            "message": "You've used all your free scans. Upgrade to Master Stag for unlimited scans.",
            "scans_remaining": 0,
            "total_scans_used": total_used,
            "is_premium": False
        }
    
    return {
        "allowed": True,
        "scans_remaining": scans_remaining,
        "total_scans_used": total_used,
        "is_premium": False
    }

async def use_scan(user: dict) -> dict:
    """Decrement scan count after successful scan"""
    if user.get("subscription_tier") == "master_stag":
        query = users_table.update().where(
            users_table.c.id == user["id"]
        ).values(total_scans_used=users_table.c.total_scans_used + 1)
        await database.execute(query)
        return {"scans_remaining": -1, "total_scans_used": user.get("total_scans_used", 0) + 1}
    
    query = users_table.update().where(
        users_table.c.id == user["id"]
    ).values(
        scans_remaining=users_table.c.scans_remaining - 1,
        total_scans_used=users_table.c.total_scans_used + 1
    )
    await database.execute(query)
    
    return {
        "scans_remaining": max(0, user.get("scans_remaining", 3) - 1),
        "total_scans_used": user.get("total_scans_used", 0) + 1
    }

# ============ SUBSCRIPTION ROUTES ============

@api_router.get("/subscription/status", response_model=SubscriptionStatus)
async def get_subscription_status(user: dict = Depends(get_current_user)):
    is_premium = user.get("subscription_tier") == "master_stag"
    return SubscriptionStatus(
        tier=user.get("subscription_tier", "tracker"),
        scans_remaining=-1 if is_premium else user.get("scans_remaining", 3),
        total_scans_used=user.get("total_scans_used", 0),
        is_premium=is_premium,
        expires_at=user.get("subscription_expires_at")
    )

@api_router.get("/subscription/scan-eligibility")
async def check_scan_eligibility_endpoint(user: dict = Depends(get_current_user)):
    return await check_scan_eligibility(user)

# ============ IN-APP PURCHASE VALIDATION ENDPOINTS ============

class IAPValidationRequest(BaseModel):
    """Request model for IAP receipt validation"""
    receipt_data: str  # Base64 encoded receipt (iOS) or purchase token (Android)
    platform: str  # "ios" or "android"
    product_id: str
    transaction_id: Optional[str] = None

class IAPValidationResponse(BaseModel):
    """Response model for IAP validation"""
    is_valid: bool
    message: str
    product_id: Optional[str] = None
    expires_at: Optional[datetime] = None
    original_transaction_id: Optional[str] = None

@api_router.post("/subscription/validate-iap", response_model=IAPValidationResponse)
async def validate_iap_receipt(data: IAPValidationRequest, user: dict = Depends(get_current_user)):
    """
    Validate an In-App Purchase receipt from iOS or Android.
    This endpoint verifies the purchase with Apple/Google servers and upgrades the user.
    """
    try:
        logger.info(f"Validating IAP receipt for user {user['id']}, platform: {data.platform}, product: {data.product_id}")
        
        if data.platform == "ios":
            result = await validate_apple_receipt(data.receipt_data, data.product_id, user)
        elif data.platform == "android":
            result = await validate_google_receipt(data.receipt_data, data.product_id, user)
        else:
            raise HTTPException(status_code=400, detail="Invalid platform. Must be 'ios' or 'android'")
        
        if result["is_valid"]:
            # Upgrade user to premium
            expires_at = result.get("expires_at")
            query = users_table.update().where(
                users_table.c.id == user["id"]
            ).values(
                subscription_tier="master_stag",
                scans_remaining=-1,  # Unlimited
                subscription_expires_at=expires_at
            )
            await database.execute(query)
            logger.info(f"User {user['id']} upgraded to master_stag via IAP")
        
        return IAPValidationResponse(
            is_valid=result["is_valid"],
            message=result["message"],
            product_id=data.product_id,
            expires_at=result.get("expires_at"),
            original_transaction_id=result.get("original_transaction_id")
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"IAP validation error: {e}")
        raise HTTPException(status_code=400, detail=str(e))

async def validate_apple_receipt(receipt_data: str, product_id: str, user: dict) -> dict:
    """
    Validate iOS receipt with Apple's App Store Server API.
    Uses the modern verifyReceipt endpoint.
    """
    try:
        # Apple's production verification URL
        verify_url = "https://buy.itunes.apple.com/verifyReceipt"
        sandbox_url = "https://sandbox.itunes.apple.com/verifyReceipt"
        
        payload = {
            "receipt-data": receipt_data,
            "password": APPLE_IAP_SHARED_SECRET,
            "exclude-old-transactions": True
        }
        
        async with httpx.AsyncClient(timeout=30.0) as client:
            # Try production first
            response = await client.post(verify_url, json=payload)
            result = response.json()
            
            # If status is 21007, the receipt is from sandbox - retry with sandbox URL
            if result.get("status") == 21007:
                logger.info("Receipt is from sandbox, retrying with sandbox URL")
                response = await client.post(sandbox_url, json=payload)
                result = response.json()
        
        status = result.get("status", -1)
        
        # Status codes: https://developer.apple.com/documentation/appstorereceipts/status
        if status == 0:
            # Valid receipt
            latest_receipt_info = result.get("latest_receipt_info", [])
            
            # Find the latest transaction for our product
            valid_purchase = None
            for receipt in latest_receipt_info:
                if receipt.get("product_id") == product_id:
                    # Check if subscription is still valid
                    expires_ms = int(receipt.get("expires_date_ms", 0))
                    if expires_ms > datetime.utcnow().timestamp() * 1000:
                        valid_purchase = receipt
                        break
            
            if valid_purchase:
                expires_at = datetime.fromtimestamp(int(valid_purchase["expires_date_ms"]) / 1000)
                return {
                    "is_valid": True,
                    "message": "Purchase validated successfully",
                    "expires_at": expires_at,
                    "original_transaction_id": valid_purchase.get("original_transaction_id")
                }
            else:
                return {
                    "is_valid": False,
                    "message": "No valid subscription found for this product"
                }
        else:
            error_messages = {
                21000: "The request was not made using HTTP POST.",
                21002: "The data in the receipt-data property was malformed.",
                21003: "The receipt could not be authenticated.",
                21004: "The shared secret does not match.",
                21005: "The receipt server is temporarily unavailable.",
                21006: "This receipt is valid but the subscription has expired.",
                21008: "Receipt is from production but sent to sandbox.",
                21010: "The user account cannot be found."
            }
            message = error_messages.get(status, f"Unknown error (status: {status})")
            return {"is_valid": False, "message": message}
            
    except Exception as e:
        logger.error(f"Apple receipt validation error: {e}")
        return {"is_valid": False, "message": f"Validation failed: {str(e)}"}

async def validate_google_receipt(purchase_token: str, product_id: str, user: dict) -> dict:
    """
    Validate Android purchase token with Google Play API.
    Note: Requires setting up Google Service Account credentials.
    """
    try:
        if not GOOGLE_SERVICE_ACCOUNT_JSON:
            logger.warning("Google Service Account not configured, skipping server validation")
            # For development/testing, accept the purchase
            # In production, you MUST configure Google service account
            return {
                "is_valid": True,
                "message": "Purchase accepted (server validation skipped)",
                "expires_at": datetime.utcnow() + timedelta(days=30)
            }
        
        # Parse service account credentials
        credentials = json.loads(GOOGLE_SERVICE_ACCOUNT_JSON)
        
        # Get access token using service account
        # This is a simplified implementation - production should use google-auth library
        token_url = "https://oauth2.googleapis.com/token"
        
        # Build JWT for service account authentication
        now = datetime.utcnow()
        payload = {
            "iss": credentials["client_email"],
            "scope": "https://www.googleapis.com/auth/androidpublisher",
            "aud": token_url,
            "iat": int(now.timestamp()),
            "exp": int((now + timedelta(hours=1)).timestamp())
        }
        
        signed_jwt = jwt.encode(payload, credentials["private_key"], algorithm="RS256")
        
        async with httpx.AsyncClient(timeout=30.0) as client:
            # Get access token
            token_response = await client.post(
                token_url,
                data={
                    "grant_type": "urn:ietf:params:oauth:grant-type:jwt-bearer",
                    "assertion": signed_jwt
                }
            )
            
            if token_response.status_code != 200:
                return {"is_valid": False, "message": "Failed to authenticate with Google"}
            
            access_token = token_response.json().get("access_token")
            
            # Verify subscription purchase
            package_name = APPLE_BUNDLE_ID  # Same package name for Android
            verify_url = f"https://androidpublisher.googleapis.com/androidpublisher/v3/applications/{package_name}/purchases/subscriptions/{product_id}/tokens/{purchase_token}"
            
            verify_response = await client.get(
                verify_url,
                headers={"Authorization": f"Bearer {access_token}"}
            )
            
            if verify_response.status_code != 200:
                return {"is_valid": False, "message": f"Google verification failed: {verify_response.status_code}"}
            
            result = verify_response.json()
            
            # Check subscription state
            expiry_time_ms = int(result.get("expiryTimeMillis", 0))
            if expiry_time_ms > datetime.utcnow().timestamp() * 1000:
                expires_at = datetime.fromtimestamp(expiry_time_ms / 1000)
                return {
                    "is_valid": True,
                    "message": "Purchase validated successfully",
                    "expires_at": expires_at,
                    "original_transaction_id": result.get("orderId")
                }
            else:
                return {"is_valid": False, "message": "Subscription has expired"}
                
    except Exception as e:
        logger.error(f"Google receipt validation error: {e}")
        return {"is_valid": False, "message": f"Validation failed: {str(e)}"}

@api_router.post("/subscription/restore")
async def restore_purchases(user: dict = Depends(get_current_user)):
    """
    Restore purchases for a user. Called when user taps "Restore Purchases".
    The actual restoration is handled client-side by querying the store.
    This endpoint is called after client gets the receipt to validate it.
    """
    # The client will call validate-iap with the restored receipt
    # This endpoint exists for any server-side restore logic
    return {
        "status": "ready",
        "message": "Send restored purchase receipts to /subscription/validate-iap"
    }

@api_router.post("/subscription/cancel")
async def cancel_subscription(user: dict = Depends(get_current_user)):
    """
    Handle subscription cancellation.
    Note: For IAP, cancellations are handled through the app store.
    This endpoint is for users manually downgrading or admin actions.
    """
    try:
        # Check if user is premium
        if user.get("subscription_tier") != "master_stag":
            raise HTTPException(status_code=400, detail="No active subscription to cancel")
        
        # For IAP subscriptions, actual cancellation happens in App Store/Play Store
        # We can only downgrade manually upgraded users here
        query = users_table.update().where(
            users_table.c.id == user["id"]
        ).values(
            subscription_tier="tracker",
            scans_remaining=0,  # They've used their free tier already
            subscription_cancel_at_period_end=True
        )
        await database.execute(query)
        
        return {
            "status": "canceled",
            "message": "You have been downgraded to Tracker tier. To cancel your App Store/Play Store subscription, please manage it through your device settings."
        }
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Cancel subscription error: {e}")
        raise HTTPException(status_code=400, detail=str(e))

@api_router.post("/subscription/verify-revenuecat")
async def verify_revenuecat(user: dict = Depends(get_current_user)):
    """
    Verify RevenueCat subscription status and update user record.
    Called after a successful in-app purchase to sync subscription status with backend.
    """
    revenuecat_api_key = os.getenv("REVENUECAT_SECRET_KEY", "")
    if not revenuecat_api_key:
        logger.warning("RevenueCat API key not configured")
        return {"status": "error", "message": "RevenueCat not configured"}
    
    user_id = user["id"]
    
    try:
        # Call RevenueCat API to get subscriber info
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"https://api.revenuecat.com/v1/subscribers/{user_id}",
                headers={
                    "Authorization": f"Bearer {revenuecat_api_key}",
                    "Content-Type": "application/json",
                }
            )
            
            if response.status_code == 404:
                # User not found in RevenueCat - no subscription
                return {"status": "ok", "is_premium": False}
            
            response.raise_for_status()
            data = response.json()
        
        # Check for active entitlements
        subscriber = data.get("subscriber", {})
        entitlements = subscriber.get("entitlements", {})
        
        # Look for our premium entitlement
        master_stag = entitlements.get("master_stag", {})
        is_active = master_stag.get("expires_date") is not None
        
        # Check if not expired
        if is_active:
            expires_date_str = master_stag.get("expires_date")
            if expires_date_str:
                from datetime import datetime
                expires_date = datetime.fromisoformat(expires_date_str.replace("Z", "+00:00"))
                is_active = expires_date > datetime.now(expires_date.tzinfo)
        
        if is_active:
            # Update user's subscription status
            await database.execute(
                """
                UPDATE users 
                SET subscription_tier = :tier,
                    subscription_status = :status,
                    subscription_end_date = :end_date
                WHERE id = :user_id
                """,
                {
                    "user_id": user_id,
                    "tier": "master_stag",
                    "status": "active",
                    "end_date": master_stag.get("expires_date"),
                }
            )
            logger.info(f"User {user_id} subscription verified via RevenueCat: master_stag active")
            return {
                "status": "ok",
                "is_premium": True,
                "tier": "master_stag",
                "expires_at": master_stag.get("expires_date"),
            }
        else:
            # No active subscription
            return {"status": "ok", "is_premium": False}
            
    except httpx.HTTPStatusError as e:
        logger.error(f"RevenueCat API error: {e}")
        return {"status": "error", "message": "Failed to verify subscription"}
    except Exception as e:
        logger.error(f"RevenueCat verification error: {e}")
        return {"status": "error", "message": str(e)}


@api_router.post("/webhooks/revenuecat")
async def revenuecat_webhook(request: Request):
    """
    RevenueCat webhook endpoint for subscription events.
    Configure this URL in RevenueCat Dashboard > Integrations > Webhooks.
    
    Events handled:
    - INITIAL_PURCHASE: New subscription
    - RENEWAL: Subscription renewed
    - CANCELLATION: Subscription cancelled
    - EXPIRATION: Subscription expired
    - BILLING_ISSUE: Payment failed
    """
    # Verify webhook authenticity using shared secret
    webhook_secret = os.getenv("REVENUECAT_WEBHOOK_SECRET", "")
    auth_header = request.headers.get("Authorization", "")
    
    if webhook_secret and auth_header != f"Bearer {webhook_secret}":
        logger.warning("RevenueCat webhook: Invalid authorization")
        raise HTTPException(status_code=401, detail="Unauthorized")
    
    try:
        body = await request.json()
        event = body.get("event", {})
        event_type = event.get("type", "")
        app_user_id = event.get("app_user_id", "")
        
        logger.info(f"RevenueCat webhook: {event_type} for user {app_user_id}")
        
        if not app_user_id:
            logger.warning("RevenueCat webhook: No app_user_id in event")
            return {"status": "ok", "message": "No user ID"}
        
        # Look up user by ID (app_user_id should match our user.id)
        user = await database.fetch_one(
            "SELECT * FROM users WHERE id = :id",
            {"id": app_user_id}
        )
        
        if not user:
            logger.warning(f"RevenueCat webhook: User {app_user_id} not found")
            return {"status": "ok", "message": "User not found"}
        
        # Handle different event types
        if event_type in ["INITIAL_PURCHASE", "RENEWAL", "UNCANCELLATION"]:
            # Subscription is active
            product_id = event.get("product_id", "")
            expiration_at = event.get("expiration_at_ms")
            
            expiration_date = None
            if expiration_at:
                from datetime import datetime
                expiration_date = datetime.utcfromtimestamp(expiration_at / 1000)
            
            await database.execute(
                """
                UPDATE users 
                SET subscription_tier = :tier,
                    subscription_status = :status,
                    subscription_end_date = :end_date
                WHERE id = :user_id
                """,
                {
                    "user_id": app_user_id,
                    "tier": "master_stag",
                    "status": "active",
                    "end_date": expiration_date,
                }
            )
            logger.info(f"RevenueCat: Activated subscription for user {app_user_id}")
            
        elif event_type in ["CANCELLATION", "EXPIRATION"]:
            # Subscription ended
            await database.execute(
                """
                UPDATE users 
                SET subscription_status = :status
                WHERE id = :user_id
                """,
                {
                    "user_id": app_user_id,
                    "status": "cancelled" if event_type == "CANCELLATION" else "expired",
                }
            )
            logger.info(f"RevenueCat: {event_type} for user {app_user_id}")
            
        elif event_type == "BILLING_ISSUE":
            # Payment problem
            await database.execute(
                """
                UPDATE users 
                SET subscription_status = :status
                WHERE id = :user_id
                """,
                {
                    "user_id": app_user_id,
                    "status": "past_due",
                }
            )
            logger.warning(f"RevenueCat: Billing issue for user {app_user_id}")
        
        return {"status": "ok"}
        
    except Exception as e:
        logger.error(f"RevenueCat webhook error: {e}")
        # Always return 200 to prevent retries for errors we can't fix
        return {"status": "error", "message": str(e)}

class RevenueCatSyncRequest(BaseModel):
    """Request model for syncing RevenueCat subscription status"""
    is_premium: bool
    expires_at: Optional[str] = None
    product_id: Optional[str] = None
    original_purchase_date: Optional[str] = None

@api_router.post("/subscription/sync-revenuecat")
async def sync_revenuecat_subscription(data: RevenueCatSyncRequest, user: dict = Depends(get_current_user)):
    """
    Sync subscription status from RevenueCat to our database.
    Called after successful purchase or restore via RevenueCat SDK.
    """
    try:
        logger.info(f"Syncing RevenueCat subscription for user {user['id']}: is_premium={data.is_premium}")
        
        if data.is_premium:
            # Parse expiration date if provided
            expires_at = None
            if data.expires_at:
                try:
                    expires_at = datetime.fromisoformat(data.expires_at.replace('Z', '+00:00'))
                except:
                    pass
            
            # Upgrade user to master_stag
            query = users_table.update().where(
                users_table.c.id == user["id"]
            ).values(
                subscription_tier="master_stag",
                scans_remaining=-1,  # Unlimited
                subscription_expires_at=expires_at
            )
            await database.execute(query)
            
            logger.info(f"User {user['id']} upgraded to master_stag via RevenueCat")
            
            return {
                "status": "success",
                "message": "Subscription synced successfully",
                "subscription_tier": "master_stag",
                "expires_at": data.expires_at
            }
        else:
            # User is not premium (subscription expired or canceled)
            query = users_table.update().where(
                users_table.c.id == user["id"]
            ).values(
                subscription_tier="tracker",
                scans_remaining=0,  # They've used their free scans
                subscription_expires_at=None
            )
            await database.execute(query)
            
            logger.info(f"User {user['id']} downgraded to tracker via RevenueCat sync")
            
            return {
                "status": "success",
                "message": "Subscription status updated",
                "subscription_tier": "tracker"
            }
            
    except Exception as e:
        logger.error(f"RevenueCat sync error: {e}")
        raise HTTPException(status_code=400, detail=str(e))

# ============ DEER ANALYSIS ============

@api_router.post("/analyze-deer", response_model=DeerAnalysisResponse)
async def analyze_deer(data: DeerAnalysisRequest, user: dict = Depends(get_current_user)):
    eligibility = await check_scan_eligibility(user)
    if not eligibility["allowed"]:
        raise HTTPException(
            status_code=403,
            detail={
                "code": "FREE_LIMIT_REACHED",
                "message": eligibility["message"],
                "scans_remaining": 0,
                "upgrade_required": True
            }
        )
    
    try:
        image_data = data.image_base64
        if not image_data.startswith("data:"):
            image_data = f"data:image/jpeg;base64,{image_data}"
        scan_created_at = datetime.utcnow()
        selected_model, model_variant = select_analysis_model(
            user_id=user["id"],
            local_image_id=data.local_image_id,
        )
        user_profile_state = user.get("state")
        scan_context = build_scan_context(
            scan_state=data.state,
            user_profile_state=user_profile_state,
            scan_datetime=scan_created_at,
            notes=data.notes,
        )
        context_text = format_scan_context_for_prompt(scan_context)
        logger.info(
            "Using analysis model %s for user %s local_image_id %s (variant=%s)",
            selected_model,
            user["id"],
            data.local_image_id,
            model_variant,
        )

        user_content = [
            {
                "type": "text",
                "text": (
                    "Analyze this image and return JSON only.\n\n"
                    f"{context_text}\n\n"
                    "Use region and season as supporting context only. "
                    "Visible body anatomy must dominate the age estimate."
                ),
            },
            {"type": "image_url", "image_url": {"url": image_data}},
        ]

        initial_analysis = run_model_analysis_pass(
            model=selected_model,
            system_prompt=build_analysis_system_prompt(),
            user_content=user_content,
            max_output_tokens=1400,
            prompt_version=ANALYSIS_PROMPT_VERSION,
            context=scan_context,
        )

        if initial_analysis is None:
            analysis = {
                "is_valid_deer": False,
                "detected_subject": "Unknown",
                "message": "Could not analyze the image. Please try again with a clearer photo.",
            }
        else:
            analysis = maybe_apply_selective_consensus(
                initial_analysis=initial_analysis,
                total_passes=SELECTIVE_CONSENSUS_TOTAL_PASSES,
                pass_builder=lambda: run_model_analysis_pass(
                    model=selected_model,
                    system_prompt=build_analysis_system_prompt(),
                    user_content=user_content,
                    max_output_tokens=1400,
                    prompt_version=ANALYSIS_PROMPT_VERSION,
                    context=scan_context,
                ),
            )
            if analysis.get("consensus"):
                logger.info(
                    "Selective consensus applied for scan local_image_id %s: %s",
                    data.local_image_id,
                    analysis.get("consensus"),
                )

        # Check if this is a valid deer image
        if not analysis.get("is_valid_deer", False):
            detected = analysis.get("detected_subject", "Unknown")
            message = analysis.get("message", f"This image appears to contain {detected}, not a deer.")

            # Return rejection without saving or using a scan
            raise HTTPException(
                status_code=400,
                detail={
                    "code": "NOT_A_DEER",
                    "detected_subject": detected,
                    "message": message,
                    "save_scan": False
                }
            )
        # Apply region-aware confidence calibration
        active_curves = await get_live_active_curves()
        calibration_result, calibrated_analysis = calibrate_from_dict_with_region(
            analysis=analysis,
            state=data.state,  # From request
            user_profile_state=user_profile_state,  # Fallback from user profile
            active_curves=active_curves,
        )

        scan_id = str(uuid.uuid4())

        # Upload image to R2 cloud storage for cross-device access
        image_url = None
        if R2_ENABLED:
            try:
                image_url = upload_scan_image(scan_id, image_data)
                if image_url:
                    logger.info(f"Image uploaded to R2 for scan {scan_id}")
            except Exception as e:
                logger.warning(f"Failed to upload image to R2: {e}")
                # Continue without cloud image - local image still works
        
        query = scans_table.insert().values(
            id=scan_id,
            user_id=user["id"],
            local_image_id=data.local_image_id,
            deer_age=calibrated_analysis.get("deer_age"),  # May be null if age_uncertain
            age_bucket=calibrated_analysis.get("age_bucket"),
            age_range=calibrated_analysis.get("age_range"),
            buck_age_class=calibrated_analysis.get("buck_age_class"),
            age_evidence=calibrated_analysis.get("age_evidence"),
            deer_type=calibrated_analysis.get("deer_type"),
            deer_sex=calibrated_analysis.get("deer_sex"),
            antler_points=calibrated_analysis.get("antler_points"),
            antler_points_left=calibrated_analysis.get("antler_points_left"),
            antler_points_right=calibrated_analysis.get("antler_points_right"),
            body_condition=calibrated_analysis.get("body_condition"),
            confidence=calibrated_analysis.get("confidence"),  # Now holds recommendation_confidence
            recommendation=calibrated_analysis.get("recommendation"),
            reasoning=calibrated_analysis.get("reasoning"),
            notes=data.notes,
            raw_response=analysis,  # Preserve original for debugging
            created_at=scan_created_at,
            # Calibration fields
            raw_confidence=calibrated_analysis.get("raw_confidence"),
            raw_age_confidence=calibrated_analysis.get("raw_age_confidence"),
            raw_recommendation_confidence=calibrated_analysis.get("raw_recommendation_confidence"),
            age_confidence=calibrated_analysis.get("age_confidence"),
            recommendation_confidence=calibrated_analysis.get("recommendation_confidence"),
            age_uncertain=calibrated_analysis.get("age_uncertain", False),
            calibration_version=calibrated_analysis.get("calibration_version"),
            # Region fields (always persist, feature-flag controls response visibility)
            region_key=calibrated_analysis.get("region_key"),
            region_source=calibrated_analysis.get("region_source"),
            region_state=calibrated_analysis.get("region_state"),
            calibration_strategy=calibrated_analysis.get("calibration_strategy"),
            calibration_fallback_reason=calibrated_analysis.get("calibration_fallback_reason"),
            season_bucket=scan_context.get("season_bucket"),
            analysis_prompt_version=ANALYSIS_PROMPT_VERSION,
            analysis_model=selected_model,
            age_estimation_allowed=calibrated_analysis.get("age_estimation_allowed"),
            retake_reason=calibrated_analysis.get("retake_reason"),
            visible_age_cues=calibrated_analysis.get("visible_age_cues"),
            image_quality_bucket=calibrated_analysis.get("image_quality_bucket"),
            quality_factors=calibrated_analysis.get("quality_factors"),
            posture_bucket=calibrated_analysis.get("posture_bucket"),
            # Cloud image storage (R2)
            image_url=image_url,
        )
        await database.execute(query)

        await use_scan(user)

        # Build response with feature-flagged fields
        config = RegionCalibrationConfig

        return DeerAnalysisResponse(
            id=scan_id,
            user_id=user["id"],
            local_image_id=data.local_image_id,
            deer_age=calibrated_analysis.get("deer_age"),
            age_bucket=calibrated_analysis.get("age_bucket"),
            age_range=calibrated_analysis.get("age_range"),
            buck_age_class=calibrated_analysis.get("buck_age_class"),
            age_evidence=calibrated_analysis.get("age_evidence") or [],
            cue_checklist=calibrated_analysis.get("cue_checklist") or {},
            alternate_age=calibrated_analysis.get("alternate_age"),
            why_not_primary=calibrated_analysis.get("why_not_primary"),
            abstain_reason=calibrated_analysis.get("abstain_reason"),
            foreshortening_risk=calibrated_analysis.get("foreshortening_risk") or calibrated_analysis.get("camera_angle_risk"),
            camera_angle_risk=calibrated_analysis.get("camera_angle_risk") or calibrated_analysis.get("foreshortening_risk"),
            distance_risk=calibrated_analysis.get("distance_risk"),
            deer_type=calibrated_analysis.get("deer_type"),
            deer_sex=calibrated_analysis.get("deer_sex"),
            antler_points=calibrated_analysis.get("antler_points"),
            antler_points_left=calibrated_analysis.get("antler_points_left"),
            antler_points_right=calibrated_analysis.get("antler_points_right"),
            body_condition=calibrated_analysis.get("body_condition"),
            confidence=calibrated_analysis.get("confidence"),  # Recommendation confidence for backward compat
            recommendation=calibrated_analysis.get("recommendation"),
            reasoning=calibrated_analysis.get("reasoning"),
            notes=data.notes,
            created_at=scan_created_at,
            # Calibration fields
            age_uncertain=calibrated_analysis.get("age_uncertain"),
            confidence_breakdown={
                "age": calibrated_analysis.get("age_confidence", 0),
                "recommendation": calibrated_analysis.get("recommendation_confidence", 0)
            },
            calibration_version=calibrated_analysis.get("calibration_version"),
            # Region fields (feature-flagged)
            region_key=calibrated_analysis.get("region_key") if config.CALIBRATION_SHOW_REGION else None,
            calibration_strategy=calibrated_analysis.get("calibration_strategy") if config.CALIBRATION_SHOW_STRATEGY else None,
            calibration_fallback_reason=calibrated_analysis.get("calibration_fallback_reason") if config.CALIBRATION_SHOW_STRATEGY else None,
            image_quality_bucket=calibrated_analysis.get("image_quality_bucket"),
            quality_factors=calibrated_analysis.get("quality_factors") or {},
            posture_bucket=calibrated_analysis.get("posture_bucket"),
            analysis_prompt_version=ANALYSIS_PROMPT_VERSION,
            analysis_model=selected_model,
            age_estimation_allowed=calibrated_analysis.get("age_estimation_allowed"),
            retake_reason=calibrated_analysis.get("retake_reason"),
            visible_age_cues=calibrated_analysis.get("visible_age_cues") or [],
            consensus=calibrated_analysis.get("consensus"),
            # Cloud image storage (R2)
            image_url=image_url,
        )
        
    except openai.OpenAIError as e:
        logger.error(f"OpenAI error: {e}")
        raise HTTPException(status_code=500, detail=f"AI analysis failed: {str(e)}")

# ============ SCANS ROUTES ============

@api_router.get("/scans", response_model=List[DeerAnalysisResponse])
async def get_user_scans(
    user: dict = Depends(get_current_user),
    limit: int = 50,
    skip: int = 0
):
    # Enforce maximum limit to prevent performance issues
    limit = min(limit, 100)
    
    query = scans_table.select().where(
        scans_table.c.user_id == user["id"]
    ).order_by(scans_table.c.created_at.desc()).limit(limit).offset(skip)
    scans = await database.fetch_all(query)
    
    return [build_scan_response(dict(s)) for s in scans]

@api_router.get("/scans/stats/summary")
async def get_scan_stats(user: dict = Depends(get_current_user)):
    query = scans_table.select().where(scans_table.c.user_id == user["id"])
    scans = await database.fetch_all(query)
    
    total = len(scans)
    harvest = sum(1 for s in scans if s["recommendation"] == "HARVEST")
    pass_count = sum(1 for s in scans if s["recommendation"] == "PASS")
    
    return {"total_scans": total, "harvest_count": harvest, "pass_count": pass_count}

@api_router.get("/scans/{scan_id}", response_model=DeerAnalysisResponse)
async def get_scan(scan_id: str, user: dict = Depends(get_current_user)):
    query = scans_table.select().where(
        (scans_table.c.id == scan_id) & (scans_table.c.user_id == user["id"])
    )
    scan = await database.fetch_one(query)
    
    if not scan:
        raise HTTPException(status_code=404, detail="Scan not found")
    
    return build_scan_response(dict(scan))

@api_router.put("/scans/{scan_id}", response_model=DeerAnalysisResponse)
async def update_scan(scan_id: str, data: ScanUpdate, user: dict = Depends(get_current_user)):
    query = scans_table.select().where(
        (scans_table.c.id == scan_id) & (scans_table.c.user_id == user["id"])
    )
    scan = await database.fetch_one(query)
    
    if not scan:
        raise HTTPException(status_code=404, detail="Scan not found")
    scan = dict(scan)

    update_values: Dict[str, Any] = {}

    if data.notes is not None:
        update_values["notes"] = data.notes

    effective_harvest_confirmed = scan.get("harvest_confirmed")
    if data.harvest_confirmed is not None:
        effective_harvest_confirmed = data.harvest_confirmed
        update_values["harvest_confirmed"] = data.harvest_confirmed
        update_values["harvested_at"] = datetime.utcnow() if data.harvest_confirmed else None
        if not data.harvest_confirmed:
            update_values["boone_crockett_score"] = None
            update_values["boone_crockett_gross"] = None
            update_values["boone_crockett_net"] = None
            update_values["boone_crockett_final_score"] = None
            update_values["boone_crockett_status"] = None
            update_values["boone_crockett_calculated_at"] = None
            update_values["boone_crockett_updated_at"] = None

    if data.boone_crockett_measurements is not None:
        if not effective_harvest_confirmed:
            raise HTTPException(
                status_code=400,
                detail="Unofficial Boone & Crockett scoring is only available for harvested bucks."
            )
        requested_score_type = None
        if isinstance(data.boone_crockett_measurements, dict):
            requested_score_type = data.boone_crockett_measurements.get("type")

        if not is_bc_score_type_allowed_for_scan(
            score_type=requested_score_type or "typical_whitetail_unofficial",
            deer_type=scan.get("deer_type"),
            deer_sex=scan.get("deer_sex"),
            harvest_confirmed=bool(effective_harvest_confirmed),
        ):
            raise HTTPException(
                status_code=400,
                detail="This score type does not match the harvested buck record."
            )

        disclaimer_accepted = data.boone_crockett_disclaimer_accepted
        if disclaimer_accepted is None:
            disclaimer_accepted = bool(
                (scan.get("boone_crockett_score") or {}).get("disclaimerAccepted")
            )

        normalized_entry = normalize_bc_score_entry(
            data.boone_crockett_measurements,
            bool(disclaimer_accepted),
        )
        if normalized_entry is None:
            update_values["boone_crockett_score"] = None
            update_values["boone_crockett_gross"] = None
            update_values["boone_crockett_net"] = None
            update_values["boone_crockett_final_score"] = None
            update_values["boone_crockett_status"] = None
            update_values["boone_crockett_calculated_at"] = None
            update_values["boone_crockett_updated_at"] = None
        else:
            score_type = normalized_entry.get("type")
            if not is_supported_bc_score_type(score_type):
                raise HTTPException(
                    status_code=400,
                    detail=f"{get_bc_score_type_label(score_type)} scoring is not implemented yet."
                )
            score = build_bc_score_record(normalized_entry, calculated_at=datetime.utcnow())
            update_values["boone_crockett_score"] = score
            update_values["boone_crockett_gross"] = score["computed"].get("grossScore")
            update_values["boone_crockett_net"] = score["computed"].get("finalScore")
            update_values["boone_crockett_final_score"] = score["computed"].get("finalScore")
            update_values["boone_crockett_status"] = score.get("status")
            score_timestamp = datetime.fromisoformat(score["updatedAt"])
            if score_timestamp.tzinfo is not None:
                score_timestamp = score_timestamp.astimezone(timezone.utc).replace(tzinfo=None)
            update_values["boone_crockett_calculated_at"] = score_timestamp
            update_values["boone_crockett_updated_at"] = score_timestamp
            update_values["antler_points_left"] = score["pointsSummary"].get("leftPointsCount")
            update_values["antler_points_right"] = score["pointsSummary"].get("rightPointsCount")
            left_points = score["pointsSummary"].get("leftPointsCount")
            right_points = score["pointsSummary"].get("rightPointsCount")
            update_values["antler_points"] = (
                (left_points or 0) + (right_points or 0)
                if left_points is not None or right_points is not None
                else None
            )

    if update_values:
        query = scans_table.update().where(
            scans_table.c.id == scan_id
        ).values(**update_values)
        await database.execute(query)

    query = scans_table.select().where(scans_table.c.id == scan_id)
    scan = await database.fetch_one(query)

    return build_scan_response(dict(scan))


# ============ FAVORITES & TAGS ENDPOINTS ============

class ToggleFavoriteRequest(BaseModel):
    is_favorite: bool


class UpdateTagsRequest(BaseModel):
    tags: List[str]


@api_router.post("/scans/{scan_id}/favorite", response_model=DeerAnalysisResponse)
async def toggle_favorite(
    scan_id: str,
    data: ToggleFavoriteRequest,
    user: dict = Depends(get_current_user)
):
    """Toggle favorite status for a scan."""
    # Verify scan ownership
    query = scans_table.select().where(
        (scans_table.c.id == scan_id) & (scans_table.c.user_id == user["id"])
    )
    scan = await database.fetch_one(query)
    
    if not scan:
        raise HTTPException(status_code=404, detail="Scan not found")
    scan = dict(scan)
    
    # Update favorite status
    update_query = scans_table.update().where(
        scans_table.c.id == scan_id
    ).values(is_favorite=data.is_favorite)
    await database.execute(update_query)
    
    # Return updated scan
    scan = await database.fetch_one(query)
    return build_scan_response(dict(scan))


@api_router.post("/scans/{scan_id}/tags", response_model=DeerAnalysisResponse)
async def update_tags(
    scan_id: str,
    data: UpdateTagsRequest,
    user: dict = Depends(get_current_user)
):
    """Update tags for a scan."""
    # Verify scan ownership
    query = scans_table.select().where(
        (scans_table.c.id == scan_id) & (scans_table.c.user_id == user["id"])
    )
    scan = await database.fetch_one(query)
    
    if not scan:
        raise HTTPException(status_code=404, detail="Scan not found")
    
    # Validate tags (max 10 tags, max 30 chars each)
    if len(data.tags) > 10:
        raise HTTPException(status_code=400, detail="Maximum 10 tags allowed")
    
    for tag in data.tags:
        if len(tag) > 30:
            raise HTTPException(status_code=400, detail="Tag must be 30 characters or less")
    
    # Clean tags (lowercase, trim whitespace)
    clean_tags = [tag.strip().lower() for tag in data.tags if tag.strip()]
    unique_tags = list(dict.fromkeys(clean_tags))  # Remove duplicates, preserve order
    
    # Update tags
    import json
    update_query = scans_table.update().where(
        scans_table.c.id == scan_id
    ).values(tags=json.dumps(unique_tags))
    await database.execute(update_query)
    
    # Return updated scan
    scan = await database.fetch_one(query)
    return build_scan_response(dict(scan))


@api_router.get("/scans/tags/all")
async def get_all_user_tags(user: dict = Depends(get_current_user)):
    """Get all unique tags used by the user across all scans."""
    query = """
        SELECT DISTINCT jsonb_array_elements_text(tags::jsonb) as tag
        FROM scans
        WHERE user_id = :user_id AND tags IS NOT NULL
        ORDER BY tag
    """
    try:
        results = await database.fetch_all(query, {"user_id": user["id"]})
        tags = [r["tag"] for r in results]
        return {"tags": tags}
    except Exception:
        # Fallback for older Postgres versions
        return {"tags": []}


# ============ SCAN LABEL ENDPOINTS (Phase 2 Empirical Calibration) ============

# Label weight constants
LABEL_WEIGHTS = {
    "exact_age_harvested": 1.0,
    "exact_age_estimated": 0.7,
    "categorical_exact": 0.3,
    "categorical_close": 0.2,
    "categorical_off": 0.4,
}

# Credibility factors
CREDIBILITY_FACTORS = {
    "harvested": 1.0,
    "has_prior_exact_labels": 0.7,
    "default": 0.5,
}


def compute_error_bucket(predicted_age: Optional[float], reported_age: float) -> str:
    """
    Compute error bucket based on prediction error.
    Primary calibration metric: within_half (±0.5 years)
    """
    if predicted_age is None:
        return "off"
    
    error = abs(predicted_age - reported_age)
    
    if error <= 0.25:
        return "exact"
    elif error <= 0.5:
        return "within_half"
    elif error <= 1.0:
        return "within_one"
    else:
        return "off"


def compute_label_weight(label_type: str, accuracy_category: Optional[str], harvest_confirmed: bool) -> float:
    """Compute base label weight based on label type."""
    if label_type == "exact_age":
        return LABEL_WEIGHTS["exact_age_harvested"] if harvest_confirmed else LABEL_WEIGHTS["exact_age_estimated"]
    elif label_type == "categorical":
        if accuracy_category == "exact":
            return LABEL_WEIGHTS["categorical_exact"]
        elif accuracy_category == "close":
            return LABEL_WEIGHTS["categorical_close"]
        elif accuracy_category == "off":
            return LABEL_WEIGHTS["categorical_off"]
    return 0.5  # Default


async def compute_credibility_factor(user_id: str, harvest_confirmed: bool) -> float:
    """
    Compute credibility factor based on user history and harvest confirmation.
    Credibility: 1.0 (harvested) -> 0.7 (prior exact labels) -> 0.5 (default)
    """
    if harvest_confirmed:
        return CREDIBILITY_FACTORS["harvested"]
    
    # Check if user has prior exact age labels
    query = """
        SELECT COUNT(*) FROM scan_labels 
        WHERE user_id = :user_id AND label_type = 'exact_age'
    """
    result = await database.fetch_one(query, {"user_id": user_id})
    if result and result[0] > 0:
        return CREDIBILITY_FACTORS["has_prior_exact_labels"]
    
    return CREDIBILITY_FACTORS["default"]


@api_router.post("/scans/{scan_id}/label", response_model=ScanLabelResponse)
async def add_scan_label(
    scan_id: str,
    data: ScanLabelRequest,
    user: dict = Depends(get_current_user)
):
    """
    Add a label to a scan for empirical calibration.
    
    Two modes:
    1. Exact age (strong signal): Provide reported_age (usually after harvest)
    2. Categorical (weak signal): Provide accuracy_category ('exact', 'close', 'off')
    
    Labels are weighted by:
    - Label type (exact_age > categorical)
    - Credibility (harvest_confirmed > prior_exact_labels > default)
    """
    # Validate request - must have either reported_age OR accuracy_category
    if data.reported_age is None and data.accuracy_category is None:
        raise HTTPException(
            status_code=400, 
            detail="Must provide either reported_age (exact age) or accuracy_category ('exact', 'close', 'off')"
        )
    
    if data.accuracy_category and data.accuracy_category not in ["exact", "close", "off"]:
        raise HTTPException(
            status_code=400,
            detail="accuracy_category must be 'exact', 'close', or 'off'"
        )

    if data.reported_age is not None and (data.reported_age < 0 or data.reported_age > 15.5):
        raise HTTPException(
            status_code=400,
            detail="reported_age must be between 0 and 15.5 years"
        )
    
    # Get the scan
    query = scans_table.select().where(
        (scans_table.c.id == scan_id) & (scans_table.c.user_id == user["id"])
    )
    scan = await database.fetch_one(query)
    
    if not scan:
        raise HTTPException(status_code=404, detail="Scan not found")
    
    # Determine label type
    label_type = "exact_age" if data.reported_age is not None else "categorical"
    age_source = normalize_age_source(data.age_source) if label_type == "exact_age" else None
    labeler_role = normalize_labeler_role(data.labeler_role) or "self"

    if label_type == "exact_age" and age_source is None:
        age_source = "unknown"
    
    # Compute error metrics for exact age labels
    prediction_error = None
    error_bucket = None
    if label_type == "exact_age" and data.reported_age is not None:
        predicted_age = scan["deer_age"]
        if predicted_age is not None:
            prediction_error = abs(predicted_age - data.reported_age)
            error_bucket = compute_error_bucket(predicted_age, data.reported_age)
        else:
            error_bucket = "off"  # No prediction to compare
    elif label_type == "categorical":
        # Map categorical to error bucket
        error_bucket = data.accuracy_category
    
    # Compute weights
    base_weight = compute_label_weight(label_type, data.accuracy_category, data.harvest_confirmed)
    credibility = await compute_credibility_factor(user["id"], data.harvest_confirmed)
    source_multiplier = compute_age_source_multiplier(age_source) if label_type == "exact_age" else 1.0
    role_multiplier = compute_labeler_role_multiplier(labeler_role)
    effective_weight = base_weight * credibility * source_multiplier * role_multiplier
    trust_source = derive_label_trust_source(
        age_source=age_source,
        labeler_role=labeler_role,
        harvest_confirmed=data.harvest_confirmed,
    )
    label_source = derive_label_source(age_source, labeler_role, data.harvest_confirmed)
    
    # Compute age_correct and recommendation_correct for curve building
    # age_correct: True if exact match, None if can't determine
    # recommendation_correct: True if harvest recommendation was appropriate
    age_correct = None
    recommendation_correct = None
    
    if label_type == "exact_age" and data.reported_age is not None:
        predicted_age = scan["deer_age"]
        if predicted_age is not None:
            # Age is "correct" if within 0.5 years of reported age
            age_correct = abs(predicted_age - data.reported_age) <= 0.5
            
            # Recommendation is correct if:
            # - HARVEST was given for mature deer (3.5+ years) AND deer was actually mature
            # - PASS was given for young deer AND deer was actually young
            recommendation = scan["recommendation"]
            actual_mature = is_mature_harvest_age(data.reported_age)
            if recommendation == "HARVEST":
                recommendation_correct = actual_mature
            else:
                recommendation_correct = not actual_mature
    elif label_type == "categorical":
        # For categorical, 'exact' means correct
        if data.accuracy_category == "exact":
            age_correct = True
            recommendation_correct = True  # If age was exact, recommendation was likely correct
        elif data.accuracy_category == "close":
            age_correct = False  # Not quite right
            recommendation_correct = True  # But probably didn't affect recommendation
        else:  # 'off'
            age_correct = False
            recommendation_correct = False
    
    # Create label
    label_id = str(uuid.uuid4())
    now = datetime.utcnow()
    
    await database.execute(
        """
        INSERT INTO scan_labels (
            id, scan_id, user_id, label_type, label_weight, reported_age, 
            accuracy_category, prediction_error, error_bucket, harvest_confirmed,
            credibility_factor, effective_weight, notes, created_at, labeled_at,
            age_source, labeler_role, label_source, trust_source, trust_weight, label_version,
            age_correct, recommendation_correct
        ) VALUES (
            :id, :scan_id, :user_id, :label_type, :label_weight, :reported_age,
            :accuracy_category, :prediction_error, :error_bucket, :harvest_confirmed,
            :credibility_factor, :effective_weight, :notes, :created_at, :labeled_at,
            :age_source, :labeler_role, :label_source, :trust_source, :trust_weight, :label_version,
            :age_correct, :recommendation_correct
        )
        """,
        {
            "id": label_id,
            "scan_id": scan_id,
            "user_id": user["id"],
            "label_type": label_type,
            "label_weight": base_weight,
            "reported_age": data.reported_age,
            "accuracy_category": data.accuracy_category,
            "prediction_error": prediction_error,
            "error_bucket": error_bucket,
            "harvest_confirmed": data.harvest_confirmed,
            "credibility_factor": credibility,
            "effective_weight": effective_weight,
            "notes": data.notes,
            "created_at": now,
            "labeled_at": now,
            "age_source": age_source,
            "labeler_role": labeler_role,
            "label_source": label_source,
            "trust_source": trust_source,
            "trust_weight": effective_weight,
            "label_version": 1,  # Current weighting schema version
            "age_correct": age_correct,
            "recommendation_correct": recommendation_correct,
        }
    )
    
    logger.info(
        f"Scan label created: scan={scan_id}, type={label_type}, "
        f"weight={base_weight:.2f}, credibility={credibility:.2f}, "
        f"effective={effective_weight:.2f}, age_source={age_source}, "
        f"labeler_role={labeler_role}, error_bucket={error_bucket}"
    )
    
    return ScanLabelResponse(
        id=label_id,
        scan_id=scan_id,
        label_type=label_type,
        label_weight=base_weight,
        effective_weight=effective_weight,
        reported_age=data.reported_age,
        accuracy_category=data.accuracy_category,
        error_bucket=error_bucket,
        prediction_error=prediction_error,
        harvest_confirmed=data.harvest_confirmed,
        age_source=age_source,
        labeler_role=labeler_role,
        trust_source=trust_source,
        created_at=now,
    )


@api_router.get("/scans/{scan_id}/label", response_model=Optional[ScanLabelResponse])
async def get_scan_label(
    scan_id: str,
    user: dict = Depends(get_current_user)
):
    """Get the label for a specific scan if it exists."""
    # Verify scan ownership
    scan = await database.fetch_one(
        "SELECT id FROM scans WHERE id = :scan_id AND user_id = :user_id",
        {"scan_id": scan_id, "user_id": user["id"]}
    )
    if not scan:
        raise HTTPException(status_code=404, detail="Scan not found")
    
    # Get label
    label = await database.fetch_one(
        "SELECT * FROM scan_labels WHERE scan_id = :scan_id ORDER BY created_at DESC LIMIT 1",
        {"scan_id": scan_id}
    )
    
    if not label:
        return None
    
    return ScanLabelResponse(
        id=label["id"],
        scan_id=label["scan_id"],
        label_type=label["label_type"] or "unknown",
        label_weight=label["label_weight"] or 0,
        effective_weight=label["effective_weight"] or 0,
        reported_age=label["reported_age"],
        accuracy_category=label["accuracy_category"],
        error_bucket=label["error_bucket"],
        prediction_error=label["prediction_error"],
        harvest_confirmed=label["harvest_confirmed"] or False,
        age_source=label["age_source"],
        labeler_role=label["labeler_role"],
        trust_source=label["trust_source"],
        created_at=label["created_at"],
    )


@api_router.delete("/scans/{scan_id}/label")
async def delete_scan_label(
    scan_id: str,
    user: dict = Depends(get_current_user)
):
    """Delete the label for a specific scan."""
    # Verify scan ownership
    scan = await database.fetch_one(
        "SELECT id FROM scans WHERE id = :scan_id AND user_id = :user_id",
        {"scan_id": scan_id, "user_id": user["id"]}
    )
    if not scan:
        raise HTTPException(status_code=404, detail="Scan not found")
    
    # Delete label
    await database.execute(
        "DELETE FROM scan_labels WHERE scan_id = :scan_id",
        {"scan_id": scan_id}
    )
    
    return {"deleted": True, "scan_id": scan_id}


# ============ ADMIN LABEL ENDPOINTS (for CLI and future dashboard) ============

async def fetch_label_breakdown(
    *,
    segment_sql: str,
    alias: str,
    params: Dict[str, Any],
    base_filter: str,
) -> Dict[str, int]:
    query = f"""
        SELECT COALESCE({segment_sql}, 'unknown') as {alias}, COUNT(*) as count
        FROM scan_labels sl
        JOIN scans s ON sl.scan_id = s.id
        WHERE 1=1 {base_filter}
        GROUP BY COALESCE({segment_sql}, 'unknown')
    """
    rows = await database.fetch_all(query, params)
    return {str(r[alias]): r["count"] for r in rows}


async def fetch_exact_age_metrics_by_segment(
    *,
    segment_sql: str,
    alias: str,
    params: Dict[str, Any],
    base_filter: str,
) -> Tuple[Dict[str, float], Dict[str, float]]:
    query = f"""
        SELECT
            COALESCE({segment_sql}, 'unknown') as {alias},
            AVG(ABS(s.deer_age - sl.reported_age)) as mae,
            AVG(CASE WHEN ABS(s.deer_age - sl.reported_age) <= 0.5 THEN 1.0 ELSE 0.0 END) as within_half_accuracy
        FROM scan_labels sl
        JOIN scans s ON sl.scan_id = s.id
        WHERE sl.label_type = 'exact_age'
          AND sl.reported_age IS NOT NULL
          AND s.deer_age IS NOT NULL
          {base_filter}
        GROUP BY COALESCE({segment_sql}, 'unknown')
    """
    rows = await database.fetch_all(query, params)
    mae_by_segment: Dict[str, float] = {}
    within_half_by_segment: Dict[str, float] = {}
    for row in rows:
        segment = str(row[alias])
        if row["mae"] is not None:
            mae_by_segment[segment] = round(float(row["mae"]), 3)
        if row["within_half_accuracy"] is not None:
            within_half_by_segment[segment] = round(float(row["within_half_accuracy"]), 3)
    return mae_by_segment, within_half_by_segment


async def fetch_exact_age_coverage_by_segment(
    *,
    segment_sql: str,
    alias: str,
    params: Dict[str, Any],
    base_filter: str,
) -> Dict[str, float]:
    query = f"""
        SELECT
            COALESCE({segment_sql}, 'unknown') as {alias},
            AVG(CASE WHEN s.deer_age IS NOT NULL THEN 1.0 ELSE 0.0 END) as coverage
        FROM scan_labels sl
        JOIN scans s ON sl.scan_id = s.id
        WHERE sl.label_type = 'exact_age'
          AND sl.reported_age IS NOT NULL
          {base_filter}
        GROUP BY COALESCE({segment_sql}, 'unknown')
    """
    rows = await database.fetch_all(query, params)
    coverage_by_segment: Dict[str, float] = {}
    for row in rows:
        if row["coverage"] is not None:
            coverage_by_segment[str(row[alias])] = round(float(row["coverage"]), 3)
    return coverage_by_segment

@api_router.get("/admin/calibration/labels/stats", response_model=LabelStatsResponse)
async def get_label_stats(
    region: Optional[str] = None
):
    """
    Get statistics about labels in the system.
    Used by CLI for inspection and maturity gate checking.
    """
    # Build base query
    base_filter = ""
    params = {}
    if region:
        base_filter = " AND s.region_key = :region"
        params["region"] = region
    
    # Total labels
    total_query = f"""
        SELECT COUNT(*) FROM scan_labels sl
        JOIN scans s ON sl.scan_id = s.id
        WHERE 1=1 {base_filter}
    """
    total_result = await database.fetch_one(total_query, params)
    total_labels = total_result[0] if total_result else 0
    
    # By label type
    exact_query = f"""
        SELECT COUNT(*) FROM scan_labels sl
        JOIN scans s ON sl.scan_id = s.id
        WHERE sl.label_type = 'exact_age' {base_filter}
    """
    exact_result = await database.fetch_one(exact_query, params)
    exact_age_count = exact_result[0] if exact_result else 0
    
    categorical_count = total_labels - exact_age_count
    
    by_region = await fetch_label_breakdown(
        segment_sql="s.region_key",
        alias="region_key",
        params=params,
        base_filter=base_filter,
    )
    by_error_bucket = await fetch_label_breakdown(
        segment_sql="sl.error_bucket",
        alias="error_bucket",
        params=params,
        base_filter=base_filter,
    )
    by_image_quality = await fetch_label_breakdown(
        segment_sql="s.image_quality_bucket",
        alias="image_quality_bucket",
        params=params,
        base_filter=base_filter,
    )
    by_season_bucket = await fetch_label_breakdown(
        segment_sql="s.season_bucket",
        alias="season_bucket",
        params=params,
        base_filter=base_filter,
    )
    by_posture_bucket = await fetch_label_breakdown(
        segment_sql="s.posture_bucket",
        alias="posture_bucket",
        params=params,
        base_filter=base_filter,
    )
    by_age_estimation_allowed = await fetch_label_breakdown(
        segment_sql="CAST(s.age_estimation_allowed AS TEXT)",
        alias="age_estimation_allowed",
        params=params,
        base_filter=base_filter,
    )
    by_age_source = await fetch_label_breakdown(
        segment_sql="sl.age_source",
        alias="age_source",
        params=params,
        base_filter=base_filter,
    )
    by_labeler_role = await fetch_label_breakdown(
        segment_sql="sl.labeler_role",
        alias="labeler_role",
        params=params,
        base_filter=base_filter,
    )
    by_analysis_model = await fetch_label_breakdown(
        segment_sql="s.analysis_model",
        alias="analysis_model",
        params=params,
        base_filter=base_filter,
    )
    by_prompt_version = await fetch_label_breakdown(
        segment_sql="s.analysis_prompt_version",
        alias="prompt_version",
        params=params,
        base_filter=base_filter,
    )

    exact_eval_query = f"""
        SELECT
            AVG(ABS(s.deer_age - sl.reported_age)) as mae,
            AVG(CASE WHEN ABS(s.deer_age - sl.reported_age) <= 0.5 THEN 1.0 ELSE 0.0 END) as within_half_accuracy
        FROM scan_labels sl
        JOIN scans s ON sl.scan_id = s.id
        WHERE sl.label_type = 'exact_age'
          AND sl.reported_age IS NOT NULL
          AND s.deer_age IS NOT NULL
          {base_filter}
    """
    exact_eval_result = await database.fetch_one(exact_eval_query, params)
    exact_age_mae = None
    exact_age_within_half_accuracy = None
    if exact_eval_result:
        if exact_eval_result["mae"] is not None:
            exact_age_mae = round(float(exact_eval_result["mae"]), 3)
        if exact_eval_result["within_half_accuracy"] is not None:
            exact_age_within_half_accuracy = round(float(exact_eval_result["within_half_accuracy"]), 3)
    exact_coverage_query = f"""
        SELECT
            AVG(CASE WHEN s.deer_age IS NOT NULL THEN 1.0 ELSE 0.0 END) as coverage
        FROM scan_labels sl
        JOIN scans s ON sl.scan_id = s.id
        WHERE sl.label_type = 'exact_age'
          AND sl.reported_age IS NOT NULL
          {base_filter}
    """
    exact_coverage_result = await database.fetch_one(exact_coverage_query, params)
    exact_age_coverage = None
    if exact_coverage_result and exact_coverage_result["coverage"] is not None:
        exact_age_coverage = round(float(exact_coverage_result["coverage"]), 3)

    exact_age_mae_by_prompt_version, exact_age_within_half_by_prompt_version = await fetch_exact_age_metrics_by_segment(
        segment_sql="s.analysis_prompt_version",
        alias="prompt_version",
        params=params,
        base_filter=base_filter,
    )
    exact_age_coverage_by_prompt_version = await fetch_exact_age_coverage_by_segment(
        segment_sql="s.analysis_prompt_version",
        alias="prompt_version",
        params=params,
        base_filter=base_filter,
    )
    exact_age_mae_by_analysis_model, exact_age_within_half_by_analysis_model = await fetch_exact_age_metrics_by_segment(
        segment_sql="s.analysis_model",
        alias="analysis_model",
        params=params,
        base_filter=base_filter,
    )
    exact_age_coverage_by_analysis_model = await fetch_exact_age_coverage_by_segment(
        segment_sql="s.analysis_model",
        alias="analysis_model",
        params=params,
        base_filter=base_filter,
    )
    exact_age_mae_by_region, exact_age_within_half_by_region = await fetch_exact_age_metrics_by_segment(
        segment_sql="s.region_key",
        alias="region_key",
        params=params,
        base_filter=base_filter,
    )
    exact_age_coverage_by_region = await fetch_exact_age_coverage_by_segment(
        segment_sql="s.region_key",
        alias="region_key",
        params=params,
        base_filter=base_filter,
    )
    exact_age_mae_by_season_bucket, exact_age_within_half_by_season_bucket = await fetch_exact_age_metrics_by_segment(
        segment_sql="s.season_bucket",
        alias="season_bucket",
        params=params,
        base_filter=base_filter,
    )
    exact_age_coverage_by_season_bucket = await fetch_exact_age_coverage_by_segment(
        segment_sql="s.season_bucket",
        alias="season_bucket",
        params=params,
        base_filter=base_filter,
    )
    exact_age_mae_by_image_quality, exact_age_within_half_by_image_quality = await fetch_exact_age_metrics_by_segment(
        segment_sql="s.image_quality_bucket",
        alias="image_quality_bucket",
        params=params,
        base_filter=base_filter,
    )
    exact_age_coverage_by_image_quality = await fetch_exact_age_coverage_by_segment(
        segment_sql="s.image_quality_bucket",
        alias="image_quality_bucket",
        params=params,
        base_filter=base_filter,
    )
    exact_age_mae_by_posture_bucket, exact_age_within_half_by_posture_bucket = await fetch_exact_age_metrics_by_segment(
        segment_sql="s.posture_bucket",
        alias="posture_bucket",
        params=params,
        base_filter=base_filter,
    )
    exact_age_coverage_by_posture_bucket = await fetch_exact_age_coverage_by_segment(
        segment_sql="s.posture_bucket",
        alias="posture_bucket",
        params=params,
        base_filter=base_filter,
    )
    
    # Total weighted samples
    weight_query = f"""
        SELECT COALESCE(SUM(sl.effective_weight), 0) 
        FROM scan_labels sl
        JOIN scans s ON sl.scan_id = s.id
        WHERE 1=1 {base_filter}
    """
    weight_result = await database.fetch_one(weight_query, params)
    total_weighted = float(weight_result[0]) if weight_result and weight_result[0] else 0.0
    
    # Check maturity gates
    maturity_gates = {
        "global_min_samples": total_labels >= 500,
        "global_min_weighted": total_weighted >= 300,
        "has_region_data": len(by_region) > 0,
        "has_quality_diversity": len(by_image_quality) >= 2,
    }
    
    return LabelStatsResponse(
        total_labels=total_labels,
        exact_age_count=exact_age_count,
        categorical_count=categorical_count,
        by_region=by_region,
        by_error_bucket=by_error_bucket,
        by_image_quality=by_image_quality,
        by_season_bucket=by_season_bucket,
        by_posture_bucket=by_posture_bucket,
        by_age_estimation_allowed=by_age_estimation_allowed,
        by_age_source=by_age_source,
        by_labeler_role=by_labeler_role,
        total_weighted_samples=total_weighted,
        maturity_gates=maturity_gates,
        exact_age_mae=exact_age_mae,
        exact_age_within_half_accuracy=exact_age_within_half_accuracy,
        exact_age_coverage=exact_age_coverage,
        by_prompt_version=by_prompt_version,
        exact_age_mae_by_prompt_version=exact_age_mae_by_prompt_version,
        exact_age_within_half_by_prompt_version=exact_age_within_half_by_prompt_version,
        exact_age_coverage_by_prompt_version=exact_age_coverage_by_prompt_version,
        by_analysis_model=by_analysis_model,
        exact_age_mae_by_analysis_model=exact_age_mae_by_analysis_model,
        exact_age_within_half_by_analysis_model=exact_age_within_half_by_analysis_model,
        exact_age_coverage_by_analysis_model=exact_age_coverage_by_analysis_model,
        exact_age_mae_by_region=exact_age_mae_by_region,
        exact_age_within_half_by_region=exact_age_within_half_by_region,
        exact_age_coverage_by_region=exact_age_coverage_by_region,
        exact_age_mae_by_season_bucket=exact_age_mae_by_season_bucket,
        exact_age_within_half_by_season_bucket=exact_age_within_half_by_season_bucket,
        exact_age_coverage_by_season_bucket=exact_age_coverage_by_season_bucket,
        exact_age_mae_by_image_quality=exact_age_mae_by_image_quality,
        exact_age_within_half_by_image_quality=exact_age_within_half_by_image_quality,
        exact_age_coverage_by_image_quality=exact_age_coverage_by_image_quality,
        exact_age_mae_by_posture_bucket=exact_age_mae_by_posture_bucket,
        exact_age_within_half_by_posture_bucket=exact_age_within_half_by_posture_bucket,
        exact_age_coverage_by_posture_bucket=exact_age_coverage_by_posture_bucket,
    )


@api_router.get("/admin/calibration/labels")
async def get_labels(
    region: Optional[str] = None,
    since: Optional[str] = None,
    label_type: Optional[str] = None,
    limit: int = 100
):
    """
    Get labels for inspection. Used by CLI.
    """
    limit = min(limit, 500)
    
    # Build query
    conditions = ["1=1"]
    params = {"limit": limit}
    
    if region:
        conditions.append("s.region_key = :region")
        params["region"] = region
    
    if since:
        conditions.append("sl.created_at >= :since")
        params["since"] = since
    
    if label_type:
        conditions.append("sl.label_type = :label_type")
        params["label_type"] = label_type
    
    where_clause = " AND ".join(conditions)
    
    query = f"""
        SELECT
            sl.*,
            s.region_key,
            s.season_bucket,
            s.image_quality_bucket,
            s.posture_bucket,
            s.analysis_prompt_version,
            s.analysis_model,
            s.age_estimation_allowed,
            s.retake_reason,
            s.deer_age as predicted_age
        FROM scan_labels sl
        JOIN scans s ON sl.scan_id = s.id
        WHERE {where_clause}
        ORDER BY sl.created_at DESC
        LIMIT :limit
    """
    
    results = await database.fetch_all(query, params)
    
    labels = []
    for r in results:
        labels.append({
            "id": r["id"],
            "scan_id": r["scan_id"],
            "label_type": r["label_type"],
            "label_weight": r["label_weight"],
            "effective_weight": r["effective_weight"],
            "reported_age": r["reported_age"],
            "accuracy_category": r["accuracy_category"],
            "error_bucket": r["error_bucket"],
            "prediction_error": r["prediction_error"],
            "harvest_confirmed": r["harvest_confirmed"],
            "age_source": r["age_source"],
            "labeler_role": r["labeler_role"],
            "trust_source": r["trust_source"],
            "region_key": r["region_key"],
            "season_bucket": r["season_bucket"],
            "image_quality_bucket": r["image_quality_bucket"],
            "posture_bucket": r["posture_bucket"],
            "analysis_prompt_version": r["analysis_prompt_version"],
            "analysis_model": r["analysis_model"],
            "age_estimation_allowed": r["age_estimation_allowed"],
            "retake_reason": r["retake_reason"],
            "predicted_age": r["predicted_age"],
            "created_at": r["created_at"].isoformat() if r["created_at"] else None,
        })
    
    return {"labels": labels, "count": len(labels)}


@api_router.post("/scans/{scan_id}/edit", response_model=DeerAnalysisResponse)
async def edit_scan_with_reanalysis(
    scan_id: str, 
    data: ScanEditRequest, 
    user: dict = Depends(get_current_user)
):
    """
    Edit scan details and optionally re-analyze with LLM.
    User can correct deer_sex, deer_type, and antler_points.
    If image_base64 is provided, the LLM will re-analyze with user corrections as hints.
    """
    # Get existing scan
    query = scans_table.select().where(
        (scans_table.c.id == scan_id) & (scans_table.c.user_id == user["id"])
    )
    scan = await database.fetch_one(query)
    
    if not scan:
        raise HTTPException(status_code=404, detail="Scan not found")
    
    # Calculate total antler points if left/right provided
    total_points = None
    if data.antler_points_left is not None or data.antler_points_right is not None:
        left = data.antler_points_left or 0
        right = data.antler_points_right or 0
        total_points = left + right
    
    # If image is provided, re-analyze with LLM
    if data.image_base64:
        try:
            logger.info(f"Re-analyzing scan {scan_id} with user corrections")
            selected_model, model_variant = resolve_reanalysis_model(dict(scan), user["id"])
            
            image_data = data.image_base64
            if not image_data.startswith("data:"):
                image_data = f"data:image/jpeg;base64,{image_data}"

            existing_region_state = scan.get("region_state")
            user_profile_state = user.get("state")
            reanalysis_context = build_scan_context(
                scan_state=existing_region_state,
                user_profile_state=user_profile_state,
                scan_datetime=scan.get("created_at") or datetime.utcnow(),
                notes=scan.get("notes"),
            )

            # Build hint text from user corrections with context about original analysis
            hints = []

            # Keep non-age context only to avoid anchoring on the previous estimate.
            original_context = []
            if scan.get("deer_type"):
                original_context.append(f"Previous deer type: {scan.get('deer_type')}")
            if scan.get("deer_sex"):
                original_context.append(f"Previous sex: {scan.get('deer_sex')}")
            if scan.get("antler_points"):
                original_context.append(f"Previous total point count: {scan.get('antler_points')} points")
            if scan.get("body_condition"):
                original_context.append(f"Previous body condition: {scan.get('body_condition')}")

            # Add user corrections
            if data.deer_sex:
                hints.append(f"The deer is actually a {data.deer_sex}.")
            if data.deer_type:
                hints.append(f"The deer type is {data.deer_type}.")
            if data.antler_points_left is not None:
                hints.append(f"Left antler has exactly {data.antler_points_left} points.")
            if data.antler_points_right is not None:
                hints.append(f"Right antler has exactly {data.antler_points_right} points.")
            if total_points is not None:
                hints.append(f"Total antler points is {total_points}.")

            # Combine original context and corrections
            context_text = "\n".join(original_context) if original_context else ""
            hint_text = "\n".join(hints) if hints else ""

            logger.info(f"Re-analysis corrections: {hint_text}")
            logger.info(
                "Using reanalysis model %s for scan %s (variant=%s)",
                selected_model,
                scan_id,
                model_variant,
            )

            # Build user message with clear correction context
            if hint_text:
                user_message = f"""RE-ANALYZE this deer image with USER CORRECTIONS.

{format_scan_context_for_prompt(reanalysis_context)}

PREVIOUS AI OBSERVATIONS (context only, may be wrong):
{context_text if context_text else "No original analysis data available"}

AUTHORITATIVE USER CORRECTIONS:
{hint_text}

INSTRUCTIONS:
1. Accept all user corrections as factual.
2. Do NOT use the previous AI age estimate as evidence.
3. Re-estimate age primarily from visible body morphology.
4. Use corrected antler counts as a weak secondary cue only.
5. Update HARVEST/PASS based on the revised assessment.

Provide your complete REVISED analysis in JSON format."""
            else:
                user_message = (
                    "Re-analyze this deer image and provide a complete assessment in JSON format.\n\n"
                    f"{format_scan_context_for_prompt(reanalysis_context)}"
                )

            def apply_reanalysis_overrides(parsed_analysis: Dict[str, Any]) -> Dict[str, Any]:
                if data.deer_sex:
                    parsed_analysis["deer_sex"] = data.deer_sex
                if data.deer_type:
                    parsed_analysis["deer_type"] = data.deer_type
                if data.antler_points_left is not None:
                    parsed_analysis["antler_points_left"] = data.antler_points_left
                if data.antler_points_right is not None:
                    parsed_analysis["antler_points_right"] = data.antler_points_right
                if total_points is not None:
                    parsed_analysis["antler_points"] = total_points
                parsed_analysis["is_valid_deer"] = True
                return parsed_analysis

            user_content = [
                {"type": "text", "text": user_message},
                {"type": "image_url", "image_url": {"url": image_data}},
            ]

            initial_analysis = run_model_analysis_pass(
                model=selected_model,
                system_prompt=build_reanalysis_system_prompt(),
                user_content=user_content,
                max_output_tokens=1500,
                prompt_version=REANALYSIS_PROMPT_VERSION,
                context=reanalysis_context,
                post_parse=apply_reanalysis_overrides,
            )

            if initial_analysis is None:
                analysis = None
            else:
                analysis = maybe_apply_selective_consensus(
                    initial_analysis=initial_analysis,
                    total_passes=SELECTIVE_CONSENSUS_TOTAL_PASSES,
                    pass_builder=lambda: run_model_analysis_pass(
                        model=selected_model,
                        system_prompt=build_reanalysis_system_prompt(),
                        user_content=user_content,
                        max_output_tokens=1500,
                        prompt_version=REANALYSIS_PROMPT_VERSION,
                        context=reanalysis_context,
                        post_parse=apply_reanalysis_overrides,
                    ),
                )
                if analysis.get("consensus"):
                    logger.info(
                        "Selective consensus applied for reanalysis scan %s: %s",
                        scan_id,
                        analysis.get("consensus"),
                    )

            if analysis:
                # Apply region-aware confidence calibration to re-analysis
                active_curves = await get_live_active_curves()
                calibration_result, calibrated_analysis = calibrate_from_dict_with_region(
                    analysis=analysis,
                    state=existing_region_state,  # Preserve original region
                    user_profile_state=user_profile_state,
                    active_curves=active_curves,
                )

                # Update the scan with new calibrated analysis
                update_query = scans_table.update().where(
                    scans_table.c.id == scan_id
                ).values(
                    deer_age=calibrated_analysis.get("deer_age"),
                    age_bucket=calibrated_analysis.get("age_bucket"),
                    age_range=calibrated_analysis.get("age_range"),
                    buck_age_class=calibrated_analysis.get("buck_age_class"),
                    age_evidence=calibrated_analysis.get("age_evidence"),
                    deer_type=calibrated_analysis.get("deer_type"),
                    deer_sex=calibrated_analysis.get("deer_sex"),
                    antler_points=calibrated_analysis.get("antler_points"),
                    antler_points_left=calibrated_analysis.get("antler_points_left"),
                    antler_points_right=calibrated_analysis.get("antler_points_right"),
                    body_condition=calibrated_analysis.get("body_condition"),
                    confidence=calibrated_analysis.get("confidence"),
                    recommendation=calibrated_analysis.get("recommendation"),
                    reasoning=calibrated_analysis.get("reasoning"),
                    raw_response=analysis,  # Store original for debugging
                    raw_confidence=calibrated_analysis.get("raw_confidence"),
                    raw_age_confidence=calibrated_analysis.get("raw_age_confidence"),
                    raw_recommendation_confidence=calibrated_analysis.get("raw_recommendation_confidence"),
                    age_confidence=calibrated_analysis.get("age_confidence"),
                    recommendation_confidence=calibrated_analysis.get("recommendation_confidence"),
                    age_uncertain=calibrated_analysis.get("age_uncertain", False),
                    calibration_version=calibrated_analysis.get("calibration_version"),
                    region_key=calibrated_analysis.get("region_key"),
                    region_source=calibrated_analysis.get("region_source"),
                    region_state=calibrated_analysis.get("region_state"),
                    calibration_strategy=calibrated_analysis.get("calibration_strategy"),
                    calibration_fallback_reason=calibrated_analysis.get("calibration_fallback_reason"),
                    season_bucket=reanalysis_context.get("season_bucket"),
                    analysis_prompt_version=REANALYSIS_PROMPT_VERSION,
                    analysis_model=selected_model,
                    age_estimation_allowed=calibrated_analysis.get("age_estimation_allowed"),
                    retake_reason=calibrated_analysis.get("retake_reason"),
                    visible_age_cues=calibrated_analysis.get("visible_age_cues"),
                    image_quality_bucket=calibrated_analysis.get("image_quality_bucket"),
                    quality_factors=calibrated_analysis.get("quality_factors"),
                    posture_bucket=calibrated_analysis.get("posture_bucket"),
                )
                await database.execute(update_query)
        except Exception as e:
            logger.error(f"Re-analysis failed: {e}")
            # Fall through to simple update
    else:
        # Simple update without re-analysis
        update_values = {}
        if data.deer_sex is not None:
            update_values["deer_sex"] = data.deer_sex
            if data.deer_sex == "Doe":
                update_values["antler_points"] = None
                update_values["antler_points_left"] = None
                update_values["antler_points_right"] = None
        if data.deer_type is not None:
            update_values["deer_type"] = data.deer_type
        if data.antler_points_left is not None and update_values.get("deer_sex") != "Doe":
            update_values["antler_points_left"] = data.antler_points_left
        if data.antler_points_right is not None and update_values.get("deer_sex") != "Doe":
            update_values["antler_points_right"] = data.antler_points_right
        if total_points is not None and update_values.get("deer_sex") != "Doe":
            update_values["antler_points"] = total_points
        
        if update_values:
            update_query = scans_table.update().where(
                scans_table.c.id == scan_id
            ).values(**update_values)
            await database.execute(update_query)
    
    # Fetch updated scan
    query = scans_table.select().where(scans_table.c.id == scan_id)
    updated_scan = await database.fetch_one(query)
    
    return build_scan_response(dict(updated_scan))

@api_router.delete("/scans/{scan_id}")
async def delete_scan(scan_id: str, user: dict = Depends(get_current_user)):
    query = scans_table.select().where(
        (scans_table.c.id == scan_id) & (scans_table.c.user_id == user["id"])
    )
    scan = await database.fetch_one(query)
    
    if not scan:
        raise HTTPException(status_code=404, detail="Scan not found")
    
    # Delete image from R2 cloud storage
    if R2_ENABLED:
        try:
            delete_scan_image(scan_id)
        except Exception as e:
            logger.warning(f"Failed to delete R2 image for scan {scan_id}: {e}")
            # Continue with DB deletion even if R2 fails
    
    query = scans_table.delete().where(scans_table.c.id == scan_id)
    await database.execute(query)
    
    return {"message": "Scan deleted"}

class DeleteByLocalImageIdsRequest(BaseModel):
    local_image_ids: list[str]

@api_router.post("/scans/delete-by-local-ids")
async def delete_scans_by_local_image_ids(
    request: DeleteByLocalImageIdsRequest, 
    user: dict = Depends(get_current_user)
):
    """
    Delete all scans matching the provided local_image_ids for the current user.
    Used when user clears local image storage.
    """
    if not request.local_image_ids:
        return {"deleted_count": 0, "message": "No local image IDs provided"}
    
    # Find all scans with matching local_image_ids for this user
    query = scans_table.select().where(
        (scans_table.c.user_id == user["id"]) & 
        (scans_table.c.local_image_id.in_(request.local_image_ids))
    )
    scans_to_delete = await database.fetch_all(query)
    
    if not scans_to_delete:
        return {"deleted_count": 0, "message": "No matching scans found"}
    
    # Delete images from R2 cloud storage
    if R2_ENABLED:
        for scan in scans_to_delete:
            try:
                delete_scan_image(scan["id"])
            except Exception as e:
                logger.warning(f"Failed to delete R2 image for scan {scan['id']}: {e}")
    
    # Delete all matching scans
    delete_query = scans_table.delete().where(
        (scans_table.c.user_id == user["id"]) & 
        (scans_table.c.local_image_id.in_(request.local_image_ids))
    )
    await database.execute(delete_query)
    
    deleted_count = len(scans_to_delete)
    logger.info(f"Deleted {deleted_count} scans for user {user['id']} by local_image_ids")
    
    return {"deleted_count": deleted_count, "message": f"Deleted {deleted_count} scan(s)"}

@api_router.delete("/scans/all")
async def delete_all_scans(user: dict = Depends(get_current_user)):
    """
    Delete ALL scans for the current user.
    Used when user wants to clear all scan history.
    """
    # Count scans before deletion
    count_query = scans_table.select().where(scans_table.c.user_id == user["id"])
    scans_to_delete = await database.fetch_all(count_query)
    
    if not scans_to_delete:
        return {"deleted_count": 0, "message": "No scans to delete"}
    
    # Delete images from R2 cloud storage
    if R2_ENABLED:
        for scan in scans_to_delete:
            try:
                delete_scan_image(scan["id"])
            except Exception as e:
                logger.warning(f"Failed to delete R2 image for scan {scan['id']}: {e}")
    
    # Delete all scans for this user
    delete_query = scans_table.delete().where(scans_table.c.user_id == user["id"])
    await database.execute(delete_query)
    
    deleted_count = len(scans_to_delete)
    logger.info(f"Deleted ALL {deleted_count} scans for user {user['id']}")
    
    return {"deleted_count": deleted_count, "message": f"Deleted all {deleted_count} scan(s)"}

# ============ LEARN CONTENT ============

@api_router.get("/learn/content")
async def get_learn_content():
    return {
        "age_classes": [
            {"id": "1", "name": "Fawn", "age_range": "0-1", "description": "Young deer"},
            {"id": "2", "name": "Yearling", "age_range": "1-2", "description": "Adolescent deer"},
            {"id": "3", "name": "Adult", "age_range": "2.5-3.5", "description": "Young adult"},
            {"id": "4", "name": "Mature", "age_range": "4.5-5.5", "description": "Prime buck"},
            {"id": "5", "name": "Post-Mature", "age_range": "6+", "description": "Trophy class"},
        ],
        "aging_tips": [
            {"id": "1", "title": "Body Structure", "content": "Look at body mass relative to legs"},
            {"id": "2", "title": "Neck Size", "content": "Older bucks have thicker necks"},
            {"id": "3", "title": "Antler Mass", "content": "Mass increases with age"},
        ]
    }

# ============ APP VERSION CHECK ============

# Version configuration - Update these values when releasing new versions
# This can also be moved to environment variables or database for dynamic updates
APP_VERSION_CONFIG = {
    "ios": {
        "latest_version": "1.0.0",
        "min_supported_version": "1.0.0",
        "store_url": "https://apps.apple.com/app/iron-stag/id6757864977"
    },
    "android": {
        "latest_version": "1.0.0",
        "min_supported_version": "1.0.0",
        "store_url": "https://play.google.com/store/apps/details?id=io.asgardsolution.ironstag"
    },
    # Global settings
    "update_mode": "none",  # 'none', 'soft', 'force' - Override for all platforms
    "release_notes": None,  # Optional release notes to show users
    "force_update_message": "A critical update is required to continue using Iron Stag. Please update now for the best experience.",
    "soft_update_message": "A new version of Iron Stag is available with improvements and bug fixes."
}

def compare_versions(current: str, target: str) -> int:
    """
    Compare two semantic version strings.
    Returns: -1 if current < target, 0 if equal, 1 if current > target
    """
    def parse_version(v: str) -> tuple:
        # Handle versions like "1.0.0" or "1.0.0-beta.1"
        parts = v.split('-')[0].split('.')
        return tuple(int(p) for p in parts)
    
    try:
        current_parts = parse_version(current)
        target_parts = parse_version(target)
        
        # Pad with zeros if needed
        max_len = max(len(current_parts), len(target_parts))
        current_parts = current_parts + (0,) * (max_len - len(current_parts))
        target_parts = target_parts + (0,) * (max_len - len(target_parts))
        
        for c, t in zip(current_parts, target_parts):
            if c < t:
                return -1
            elif c > t:
                return 1
        return 0
    except Exception:
        return 0  # If parsing fails, assume versions are equal

@api_router.post("/app/version-check", response_model=VersionCheckResponse)
async def check_app_version(request: VersionCheckRequest):
    """
    Check if the app needs to be updated.
    
    Returns update_mode:
    - 'none': App is up to date
    - 'soft': Update available but optional
    - 'force': Update required (current version below minimum supported)
    
    Logic:
    1. If current < min_supported → force update
    2. If current < latest → soft update (unless global update_mode is 'force')
    3. Otherwise → no update needed
    """
    platform = request.platform.lower()
    current_version = request.current_version
    
    # Get platform-specific config
    if platform not in ['ios', 'android']:
        raise HTTPException(status_code=400, detail="Invalid platform. Use 'ios' or 'android'")
    
    platform_config = APP_VERSION_CONFIG.get(platform, {})
    latest_version = platform_config.get("latest_version", "1.0.0")
    min_supported_version = platform_config.get("min_supported_version", "1.0.0")
    store_url = platform_config.get("store_url", "")
    
    global_update_mode = APP_VERSION_CONFIG.get("update_mode", "none")
    release_notes = APP_VERSION_CONFIG.get("release_notes")
    
    # Determine update status
    is_below_minimum = compare_versions(current_version, min_supported_version) < 0
    is_below_latest = compare_versions(current_version, latest_version) < 0
    
    # Determine update_mode
    if is_below_minimum:
        # Force update - version is too old
        update_mode = "force"
        message = APP_VERSION_CONFIG.get("force_update_message")
        update_available = True
    elif is_below_latest:
        # Update available - use global setting or default to soft
        update_mode = global_update_mode if global_update_mode != "none" else "soft"
        message = APP_VERSION_CONFIG.get("soft_update_message")
        update_available = True
    else:
        # Up to date
        update_mode = "none"
        message = None
        update_available = False
    
    logger.info(f"Version check: platform={platform}, current={current_version}, "
                f"latest={latest_version}, min={min_supported_version}, mode={update_mode}")
    
    return VersionCheckResponse(
        update_available=update_available,
        update_mode=update_mode,
        latest_version=latest_version,
        min_supported_version=min_supported_version,
        release_notes=release_notes,
        store_url=store_url,
        message=message
    )

@api_router.get("/app/version-config")
async def get_version_config():
    """
    Get current version configuration (for admin/debugging).
    """
    return APP_VERSION_CONFIG

# ============ CALIBRATION ADMIN ENDPOINTS ============

@api_router.get("/admin/calibration-config")
async def get_calibration_config():
    """
    Get comprehensive region calibration configuration.
    Includes all feature flags, thresholds, and region settings.
    """
    return get_region_calibration_metadata()

@api_router.get("/admin/calibration/status")
async def get_calibration_status_endpoint():
    """
    Get calibration system status for diagnostics.
    Returns:
    - Active calibration version
    - Available strategies
    - Curve availability and maturity status
    - Feature flag states
    """
    status = get_calibration_status()
    await get_live_active_curves()
    status["curves"] = {
        **status.get("curves", {}),
        **get_live_curve_cache_metadata(),
    }
    return status

@api_router.get("/admin/calibration/regions")
async def get_calibration_regions():
    """
    Get all configured regions with their settings.
    Includes:
    - Region keys
    - Difficulty multipliers
    - Uncertainty thresholds
    - State mappings
    """
    return get_all_regions()

# ============ PHASE 2: EMPIRICAL CALIBRATION ADMIN ENDPOINTS ============

class BuildCurvesRequest(BaseModel):
    dry_run: bool = True  # Default to dry run for safety

class ActivateCurveRequest(BaseModel):
    curve_id: str
    deactivate_others: bool = True  # Deactivate other curves of same type/region

class RecalibrateScansRequest(BaseModel):
    dry_run: bool = True  # Default to dry run for safety
    curve_version: Optional[str] = None  # Optional specific version
    since: Optional[datetime] = None  # Only scans after this date
    region: Optional[str] = None  # Only scans in this region

@api_router.get("/admin/calibration/curves")
async def get_calibration_curves():
    """
    Get summary of all calibration curves.
    Returns:
    - Total curves count
    - Active curves count
    - Mature curves count
    - List of all curves with their status
    """
    try:
        return await get_curves_summary(database, calibration_curves_table)
    except Exception as e:
        logger.error(f"Error fetching curves summary: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@api_router.get("/admin/calibration/curves/{curve_id}")
async def get_calibration_curve_details(curve_id: str):
    """
    Get detailed information about a specific curve.
    Includes:
    - All bin data
    - Sample counts
    - Maturity status
    """
    try:
        curve = await get_curve_details(database, calibration_curves_table, curve_id)
        if not curve:
            raise HTTPException(status_code=404, detail="Curve not found")
        return curve
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching curve details: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@api_router.get("/admin/calibration/jobs/status")
async def get_calibration_jobs_status():
    """
    Get status of calibration jobs.
    Returns:
    - Whether build_curves job is running
    - Whether recalibrate_scans job is running
    - Current configuration
    """
    return get_job_status()

@api_router.post("/admin/calibration/build-curves")
async def build_calibration_curves(data: BuildCurvesRequest):
    """
    Build calibration curves from labeled scan data.
    
    This job:
    - Reads all scan_labels joined with scans
    - Groups by curve type and region
    - Computes empirical correctness per confidence bin
    - Creates new curves (inactive by default)
    
    Safety features:
    - dry_run mode (default) previews results without DB changes
    - Locking prevents concurrent builds
    - All new curves are inactive until explicitly activated
    """
    # Check feature flag
    if not CalibrationJobConfig.CALIBRATION_CURVES_ENABLED:
        raise HTTPException(
            status_code=400, 
            detail="Empirical calibration curves are not enabled. Set CALIBRATION_CURVES_ENABLED=true to enable."
        )
    
    # Acquire job lock
    if not acquire_job_lock("build_curves"):
        raise HTTPException(
            status_code=409,
            detail="A curve build job is already running. Please wait for it to complete."
        )
    
    try:
        result = await build_curves_from_labels(
            database=database,
            scans_table=scans_table,
            scan_labels_table=scan_labels_table,
            calibration_curves_table=calibration_curves_table,
            dry_run=data.dry_run
        )
        
        return {
            "success": True,
            "dry_run": result.dry_run,
            "version": result.version,
            "curves_built": result.curves_built,
            "curves_mature": result.curves_mature,
            "curves_immature": result.curves_immature,
            "total_labels_processed": result.total_labels_processed,
            "regions_processed": result.regions_processed,
            "duration_seconds": result.duration_seconds,
            "errors": result.errors,
            "message": "Dry run completed - no changes saved" if result.dry_run else f"Built {result.curves_built} curves"
        }
    finally:
        release_job_lock("build_curves")

@api_router.post("/admin/calibration/activate-curve")
async def activate_calibration_curve(data: ActivateCurveRequest):
    """
    Activate a calibration curve.
    
    This makes the curve available for use in the calibration fallback chain.
    
    Safety features:
    - Only mature curves can be activated
    - Optionally deactivates other curves of the same type/region
    """
    # Check feature flag
    if not CalibrationJobConfig.CALIBRATION_CURVES_ENABLED:
        raise HTTPException(
            status_code=400,
            detail="Empirical calibration curves are not enabled. Set CALIBRATION_CURVES_ENABLED=true to enable."
        )
    
    try:
        result = await activate_curve(
            database=database,
            calibration_curves_table=calibration_curves_table,
            curve_id=data.curve_id,
            deactivate_others=data.deactivate_others
        )
        
        if not result["success"]:
            raise HTTPException(status_code=400, detail=result.get("error", "Activation failed"))

        await get_live_active_curves(force_refresh=True)
        
        return result
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error activating curve: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@api_router.post("/admin/calibration/deactivate-curve/{curve_id}")
async def deactivate_calibration_curve(curve_id: str):
    """
    Deactivate a calibration curve.
    
    The curve remains in the database but is no longer used for calibration.
    """
    try:
        result = await deactivate_curve(
            database=database,
            calibration_curves_table=calibration_curves_table,
            curve_id=curve_id
        )
        await get_live_active_curves(force_refresh=True)
        return result
    except Exception as e:
        logger.error(f"Error deactivating curve: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@api_router.post("/admin/calibration/recalibrate-scans")
async def recalibrate_scans_endpoint(data: RecalibrateScansRequest):
    """
    Recalibrate existing scans using active curves.
    
    This job:
    - Does NOT re-run ML inference
    - Only recomputes calibrated confidence values
    - Updates calibration metadata
    
    Safety features:
    - dry_run mode (default) previews results without DB changes
    - Locking prevents concurrent recalibration
    - Batch processing with safety limits
    
    Filters:
    - curve_version: Use specific curve version (default: active curves)
    - since: Only process scans created after this date
    - region: Only process scans in this region
    """
    # Check feature flag
    if not CalibrationJobConfig.CALIBRATION_CURVES_ENABLED:
        raise HTTPException(
            status_code=400,
            detail="Empirical calibration curves are not enabled. Set CALIBRATION_CURVES_ENABLED=true to enable."
        )
    
    # Acquire job lock
    if not acquire_job_lock("recalibrate_scans"):
        raise HTTPException(
            status_code=409,
            detail="A recalibration job is already running. Please wait for it to complete."
        )
    
    try:
        result = await recalibrate_scans(
            database=database,
            scans_table=scans_table,
            calibration_curves_table=calibration_curves_table,
            curve_version=data.curve_version,
            since=data.since,
            region=data.region,
            dry_run=data.dry_run
        )
        
        return {
            "success": True,
            "dry_run": result.dry_run,
            "curve_version": result.curve_version,
            "scans_processed": result.scans_processed,
            "scans_updated": result.scans_updated,
            "scans_skipped": result.scans_skipped,
            "duration_seconds": result.duration_seconds,
            "errors": result.errors,
            "message": "Dry run completed - no changes saved" if result.dry_run else f"Recalibrated {result.scans_updated} scans"
        }
    finally:
        release_job_lock("recalibrate_scans")

# ============ PHASE 3: ADAPTIVE CALIBRATION ADMIN ENDPOINTS ============

class RunDriftRequest(BaseModel):
    dry_run: bool = True
    time_window_days: int = 30
    include_seasons: bool = True

class RunMaturityRequest(BaseModel):
    dry_run: bool = True

class RunRecommendationsRequest(BaseModel):
    dry_run: bool = True


@api_router.get("/admin/calibration/phase3/status")
async def get_phase3_calibration_status():
    """
    Get Phase 3 (Adaptive Calibration) system status.
    Returns:
    - Whether adaptive calibration is enabled
    - Job running states
    - Configuration values
    """
    return get_phase3_status()


@api_router.get("/admin/calibration/drift")
async def get_calibration_drift(days: int = 30):
    """
    Get summary of drift events.
    
    Returns recent drift events with statistics grouped by severity and region.
    
    NOTE: Returns 400 if CALIBRATION_ADAPTIVE_ENABLED=false
    """
    if not AdaptiveCalibrationConfig.is_enabled():
        raise HTTPException(
            status_code=400,
            detail="Adaptive calibration is not enabled. Set CALIBRATION_ADAPTIVE_ENABLED=true to enable."
        )
    
    try:
        return await get_drift_summary(database, calibration_drift_events_table, days)
    except Exception as e:
        logger.error(f"Error getting drift summary: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@api_router.get("/admin/calibration/maturity")
async def get_calibration_maturity():
    """
    Get region maturity summary.
    
    Returns maturity levels for all regions with labeled data.
    
    NOTE: Returns 400 if CALIBRATION_ADAPTIVE_ENABLED=false
    """
    if not AdaptiveCalibrationConfig.is_enabled():
        raise HTTPException(
            status_code=400,
            detail="Adaptive calibration is not enabled. Set CALIBRATION_ADAPTIVE_ENABLED=true to enable."
        )
    
    try:
        return await get_maturity_summary(database, region_maturity_table)
    except Exception as e:
        logger.error(f"Error getting maturity summary: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@api_router.get("/admin/calibration/recommendations")
async def get_calibration_recommendations(days: int = 30):
    """
    Get model action recommendations.
    
    Returns advisory recommendations based on drift patterns.
    
    NOTE: Returns 400 if CALIBRATION_ADAPTIVE_ENABLED=false
    """
    if not AdaptiveCalibrationConfig.is_enabled():
        raise HTTPException(
            status_code=400,
            detail="Adaptive calibration is not enabled. Set CALIBRATION_ADAPTIVE_ENABLED=true to enable."
        )
    
    try:
        return await get_recommendations_summary(database, model_action_recommendations_table, days)
    except Exception as e:
        logger.error(f"Error getting recommendations: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@api_router.post("/admin/calibration/phase3/run-drift")
async def run_drift_detection(data: RunDriftRequest):
    """
    Manually trigger drift detection job.
    
    Detects confidence drift by comparing expected vs observed accuracy.
    
    ADVISORY ONLY - Does not modify calibration behavior.
    
    Safety features:
    - dry_run mode (default) previews results without DB changes
    - Locking prevents concurrent runs
    - Feature flag must be enabled
    """
    if not AdaptiveCalibrationConfig.is_enabled():
        raise HTTPException(
            status_code=400,
            detail="Adaptive calibration is not enabled. Set CALIBRATION_ADAPTIVE_ENABLED=true to enable."
        )
    
    if not acquire_phase3_lock("drift_detection"):
        raise HTTPException(
            status_code=409,
            detail="A drift detection job is already running. Please wait for it to complete."
        )
    
    try:
        result = await detect_calibration_drift(
            database=database,
            scans_table=scans_table,
            scan_labels_table=scan_labels_table,
            calibration_curves_table=calibration_curves_table,
            drift_events_table=calibration_drift_events_table,
            time_window_days=data.time_window_days,
            include_seasons=data.include_seasons,
            dry_run=data.dry_run
        )
        
        return {
            "success": True,
            "dry_run": result.dry_run,
            "events_detected": result.events_detected,
            "warnings": result.warnings,
            "criticals": result.criticals,
            "regions_analyzed": result.regions_analyzed,
            "time_windows_used": result.time_windows_used,
            "duration_seconds": result.duration_seconds,
            "errors": result.errors,
            "message": "Dry run completed - no changes saved" if result.dry_run else f"Detected {result.events_detected} drift events"
        }
    finally:
        release_phase3_lock("drift_detection")


@api_router.post("/admin/calibration/phase3/run-maturity")
async def run_maturity_computation(data: RunMaturityRequest):
    """
    Manually trigger region maturity computation job.
    
    Computes data maturity scores for all regions based on:
    - Labeled sample count
    - Label source diversity
    - Drift stability over time
    
    ADVISORY ONLY - Does not affect calibration behavior.
    
    Safety features:
    - dry_run mode (default) previews results without DB changes
    - Locking prevents concurrent runs
    - Feature flag must be enabled
    """
    if not AdaptiveCalibrationConfig.is_enabled():
        raise HTTPException(
            status_code=400,
            detail="Adaptive calibration is not enabled. Set CALIBRATION_ADAPTIVE_ENABLED=true to enable."
        )
    
    if not acquire_phase3_lock("maturity_computation"):
        raise HTTPException(
            status_code=409,
            detail="A maturity computation job is already running. Please wait for it to complete."
        )
    
    try:
        result = await compute_region_maturity(
            database=database,
            scans_table=scans_table,
            scan_labels_table=scan_labels_table,
            drift_events_table=calibration_drift_events_table,
            region_maturity_table=region_maturity_table,
            dry_run=data.dry_run
        )
        
        return {
            "success": True,
            "dry_run": result.dry_run,
            "regions_computed": result.regions_computed,
            "low_maturity": result.low_maturity,
            "medium_maturity": result.medium_maturity,
            "high_maturity": result.high_maturity,
            "duration_seconds": result.duration_seconds,
            "errors": result.errors,
            "message": "Dry run completed - no changes saved" if result.dry_run else f"Computed maturity for {result.regions_computed} regions"
        }
    finally:
        release_phase3_lock("maturity_computation")


@api_router.post("/admin/calibration/phase3/run-recommendations")
async def run_recommendations_generation(data: RunRecommendationsRequest):
    """
    Manually trigger model recommendations generation job.
    
    Generates advisory recommendations based on drift patterns:
    - rebuild_calibration: Drift high, accuracy stable
    - consider_retraining: Accuracy declining
    - investigate_data: Both drifting
    - region_curve_update: Region-specific drift
    
    ADVISORY ONLY - Does not take any automatic action.
    
    Safety features:
    - dry_run mode (default) previews results without DB changes
    - Locking prevents concurrent runs
    - Feature flag must be enabled
    """
    if not AdaptiveCalibrationConfig.is_enabled():
        raise HTTPException(
            status_code=400,
            detail="Adaptive calibration is not enabled. Set CALIBRATION_ADAPTIVE_ENABLED=true to enable."
        )
    
    if not acquire_phase3_lock("recommendation_generation"):
        raise HTTPException(
            status_code=409,
            detail="A recommendation generation job is already running. Please wait for it to complete."
        )
    
    try:
        result = await generate_model_recommendations(
            database=database,
            drift_events_table=calibration_drift_events_table,
            region_maturity_table=region_maturity_table,
            recommendations_table=model_action_recommendations_table,
            dry_run=data.dry_run
        )
        
        return {
            "success": True,
            "dry_run": result.dry_run,
            "recommendations_generated": result.recommendations_generated,
            "by_type": result.by_type,
            "duration_seconds": result.duration_seconds,
            "errors": result.errors,
            "message": "Dry run completed - no changes saved" if result.dry_run else f"Generated {result.recommendations_generated} recommendations"
        }
    finally:
        release_phase3_lock("recommendation_generation")

# ============ HEALTH CHECK ============

@app.get("/health")
async def root_health():
    return {
        "status": "ok",
        "service": "iron-stag-api",
        "timestamp": datetime.utcnow().isoformat()
    }

# ============ TEST/ADMIN ENDPOINTS ============

@api_router.post("/admin/upgrade-user")
async def admin_upgrade_user(user: dict = Depends(get_current_user)):
    """Temporary endpoint to upgrade current user to premium for testing"""
    query = users_table.update().where(
        users_table.c.id == user["id"]
    ).values(subscription_tier="master_stag", scans_remaining=-1)
    await database.execute(query)
    return {"status": "upgraded", "tier": "master_stag"}


# ============ DEBUG/CRASH REPORTING ENDPOINTS ============

# Environment variable to control debug mode (default: disabled)
DEBUG_MODE_ENABLED = os.getenv("DEBUG_MODE_ENABLED", "false").lower() == "true"

class CrashReportRequest(BaseModel):
    id: str
    timestamp: str
    error_message: str
    error_stack: Optional[str] = None
    component_stack: Optional[str] = None
    screen: Optional[str] = None
    user_id: Optional[str] = None
    platform: str
    app_version: str
    build_number: str
    device_info: dict = {}
    extra_data: dict = {}

class BreadcrumbRequest(BaseModel):
    timestamp: str
    message: str
    screen: Optional[str] = None
    user_id: Optional[str] = None
    platform: str
    app_version: str
    data: dict = {}

@api_router.get("/debug/status")
async def get_debug_status():
    """Get debug mode status - controls whether crash reporting is enabled"""
    return {
        "debug_enabled": DEBUG_MODE_ENABLED,
        "environment": os.getenv("ENVIRONMENT", "development"),
    }

@api_router.post("/debug/crash-report")
async def submit_crash_report(report: CrashReportRequest):
    """
    Receive and store crash reports from mobile apps.
    Only processes reports if DEBUG_MODE_ENABLED is true.
    """
    if not DEBUG_MODE_ENABLED:
        return {"status": "ignored", "message": "Debug mode disabled"}
    
    try:
        # Create crash_reports table if it doesn't exist
        create_query = """
        CREATE TABLE IF NOT EXISTS crash_reports (
            id TEXT PRIMARY KEY,
            timestamp TIMESTAMP NOT NULL,
            error_message TEXT NOT NULL,
            error_stack TEXT,
            component_stack TEXT,
            screen TEXT,
            user_id TEXT,
            platform TEXT NOT NULL,
            app_version TEXT NOT NULL,
            build_number TEXT,
            device_info JSONB,
            extra_data JSONB,
            created_at TIMESTAMP DEFAULT NOW()
        )
        """
        await database.execute(create_query)
        
        # Insert crash report
        insert_query = """
        INSERT INTO crash_reports (
            id, timestamp, error_message, error_stack, component_stack,
            screen, user_id, platform, app_version, build_number,
            device_info, extra_data
        ) VALUES (
            :id, :timestamp, :error_message, :error_stack, :component_stack,
            :screen, :user_id, :platform, :app_version, :build_number,
            :device_info, :extra_data
        )
        ON CONFLICT (id) DO NOTHING
        """
        await database.execute(insert_query, {
            "id": report.id,
            "timestamp": report.timestamp,
            "error_message": report.error_message,
            "error_stack": report.error_stack,
            "component_stack": report.component_stack,
            "screen": report.screen,
            "user_id": report.user_id,
            "platform": report.platform,
            "app_version": report.app_version,
            "build_number": report.build_number,
            "device_info": json.dumps(report.device_info),
            "extra_data": json.dumps(report.extra_data),
        })
        
        logger.warning(f"[CrashReport] {report.platform}/{report.app_version} - {report.error_message[:100]}")
        
        return {"status": "received", "id": report.id}
    except Exception as e:
        logger.error(f"Failed to store crash report: {e}")
        return {"status": "error", "message": str(e)}

@api_router.post("/debug/breadcrumb")
async def submit_breadcrumb(breadcrumb: BreadcrumbRequest):
    """
    Receive breadcrumb/event data for debugging.
    Only processes if DEBUG_MODE_ENABLED is true.
    """
    if not DEBUG_MODE_ENABLED:
        return {"status": "ignored"}
    
    try:
        # Create breadcrumbs table if it doesn't exist
        create_query = """
        CREATE TABLE IF NOT EXISTS debug_breadcrumbs (
            id SERIAL PRIMARY KEY,
            timestamp TIMESTAMP NOT NULL,
            message TEXT NOT NULL,
            screen TEXT,
            user_id TEXT,
            platform TEXT NOT NULL,
            app_version TEXT NOT NULL,
            data JSONB,
            created_at TIMESTAMP DEFAULT NOW()
        )
        """
        await database.execute(create_query)
        
        # Insert breadcrumb
        insert_query = """
        INSERT INTO debug_breadcrumbs (
            timestamp, message, screen, user_id, platform, app_version, data
        ) VALUES (
            :timestamp, :message, :screen, :user_id, :platform, :app_version, :data
        )
        """
        await database.execute(insert_query, {
            "timestamp": breadcrumb.timestamp,
            "message": breadcrumb.message,
            "screen": breadcrumb.screen,
            "user_id": breadcrumb.user_id,
            "platform": breadcrumb.platform,
            "app_version": breadcrumb.app_version,
            "data": json.dumps(breadcrumb.data),
        })
        
        return {"status": "received"}
    except Exception as e:
        logger.error(f"Failed to store breadcrumb: {e}")
        return {"status": "error"}

@api_router.get("/debug/crash-reports")
async def get_crash_reports(
    limit: int = 50,
    platform: Optional[str] = None,
    app_version: Optional[str] = None
):
    """
    Get recent crash reports (admin only).
    """
    if not DEBUG_MODE_ENABLED:
        return {"reports": [], "message": "Debug mode disabled"}
    
    try:
        query = "SELECT * FROM crash_reports WHERE 1=1"
        params = {}
        
        if platform:
            query += " AND platform = :platform"
            params["platform"] = platform
        
        if app_version:
            query += " AND app_version = :app_version"
            params["app_version"] = app_version
        
        query += " ORDER BY timestamp DESC LIMIT :limit"
        params["limit"] = limit
        
        reports = await database.fetch_all(query, params)
        
        return {
            "reports": [dict(r) for r in reports],
            "count": len(reports),
        }
    except Exception as e:
        return {"reports": [], "error": str(e)}

@api_router.post("/debug/enable")
async def enable_debug_mode(secret: str):
    """
    Enable debug mode (requires admin secret).
    In production, this would update a config in the database.
    """
    admin_secret = os.getenv("ADMIN_SECRET", "iron_stag_debug_2024")
    if secret != admin_secret:
        raise HTTPException(status_code=403, detail="Invalid secret")
    
    # In a real implementation, this would update a database flag
    # For now, we just return the current status
    return {
        "status": "Debug mode controlled via DEBUG_MODE_ENABLED env var",
        "current_status": DEBUG_MODE_ENABLED,
        "message": "Set DEBUG_MODE_ENABLED=true in .env to enable"
    }
    

# Include router
app.include_router(api_router)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

if __name__ == "__main__":
    import os
    import uvicorn

    port = int(os.environ.get("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
