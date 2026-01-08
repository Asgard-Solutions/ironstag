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

ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / '.env')

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
    Column("body_condition", String(50)),
    Column("confidence", Integer),
    Column("recommendation", String(50)),
    Column("reasoning", Text),
    Column("notes", Text),
    Column("raw_response", JSON),
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
STRIPE_SECRET_KEY = os.environ.get('STRIPE_SECRET_KEY', '')
STRIPE_WEBHOOK_SECRET = os.environ.get('STRIPE_WEBHOOK_SECRET', '')
REVENUECAT_SECRET_KEY = os.environ.get('REVENUECAT_SECRET_KEY', '')
JWT_SECRET = os.environ.get('JWT_SECRET', 'iron-stag-secret-key-2025')
JWT_ALGORITHM = 'HS256'

# Microsoft Graph Configuration
MS_GRAPH_CLIENT_ID = os.environ.get('MICROSOFT_GRAPH_CLIENT_ID', '')
MS_GRAPH_CLIENT_SECRET = os.environ.get('MICROSOFT_GRAPH_CLIENT_SECRET', '')
MS_GRAPH_TENANT_ID = os.environ.get('MICROSOFT_GRAPH_TENANT_ID', '')
MS_GRAPH_SENDER_EMAIL = 'support@asgardsolution.io'

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

class DeerAnalysisResponse(BaseModel):
    id: str
    user_id: str
    local_image_id: str
    deer_age: Optional[float] = None
    deer_type: Optional[str] = None
    deer_sex: Optional[str] = None
    antler_points: Optional[int] = None
    body_condition: Optional[str] = None
    confidence: Optional[int] = None
    recommendation: Optional[str] = None
    reasoning: Optional[str] = None
    notes: Optional[str] = None
    created_at: datetime

class ScanUpdate(BaseModel):
    notes: Optional[str] = None

class PasswordResetRequest(BaseModel):
    email: EmailStr

class PasswordResetVerify(BaseModel):
    email: EmailStr
    code: str
    new_password: str

# ============ DATABASE INITIALIZATION ============

@app.on_event("startup")
async def startup():
    await database.connect()
    # Create tables if they don't exist
    engine = sqlalchemy.create_engine(DATABASE_URL.replace("postgresql://", "postgresql+psycopg2://") if "postgresql://" in DATABASE_URL else DATABASE_URL)
    metadata.create_all(engine)
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
            disclaimer_accepted=user.get("disclaimer_accepted", False)
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
                    "content": """You are an expert wildlife biologist specializing in deer aging. 
                    Analyze the deer image and return ONLY valid JSON:
                    {
                        "deer_age": <number or null>,
                        "deer_type": <string>,
                        "deer_sex": <string>,
                        "antler_points": <number or null>,
                        "body_condition": <string>,
                        "confidence": <number 1-100>,
                        "recommendation": <"HARVEST" or "PASS">,
                        "reasoning": <string>
                    }"""
                },
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": "Analyze this deer:"},
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
                "deer_age": None, "deer_type": "Unknown", "deer_sex": "Unknown",
                "antler_points": None, "body_condition": "Unknown",
                "confidence": 0, "recommendation": "PASS",
                "reasoning": f"Could not parse AI response: {response_text[:200]}"
            }
        
        scan_id = str(uuid.uuid4())
        
        query = scans_table.insert().values(
            id=scan_id,
            user_id=user["id"],
            local_image_id=data.local_image_id,
            deer_age=analysis.get("deer_age"),
            deer_type=analysis.get("deer_type"),
            deer_sex=analysis.get("deer_sex"),
            antler_points=analysis.get("antler_points"),
            body_condition=analysis.get("body_condition"),
            confidence=analysis.get("confidence"),
            recommendation=analysis.get("recommendation"),
            reasoning=analysis.get("reasoning"),
            notes=data.notes,
            raw_response=analysis,
            created_at=datetime.utcnow()
        )
        await database.execute(query)
        
        await use_scan(user)
        
        return DeerAnalysisResponse(
            id=scan_id,
            user_id=user["id"],
            local_image_id=data.local_image_id,
            deer_age=analysis.get("deer_age"),
            deer_type=analysis.get("deer_type"),
            deer_sex=analysis.get("deer_sex"),
            antler_points=analysis.get("antler_points"),
            body_condition=analysis.get("body_condition"),
            confidence=analysis.get("confidence"),
            recommendation=analysis.get("recommendation"),
            reasoning=analysis.get("reasoning"),
            notes=data.notes,
            created_at=datetime.utcnow()
        )
        
    except openai.OpenAIError as e:
        logger.error(f"OpenAI error: {e}")
        raise HTTPException(status_code=500, detail=f"AI analysis failed: {str(e)}")

# ============ SCANS ROUTES ============

@api_router.get("/scans", response_model=List[DeerAnalysisResponse])
async def get_user_scans(user: dict = Depends(get_current_user)):
    query = scans_table.select().where(
        scans_table.c.user_id == user["id"]
    ).order_by(scans_table.c.created_at.desc())
    scans = await database.fetch_all(query)
    
    return [DeerAnalysisResponse(
        id=s["id"],
        user_id=s["user_id"],
        local_image_id=s["local_image_id"],
        deer_age=s["deer_age"],
        deer_type=s["deer_type"],
        deer_sex=s["deer_sex"],
        antler_points=s["antler_points"],
        body_condition=s["body_condition"],
        confidence=s["confidence"],
        recommendation=s["recommendation"],
        reasoning=s["reasoning"],
        notes=s["notes"],
        created_at=s["created_at"]
    ) for s in scans]

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
    
    return DeerAnalysisResponse(
        id=scan["id"],
        user_id=scan["user_id"],
        local_image_id=scan["local_image_id"],
        deer_age=scan["deer_age"],
        deer_type=scan["deer_type"],
        deer_sex=scan["deer_sex"],
        antler_points=scan["antler_points"],
        body_condition=scan["body_condition"],
        confidence=scan["confidence"],
        recommendation=scan["recommendation"],
        reasoning=scan["reasoning"],
        notes=scan["notes"],
        created_at=scan["created_at"]
    )

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
    
    return DeerAnalysisResponse(
        id=scan["id"],
        user_id=scan["user_id"],
        local_image_id=scan["local_image_id"],
        deer_age=scan["deer_age"],
        deer_type=scan["deer_type"],
        deer_sex=scan["deer_sex"],
        antler_points=scan["antler_points"],
        body_condition=scan["body_condition"],
        confidence=scan["confidence"],
        recommendation=scan["recommendation"],
        reasoning=scan["reasoning"],
        notes=scan["notes"],
        created_at=scan["created_at"]
    )

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

# ============ HEALTH CHECK ============

@api_router.get("/health")
async def health_check():
    return {"status": "healthy", "database": "postgresql", "timestamp": datetime.utcnow().isoformat()}

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
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8001)
