# Railway Deployment Guide

This guide walks you through deploying the Video Downloader monorepo to Railway as two separate services.

## Prerequisites

1. A [Railway](https://railway.app) account
2. This repository pushed to GitHub (or GitLab/Bitbucket)
3. Railway CLI installed (optional, for local testing):
   ```bash
   npm install -g @railway/cli
   ```

## Overview

You'll create two Railway services from the same monorepo:
1. **Backend** (FastAPI + yt-dlp) — Docker build from `backend/`
2. **Frontend** (Next.js 16) — Docker build from `frontend/`

Railway auto-detects the `railway.toml` in each service's root directory and passes all environment variables as Docker build args.

---

## Step 1: Create a New Railway Project

1. Log in to [Railway](https://railway.app)
2. Click "New Project"
3. Select "Deploy from GitHub repo"
4. Authorize Railway to access your GitHub account
5. Select your `youtube-video-downloader` repository

---

## Step 2: Deploy the Backend Service

### 2.1 Create Backend Service

1. In your Railway project, click "+ New Service"
2. Select your repository
3. Name it `backend`

### 2.2 Configure Backend Build

1. Go to the Backend service **Settings**
2. Under **Build**, set:
   - **Root Directory**: `backend`
   - **Builder**: Docker (auto-detected from `railway.toml`)

> **Note**: Railway injects a `PORT` environment variable at runtime. The Dockerfile uses `${PORT:-8000}`, so it works automatically.

### 2.3 Configure Backend Domain

1. Go to **Settings** → **Networking**
2. Click "Generate Domain" to get a public URL
3. Copy this URL — you'll need it for the frontend

Example: `https://backend-production-abc123.up.railway.app`

### 2.4 Configure Backend Environment Variables

Go to the Backend service **Variables** tab and add:

```env
ENV=production
API_V1_PREFIX=/api/v1
LOG_LEVEL=INFO
BLOCK_PRIVATE_NETWORKS=true
ALLOWED_URL_SCHEMES=http,https
```

**For CORS**, use Railway's variable reference to auto-discover the frontend domain:

```env
CORS_ORIGINS=https://${{Frontend.RAILWAY_PUBLIC_DOMAIN}}
```

> This automatically resolves to the frontend's Railway domain. Replace `Frontend` with whatever you named your frontend service.

If you don't want to use variable references, set it manually after deploying the frontend:
```env
CORS_ORIGINS=https://your-frontend-url.up.railway.app
```

### 2.5 Verify Backend Deployment

1. Wait for the build and deployment to complete
2. Visit `https://your-backend-url.up.railway.app/health`
   - Should return: `{"status": "healthy", "version": "0.1.0"}`
3. Visit `https://your-backend-url.up.railway.app/docs`
   - Should show FastAPI Swagger UI

---

## Step 3: Deploy the Frontend Service

### 3.1 Create Frontend Service

1. In your Railway project, click "+ New Service"
2. Select your repository again
3. Name it `frontend`

### 3.2 Configure Frontend Build

1. Go to the Frontend service **Settings**
2. Under **Build**, set:
   - **Root Directory**: `frontend`
   - **Builder**: Docker (auto-detected from `railway.toml`)

### 3.3 Configure Frontend Environment Variables

Go to the Frontend service **Variables** tab and add:

**Using Railway variable references** (recommended):
```env
NEXT_PUBLIC_API_BASE=https://${{Backend.RAILWAY_PUBLIC_DOMAIN}}/api/v1
```

> Replace `Backend` with whatever you named your backend service. This variable is passed as a Docker build arg and baked into the Next.js bundle at build time.

**Or set manually:**
```env
NEXT_PUBLIC_API_BASE=https://your-backend-url.up.railway.app/api/v1
```

### 3.4 Configure Frontend Domain

1. Go to **Settings** → **Networking**
2. Click "Generate Domain" to get a public URL

Example: `https://frontend-production-xyz789.up.railway.app`

### 3.5 Verify Frontend Deployment

1. Visit your frontend URL
2. The Video Downloader UI should load
3. Paste a video URL and click "Fetch Formats"
4. Verify that formats load successfully

---

## Step 4: Final Checklist

| Service  | Variable | Value |
|----------|----------|-------|
| Backend  | `ENV` | `production` |
| Backend  | `API_V1_PREFIX` | `/api/v1` |
| Backend  | `CORS_ORIGINS` | `https://${{Frontend.RAILWAY_PUBLIC_DOMAIN}}` |
| Backend  | `LOG_LEVEL` | `INFO` |
| Backend  | `BLOCK_PRIVATE_NETWORKS` | `true` |
| Backend  | `ALLOWED_URL_SCHEMES` | `http,https` |
| Frontend | `NEXT_PUBLIC_API_BASE` | `https://${{Backend.RAILWAY_PUBLIC_DOMAIN}}/api/v1` |

> **Important**: After setting `NEXT_PUBLIC_API_BASE`, you may need to trigger a **redeploy** of the frontend because this value is baked in at build time. Go to the frontend service → Deployments → Redeploy.

### Test End-to-End Flow

1. Open the frontend in your browser
2. Enter a YouTube video URL (e.g., `https://www.youtube.com/watch?v=dQw4w9WgXcQ`)
3. Click "Fetch Formats" — should load video metadata and formats
4. Click "Download" on any format — should stream the video file

### Check Logs

1. **Backend Logs**: Go to Backend service → **Deployments** → Click latest deployment
   - Look for successful API requests
   - Check for any `yt-dlp` errors

2. **Frontend Logs**: Go to Frontend service → **Deployments** → Click latest deployment
   - Look for successful builds
   - Check for any runtime errors

---

## Step 5: Custom Domains (Optional)

### Add Custom Domain to Frontend

1. Go to Frontend service → **Settings** → **Networking**
2. Click "Add Custom Domain"
3. Enter your domain (e.g., `downloader.yourdomain.com`)
4. Follow Railway's DNS configuration instructions
5. Update Backend's `CORS_ORIGINS` to include the custom domain:
   ```env
   CORS_ORIGINS=https://downloader.yourdomain.com
   ```

### Add Custom Domain to Backend

1. Go to Backend service → **Settings** → **Networking**
2. Click "Add Custom Domain"
3. Enter your API subdomain (e.g., `api.yourdomain.com`)
4. Follow Railway's DNS configuration instructions
5. Update Frontend's `NEXT_PUBLIC_API_BASE` and **redeploy**:
   ```env
   NEXT_PUBLIC_API_BASE=https://api.yourdomain.com/api/v1
   ```

---

## Troubleshooting

### Backend Issues

| Problem | Solution |
|---------|----------|
| `/health` returns 502 or timeout | Check Backend logs for startup errors; ensure Dockerfile builds successfully |
| CORS errors in browser console | Verify `CORS_ORIGINS` matches the Frontend domain exactly (include `https://`) |
| yt-dlp fails with "command not found" | Ensure the Dockerfile installs yt-dlp correctly (it's included in the provided Dockerfile) |
| Downloads timeout | Increase service memory in Settings → Resources; Railway default timeout is 5 min |

### Frontend Issues

| Problem | Solution |
|---------|----------|
| API requests fail | Verify `NEXT_PUBLIC_API_BASE` points to the Backend URL with `/api/v1` suffix; **redeploy** after changing |
| Build fails | Check logs — `NEXT_PUBLIC_API_BASE` must be set before build since it's baked into the JS bundle |
| Page loads but shows errors | Open browser DevTools → Console; check for CORS or network errors |

### Variable Reference Issues

| Problem | Solution |
|---------|----------|
| `${{Backend.RAILWAY_PUBLIC_DOMAIN}}` is empty | Ensure the backend service is named exactly `Backend` (or update the reference to match your service name) |
| Changes to `NEXT_PUBLIC_API_BASE` don't take effect | This variable is baked at build time — you must trigger a **redeploy** of the frontend service |

---

## Monitoring

### View Logs in Real-Time

```bash
# Install Railway CLI
npm install -g @railway/cli

# Login and link to your project
railway login
railway link

# View backend logs
railway logs --service backend

# View frontend logs
railway logs --service frontend
```

---

## Support

- Railway Docs: https://docs.railway.app
- FastAPI Docs: https://fastapi.tiangolo.com
- Next.js Docs: https://nextjs.org/docs
- yt-dlp Docs: https://github.com/yt-dlp/yt-dlp

For project-specific issues, refer to the main [README.md](./README.md).
