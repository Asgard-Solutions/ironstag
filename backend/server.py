from fastapi import FastAPI, APIRouter, HTTPException, Depends, Header, UploadFile, File
from dotenv import load_dotenv
from starlette.middleware.cors import CORSMiddleware
from motor.motor_asyncio import AsyncIOMotorClient
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

ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / '.env')

# MongoDB connection
mongo_url = os.environ['MONGO_URL']
client = AsyncIOMotorClient(mongo_url)
db = client[os.environ.get('DB_NAME', 'iron_stag_db')]

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

# ============ MODELS ============

class UserCreate(BaseModel):
    email: EmailStr
    password: str
    name: str
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
    subscription_tier: str = "scout"
    scans_remaining: int = 3
    disclaimer_accepted: bool = False

class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserResponse

class PasswordResetRequest(BaseModel):
    email: EmailStr

class PasswordResetVerify(BaseModel):
    email: EmailStr
    code: str
    new_password: str

class DisclaimerAccept(BaseModel):
    accepted: bool

class ProfileUpdate(BaseModel):
    name: Optional[str] = None
    username: Optional[str] = None
    email: Optional[str] = None
    current_password: Optional[str] = None
    new_password: Optional[str] = None

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
    raw_response: Optional[Dict[str, Any]] = None
    created_at: datetime

class ScanUpdate(BaseModel):
    notes: Optional[str] = None

class SubscriptionStatus(BaseModel):
    tier: str
    scans_remaining: int
    is_premium: bool
    expires_at: Optional[datetime] = None

# ============ AUTH HELPERS ============

def create_token(user_id: str) -> str:
    payload = {
        "sub": user_id,
        "exp": datetime.utcnow() + timedelta(days=30),
        "iat": datetime.utcnow()
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
    
    token = authorization.split(" ")[1]
    user_id = verify_token(token)
    
    user = await db.users.find_one({"id": user_id})
    if not user:
        raise HTTPException(status_code=401, detail="User not found")
    
    return user

async def get_optional_user(authorization: str = Header(None)) -> Optional[dict]:
    if not authorization or not authorization.startswith("Bearer "):
        return None
    try:
        token = authorization.split(" ")[1]
        user_id = verify_token(token)
        user = await db.users.find_one({"id": user_id})
        return user
    except:
        return None

# ============ AUTH ROUTES ============

@api_router.post("/auth/register", response_model=TokenResponse)
async def register(data: UserCreate):
    # Check if user exists
    existing = await db.users.find_one({"email": data.email.lower()})
    if existing:
        raise HTTPException(status_code=400, detail="Email already registered")
    
    # Check if username is taken
    if data.username:
        existing_username = await db.users.find_one({"username": data.username.lower()})
        if existing_username:
            raise HTTPException(status_code=400, detail="Username already taken")
    
    # Create user
    user_id = str(uuid.uuid4())
    hashed_password = ph.hash(data.password)
    
    # Build name from first_name and last_name if provided
    name = data.name
    if data.first_name and data.last_name:
        name = f"{data.first_name} {data.last_name}"
    elif data.first_name:
        name = data.first_name
    
    user = {
        "id": user_id,
        "email": data.email.lower(),
        "password": hashed_password,
        "name": name,
        "first_name": data.first_name,
        "last_name": data.last_name,
        "username": data.username.lower() if data.username else None,
        "created_at": datetime.utcnow(),
        "subscription_tier": "scout",
        "scans_remaining": 3,
        "scans_reset_date": datetime.utcnow().date().isoformat(),
        "disclaimer_accepted": False,
        "stripe_customer_id": None,
        "revenuecat_id": None
    }
    
    await db.users.insert_one(user)
    
    token = create_token(user_id)
    
    return TokenResponse(
        access_token=token,
        user=UserResponse(
            id=user_id,
            email=user["email"],
            name=user["name"],
            username=user["username"],
            created_at=user["created_at"],
            subscription_tier=user["subscription_tier"],
            scans_remaining=user["scans_remaining"],
            disclaimer_accepted=user["disclaimer_accepted"]
        )
    )

@api_router.post("/auth/login", response_model=TokenResponse)
async def login(data: UserLogin):
    # Check if input is email or username
    identifier = data.email.lower().strip()
    
    # Try to find user by email first, then by username
    user = await db.users.find_one({"email": identifier})
    if not user:
        # Try finding by username (case-insensitive)
        user = await db.users.find_one({"username": {"$regex": f"^{identifier}$", "$options": "i"}})
    
    if not user:
        raise HTTPException(status_code=401, detail="Invalid credentials")
    
    try:
        ph.verify(user["password"], data.password)
    except VerifyMismatchError:
        raise HTTPException(status_code=401, detail="Invalid credentials")
    
    # Reset scans if new day
    user = await reset_daily_scans(user)
    
    token = create_token(user["id"])
    
    return TokenResponse(
        access_token=token,
        user=UserResponse(
            id=user["id"],
            email=user["email"],
            name=user["name"],
            username=user.get("username"),
            created_at=user["created_at"],
            subscription_tier=user.get("subscription_tier", "scout"),
            scans_remaining=user.get("scans_remaining", 3),
            disclaimer_accepted=user.get("disclaimer_accepted", False)
        )
    )

@api_router.post("/auth/password-reset/request")
async def request_password_reset(data: PasswordResetRequest):
    user = await db.users.find_one({"email": data.email.lower()})
    if not user:
        # Don't reveal if email exists
        return {"message": "If the email exists, a reset code has been sent", "success": True}
    
    # Generate 6-digit code
    code = ''.join(random.choices(string.digits, k=6))
    
    # Store code with expiration
    await db.password_reset_codes.insert_one({
        "email": data.email.lower(),
        "code": code,
        "created_at": datetime.utcnow(),
        "expires_at": datetime.utcnow() + timedelta(minutes=15),
        "used": False
    })
    
    # Send email using Microsoft Graph
    email_sent = await send_reset_email(data.email, code, user.get("name", "User"))
    
    if email_sent:
        logger.info(f"Password reset email sent to {data.email}")
    else:
        logger.error(f"Failed to send password reset email to {data.email}")
    
    return {"message": "If the email exists, a reset code has been sent", "success": True}

async def send_reset_email(to_email: str, code: str, user_name: str) -> bool:
    """Send password reset email using Microsoft Graph API"""
    try:
        # Get access token using MSAL
        app = msal.ConfidentialClientApplication(
            MS_GRAPH_CLIENT_ID,
            authority=f"https://login.microsoftonline.com/{MS_GRAPH_TENANT_ID}",
            client_credential=MS_GRAPH_CLIENT_SECRET,
        )
        
        result = app.acquire_token_for_client(scopes=["https://graph.microsoft.com/.default"])
        
        if "access_token" not in result:
            logger.error(f"Failed to get access token: {result.get('error_description', 'Unknown error')}")
            return False
        
        access_token = result["access_token"]
        
        # Create email content
        email_html = f"""
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
</head>
<body style="margin: 0; padding: 0; background-color: #0E1A14; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif;">
    <table role="presentation" width="100%" cellspacing="0" cellpadding="0" style="background-color: #0E1A14;">
        <tr>
            <td align="center" style="padding: 40px 20px;">
                <table role="presentation" width="100%" style="max-width: 500px; background-color: #1A2B22; border-radius: 16px; overflow: hidden;">
                    <!-- Header -->
                    <tr>
                        <td align="center" style="padding: 40px 40px 20px 40px;">
                            <h1 style="margin: 0; color: #C8A24A; font-size: 28px; font-weight: 700; letter-spacing: 2px;">IRON STAG</h1>
                        </td>
                    </tr>
                    
                    <!-- Content -->
                    <tr>
                        <td style="padding: 20px 40px;">
                            <h2 style="margin: 0 0 10px 0; color: #FFFFFF; font-size: 24px; font-weight: 600; text-align: center;">Password Reset</h2>
                            <p style="margin: 0 0 30px 0; color: #A0A0A0; font-size: 16px; text-align: center; line-height: 1.5;">
                                We received a request to reset your password. Use the code below to complete the process.
                            </p>
                            
                            <!-- Code Box -->
                            <table role="presentation" width="100%" cellspacing="0" cellpadding="0">
                                <tr>
                                    <td align="center" style="padding: 20px; background-color: #0E1A14; border-radius: 12px; border: 1px solid #2A3F32;">
                                        <p style="margin: 0 0 10px 0; color: #A0A0A0; font-size: 14px;">Your verification code:</p>
                                        <p style="margin: 0; color: #C8A24A; font-size: 36px; font-weight: 700; letter-spacing: 8px;">{code}</p>
                                    </td>
                                </tr>
                            </table>
                            
                            <p style="margin: 30px 0 0 0; color: #6B6B6B; font-size: 14px; text-align: center; line-height: 1.5;">
                                This code expires in 15 minutes. If you didn't request a password reset, please ignore this email.
                            </p>
                        </td>
                    </tr>
                    
                    <!-- Footer -->
                    <tr>
                        <td align="center" style="padding: 30px 40px 40px 40px; border-top: 1px solid #2A3F32;">
                            <p style="margin: 0 0 5px 0; color: #6B6B6B; font-size: 13px; font-style: italic;">Forged in Asgard, Tested in the Field</p>
                            <p style="margin: 0; color: #6B6B6B; font-size: 12px;">© 2025 Asgard Solutions LLC</p>
                        </td>
                    </tr>
                </table>
            </td>
        </tr>
    </table>
</body>
</html>
"""
        
        # Send email via Graph API
        email_message = {
            "message": {
                "subject": "Reset Your Iron Stag Password",
                "body": {
                    "contentType": "HTML",
                    "content": email_html
                },
                "toRecipients": [
                    {
                        "emailAddress": {
                            "address": to_email
                        }
                    }
                ]
            },
            "saveToSentItems": "true"
        }
        
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"https://graph.microsoft.com/v1.0/users/{MS_GRAPH_SENDER_EMAIL}/sendMail",
                headers={
                    "Authorization": f"Bearer {access_token}",
                    "Content-Type": "application/json"
                },
                json=email_message
            )
        
        if response.status_code == 202:
            return True
        else:
            logger.error(f"Graph API error: {response.status_code} - {response.text}")
            return False
            
    except Exception as e:
        logger.error(f"Error sending email: {str(e)}")
        return False

@api_router.post("/auth/password-reset/verify")
async def verify_password_reset(data: PasswordResetVerify):
    reset_code = await db.password_reset_codes.find_one({
        "email": data.email.lower(),
        "code": data.code,
        "used": False,
        "expires_at": {"$gt": datetime.utcnow()}
    })
    
    if not reset_code:
        raise HTTPException(status_code=400, detail="Invalid or expired code")
    
    # Update password
    hashed_password = ph.hash(data.new_password)
    await db.users.update_one(
        {"email": data.email.lower()},
        {"$set": {"password": hashed_password}}
    )
    
    # Mark code as used
    await db.password_reset_codes.update_one(
        {"_id": reset_code["_id"]},
        {"$set": {"used": True}}
    )
    
    return {"message": "Password reset successful"}

@api_router.get("/auth/me", response_model=UserResponse)
async def get_me(user: dict = Depends(get_current_user)):
    user = await reset_daily_scans(user)
    return UserResponse(
        id=user["id"],
        email=user["email"],
        name=user["name"],
        username=user.get("username"),
        created_at=user["created_at"],
        subscription_tier=user.get("subscription_tier", "scout"),
        scans_remaining=user.get("scans_remaining", 3),
        disclaimer_accepted=user.get("disclaimer_accepted", False)
    )

@api_router.put("/auth/profile", response_model=UserResponse)
async def update_profile(data: ProfileUpdate, user: dict = Depends(get_current_user)):
    updates = {}
    if data.name is not None:
        updates["name"] = data.name
    if data.username is not None:
        # Check username uniqueness
        existing = await db.users.find_one({"username": data.username, "id": {"$ne": user["id"]}})
        if existing:
            raise HTTPException(status_code=400, detail="Username already taken")
        updates["username"] = data.username
    
    if data.email is not None:
        # Check email uniqueness
        existing = await db.users.find_one({"email": data.email.lower(), "id": {"$ne": user["id"]}})
        if existing:
            raise HTTPException(status_code=400, detail="Email already in use")
        updates["email"] = data.email.lower()
    
    # Handle password change
    if data.new_password:
        if not data.current_password:
            raise HTTPException(status_code=400, detail="Current password is required to change password")
        
        # Verify current password
        if not verify_password(data.current_password, user["hashed_password"]):
            raise HTTPException(status_code=400, detail="Current password is incorrect")
        
        # Hash and set new password
        updates["hashed_password"] = hash_password(data.new_password)
    
    if updates:
        await db.users.update_one({"id": user["id"]}, {"$set": updates})
        user.update(updates)
    
    return UserResponse(
        id=user["id"],
        email=user.get("email"),
        name=user.get("name", user["email"]),
        username=user.get("username"),
        created_at=user["created_at"],
        subscription_tier=user.get("subscription_tier", "scout"),
        scans_remaining=user.get("scans_remaining", 3),
        disclaimer_accepted=user.get("disclaimer_accepted", False)
    )

@api_router.post("/auth/disclaimer", response_model=UserResponse)
async def accept_disclaimer(data: DisclaimerAccept, user: dict = Depends(get_current_user)):
    await db.users.update_one(
        {"id": user["id"]},
        {"$set": {"disclaimer_accepted": data.accepted}}
    )
    user["disclaimer_accepted"] = data.accepted
    
    return UserResponse(
        id=user["id"],
        email=user["email"],
        name=user["name"],
        username=user.get("username"),
        created_at=user["created_at"],
        subscription_tier=user.get("subscription_tier", "scout"),
        scans_remaining=user.get("scans_remaining", 3),
        disclaimer_accepted=user["disclaimer_accepted"]
    )

# ============ SUBSCRIPTION HELPERS ============

async def reset_daily_scans(user: dict) -> dict:
    """Reset daily scans if it's a new day (for free tier)"""
    if user.get("subscription_tier") == "master_stag":
        return user
    
    today = datetime.utcnow().date().isoformat()
    last_reset = user.get("scans_reset_date", "")
    
    if last_reset != today:
        await db.users.update_one(
            {"id": user["id"]},
            {"$set": {"scans_remaining": 3, "scans_reset_date": today}}
        )
        user["scans_remaining"] = 3
        user["scans_reset_date"] = today
    
    return user

async def decrement_scan(user: dict) -> bool:
    """Decrement scan count for free tier users"""
    if user.get("subscription_tier") == "master_stag":
        return True
    
    if user.get("scans_remaining", 0) <= 0:
        return False
    
    await db.users.update_one(
        {"id": user["id"]},
        {"$inc": {"scans_remaining": -1}}
    )
    return True

# ============ SUBSCRIPTION ROUTES ============

@api_router.get("/subscription/status", response_model=SubscriptionStatus)
async def get_subscription_status(user: dict = Depends(get_current_user)):
    user = await reset_daily_scans(user)
    
    return SubscriptionStatus(
        tier=user.get("subscription_tier", "scout"),
        scans_remaining=user.get("scans_remaining", 3),
        is_premium=user.get("subscription_tier") == "master_stag",
        expires_at=user.get("subscription_expires_at")
    )

@api_router.post("/subscription/create-checkout")
async def create_checkout_session(user: dict = Depends(get_current_user)):
    """Create Stripe checkout session for Master Stag subscription"""
    try:
        # Create or get Stripe customer
        if not user.get("stripe_customer_id"):
            customer = stripe.Customer.create(
                email=user["email"],
                name=user["name"],
                metadata={"user_id": user["id"]}
            )
            await db.users.update_one(
                {"id": user["id"]},
                {"$set": {"stripe_customer_id": customer.id}}
            )
            customer_id = customer.id
        else:
            customer_id = user["stripe_customer_id"]
        
        # Create checkout session
        session = stripe.checkout.Session.create(
            customer=customer_id,
            payment_method_types=["card"],
            line_items=[{
                "price_data": {
                    "currency": "usd",
                    "product_data": {
                        "name": "Master Stag Subscription",
                        "description": "Unlimited deer scans with Iron Stag"
                    },
                    "unit_amount": 999,  # $9.99
                    "recurring": {"interval": "month"}
                },
                "quantity": 1
            }],
            mode="subscription",
            success_url="ironstag://subscription/success",
            cancel_url="ironstag://subscription/cancel",
            metadata={"user_id": user["id"]}
        )
        
        return {"checkout_url": session.url, "session_id": session.id}
    except stripe.error.StripeError as e:
        logger.error(f"Stripe error: {e}")
        raise HTTPException(status_code=400, detail=str(e))

@api_router.post("/subscription/webhook")
async def stripe_webhook(request_body: bytes = Depends(lambda r: r.body())):
    """Handle Stripe webhook events"""
    try:
        sig_header = request_body.headers.get("stripe-signature")
        event = stripe.Webhook.construct_event(
            request_body, sig_header, STRIPE_WEBHOOK_SECRET
        )
        
        if event["type"] == "checkout.session.completed":
            session = event["data"]["object"]
            user_id = session["metadata"]["user_id"]
            
            await db.users.update_one(
                {"id": user_id},
                {"$set": {
                    "subscription_tier": "master_stag",
                    "stripe_subscription_id": session.get("subscription")
                }}
            )
        
        elif event["type"] == "customer.subscription.deleted":
            subscription = event["data"]["object"]
            await db.users.update_one(
                {"stripe_subscription_id": subscription["id"]},
                {"$set": {
                    "subscription_tier": "scout",
                    "scans_remaining": 3
                }}
            )
        
        return {"status": "success"}
    except Exception as e:
        logger.error(f"Webhook error: {e}")
        raise HTTPException(status_code=400, detail=str(e))

@api_router.post("/subscription/verify-revenuecat")
async def verify_revenuecat(user: dict = Depends(get_current_user)):
    """Verify subscription status with RevenueCat"""
    try:
        app_user_id = user.get("revenuecat_id") or user["id"]
        
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"https://api.revenuecat.com/v1/subscribers/{app_user_id}",
                headers={
                    "Authorization": f"Bearer {REVENUECAT_SECRET_KEY}",
                    "Content-Type": "application/json"
                }
            )
        
        if response.status_code == 200:
            data = response.json()
            subscriber = data.get("subscriber", {})
            entitlements = subscriber.get("entitlements", {})
            
            is_premium = "master_stag" in entitlements and entitlements["master_stag"].get("expires_date")
            
            if is_premium:
                expires_at = entitlements["master_stag"]["expires_date"]
                await db.users.update_one(
                    {"id": user["id"]},
                    {"$set": {
                        "subscription_tier": "master_stag",
                        "subscription_expires_at": expires_at,
                        "revenuecat_id": app_user_id
                    }}
                )
                return {"status": "premium", "expires_at": expires_at}
        
        return {"status": "free"}
    except Exception as e:
        logger.error(f"RevenueCat error: {e}")
        return {"status": "error", "message": str(e)}

# ============ DEER ANALYSIS ROUTES ============

@api_router.post("/analyze-deer", response_model=DeerAnalysisResponse)
async def analyze_deer(data: DeerAnalysisRequest, user: dict = Depends(get_current_user)):
    """Analyze deer image using GPT-4 Vision"""
    
    # Check scan availability
    user = await reset_daily_scans(user)
    if not await decrement_scan(user):
        raise HTTPException(
            status_code=403,
            detail="No scans remaining. Upgrade to Master Stag for unlimited scans!"
        )
    
    try:
        # Prepare the image for OpenAI
        image_data = data.image_base64
        if not image_data.startswith("data:"):
            image_data = f"data:image/jpeg;base64,{image_data}"
        
        # Call GPT-4 Vision
        response = openai_client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {
                    "role": "system",
                    "content": """You are an expert wildlife biologist specializing in deer aging and assessment. 
                    Analyze the deer image and provide a detailed assessment in JSON format.
                    
                    Return ONLY valid JSON with these exact fields:
                    {
                        "deer_age": <number or null> (estimated age in years, e.g., 2.5, 3.5, 4.5),
                        "deer_type": <string> (species like "White-tailed Deer", "Mule Deer", etc.),
                        "deer_sex": <string> ("Buck" or "Doe"),
                        "antler_points": <number or null> (count for bucks, null for does),
                        "body_condition": <string> ("Poor", "Fair", "Good", "Excellent"),
                        "confidence": <number> (1-100 percentage of confidence in assessment),
                        "recommendation": <string> ("HARVEST" or "PASS"),
                        "reasoning": <string> (detailed explanation of the assessment and recommendation)
                    }
                    
                    Base your recommendation on:
                    - Age maturity (typically PASS for deer under 3.5 years)
                    - Body condition
                    - Conservation best practices
                    - Regional deer management principles
                    
                    If the image doesn't contain a deer or is unclear, still return JSON with null values and explain in reasoning."""
                },
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "text",
                            "text": "Analyze this deer image and provide your assessment:"
                        },
                        {
                            "type": "image_url",
                            "image_url": {"url": image_data}
                        }
                    ]
                }
            ],
            max_tokens=1000
        )
        
        # Parse the response
        response_text = response.choices[0].message.content
        
        # Extract JSON from response
        try:
            # Try to find JSON in the response
            if "```json" in response_text:
                json_str = response_text.split("```json")[1].split("```")[0]
            elif "```" in response_text:
                json_str = response_text.split("```")[1].split("```")[0]
            else:
                json_str = response_text
            
            analysis = json.loads(json_str.strip())
        except json.JSONDecodeError:
            # If JSON parsing fails, create a default response
            analysis = {
                "deer_age": None,
                "deer_type": "Unknown",
                "deer_sex": "Unknown",
                "antler_points": None,
                "body_condition": "Unknown",
                "confidence": 0,
                "recommendation": "PASS",
                "reasoning": response_text
            }
        
        # Create scan record
        scan_id = str(uuid.uuid4())
        scan = {
            "id": scan_id,
            "user_id": user["id"],
            "local_image_id": data.local_image_id,
            "deer_age": analysis.get("deer_age"),
            "deer_type": analysis.get("deer_type"),
            "deer_sex": analysis.get("deer_sex"),
            "antler_points": analysis.get("antler_points"),
            "body_condition": analysis.get("body_condition"),
            "confidence": analysis.get("confidence"),
            "recommendation": analysis.get("recommendation"),
            "reasoning": analysis.get("reasoning"),
            "notes": data.notes,
            "raw_response": analysis,
            "created_at": datetime.utcnow()
        }
        
        await db.scans.insert_one(scan)
        
        return DeerAnalysisResponse(**scan)
        
    except openai.OpenAIError as e:
        logger.error(f"OpenAI error: {e}")
        # Refund the scan on error
        await db.users.update_one(
            {"id": user["id"]},
            {"$inc": {"scans_remaining": 1}}
        )
        raise HTTPException(status_code=500, detail=f"AI analysis failed: {str(e)}")

# ============ SCAN HISTORY ROUTES ============

@api_router.get("/scans", response_model=List[DeerAnalysisResponse])
async def get_scans(
    user: dict = Depends(get_current_user),
    deer_type: Optional[str] = None,
    deer_sex: Optional[str] = None,
    recommendation: Optional[str] = None,
    limit: int = 50,
    skip: int = 0
):
    """Get user's scan history with optional filters"""
    query = {"user_id": user["id"]}
    
    if deer_type:
        query["deer_type"] = {"$regex": deer_type, "$options": "i"}
    if deer_sex:
        query["deer_sex"] = deer_sex
    if recommendation:
        query["recommendation"] = recommendation
    
    scans = await db.scans.find(query).sort("created_at", -1).skip(skip).limit(limit).to_list(limit)
    
    return [DeerAnalysisResponse(**scan) for scan in scans]

@api_router.get("/scans/{scan_id}", response_model=DeerAnalysisResponse)
async def get_scan(scan_id: str, user: dict = Depends(get_current_user)):
    """Get a specific scan by ID"""
    scan = await db.scans.find_one({"id": scan_id, "user_id": user["id"]})
    if not scan:
        raise HTTPException(status_code=404, detail="Scan not found")
    
    return DeerAnalysisResponse(**scan)

@api_router.put("/scans/{scan_id}", response_model=DeerAnalysisResponse)
async def update_scan(scan_id: str, data: ScanUpdate, user: dict = Depends(get_current_user)):
    """Update scan notes"""
    scan = await db.scans.find_one({"id": scan_id, "user_id": user["id"]})
    if not scan:
        raise HTTPException(status_code=404, detail="Scan not found")
    
    updates = {}
    if data.notes is not None:
        updates["notes"] = data.notes
    
    if updates:
        await db.scans.update_one({"id": scan_id}, {"$set": updates})
        scan.update(updates)
    
    return DeerAnalysisResponse(**scan)

@api_router.delete("/scans/{scan_id}")
async def delete_scan(scan_id: str, user: dict = Depends(get_current_user)):
    """Delete a scan"""
    result = await db.scans.delete_one({"id": scan_id, "user_id": user["id"]})
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Scan not found")
    
    return {"message": "Scan deleted"}

@api_router.get("/scans/stats/summary")
async def get_scan_stats(user: dict = Depends(get_current_user)):
    """Get user's scan statistics"""
    pipeline = [
        {"$match": {"user_id": user["id"]}},
        {"$group": {
            "_id": None,
            "total_scans": {"$sum": 1},
            "harvest_count": {"$sum": {"$cond": [{"$eq": ["$recommendation", "HARVEST"]}, 1, 0]}},
            "pass_count": {"$sum": {"$cond": [{"$eq": ["$recommendation", "PASS"]}, 1, 0]}}
        }}
    ]
    
    result = await db.scans.aggregate(pipeline).to_list(1)
    
    if result:
        stats = result[0]
        return {
            "total_scans": stats["total_scans"],
            "harvest_count": stats["harvest_count"],
            "pass_count": stats["pass_count"]
        }
    
    return {"total_scans": 0, "harvest_count": 0, "pass_count": 0}

# ============ LEARN CONTENT ============

@api_router.get("/learn/content")
async def get_learn_content():
    """Get educational content for the Learn tab"""
    return {
        "sections": [
            {
                "id": "aging",
                "title": "Deer Aging Techniques",
                "content": [
                    {
                        "title": "Body Size & Shape",
                        "description": "Mature bucks (4.5+ years) have a deep chest, swayed back, and their belly drops below their chest. Young bucks appear more athletic and sleek."
                    },
                    {
                        "title": "Neck & Shoulders",
                        "description": "During rut, mature bucks develop a heavily muscled, swollen neck that blends into their shoulders. Young bucks maintain a distinct neck-shoulder separation."
                    },
                    {
                        "title": "Leg-to-Body Ratio",
                        "description": "Young deer appear 'leggy' with legs that seem too long for their body. Mature deer have proportionate legs that appear shorter relative to body depth."
                    },
                    {
                        "title": "Antler Development",
                        "description": "While genetics and nutrition affect antler size, most bucks don't reach their full potential until 5-7 years old. Main beam length and mass increase with age."
                    }
                ]
            },
            {
                "id": "ethics",
                "title": "Ethical Hunting Guidelines",
                "content": [
                    {
                        "title": "Fair Chase Principles",
                        "description": "Hunt in a manner that does not give the hunter improper advantage over game animals. This includes avoiding baiting, spotlighting, and using motorized vehicles to chase game."
                    },
                    {
                        "title": "Clean Harvest",
                        "description": "Practice regularly to ensure clean, ethical kills. Know your effective range and only take shots you are confident in making."
                    },
                    {
                        "title": "Respect for the Animal",
                        "description": "Use all usable parts of harvested game. Waste nothing and honor the animal through complete utilization."
                    },
                    {
                        "title": "Land Stewardship",
                        "description": "Leave the land better than you found it. Practice habitat conservation and respect property boundaries."
                    }
                ]
            },
            {
                "id": "management",
                "title": "Wildlife Management",
                "content": [
                    {
                        "title": "Age Structure",
                        "description": "Healthy deer populations have balanced age structures. Passing on young bucks allows them to reach maturity and improve genetics."
                    },
                    {
                        "title": "Population Control",
                        "description": "Doe harvest is crucial for population management. An overpopulated herd leads to habitat destruction and disease spread."
                    },
                    {
                        "title": "Habitat Management",
                        "description": "Quality deer management includes food plots, water sources, and cover. Healthy habitat produces healthier deer."
                    },
                    {
                        "title": "Record Keeping",
                        "description": "Track harvest data, trail camera photos, and observations. This data helps make informed management decisions."
                    }
                ]
            }
        ]
    }

# ============ HEALTH CHECK ============

@api_router.get("/")
async def root():
    return {"message": "Iron Stag API - Hunt Smarter. Harvest Responsibly."}

@api_router.get("/health")
async def health_check():
    return {"status": "healthy", "version": "1.0.0"}

# Include router
app.include_router(api_router)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_credentials=True,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.on_event("shutdown")
async def shutdown_db_client():
    client.close()
