# Railway Deployment Guide

This guide walks you through deploying the Video Downloader monorepo to Railway as two separate services.

## Prerequisites

1. A [Railway](https://railway.app) account
2. This repository pushed to GitHub (or GitLab/Bitbucket)
3. Railway CLI (recommended for logs, variables, and redeploys):
   ```bash
   npm install -g @railway/cli
   ```
   See [Setup with Railway CLI](#setup-with-railway-cli) below.

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

**yt-dlp / YouTube (optional but recommended):** The backend defaults in code already use `YTDLP_YOUTUBE_PLAYER_CLIENT=tv_embedded` (avoids “Requested format is not available” when the iOS client is used without a PO token). You do **not** have to set anything for basic YouTube support.

For production tuning (aligned with `docker-compose.yml`), you may add:

```env
YTDLP_YOUTUBE_PLAYER_CLIENT=tv_embedded
YTDLP_USE_IOS_CLIENT=false
YTDLP_CONCURRENT_FRAGMENTS=32
YTDLP_HTTP_CHUNK_SIZE=
YTDLP_STREAM_CHUNK_SIZE=2097152
YTDLP_BUFFER_SIZE=1M
YTDLP_SOCKET_TIMEOUT=60
YTDLP_THROTTLED_RATE=50K
YTDLP_PREFER_FREE_FORMATS=true
```

**Authenticated YouTube (cookies):** Use `YTDLP_COOKIES_BASE64` or chunked `YTDLP_COOKIES_BASE64_1`, `_2`, … (see `backend/entrypoint.sh`). Railway caps each variable at **32KB** — use `./scripts/railway-cookies-chunks.sh` for large cookie files.

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

**Build-time requirement:** `NEXT_PUBLIC_API_BASE` must be **non-empty** when Docker runs `pnpm build`. The `frontend/Dockerfile` fails the build with a clear error if it is missing. The final image also sets `ENV NEXT_PUBLIC_API_BASE` so the Node server has the same value at **runtime** (fixes “Missing required environment variable: NEXT_PUBLIC_API_BASE” after deploy).

The repo’s `frontend/railway.toml` passes it via `dockerfileArgs = { NEXT_PUBLIC_API_BASE = "${{NEXT_PUBLIC_API_BASE}}" }`. In Railway → Frontend → **Variables**, define `NEXT_PUBLIC_API_BASE` (e.g. `https://${{Backend.RAILWAY_PUBLIC_DOMAIN}}/api/v1`), then **redeploy** so the frontend **rebuilds**. If the build-arg is empty, the Docker build will fail early—check that the variable exists and is not blank.

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
| Backend  | `YTDLP_YOUTUBE_PLAYER_CLIENT` | `tv_embedded` (optional; same default in app code) |
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
| `FORMAT_NOT_AVAILABLE` / "Requested format is not available" (YouTube) | Do **not** set `player_client=ios` without a PO token. Keep `YTDLP_YOUTUBE_PLAYER_CLIENT=tv_embedded` (default in code) or leave unset. See [PO Token Guide](https://github.com/yt-dlp/yt-dlp/wiki/PO-Token-Guide). |
| `YTDLP_COOKIES_BASE64` exceeds maximum length 32768 | Delete that variable (or cancel the pending change), then run `./scripts/railway-cookies-chunks.sh /path/to/cookies.txt` to upload `YTDLP_COOKIES_BASE64_1`, `_2`, … |
| Downloads timeout | Increase service memory in Settings → Resources; Railway default timeout is 5 min |
| Frontend shows API errors / wrong backend | `NEXT_PUBLIC_API_BASE` must point at your backend with `/api/v1`; **redeploy** frontend after changing it. Do not rely on a hardcoded URL — set the variable in Railway. |

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

# View backend logs (use your exact service name, e.g. Backend)
railway logs -s Backend

# View frontend logs
railway logs -s Frontend
```

---

## Support

- Railway Docs: https://docs.railway.app
- FastAPI Docs: https://fastapi.tiangolo.com
- Next.js Docs: https://nextjs.org/docs
- yt-dlp Docs: https://github.com/yt-dlp/yt-dlp

For project-specific issues, refer to the main [README.md](./README.md).

---

## Setup with Railway CLI

Use this after you have a Railway **project** with **two services** (same repo, root directories `backend` and `frontend`) connected to GitHub.

### Terminal paste tips

- Run **one command per line** (or use `;` between commands). Pasting `./scripts/railway-bootstrap.sh` and `cd ...` **without a newline** creates `./scripts/railway-bootstrap.shcd` and fails.
- Do **not** paste lines that start with `#` from docs unless your shell treats them as comments (some copied “smart” `#` characters are not ASCII and zsh may try to run `#` as a command).
- For cookies, use a **real path** to your file, not the placeholder `/path/to/your/cookies.txt`.

The helper scripts **`railway-set-env.sh`**, **`railway-bootstrap.sh`**, and **`railway-cookies-chunks.sh`** resolve service names from `railway status --json` (matching `rootDirectory` `backend` / `frontend`). You can still override with `RAILWAY_BACKEND_SERVICE` / `RAILWAY_FRONTEND_SERVICE`.

### 1. Install and link

```bash
npm install -g @railway/cli
railway login
cd /path/to/youtube-video-downloader
railway link    # pick your project (monorepo root is fine)
```

### 2. Public URLs (once per service)

`-s` must match the **exact** service name (case-sensitive), e.g. `Backend` and `Frontend` as shown in the dashboard.

```bash
railway domain -s Backend
railway domain -s Frontend
```

### 3. Set variables (copy-paste)

Replace `Backend` / `Frontend` with your **exact** Railway service names if they differ.  
The `${{ … }}` tokens must match what Railway shows when you insert a reference (usually the same as the service name).

**Backend:**

```bash
railway variable set --skip-deploys -s Backend \
  ENV=production \
  API_V1_PREFIX=/api/v1 \
  LOG_LEVEL=INFO \
  BLOCK_PRIVATE_NETWORKS=true \
  ALLOWED_URL_SCHEMES=http,https \
  YTDLP_YOUTUBE_PLAYER_CLIENT=tv_embedded \
  YTDLP_USE_IOS_CLIENT=false \
  YTDLP_CONCURRENT_FRAGMENTS=32 \
  YTDLP_STREAM_CHUNK_SIZE=2097152 \
  YTDLP_BUFFER_SIZE=1M \
  YTDLP_SOCKET_TIMEOUT=60 \
  YTDLP_FILE_ACCESS_RETRIES=5 \
  YTDLP_THROTTLED_RATE=50K \
  YTDLP_PREFER_FREE_FORMATS=true

railway variable set --skip-deploys -s Backend \
  'CORS_ORIGINS=https://${{Frontend.RAILWAY_PUBLIC_DOMAIN}}'
```

**Frontend:**

```bash
railway variable set --skip-deploys -s Frontend \
  'NEXT_PUBLIC_API_BASE=https://${{Backend.RAILWAY_PUBLIC_DOMAIN}}/api/v1'
```

If your services use other names, change both `-s` and the `${{…}}` tokens, e.g. `'CORS_ORIGINS=https://${{my-frontend.RAILWAY_PUBLIC_DOMAIN}}'`.

### 4. Redeploy (apply variables / rebuild frontend)

```bash
railway redeploy -y -s Backend
railway redeploy -y -s Frontend
```

`NEXT_PUBLIC_*` is baked at **build** time; always redeploy the frontend after changing it.

### 5. Verify

```bash
railway variable list -s Backend -k
railway variable list -s Frontend -k
railway logs -s Backend
railway logs -s Frontend
```

Open `https://<backend-domain>/health` and your frontend URL; test **Fetch formats** in the UI.

### Helper scripts (from monorepo root)

**Full flow** (variables + try domains + redeploy both services) — run after `railway login` and `railway link`:

```bash
chmod +x scripts/railway-bootstrap.sh scripts/railway-set-env.sh   # first time only
./scripts/railway-bootstrap.sh
```

**Variables only** (no redeploy; prints redeploy commands):

```bash
./scripts/railway-set-env.sh
```

Override service slugs / reference names if needed:

```bash
RAILWAY_BACKEND_SERVICE=my-api \
RAILWAY_FRONTEND_SERVICE=my-web \
RAILWAY_BACKEND_REF=MyApi \
RAILWAY_FRONTEND_REF=MyWeb \
./scripts/railway-set-env.sh
```

### Optional: cookies for YouTube (CLI)

Railway **rejects any single variable longer than 32,768 characters**. A full browser `cookies.txt` often base64-encodes to more than that — you will see:

`Variable 'YTDLP_COOKIES_BASE64' value exceeds maximum length of 32768`

**Fix:** (1) In the Railway dashboard, **delete** the variable `YTDLP_COOKIES_BASE64` (or discard the pending change) so deploy is unblocked. (2) Upload the file in chunks using the helper script (sets `YTDLP_COOKIES_BASE64_1`, `_2`, … — decoded by `backend/entrypoint.sh`):

```bash
chmod +x scripts/railway-cookies-chunks.sh
./scripts/railway-cookies-chunks.sh --delete-single /path/to/cookies.txt
# Or delete YTDLP_COOKIES_BASE64 manually in the UI, then:
./scripts/railway-cookies-chunks.sh /path/to/cookies.txt
```

Override service name if needed: `RAILWAY_BACKEND_SERVICE=Backend ./scripts/railway-cookies-chunks.sh cookies.txt`

If the file is small enough (base64 ≤ 32KB), the script uploads a single `YTDLP_COOKIES_BASE64` instead.

**Manual one-liner** (only when base64 fits):

```bash
base64 < cookies.txt | tr -d '\n' | railway variable set YTDLP_COOKIES_BASE64 --stdin -s Backend
```
