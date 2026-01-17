# Iron Stag - Railway Deployment Guide

## Overview

This guide will help you deploy the Iron Stag FastAPI backend to Railway. Your frontend (Expo app) will continue to be built with EAS and distributed through the App Store/Play Store.

## Architecture After Deployment

```
┌─────────────────────────────────────────────────────────────────┐
│                     MOBILE APPS                                  │
│  ┌─────────────────┐    ┌─────────────────┐                     │
│  │   iOS App       │    │  Android App    │                     │
│  │ (App Store)     │    │ (Play Store)    │                     │
│  └────────┬────────┘    └────────┬────────┘                     │
└───────────┼──────────────────────┼──────────────────────────────┘
            │                      │
            └──────────┬───────────┘
                       │ HTTPS
                       ▼
┌─────────────────────────────────────────────────────────────────┐
│                   RAILWAY (Backend)                              │
│  ┌─────────────────────────────────────────────────────────┐    │
│  │              FastAPI Application                         │    │
│  │              iron-stag-api.railway.app                   │    │
│  └─────────────────────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────────────────┘
                       │
         ┌─────────────┼─────────────┐
         │             │             │
         ▼             ▼             ▼
┌─────────────┐ ┌─────────────┐ ┌─────────────┐
│   Neon      │ │   OpenAI    │ │ RevenueCat  │
│ PostgreSQL  │ │  GPT-4o     │ │  Payments   │
└─────────────┘ └─────────────┘ └─────────────┘
```

---

## Step 1: Prepare Your Repository

### 1.1 Create Railway-specific files in `/backend`

You'll need these files in your `backend/` folder:

#### `Procfile`
```
web: uvicorn server:app --host 0.0.0.0 --port $PORT
```

#### `runtime.txt`
```
python-3.11.7
```

#### `railway.json` (optional, for configuration)
```json
{
  "$schema": "https://railway.app/railway.schema.json",
  "build": {
    "builder": "NIXPACKS"
  },
  "deploy": {
    "startCommand": "uvicorn server:app --host 0.0.0.0 --port $PORT",
    "healthcheckPath": "/api/health",
    "healthcheckTimeout": 30,
    "restartPolicyType": "ON_FAILURE",
    "restartPolicyMaxRetries": 3
  }
}
```

### 1.2 Update requirements.txt

Your `requirements.txt` is already complete. Railway will use it automatically.

---

## Step 2: Create Railway Project

### 2.1 Via Railway Dashboard

1. Go to [railway.app](https://railway.app) and sign in
2. Click **"New Project"**
3. Select **"Deploy from GitHub repo"**
4. Connect your GitHub account if not already connected
5. Select **`Asgard-Solutions/ironstag`** repository
6. **Important:** Set the **Root Directory** to `backend`

### 2.2 Via Railway CLI (Alternative)

```bash
# Install Railway CLI
npm install -g @railway/cli

# Login
railway login

# Create new project
railway init

# Link to your repo
railway link
```

---

## Step 3: Configure Environment Variables

In Railway Dashboard → Your Project → Variables tab, add these:

### Required Variables

| Variable | Description | Example |
|----------|-------------|----------|
| `DATABASE_URL` | Your Neon PostgreSQL URL | `postgresql://user:pass@host/db?sslmode=require` |
| `SECRET_KEY` | JWT signing secret (generate a strong random string) | `your-super-secret-jwt-key-min-32-chars` |
| `EMERGENT_LLM_KEY` | OpenAI API key for GPT-4o | `sk-...` |
| `MS_GRAPH_CLIENT_ID` | Azure app client ID for email | `xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx` |
| `MS_GRAPH_CLIENT_SECRET` | Azure app secret | `your-client-secret` |
| `MS_GRAPH_TENANT_ID` | Azure tenant ID | `xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx` |
| `MS_GRAPH_SENDER_EMAIL` | Email sender address | `support@asgardsolution.io` |

### Optional Variables

| Variable | Description | Default |
|----------|-------------|----------|
| `PORT` | Server port | `8001` (Railway sets this automatically) |
| `LOG_LEVEL` | Logging level | `INFO` |

### How to Add Variables

1. Go to Railway Dashboard
2. Click on your service
3. Go to **Variables** tab
4. Click **"+ New Variable"**
5. Add each variable

Or use **Raw Editor** to paste all at once:

```env
DATABASE_URL=postgresql://neondb_owner:YOUR_PASSWORD@ep-square-silence-ahbepao1-pooler.c-3.us-east-1.aws.neon.tech/neondb?sslmode=require
SECRET_KEY=your-super-secret-jwt-signing-key-at-least-32-characters
EMERGENT_LLM_KEY=your-openai-api-key
MS_GRAPH_CLIENT_ID=your-azure-client-id
MS_GRAPH_CLIENT_SECRET=your-azure-client-secret
MS_GRAPH_TENANT_ID=your-azure-tenant-id
MS_GRAPH_SENDER_EMAIL=support@asgardsolution.io
```

---

## Step 4: Configure Build Settings

### 4.1 Set Root Directory

1. Go to your service **Settings**
2. Under **Build**, set **Root Directory** to: `backend`
3. Railway will now only deploy the backend folder

### 4.2 Start Command (if not using Procfile)

In Settings → Deploy, set:
```
uvicorn server:app --host 0.0.0.0 --port $PORT
```

---

## Step 5: Deploy

### Automatic Deployment

Railway automatically deploys when you push to your connected branch (usually `main`).

### Manual Deployment

1. Go to your service
2. Click **"Deploy"** button
3. Or use CLI: `railway up`

---

## Step 6: Get Your Production URL

After deployment:

1. Go to your service **Settings**
2. Under **Domains**, click **"Generate Domain"**
3. You'll get a URL like: `iron-stag-api-production.up.railway.app`

### Custom Domain (Optional)

1. Click **"+ Custom Domain"**
2. Enter your domain: `api.ironstag.com`
3. Add the CNAME record to your DNS provider
4. Wait for SSL certificate provisioning

---

## Step 7: Update Mobile App Configuration

### 7.1 Update Frontend Environment

Update `frontend/.env` for production builds:

```env
# For production builds
EXPO_PUBLIC_API_BASE_URL=https://your-app.up.railway.app
EXPO_PUBLIC_BACKEND_URL=https://your-app.up.railway.app/api
```

### 7.2 Update EAS Build Environment

Update `frontend/eas.json` to use production URL:

```json
{
  "build": {
    "production": {
      "env": {
        "EXPO_PUBLIC_API_BASE_URL": "https://your-app.up.railway.app",
        "EXPO_PUBLIC_BACKEND_URL": "https://your-app.up.railway.app/api"
      }
    }
  }
}
```

---

## Step 8: Verify Deployment

### Health Check

```bash
curl https://your-app.up.railway.app/api/health
```

Expected response:
```json
{
  "status": "healthy",
  "database": "postgresql",
  "timestamp": "2026-01-17T12:00:00Z"
}
```

### Test Login

```bash
curl -X POST https://your-app.up.railway.app/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email": "test@test.com", "password": "test123"}'
```

---

## Step 9: Set Up Monitoring (Optional)

### Railway Metrics

Railway provides built-in metrics:
- CPU usage
- Memory usage
- Network traffic
- Request logs

### Health Check Monitoring

Railway can restart your service if health checks fail:

1. Go to Settings → Deploy
2. Enable **Health Checks**
3. Set path to `/api/health`

---

## Troubleshooting

### Common Issues

#### 1. "Module not found" Error

**Cause:** Missing dependency in requirements.txt

**Fix:** Ensure all imports have corresponding packages in requirements.txt

#### 2. Database Connection Failed

**Cause:** DATABASE_URL not set or incorrect

**Fix:** 
- Verify DATABASE_URL is set in Railway Variables
- Check Neon dashboard for correct connection string
- Ensure `?sslmode=require` is included

#### 3. Port Binding Error

**Cause:** Hardcoded port instead of using `$PORT`

**Fix:** Use `--port $PORT` in start command

#### 4. Build Fails

**Cause:** Python version mismatch or dependency conflict

**Fix:** 
- Add `runtime.txt` with `python-3.11.7`
- Check build logs for specific errors

#### 5. Slow Cold Starts

**Cause:** Railway's free tier spins down after inactivity

**Fix:** 
- Upgrade to paid plan for always-on
- Or accept ~5 second cold starts

### Viewing Logs

```bash
# Via CLI
railway logs

# Or in Dashboard → Deployments → View Logs
```

---

## Cost Estimation

### Railway Pricing (as of 2026)

| Plan | Cost | Features |
|------|------|----------|
| Hobby | $5/month | 500 hours, 512MB RAM |
| Pro | $20/month | Unlimited hours, 8GB RAM, Team features |
| Enterprise | Custom | SLA, Support, Custom limits |

### Estimated Monthly Cost

For Iron Stag backend:
- **Hobby Plan:** $5/month (sufficient for moderate traffic)
- **Pro Plan:** $20/month (recommended for production)

**Note:** Database (Neon) and AI (OpenAI) costs are separate.

---

## Complete Deployment Checklist

```
□ 1. Create Procfile in backend/
□ 2. Create runtime.txt in backend/
□ 3. Push changes to GitHub
□ 4. Create Railway project
□ 5. Connect GitHub repo
□ 6. Set Root Directory to 'backend'
□ 7. Add all environment variables
□ 8. Deploy
□ 9. Generate Railway domain
□ 10. Test /api/health endpoint
□ 11. Update frontend .env with production URL
□ 12. Update eas.json with production URL
□ 13. Build production mobile apps with EAS
□ 14. Test end-to-end flow
```

---

## Quick Commands Reference

```bash
# Railway CLI
railway login                    # Login to Railway
railway init                     # Initialize project
railway link                     # Link to existing project
railway up                       # Deploy current directory
railway logs                     # View logs
railway status                   # Check deployment status
railway variables                # List environment variables
railway variables set KEY=value  # Set variable
railway open                     # Open dashboard

# Testing
curl https://your-app.up.railway.app/api/health
```

---

## Support

- **Railway Docs:** https://docs.railway.app
- **Railway Discord:** https://discord.gg/railway
- **Iron Stag Support:** support@asgardsolution.io

---

**Happy Deploying! 🚀**
