# Video Downloader Backend

FastAPI backend service that wraps yt-dlp for video metadata extraction and streaming downloads.

## Setup

```bash
# Install uv if not already installed
curl -LsSf https://astral.sh/uv/install.sh | sh

# Install dependencies
uv sync

# Copy environment template
cp .env.example .env

# Run development server
uv run uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

## Development

```bash
# Run tests
uv run pytest

# Lint
uv run ruff check .

# Format
uv run ruff format .

# Type check
uv run mypy app

# Run with coverage
uv run pytest --cov=app --cov-report=html
```

## API Documentation

Once running, visit:
- Swagger UI: http://localhost:8000/docs
- ReDoc: http://localhost:8000/redoc
- Health check: http://localhost:8000/health

## Project Structure

```
backend/
├── app/
│   ├── main.py              # Application entry point
│   ├── core/
│   │   ├── config.py        # Settings and configuration
│   │   └── logging.py       # Structured logging setup
│   ├── models/
│   │   └── video.py         # Pydantic models (API contracts)
│   ├── services/
│   │   ├── errors.py        # Domain exceptions
│   │   └── yt_dlp_service.py # yt-dlp integration
│   └── api/
│       ├── errors.py        # Exception handlers
│       └── v1/
│           ├── router.py    # v1 API router
│           └── endpoints/
│               └── videos.py # Video endpoints
├── tests/
│   ├── conftest.py          # Test fixtures
│   ├── test_api/            # API endpoint tests
│   └── test_services/       # Service layer tests
├── pyproject.toml           # Dependencies and tooling
├── Dockerfile               # Production container
└── .env.example             # Environment template
```
