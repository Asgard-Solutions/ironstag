from fastapi import FastAPI, APIRouter, HTTPException, Depends, Header, UploadFile, File
from dotenv import load_dotenv
from starlette.middleware.cors import CORSMiddleware
import os
import logging
from pathlib import Path
from pydantic import BaseModel, Field, EmailStr
from typing import List, Optional, Dict, Any
import uuid
from datetime import datetime, timedelta
import jwt
from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError
import openai
import stripe
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
    RegionCalibrationConfig
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
    Column("deer_age", Float),
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
)

# Scan labels table for future empirical calibration (Phase 2)
scan_labels_table = Table(
    "scan_labels",
    metadata,
    Column("id", String(36), primary_key=True),
    Column("scan_id", String(36), nullable=False),
    Column("label_source", String(50)),  # expert, user_self_report, admin_review
    Column("true_age_bucket", String(20)),  # Age range bucket
    Column("age_correct", Boolean),  # Was age estimation correct
    Column("recommendation_correct", Boolean),  # Was recommendation correct
    Column("created_at", DateTime, default=datetime.utcnow),
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
STRIPE_SECRET_KEY = os.environ.get('STRIPE_SECRET_KEY', '')
STRIPE_WEBHOOK_SECRET = os.environ.get('STRIPE_WEBHOOK_SECRET', '')
REVENUECAT_SECRET_KEY = os.environ.get('REVENUECAT_SECRET_KEY', '')
JWT_SECRET = os.environ.get('JWT_SECRET', 'iron-stag-secret-key-2025')
JWT_ALGORITHM = 'HS256'

# Microsoft Graph Configuration
MS_GRAPH_CLIENT_ID = os.environ.get('MICROSOFT_GRAPH_CLIENT_ID', '')
MS_GRAPH_CLIENT_SECRET = os.environ.get('MICROSOFT_GRAPH_CLIENT_SECRET', '')
MS_GRAPH_TENANT_ID = os.environ.get('MICROSOFT_GRAPH_TENANT_ID', '')
MS_GRAPH_SENDER_EMAIL = os.environ.get('MS_GRAPH_SENDER_EMAIL', 'support@asgardsolution.io')

# Initialize clients
openai_client = openai.OpenAI(api_key=OPENAI_API_KEY)
stripe.api_key = STRIPE_SECRET_KEY

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

class TokenResponse(BaseModel):
    access_token: str
    user: UserResponse

class ProfileUpdate(BaseModel):
    name: Optional[str] = None
    username: Optional[str] = None
    email: Optional[str] = None
    current_password: Optional[str] = None
    new_password: Optional[str] = None

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

class ScanUpdate(BaseModel):
    notes: Optional[str] = None

class ScanEditRequest(BaseModel):
    """Request model for editing scan details and re-analyzing with LLM"""
    deer_sex: Optional[str] = None
    deer_type: Optional[str] = None
    antler_points_left: Optional[int] = None
    antler_points_right: Optional[int] = None
    image_base64: Optional[str] = None  # Required if re-analyzing with LLM

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
        
        # Create indexes for region calibration queries
        await database.execute("CREATE INDEX IF NOT EXISTS idx_scans_region_key ON scans(region_key)")
        await database.execute("CREATE INDEX IF NOT EXISTS idx_scans_calibration_version ON scans(calibration_version)")
        await database.execute("CREATE INDEX IF NOT EXISTS idx_scans_age_uncertain ON scans(age_uncertain)")
        
        logger.info("Database migrations completed")
    except Exception as e:
        logger.warning(f"Migration note: {e}")
    
    logger.info("Database connected and tables created")

@app.on_event("shutdown")
async def shutdown():
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
    
    return DeerAnalysisResponse(
        id=scan["id"],
        user_id=scan["user_id"],
        local_image_id=scan["local_image_id"],
        deer_age=scan["deer_age"],
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
        calibration_fallback_reason=calibration_fallback_reason
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
            disclaimer_accepted=False
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
            disclaimer_accepted_at=user.get("disclaimer_accepted_at")
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
                disclaimer_accepted_at=user.get("disclaimer_accepted_at")
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
                    disclaimer_accepted_at=existing_user.get("disclaimer_accepted_at")
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
            disclaimer_accepted_at=None
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
        disclaimer_accepted_at=user.get("disclaimer_accepted_at")
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
        disclaimer_accepted_at=user.get("disclaimer_accepted_at")
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
        disclaimer_accepted_at=user.get("disclaimer_accepted_at")
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

@api_router.post("/subscription/create-checkout")
async def create_checkout_session(data: CheckoutRequest, user: dict = Depends(get_current_user)):
    try:
        if not user.get("stripe_customer_id"):
            customer = stripe.Customer.create(
                email=user["email"],
                name=user["name"],
                metadata={"user_id": user["id"]}
            )
            query = users_table.update().where(
                users_table.c.id == user["id"]
            ).values(stripe_customer_id=customer.id)
            await database.execute(query)
            customer_id = customer.id
        else:
            customer_id = user["stripe_customer_id"]
        
        if data.plan == "annual":
            unit_amount = 8999
            interval = "year"
            plan_name = "Master Stag Annual"
            description = "Unlimited deer scans - Save $30/year!"
        else:
            unit_amount = 999
            interval = "month"
            plan_name = "Master Stag Monthly"
            description = "Unlimited deer scans with Iron Stag"
        
        session = stripe.checkout.Session.create(
            customer=customer_id,
            payment_method_types=["card"],
            line_items=[{
                "price_data": {
                    "currency": "usd",
                    "product_data": {"name": plan_name, "description": description},
                    "unit_amount": unit_amount,
                    "recurring": {"interval": interval}
                },
                "quantity": 1
            }],
            mode="subscription",
            success_url="ironstag://subscription/success",
            cancel_url="ironstag://subscription/cancel",
            metadata={"user_id": user["id"], "plan": data.plan}
        )
        
        return {"checkout_url": session.url, "session_id": session.id}
    except stripe.error.StripeError as e:
        logger.error(f"Stripe error: {e}")
        raise HTTPException(status_code=400, detail=str(e))

@api_router.post("/subscription/webhook")
async def stripe_webhook(request_body: bytes = Depends(lambda r: r.body())):
    try:
        event = stripe.Webhook.construct_event(
            request_body,
            request_body.headers.get("stripe-signature"),
            STRIPE_WEBHOOK_SECRET
        )
        
        if event["type"] == "checkout.session.completed":
            session = event["data"]["object"]
            user_id = session.get("metadata", {}).get("user_id")
            
            if user_id:
                query = users_table.update().where(
                    users_table.c.id == user_id
                ).values(
                    subscription_tier="master_stag",
                    stripe_subscription_id=session.get("subscription"),
                    scans_remaining=-1
                )
                await database.execute(query)
        
        elif event["type"] == "customer.subscription.deleted":
            subscription = event["data"]["object"]
            query = users_table.select().where(
                users_table.c.stripe_subscription_id == subscription["id"]
            )
            user = await database.fetch_one(query)
            
            if user:
                query = users_table.update().where(
                    users_table.c.id == user["id"]
                ).values(
                    subscription_tier="tracker",
                    stripe_subscription_id=None,
                    scans_remaining=3
                )
                await database.execute(query)
        
        return {"status": "success"}
    except Exception as e:
        logger.error(f"Webhook error: {e}")
        raise HTTPException(status_code=400, detail=str(e))

@api_router.post("/subscription/portal")
async def create_customer_portal(user: dict = Depends(get_current_user)):
    try:
        customer_id = user.get("stripe_customer_id")
        
        # If no customer ID, create one for premium users
        if not customer_id:
            if user.get("subscription_tier") != "master_stag":
                raise HTTPException(status_code=400, detail="No subscription found. Please upgrade first.")
            
            # Create Stripe customer for manually upgraded users
            customer = stripe.Customer.create(
                email=user["email"],
                name=user["name"],
                metadata={"user_id": user["id"]}
            )
            customer_id = customer.id
            
            # Save the customer ID
            query = users_table.update().where(
                users_table.c.id == user["id"]
            ).values(stripe_customer_id=customer_id)
            await database.execute(query)
        
        session = stripe.billing_portal.Session.create(
            customer=customer_id,
            return_url="ironstag://profile"
        )
        
        return {"portal_url": session.url}
    except stripe.error.StripeError as e:
        logger.error(f"Stripe portal error: {e}")
        raise HTTPException(status_code=400, detail=str(e))

@api_router.post("/subscription/cancel")
async def cancel_subscription(user: dict = Depends(get_current_user)):
    try:
        # Check if user is premium
        if user.get("subscription_tier") != "master_stag":
            raise HTTPException(status_code=400, detail="No active subscription to cancel")
        
        subscription_id = user.get("stripe_subscription_id")
        
        if subscription_id:
            # User has a real Stripe subscription - cancel it
            subscription = stripe.Subscription.modify(
                subscription_id,
                cancel_at_period_end=True
            )
            
            query = users_table.update().where(
                users_table.c.id == user["id"]
            ).values(subscription_cancel_at_period_end=True)
            await database.execute(query)
            
            return {
                "status": "canceled",
                "cancel_at": subscription.cancel_at,
                "current_period_end": subscription.current_period_end
            }
        else:
            # User was manually upgraded (no Stripe subscription) - downgrade immediately
            query = users_table.update().where(
                users_table.c.id == user["id"]
            ).values(
                subscription_tier="tracker",
                scans_remaining=0,  # They've used their free tier already
                subscription_cancel_at_period_end=False
            )
            await database.execute(query)
            
            return {
                "status": "canceled",
                "message": "Subscription canceled. You have been downgraded to Tracker tier."
            }
            
    except stripe.error.StripeError as e:
        logger.error(f"Stripe cancel error: {e}")
        raise HTTPException(status_code=400, detail=str(e))
    except stripe.error.StripeError as e:
        logger.error(f"Stripe cancel error: {e}")
        raise HTTPException(status_code=400, detail=str(e))

@api_router.post("/subscription/verify-revenuecat")
async def verify_revenuecat(user: dict = Depends(get_current_user)):
    return {"status": "not_implemented"}

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
        
        response = openai_client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {
                    "role": "system",
                    "content": """You are an expert wildlife biologist specializing in deer identification and aging.
                    
                    FIRST, determine what is in the image. Return ONLY valid JSON.
                    
                    If the image does NOT contain a deer (Whitetail or Mule Deer only), return:
                    {
                        "is_valid_deer": false,
                        "detected_subject": <string describing what you see - e.g., "Elk", "Moose", "Wild Hog", "Turkey", "Coyote", "Wolf", "Bobcat", "Bear", "Person", "Landscape", "Unknown Object", etc.>,
                        "message": <friendly message explaining this app is for Whitetail and Mule Deer only>
                    }
                    
                    Note: Elk and Moose are NOT deer for this app's purposes. Only Whitetail Deer and Mule Deer are valid.
                    
                    If the image DOES contain a valid deer (Whitetail or Mule Deer), return:
                    {
                        "is_valid_deer": true,
                        "deer_age": <number or null>,
                        "deer_type": <"Whitetail" or "Mule Deer">,
                        "deer_sex": <"Buck" or "Doe" or "Unknown">,
                        "antler_points": <total number or null>,
                        "antler_points_left": <number of points on left antler or null>,
                        "antler_points_right": <number of points on right antler or null>,
                        "body_condition": <string>,
                        "confidence": <number 1-100>,
                        "recommendation": <"HARVEST" or "PASS">,
                        "reasoning": <string>
                    }
                    For antler points, count tines on each side separately. Total should equal left + right."""
                },
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": "Analyze this image:"},
                        {"type": "image_url", "image_url": {"url": image_data}}
                    ]
                }
            ],
            max_tokens=1000
        )
        
        response_text = response.choices[0].message.content
        
        try:
            if "```json" in response_text:
                json_str = response_text.split("```json")[1].split("```")[0]
            elif "```" in response_text:
                json_str = response_text.split("```")[1].split("```")[0]
            else:
                json_str = response_text
            analysis = json.loads(json_str.strip())
        except json.JSONDecodeError:
            analysis = {
                "is_valid_deer": False,
                "detected_subject": "Unknown",
                "message": "Could not analyze the image. Please try again with a clearer photo."
            }
        
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
        # Get user's profile state for fallback
        user_profile_state = user.get("state")
        
        calibration_result, calibrated_analysis = calibrate_from_dict_with_region(
            analysis=analysis,
            state=data.state,  # From request
            user_profile_state=user_profile_state  # Fallback from user profile
        )
        
        scan_id = str(uuid.uuid4())
        
        query = scans_table.insert().values(
            id=scan_id,
            user_id=user["id"],
            local_image_id=data.local_image_id,
            deer_age=calibrated_analysis.get("deer_age"),  # May be null if age_uncertain
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
            created_at=datetime.utcnow(),
            # Calibration fields
            raw_confidence=calibrated_analysis.get("raw_confidence"),
            age_confidence=calibrated_analysis.get("age_confidence"),
            recommendation_confidence=calibrated_analysis.get("recommendation_confidence"),
            age_uncertain=calibrated_analysis.get("age_uncertain", False),
            calibration_version=calibrated_analysis.get("calibration_version"),
            # Region fields (always persist, feature-flag controls response visibility)
            region_key=calibrated_analysis.get("region_key"),
            region_source=calibrated_analysis.get("region_source"),
            region_state=calibrated_analysis.get("region_state"),
            calibration_strategy=calibrated_analysis.get("calibration_strategy"),
            calibration_fallback_reason=calibrated_analysis.get("calibration_fallback_reason")
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
            created_at=datetime.utcnow(),
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
            calibration_fallback_reason=calibrated_analysis.get("calibration_fallback_reason") if config.CALIBRATION_SHOW_STRATEGY else None
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
    
    if data.notes is not None:
        query = scans_table.update().where(
            scans_table.c.id == scan_id
        ).values(notes=data.notes)
        await database.execute(query)
    
    query = scans_table.select().where(scans_table.c.id == scan_id)
    scan = await database.fetch_one(query)
    
    return build_scan_response(dict(scan))

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
            image_data = data.image_base64
            if not image_data.startswith("data:"):
                image_data = f"data:image/jpeg;base64,{image_data}"
            
            # Build hint text from user corrections
            hints = []
            if data.deer_sex:
                hints.append(f"The deer is a {data.deer_sex}")
            if data.deer_type:
                hints.append(f"The deer type is {data.deer_type}")
            if data.antler_points_left is not None:
                hints.append(f"Left antler has {data.antler_points_left} points")
            if data.antler_points_right is not None:
                hints.append(f"Right antler has {data.antler_points_right} points")
            
            hint_text = ". ".join(hints) if hints else ""
            
            response = openai_client.chat.completions.create(
                model="gpt-4o",
                messages=[
                    {
                        "role": "system",
                        "content": """You are an expert wildlife biologist specializing in deer aging. 
                        Analyze the deer image and return ONLY valid JSON:
                        {
                            "deer_age": <number or null>,
                            "deer_type": <string like "Whitetail", "Mule Deer", "Elk", etc.>,
                            "deer_sex": <"Buck" or "Doe" or "Unknown">,
                            "antler_points": <total number or null>,
                            "antler_points_left": <number of points on left antler or null>,
                            "antler_points_right": <number of points on right antler or null>,
                            "body_condition": <string>,
                            "confidence": <number 1-100>,
                            "recommendation": <"HARVEST" or "PASS">,
                            "reasoning": <string>
                        }
                        The user has provided corrections - incorporate them into your analysis."""
                    },
                    {
                        "role": "user",
                        "content": [
                            {"type": "text", "text": f"Re-analyze this deer with these corrections: {hint_text}" if hint_text else "Analyze this deer:"},
                            {"type": "image_url", "image_url": {"url": image_data}}
                        ]
                    }
                ],
                max_tokens=1000
            )
            
            response_text = response.choices[0].message.content
            
            try:
                if "```json" in response_text:
                    json_str = response_text.split("```json")[1].split("```")[0]
                elif "```" in response_text:
                    json_str = response_text.split("```")[1].split("```")[0]
                else:
                    json_str = response_text
                analysis = json.loads(json_str.strip())
            except json.JSONDecodeError:
                analysis = None
            
            if analysis:
                # Override with user corrections where provided
                if data.deer_sex:
                    analysis["deer_sex"] = data.deer_sex
                if data.deer_type:
                    analysis["deer_type"] = data.deer_type
                if data.antler_points_left is not None:
                    analysis["antler_points_left"] = data.antler_points_left
                if data.antler_points_right is not None:
                    analysis["antler_points_right"] = data.antler_points_right
                if total_points is not None:
                    analysis["antler_points"] = total_points
                
                # Apply region-aware confidence calibration to re-analysis
                # Get existing scan's region state (preserve from original scan)
                existing_region_state = scan.get("region_state")
                user_profile_state = user.get("state")
                
                calibration_result, calibrated_analysis = calibrate_from_dict_with_region(
                    analysis=analysis,
                    state=existing_region_state,  # Preserve original region
                    user_profile_state=user_profile_state
                )
                
                # Update the scan with new calibrated analysis
                update_query = scans_table.update().where(
                    scans_table.c.id == scan_id
                ).values(
                    deer_age=calibrated_analysis.get("deer_age"),
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
                    age_confidence=calibrated_analysis.get("age_confidence"),
                    recommendation_confidence=calibrated_analysis.get("recommendation_confidence"),
                    age_uncertain=calibrated_analysis.get("age_uncertain", False),
                    calibration_version=calibrated_analysis.get("calibration_version"),
                    region_key=calibrated_analysis.get("region_key"),
                    region_source=calibrated_analysis.get("region_source"),
                    region_state=calibrated_analysis.get("region_state"),
                    calibration_strategy=calibrated_analysis.get("calibration_strategy"),
                    calibration_fallback_reason=calibrated_analysis.get("calibration_fallback_reason")
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
        if data.deer_type is not None:
            update_values["deer_type"] = data.deer_type
        if data.antler_points_left is not None:
            update_values["antler_points_left"] = data.antler_points_left
        if data.antler_points_right is not None:
            update_values["antler_points_right"] = data.antler_points_right
        if total_points is not None:
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
    return get_calibration_status()

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
