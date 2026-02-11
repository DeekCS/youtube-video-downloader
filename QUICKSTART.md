# Quick Start Guide

Get the video downloader running locally in minutes.

## Prerequisites

- Python 3.11+
- Node.js 20+
- pnpm (install with `npm install -g pnpm`) - or use npm
- uv (install with `curl -LsSf https://astral.sh/uv/install.sh | sh`)

## Automated Setup (Recommended)

Run the setup script to install everything automatically:

```bash
./setup.sh
```

This will:
- ✅ Check prerequisites
- ✅ Install backend dependencies (uv sync)
- ✅ Install frontend dependencies (pnpm/npm install)
- ✅ Copy environment configuration files
- ✅ Verify everything is ready

Then skip to [Run the App](#run-the-app).

## Manual Setup

If you prefer to set up manually:

### Backend Setup
```bash
cd backend

# Install dependencies
source $HOME/.local/bin/env  # Add uv to PATH
uv sync

# Copy environment template
cp .env.example .env
```

### Frontend Setup
```bash
cd frontend

# Install dependencies
npm install  # or: pnpm install

# Copy environment template
cp .env.example .env.local

# Edit .env.local to set the backend URL:
# NEXT_PUBLIC_API_BASE=http://localhost:8000/api/v1
```

## Run the App

## Option 1: Run with Docker Compose (Recommended)

The fastest way to get started:

```bash
# Clone the repository
git clone <your-repo-url>
cd youtube-video-downloader

# Start both services
docker-compose up

# Access the app
# - Frontend: http://localhost:3000
# - Backend API: http://localhost:8000
# - API Docs: http://localhost:8000/docs
```

## Option 2: Run Services Individually

### Start the Backend

```bash
cd backend

# Install dependencies
uv sync

# Copy environment template
cp .env.example .env

# Run development server
uv run uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

# Verify it's running
curl http://localhost:8000/health
```

### Start the Frontend

In a new terminal:

```bash
cd frontend

# Install dependencies
pnpm install

# Copy environment template
cp .env.example .env.local

# Edit .env.local to set the backend URL:
# NEXT_PUBLIC_API_BASE=http://localhost:8000/api/v1

# Run development server
pnpm dev

# Access at http://localhost:3000
```

## Test the App

1. Open http://localhost:3000 in your browser
2. Paste a YouTube video URL:
   ```
   https://www.youtube.com/watch?v=dQw4w9WgXcQ
   ```
3. Click "Fetch Formats"
4. Select a format and click "Download"

## Common Issues

### Backend: "yt-dlp: command not found"

Install yt-dlp:
```bash
# macOS
brew install yt-dlp

# Ubuntu/Debian
sudo apt install yt-dlp

# Or via pip
pip install yt-dlp
```

### Frontend: "Missing required environment variable"

Make sure `.env.local` exists with:
```
NEXT_PUBLIC_API_BASE=http://localhost:8000/api/v1
```

### CORS Errors

Check that backend `.env` has:
```
CORS_ORIGINS=http://localhost:3000,http://127.0.0.1:3000
```

## Next Steps

- Read the [main README](README.md) for detailed documentation
- See [RAILWAY.md](RAILWAY.md) for deployment instructions
- Check [backend/README.md](backend/README.md) for API details
- Check [frontend/README.md](frontend/README.md) for UI development

## Development Workflow

### Backend

```bash
cd backend

# Run tests
uv run pytest

# Lint and format
uv run ruff check .
uv run ruff format .

# Type check
uv run mypy app
```

### Frontend

```bash
cd frontend

# Lint
pnpm lint

# Type check
pnpm typecheck

# Format
pnpm format
```

---

Happy downloading! 🎥
