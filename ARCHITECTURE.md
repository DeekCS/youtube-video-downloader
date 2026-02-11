# Architecture Overview

This document provides a detailed architectural overview of the Video Downloader system.

## High-Level Architecture

```
┌─────────────┐
│   Browser   │
│   (User)    │
└──────┬──────┘
       │ HTTPS
       │
       ▼
┌─────────────────────────────────────────┐
│         Next.js 16 Frontend             │
│  ┌─────────────────────────────────┐   │
│  │  Server Components (RSC)        │   │
│  │  - Layout, Page Shell           │   │
│  └──────────────┬──────────────────┘   │
│                 │                       │
│  ┌──────────────▼──────────────────┐   │
│  │  Client Components              │   │
│  │  - URL Form (validation)        │   │
│  │  - Formats Table (display)      │   │
│  │  - React Query (caching)        │   │
│  └──────────────┬──────────────────┘   │
└─────────────────┼───────────────────────┘
                  │ fetch()
                  │ /api/v1/videos/*
                  ▼
┌─────────────────────────────────────────┐
│         FastAPI Backend                 │
│  ┌──────────────────────────────────┐  │
│  │  API Layer (v1)                  │  │
│  │  - POST /videos/formats          │  │
│  │  - GET/POST /videos/download     │  │
│  └────────┬─────────────────────────┘  │
│           │                             │
│  ┌────────▼─────────────────────────┐  │
│  │  Service Layer                   │  │
│  │  - URL validation & safety       │  │
│  │  - Format normalization          │  │
│  │  - Error handling                │  │
│  └────────┬─────────────────────────┘  │
│           │                             │
│  ┌────────▼─────────────────────────┐  │
│  │  yt-dlp Wrapper                  │  │
│  │  - Subprocess spawning           │  │
│  │  - Streaming stdout              │  │
│  └────────┬─────────────────────────┘  │
└───────────┼──────────────────────────────┘
            │ HTTP(S)
            ▼
   ┌─────────────────┐
   │  Video Platform │
   │  (YouTube, etc) │
   └─────────────────┘
```

## Component Breakdown

### 1. Browser (Client)

**Responsibilities:**
- Render UI
- Capture user input (video URL)
- Display video metadata and formats
- Trigger downloads via navigation

**Key Libraries:**
- Modern browser (ES2022+)
- Fetch API for requests

---

### 2. Next.js 16 Frontend

**Technology Stack:**
- Next.js 16 (App Router)
- React 19
- TypeScript (strict)
- Tailwind CSS + shadcn/ui
- React Query v5
- zod

**Architecture Pattern:**
- Server Components for static shell
- Client Components for interactivity
- API client with strict validation

**File Structure:**
```
frontend/
├── app/
│   ├── layout.tsx         # Server Component (shell)
│   ├── page.tsx           # Server Component (page shell)
│   ├── providers.tsx      # Client Component (React Query)
│   └── globals.css
├── components/
│   ├── video/
│   │   ├── downloader.tsx     # Client (state + mutations)
│   │   ├── url-form.tsx       # Client (form + validation)
│   │   └── formats-table.tsx  # Client (display)
│   └── ui/                    # shadcn components
└── lib/
    ├── api-client.ts      # API calls + zod schemas
    ├── env.ts             # Typed env validation
    └── utils.ts           # Helpers
```

**Data Flow:**
1. User enters URL → `url-form.tsx` validates with zod
2. `downloader.tsx` calls `fetchFormats()` via React Query
3. `api-client.ts` POSTs to backend, validates response with zod
4. `formats-table.tsx` renders validated `VideoInfo`
5. User clicks Download → browser navigates to `GET /videos/download?...`

**Security:**
- Client-side URL validation (zod)
- Server response validation (zod)
- No sensitive data in client
- HTTPS enforced in production

---

### 3. FastAPI Backend

**Technology Stack:**
- Python 3.11+
- FastAPI + Pydantic v2
- yt-dlp
- uvicorn (ASGI server)

**Architecture Pattern:**
- Layered architecture (API → Service → Integration)
- Domain-driven error taxonomy
- Streaming responses for downloads

**File Structure:**
```
backend/
├── app/
│   ├── main.py                # App creation + middleware
│   ├── core/
│   │   ├── config.py          # Settings (env vars)
│   │   └── logging.py         # Structured logs
│   ├── models/
│   │   └── video.py           # Pydantic models (contract)
│   ├── services/
│   │   ├── errors.py          # Domain exceptions
│   │   └── yt_dlp_service.py  # Integration
│   └── api/
│       ├── errors.py          # Exception handlers
│       └── v1/
│           ├── router.py      # Router aggregation
│           └── endpoints/
│               └── videos.py  # Endpoint logic
└── tests/                     # Unit + integration tests
```

**Request Flow:**

#### Fetch Formats Flow
```
POST /api/v1/videos/formats
  ├─ videos.py: fetch_formats() endpoint
  │    ├─ Validate FormatsRequest (Pydantic)
  │    └─ Call YtDlpService.fetch_formats()
  │
  └─ yt_dlp_service.py: fetch_formats()
       ├─ Normalize URL (SSRF protection)
       ├─ Call yt_dlp.YoutubeDL.extract_info()
       ├─ Normalize raw formats to Format models
       └─ Return VideoInfo
```

#### Download Flow
```
GET /api/v1/videos/download?url=...&format_id=...
  ├─ videos.py: download_video_get() endpoint
  │    ├─ Validate params (query strings)
  │    ├─ Fetch formats to verify format_id exists
  │    └─ Call YtDlpService.download_format()
  │
  └─ yt_dlp_service.py: download_format()
       ├─ Normalize URL
       ├─ Spawn subprocess: yt-dlp -f <format_id> -o - <url>
       └─ Return Popen handle
  │
  └─ videos.py: _stream_download()
       ├─ Read chunks from subprocess.stdout
       ├─ Yield chunks to StreamingResponse
       └─ Cleanup subprocess on disconnect
```

**Error Handling:**
- Domain exceptions map to HTTP status codes
- Stable error codes for client handling
- Structured error responses (JSON)

**Security:**
- CORS locked to known origins
- Private network URL blocking (SSRF)
- URL logging sanitized (no query params)
- Input validation (Pydantic)

---

### 4. yt-dlp Integration

**Responsibilities:**
- Extract video metadata (title, thumbnail, duration, formats)
- Stream video data to stdout

**Integration Modes:**

#### Metadata Extraction (Python API)
```python
with yt_dlp.YoutubeDL(opts) as ydl:
    info = ydl.extract_info(url, download=False)
```

#### Download Streaming (Subprocess)
```python
subprocess.Popen([
    "yt-dlp",
    "-f", format_id,
    "-o", "-",  # stdout
    url
], stdout=PIPE)
```

**Why subprocess for download?**
- Avoids blocking Python GIL
- Easier to terminate on client disconnect
- More robust for large files

---

## Data Models and Contracts

### API Contract (Backend ↔ Frontend)

#### POST /api/v1/videos/formats

**Request:**
```typescript
{
  url: string  // Video URL
}
```

**Response:**
```typescript
{
  title: string
  thumbnail_url: string | null
  duration_seconds: number | null
  formats: Array<{
    id: string
    quality_label: string
    mime_type: string
    filesize_bytes: number | null
    is_audio_only: boolean
    is_video_only: boolean
  }>
}
```

**Errors:**
- `400` → `INVALID_URL`
- `404` → `NOT_FOUND`
- `422` → `UNSUPPORTED_PLATFORM`
- `502` → `YTDLP_FAILED`

#### GET /api/v1/videos/download

**Query Parameters:**
- `url`: Video URL
- `format_id`: Format ID from formats list

**Response:**
- Streaming binary data
- Headers:
  - `Content-Disposition: attachment; filename="..."`
  - `Content-Type: video/mp4` (or appropriate)

---

## Deployment Architecture

### Local Development
```
┌─────────────────┐    ┌─────────────────┐
│  Frontend       │    │  Backend        │
│  localhost:3000 │───▶│  localhost:8000 │
│  (Next dev)     │    │  (uvicorn)      │
└─────────────────┘    └─────────────────┘
```

### Railway Production
```
┌──────────────────────────────────────┐
│         Railway Project              │
│                                      │
│  ┌─────────────────────────────┐    │
│  │  Frontend Service           │    │
│  │  - Next.js build + start    │    │
│  │  - Public domain            │    │
│  │  - NEXT_PUBLIC_API_BASE env │    │
│  └─────────────┬───────────────┘    │
│                │ HTTPS                │
│                ▼                     │
│  ┌─────────────────────────────┐    │
│  │  Backend Service            │    │
│  │  - Docker (yt-dlp+ffmpeg)   │    │
│  │  - Public domain            │    │
│  │  - CORS_ORIGINS env         │    │
│  └─────────────────────────────┘    │
│                                      │
└──────────────────────────────────────┘
```

**Service Communication:**
- Frontend makes HTTPS requests to backend
- CORS configured to allow only frontend domain
- Both services have public Railway domains

---

## Scalability Considerations

### Current Limitations
- **Synchronous downloads**: Blocks worker during download
- **Ephemeral filesystem**: Can't store temp files long-term
- **No caching**: Each request re-fetches metadata

### Scaling Strategies

#### 1. Horizontal Scaling (Short-term)
- Increase Uvicorn workers (2 → 4 → 8)
- Railway auto-scales based on CPU/memory

#### 2. Background Jobs (Medium-term)
```
Browser → Frontend → Backend API → Job Queue (Redis)
                                        ↓
                                   Worker Pool
                                        ↓
                                  Object Storage (S3)
                                        ↓
                                   Download URL
```

**Benefits:**
- Non-blocking API responses
- Support for long downloads
- Resumable downloads

#### 3. Caching Layer (Medium-term)
```
Backend → Redis Cache → yt-dlp
           ↑
           └─ Cache video metadata (5 min TTL)
```

**Benefits:**
- Reduce yt-dlp calls
- Faster format fetching
- Lower platform API rate limits

---

## Security Architecture

### Threat Model

#### SSRF (Server-Side Request Forgery)
**Risk:** Attacker provides URL to internal services
**Mitigation:**
- Block private IP ranges (192.168.x.x, 10.x.x.x, 127.x.x.x)
- Block localhost and ::1
- Allowlist URL schemes (http, https only)

#### Command Injection
**Risk:** Attacker injects shell commands via URL
**Mitigation:**
- yt-dlp Python API for metadata (no shell)
- Subprocess with list args (not shell=True)
- Input validation before subprocess

#### CORS Bypass
**Risk:** Unauthorized frontend calls API
**Mitigation:**
- CORS middleware with explicit origins
- No `*` wildcard in production

#### Rate Limiting (Future)
**Risk:** Abuse via repeated downloads
**Mitigation:**
- Add rate limiting middleware (slowapi)
- Per-IP quotas (Redis-backed)

---

## Observability

### Current Logging
- Structured JSON logs in production
- Request/response logging (sanitized URLs)
- Error taxonomy with stable codes

### Future Monitoring (Roadmap)
- **Metrics:** Prometheus (request rate, error rate, latency)
- **Tracing:** OpenTelemetry (distributed traces)
- **Alerts:** Railway notifications + Sentry

---

## Future Architecture (v0.2.0+)

### Proposed: Background Job System
```
┌─────────┐    ┌─────────┐    ┌─────────┐    ┌──────────┐
│ Browser │───▶│ FastAPI │───▶│  Redis  │◀───│  Worker  │
└─────────┘    └─────────┘    │  Queue  │    │  (RQ)    │
     │              │          └─────────┘    └────┬─────┘
     │              │                               │
     │         ┌────▼──────┐                  ┌────▼──────┐
     │         │ Redis DB  │                  │    S3     │
     │         │ (job IDs) │                  │ (storage) │
     │         └───────────┘                  └───────────┘
     │                                             │
     └─────────────────────────────────────────────┘
              (Presigned download URL)
```

**Benefits:**
- Async downloads
- Progress tracking
- Resumable downloads
- Persistent storage

---

## Questions?

See the main [README.md](README.md) or [CONTRIBUTING.md](CONTRIBUTING.md) for more details.
