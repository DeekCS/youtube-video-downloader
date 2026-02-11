# GitHub & Railway CI/CD Setup Guide

Your local git repo is ready! Follow these steps to complete the integration:

## Step 1: Create GitHub Repository

1. Go to [github.com/new](https://github.com/new)
2. Create a new repository with these settings:
   - **Repository name:** `youtube-video-downloader`
   - **Description:** "YouTube/Instagram video downloader with FastAPI backend and Next.js frontend"
   - **Visibility:** Public (or Private if preferred)
   - **Initialize repository:** ✗ **Leave unchecked** (we already have git history)
   - Click **Create repository**

3. You'll see a page with commands. Copy the repository URL (it should be `https://github.com/deekcs/youtube-video-downloader.git`)

## Step 2: Push Code to GitHub

Run this command to push your code to GitHub:

```bash
cd /Users/macbookpro/Desktop/youtube-video-downloader
git push -u origin main
```

When prompted for authentication:
- **Username:** `deekcs`
- **Password:** Use a GitHub Personal Access Token (not your GitHub password)
  - Go to [github.com/settings/tokens](https://github.com/settings/tokens)
  - Click "Generate new token" (Fine-grained tokens recommended)
  - Give it permissions for: `repo`, `read:repo_hook`
  - Copy the token and paste it when prompted

Alternative: Use GitHub CLI if installed (`gh auth login`)

## Step 3: Connect Railway to GitHub

1. Go to your Railway project: https://railway.com/project/b388db69-4611-423e-bc8d-34e957a3d0f2

2. In the **Settings** tab, look for **GitHub** integration
   - Click "Connect GitHub" or "GitHub App"
   - Authorize Railway to access your repositories
   - Select the `youtube-video-downloader` repository
   - Railway automatically detects services from `docker-compose.yml`

3. Configure deploy settings:
   - **Watch branch:** Set to `main`
   - **Auto-deploy on push:** Should be enabled by default

## Step 4: Deploy Backend Service

After Railway connects to GitHub:

1. Go to your Railway project
2. Click on the **Backend** service
3. In the **Deploy** tab, you should see:
   - Source: `GitHub`
   - Repo: `youtube-video-downloader`
   - Branch: `main`
   - Status: Ready to deploy

4. Click **Deploy** to trigger the first deployment

5. Once deployed, Railway provides a public URL - this will be your backend API endpoint

## Step 5: Update Frontend API URL

After backend is deployed on Railway:

1. Note the Railway backend public URL (e.g., `https://your-app-xyz.railway.app`)
2. Update [frontend/lib/env.ts](../frontend/lib/env.ts):
   ```typescript
   export const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || 'https://your-app-xyz.railway.app'
   ```

3. Push this change:
   ```bash
   git add frontend/lib/env.ts
   git commit -m "Update API URL for Railway deployment"
   git push
   ```

4. Railway auto-deploys the frontend update

## Step 6: Test Deployed Services

Once both services are deployed:

1. **Frontend:** Visit `https://your-frontend-url.railway.app`
2. **Backend API:** Visit `https://your-backend-url.railway.app/docs` (Swagger UI)
3. Test downloading a video from the frontend

## Troubleshooting

**GitHub push fails:**
- Verify you're using a GitHub Personal Access Token (not password)
- Check token has `repo` scope rights

**Railway deployment fails:**
- Check Railway logs: Project → Service → Logs tab
- Ensure `docker-compose.yml` is in repo root
- Verify environment variables are set if needed

**Videos download but show errors:**
- Check Railway backend logs for yt-dlp errors
- Ensure FFmpeg is available in Docker image
- Test with: `curl https://your-backend/api/v1/videos/formats?url=https://youtube.com/watch?v=...`

## Continuous Deployment Workflow

After setup, deployment is automatic:

```bash
# Make changes locally
git add .
git commit -m "Your change"
git push origin main

# Railway auto-deploys within 1-2 minutes
# Check Railway dashboard for deployment status
```

---

**Next steps after deployment:**
- [ ] Create GitHub repo and push
- [ ] Connect Railway to GitHub
- [ ] Deploy backend service
- [ ] Update frontend API URL
- [ ] Deploy frontend service
- [ ] Test deployed application
- [ ] (Optional) Set up Expo mobile app for downloading
