# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.1.0] - 2026-02-11

### Added

#### Backend
- FastAPI application with Python 3.11+ and Pydantic v2
- yt-dlp integration for video metadata extraction and downloads
- Streaming download support via `GET /api/v1/videos/download`
- Format listing via `POST /api/v1/videos/formats`
- CORS middleware with configurable origins
- Comprehensive error handling with stable error codes
- SSRF protection (blocks private network URLs)
- Structured logging (JSON in production, readable in dev)
- Health check endpoint at `/health`
- Unit and integration tests with pytest
- Docker support with production-ready Dockerfile
- uv for dependency management
- ruff + mypy for linting and type checking

#### Frontend
- Next.js 16 App Router with TypeScript strict mode
- React 19 and Server Components architecture
- shadcn/ui component library with Tailwind CSS
- React Query v5 for data fetching and caching
- zod for runtime validation of API contracts
- Responsive video downloader UI with:
  - URL input form with client-side validation
  - Video metadata display (thumbnail, title, duration)
  - Formats table with quality, type, and file size
  - One-click download buttons
- Legal notice about content rights
- Dark mode support (via shadcn theming)
- pnpm for package management
- ESLint and Prettier for code quality

#### Infrastructure
- Monorepo structure with backend/ and frontend/
- Docker Compose for local development
- Railway deployment guides (RAILWAY.md)
- Quick start guide (QUICKSTART.md)
- Comprehensive README with architecture details
- EditorConfig for consistent coding styles
- MIT License
- Contributing guidelines

### Initial Features
- YouTube video download support
- Multiple format options (video quality, audio-only, etc.)
- Real-time format metadata (filesize, quality labels)
- Streaming downloads (no server-side storage required)
- Self-hosted, no third-party APIs

### Known Limitations
- No ffmpeg merging support yet (merged formats coming in v0.2.0)
- No authentication or rate limiting
- No download history or persistence
- No background job processing (downloads are synchronous)

## [Unreleased]

### Planned for v0.2.0
- ffmpeg support for best quality merged downloads (bestvideo+bestaudio)
- Background job processing (Celery/RQ)
- Object storage integration (S3/R2)
- Download history with user accounts
- Rate limiting and abuse prevention
- Extended platform support beyond YouTube
- Prometheus metrics and OpenTelemetry tracing

---

[0.1.0]: https://github.com/yourusername/video-downloader/releases/tag/v0.1.0
