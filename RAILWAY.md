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

You'll create two Railway services:
1. **Backend** (FastAPI + yt-dlp)
2. **Frontend** (Next.js 16)

Both services will be deployed from the same monorepo using Railway's root directory configuration.

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
3. Name it "Backend" or "API"

### 2.2 Configure Backend Build

1. Go to the Backend service **Settings**
2. Under **Build**, set:
   - **Root Directory**: `backend`
   - **Builder**: Docker (will auto-detect the Dockerfile)

> **Note**: Railway injects a `PORT` environment variable. The Dockerfile is already configured to use `${PORT:-8000}`, so no additional port configuration is needed.

### 2.3 Configure Backend Environment Variables

Go to the Backend service **Variables** tab and add:

```env
ENV=production
API_V1_PREFIX=/api/v1
CORS_ORIGINS=https://your-frontend-url.up.railway.app
LOG_LEVEL=INFO
BLOCK_PRIVATE_NETWORKS=true
ALLOWED_URL_SCHEMES=http,https
```

> **Important**: Update `CORS_ORIGINS` after deploying the frontend (see Step 3).

### 2.4 Configure Backend Domain

1. Go to **Settings** → **Networking**
2. Click "Generate Domain" to get a public URL
3. Copy this URL (you'll need it for the frontend)

Example: `https://backend-production-abc123.up.railway.app`

### 2.5 Update CORS Origins

Once you have the frontend domain (Step 3), update the backend's `CORS_ORIGINS`:

```env
CORS_ORIGINS=https://frontend-production-xyz789.up.railway.app
```

### 2.6 Verify Backend Deployment

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
3. Name it "Frontend" or "Web"

### 3.2 Configure Frontend Build

1. Go to the Frontend service **Settings**
2. Under **Build**, set:
   - **Root Directory**: `frontend`
   - **Builder**: Nixpacks (Railway auto-detects Next.js)
   - **Install Command**: `pnpm install` (auto-detected)
   - **Build Command**: `pnpm build` (auto-detected)
   - **Start Command**: `pnpm start` (auto-detected)

### 3.3 Configure Frontend Environment Variables

Go to the Frontend service **Variables** tab and add:

```env
NEXT_PUBLIC_API_BASE=https://your-backend-url.up.railway.app/api/v1
```

> Replace `your-backend-url` with the actual backend domain from Step 2.4.

### 3.4 Configure Frontend Domain

1. Go to **Settings** → **Networking**
2. Click "Generate Domain" to get a public URL

Example: `https://frontend-production-xyz789.up.railway.app`

### 3.5 Update Backend CORS

Now that you have the frontend URL, go back to the Backend service and update `CORS_ORIGINS` (see Step 2.5).

### 3.6 Verify Frontend Deployment

1. Visit your frontend URL
2. The Video Downloader UI should load
3. Paste a YouTube URL and click "Fetch Formats"
4. Verify that formats load successfully

---

## Step 4: Final Verification

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
5. Update Backend's `CORS_ORIGINS` to include the custom domain

### Add Custom Domain to Backend

1. Go to Backend service → **Settings** → **Networking**
2. Click "Add Custom Domain"
3. Enter your API subdomain (e.g., `api.yourdomain.com`)
4. Follow Railway's DNS configuration instructions
5. Update Frontend's `NEXT_PUBLIC_API_BASE` to use the custom domain

---

## Troubleshooting

### Backend Issues

**Problem**: `/health` endpoint returns 502 or timeout
- **Solution**: Check Backend logs for startup errors; ensure Dockerfile builds successfully

**Problem**: CORS errors in browser console
- **Solution**: Verify `CORS_ORIGINS` in Backend matches the Frontend domain exactly (include `https://`)

**Problem**: yt-dlp fails with "command not found"
- **Solution**: Ensure the Backend Dockerfile installs `yt-dlp` correctly (it's included in the provided Dockerfile)

### Frontend Issues

**Problem**: "Missing required environment variable: NEXT_PUBLIC_API_BASE"
- **Solution**: Add `NEXT_PUBLIC_API_BASE` to Frontend service variables

**Problem**: API requests fail with network error
- **Solution**: Verify `NEXT_PUBLIC_API_BASE` points to the correct Backend URL (include `/api/v1` suffix)

**Problem**: Build fails with Node.js version mismatch
- **Solution**: Railway should auto-detect Node 20; ensure `package.json` has `"engines": {"node": ">=20.0.0"}`

### Download Issues

**Problem**: Downloads fail with 404
- **Solution**: Check Backend logs; ensure the video URL is accessible and platform is supported

**Problem**: Large downloads timeout
- **Solution**: Railway's default timeout is 5 minutes; for longer downloads, consider implementing background jobs (see Roadmap in README)

---

## Scaling

### Increase Backend Resources

1. Go to Backend service → **Settings** → **Resources**
2. Increase memory/CPU if downloads are slow or timing out

### Increase Uvicorn Workers

The backend Dockerfile uses Railway's `PORT` env var automatically. To increase workers, edit the `CMD` line in `backend/Dockerfile`:

```dockerfile
CMD sh -c "uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000} --workers 4"
```

Redeploy the Backend service.

---

## Monitoring

### View Logs in Real-Time

```bash
# Install Railway CLI
npm install -g @railway/cli

# Link to your project
railway link

# View backend logs
railway logs --service backend

# View frontend logs
railway logs --service frontend
```

### Set Up Alerts (Optional)

1. Go to Project → **Settings** → **Notifications**
2. Add Slack/Discord webhook for deployment notifications

---

## Next Steps

- Add authentication (e.g., Clerk, Auth0)
- Implement rate limiting (e.g., Redis + middleware)
- Add background job processing (Celery + Redis, or Railway's new Queue service)
- Set up monitoring (Sentry for errors, Prometheus + Grafana for metrics)

---

## Support

- Railway Docs: https://docs.railway.app
- FastAPI Docs: https://fastapi.tiangolo.com
- Next.js Docs: https://nextjs.org/docs
- yt-dlp Docs: https://github.com/yt-dlp/yt-dlp

For project-specific issues, refer to the main [README.md](../README.md).
