# YouTube Video Downloader

A self-hosted multi-platform downloader with a clean web UI, a FastAPI backend, and yt-dlp powering metadata extraction and downloads.

## Features

- Download a single track from supported platforms
- Download an entire playlist as one zip file
- Fetch available formats for track downloads
- Fetch playlist metadata and entry counts
- Real-time progress updates through SSE
- Server-side file handling so the browser gets a local file transfer
- Support for yt-dlp-compatible platforms such as YouTube, SoundCloud, Vimeo, Instagram, TikTok, X/Twitter, and more

## Architecture

```text
Browser -> Next.js 16 frontend -> FastAPI backend -> yt-dlp -> platform
```

## Tech Stack

**Backend**
- FastAPI + Pydantic v2
- yt-dlp
- Python 3.11+
- pytest
- ruff
- mypy

**Frontend**
- Next.js 16 (App Router)
- TypeScript
- React Query
- zod
- Tailwind CSS + shadcn/ui
- pnpm

**Deployment**
- Railway
- Docker

## Project Structure

```text
youtube-video-downloader/
├── backend/
│   ├── app/
│   │   ├── api/
│   │   ├── core/
│   │   ├── models/
│   │   └── services/
│   ├── tests/
│   └── pyproject.toml
├── frontend/
│   ├── app/
│   ├── components/
│   ├── lib/
│   └── package.json
├── docs/
├── docker-compose.yml
└── README.md
```

## Download Modes

### Track mode

Track mode keeps the existing format picker flow:

1. Paste a supported media URL
2. Fetch available formats
3. Pick a format
4. Download the selected track

### Playlist mode

Playlist mode uses a separate metadata flow:

1. Paste a playlist URL
2. Fetch playlist title and entries
3. Start one playlist download job
4. Receive one zip file containing the playlist entries

## API Overview

### `POST /api/v1/videos/formats`

Fetch metadata and formats for a single track.

**Request**
```json
{
  "url": "https://www.youtube.com/watch?v=..."
}
```

### `POST /api/v1/videos/playlist`

Fetch playlist metadata and entries.

**Request**
```json
{
  "url": "https://soundcloud.com/user/sets/demo"
}
```

### `POST /api/v1/videos/download/start`

Start a track or playlist download.

**Track request**
```json
{
  "url": "https://www.youtube.com/watch?v=...",
  "format_id": "22",
  "download_mode": "track"
}
```

**Playlist request**
```json
{
  "url": "https://soundcloud.com/user/sets/demo",
  "download_mode": "playlist"
}
```

### `GET /api/v1/videos/download/{download_id}/progress`

Server-sent events stream for progress updates.

### `GET /api/v1/videos/download/{download_id}/file`

Fetch the completed file after the job finishes.

## Error Codes

- `INVALID_URL`
- `UNSUPPORTED_PLATFORM`
- `NOT_FOUND`
- `FORMAT_NOT_AVAILABLE`
- `YTDLP_FAILED`
- `INTERNAL_ERROR`
- `RATE_LIMITED`

## Local Development

### Prerequisites

- Python 3.11+
- Node 20+
- pnpm
- uv

### Quick start

```bash
./setup.sh
```

### Backend

```bash
cd backend
uv sync
cp .env.example .env
uv run uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

**Backend checks**

```bash
uv run pytest
uv run ruff check .
uv run mypy app
```

### Frontend

```bash
cd frontend
pnpm install
cp .env.example .env.local
pnpm dev
```

**Frontend checks**

```bash
pnpm lint
pnpm typecheck
```

### Docker Compose

```bash
docker-compose up
```

- Frontend: `http://localhost:3000`
- Backend: `http://localhost:8000`

## Environment Variables

### Backend

Typical backend variables include:

- `ENV`
- `API_V1_PREFIX`
- `CORS_ORIGINS`
- `LOG_LEVEL`

### Frontend

- `NEXT_PUBLIC_API_BASE=http://localhost:8000/api/v1`

## CLI

The backend also provides a `video-dl` CLI that uses the same yt-dlp configuration as the API.

```bash
cd backend
uv run video-dl formats "https://www.youtube.com/watch?v=..."
uv run video-dl download "https://www.youtube.com/watch?v=..." -f 22 -y
```

## Security Notes

- Private and localhost URLs are blocked by default
- Frontend and backend are CORS-configured for known origins
- URL logging strips sensitive query data

## Deployment

Railway deploys the backend and frontend as separate services.

- Backend root: `backend/`
- Frontend root: `frontend/`

See `RAILWAY.md` for the full setup guide.

## Contributing

- Follow the existing code style
- Add tests for behavior changes
- Update both backend models and frontend schemas when APIs change
- Keep this README current when features change

## License

MIT
