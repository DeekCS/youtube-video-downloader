# YouTube Video Downloader

A production-ready, self-hosted multi-platform video downloader with a clean web interface.

## Architecture

```
Browser → Next.js 16 (App Router) → FastAPI (/api/v1) → yt-dlp → Video Platform
```

### Tech Stack

**Backend:**
- FastAPI + Pydantic v2 (Python 3.11+)
- yt-dlp for video metadata extraction and download
- uv for dependency management
- ruff + mypy for linting and type checking
- pytest for testing

**Frontend:**
- Next.js 16 (App Router, Server Components)
- TypeScript (strict mode)
- shadcn/ui + Tailwind CSS
- React Query v5 for data fetching
- zod for runtime validation
- pnpm for package management

**Deployment:**
- Railway (two services: backend + frontend)
- Node 20 LTS (frontend)
- Python 3.11+ (backend)

## Project Structure

```
youtube-video-downloader/
├── backend/                 # FastAPI application
│   ├── app/
│   │   ├── main.py         # Application entry point
│   │   ├── core/           # Configuration, logging
│   │   ├── models/         # Pydantic models (API contracts)
│   │   ├── services/       # Business logic (yt-dlp integration)
│   │   └── api/            # REST endpoints
│   ├── tests/              # Unit and integration tests
│   ├── pyproject.toml      # Dependencies and tooling config
│   ├── Dockerfile          # Production container
│   └── .env.example        # Environment variables template
├── frontend/               # Next.js application
│   ├── app/                # App Router pages and layouts
│   ├── components/         # React components
│   ├── lib/                # Utilities and API client
│   ├── public/             # Static assets
│   ├── package.json        # Dependencies
│   └── .env.example        # Environment variables template
├── docker-compose.yml      # Local development orchestration
└── README.md               # This file
```

## API Contract

### Endpoint: `POST /api/v1/videos/formats`

**Request:**
```json
{
  "url": "https://www.youtube.com/watch?v=..."
}
```

**Response:**
```json
{
  "title": "Video Title",
  "thumbnail_url": "https://...",
  "duration_seconds": 180,
  "formats": [
    {
      "id": "22",
      "quality_label": "720p",
      "mime_type": "video/mp4",
      "filesize_bytes": 12345678,
      "is_audio_only": false,
      "is_video_only": false
    }
  ]
}
```

### Endpoint: `GET /api/v1/videos/download`

**Query Parameters:**
- `url`: Video URL (required)
- `format_id`: Format ID from formats list (required)

**Response:**
- Streaming file download with appropriate `Content-Disposition` and `Content-Type` headers

### Error Response Format

All errors return:
```json
{
  "code": "INVALID_URL",
  "message": "Human-readable error message"
}
```

**Error Codes:**
- `INVALID_URL`: Malformed or blocked URL
- `UNSUPPORTED_PLATFORM`: Platform not supported by yt-dlp
- `NOT_FOUND`: Video not found or unavailable
- `FORMAT_NOT_AVAILABLE`: Requested format not available
- `YTDLP_FAILED`: yt-dlp execution failed
- `INTERNAL_ERROR`: Unexpected server error

## Local Development

### Quick Setup (Recommended)

Run the automated setup script:

```bash
./setup.sh
```

This will check prerequisites, install dependencies, and configure environment files.

### Prerequisites

- Python 3.11+
- Node 20 LTS
- pnpm (`npm install -g pnpm`)
- uv (`curl -LsSf https://astral.sh/uv/install.sh | sh`)

### Backend Setup

```bash
cd backend

# Install dependencies
uv sync

# Copy environment template
cp .env.example .env

# Run development server (with auto-reload)
uv run uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

# Run tests
uv run pytest

# Lint and type check
uv run ruff check .
uv run mypy app
```

### Frontend Setup

```bash
cd frontend

# Install dependencies
pnpm install

# Copy environment template
cp .env.example .env.local

# Edit .env.local and set:
# NEXT_PUBLIC_API_BASE=http://localhost:8000/api/v1

# Run development server
pnpm dev

# Lint and type check
pnpm lint
pnpm typecheck
```

### Using Docker Compose (Optional)

```bash
# Start both services
docker-compose up

# Backend: http://localhost:8000
# Frontend: http://localhost:3000
```

## Railway Deployment

### Backend Service

1. Create a new Railway service from this repository
2. Set root directory to `backend/`
3. Configure environment variables:
   ```
   ENV=production
   API_V1_PREFIX=/api/v1
   CORS_ORIGINS=https://your-frontend.up.railway.app
   LOG_LEVEL=INFO
   ```
4. Railway will detect the Dockerfile and build automatically
5. Verify deployment:
   - `GET /health` → `{"status": "healthy"}`
   - `GET /docs` → FastAPI Swagger UI

### Frontend Service

1. Create a new Railway service from this repository
2. Set root directory to `frontend/`
3. Configure environment variables:
   ```
   NEXT_PUBLIC_API_BASE=https://your-backend.up.railway.app/api/v1
   ```
4. Railway will auto-detect Next.js and run:
   ```bash
   pnpm install
   pnpm build
   pnpm start
   ```
5. Verify: Navigate to the frontend URL and test the downloader flow

### Monitoring

- Use Railway logs to inspect yt-dlp failures (structured JSON logs in production)
- Watch for `YTDLP_FAILED` errors with full context
- Scale Uvicorn workers if downloads become heavy (edit Dockerfile `CMD`)

## Updating API Contracts

When changing the API shape:

1. Update Pydantic models in `backend/app/models/video.py`
2. Update zod schemas in `frontend/lib/api-client.ts`
3. Run backend tests: `uv run pytest`
4. Run frontend type check: `pnpm typecheck`
5. Test end-to-end: formats fetch → download

## Security Considerations

- **SSRF Protection:** Backend blocks private/localhost URLs by default
- **CORS:** Locked to known frontend origins only
- **URL Logging:** Only hostname + hash are logged, not full URL (sensitive query params)
- **Legal Notice:** Frontend displays clear ToS/legal constraints

## Roadmap

### Completed (MVP)
- ✅ YouTube video metadata and single-format download
- ✅ Clean, responsive shadcn/ui interface
- ✅ Strict typing (Pydantic + zod)
- ✅ Railway deployment

### Future Enhancements
- [ ] **Best Quality Merges:** Add ffmpeg support for bestvideo+bestaudio merging
- [ ] **More Platforms:** Extend beyond YouTube (Vimeo, Twitter, etc.) via yt-dlp
- [ ] **Background Jobs:** Offload downloads to Celery/RQ with job polling
- [ ] **Object Storage:** Store downloads in S3/R2 for resumable access
- [ ] **User History:** Track downloads (requires auth + database)
- [ ] **Rate Limiting:** Prevent abuse (per-IP or per-user quotas)
- [ ] **Observability:** OpenTelemetry tracing, Prometheus metrics

## Legal Notice

This tool is intended for downloading content you own or have explicit rights to download. Users are responsible for complying with applicable copyright laws, terms of service, and platform policies. Misuse may violate laws in your jurisdiction.

## License

MIT License - See LICENSE file for details

## Contributing

Contributions welcome! Please:
1. Follow existing code style (ruff for Python, prettier for TypeScript)
2. Add tests for new features
3. Update API contracts in both backend models and frontend zod schemas
4. Keep the README updated

---

**Built with ❤️ using FastAPI, Next.js, and yt-dlp**
# Last updated: Fri Feb 13 13:51:02 +03 2026
