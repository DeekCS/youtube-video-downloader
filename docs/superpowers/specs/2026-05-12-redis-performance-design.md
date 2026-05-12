# Performance Improvement: Redis-Backed Task State & Format Cache

**Date:** 2026-05-12  
**Status:** Approved  
**Scope:** Backend task store, format cache, multi-worker support, frontend API timeouts

---

## Problem

The app is locked to a single uvicorn worker because all state lives in Python process memory:

- Download task progress stored in `dict[str, DownloadTask]` (in-memory, per-process)
- Format cache stored in `TTLCache` (in-memory, lost on restart, not shared)
- Frontend API calls have no timeout — requests can hang indefinitely

This means concurrent downloads queue behind each other, a server restart loses all cached metadata, and a hung request blocks the UI with no recovery path.

---

## Approach

Replace in-memory state with Redis as a shared state layer. All uvicorn workers read and write task/cache data through Redis, allowing 4 parallel workers. Frontend API calls gain `AbortController` timeouts.

---

## Architecture

```
Browser
  ↓
Next.js → FastAPI (4 workers, round-robin)
              ↓                    ↓
           Redis               yt-dlp subprocess
       (task state +          (writes progress to
        format cache)          Redis every ~500ms)
              ↓
         Local disk (temp files — safe, all workers share same filesystem)
```

---

## Components

### New: `backend/app/core/redis.py`
- Creates a single `redis.asyncio.ConnectionPool` at startup
- Exposes `get_redis()` — returns the shared client, reused across all requests
- Initialized in `lifespan()` in `main.py`, closed on shutdown

### Modified: `backend/app/core/config.py`
Add settings:
```
REDIS_URL: str = "redis://localhost:6379/0"
REDIS_ENABLED: bool = True
```

### Modified: `backend/app/services/download_tasks.py`
Replace `dict + threading.Lock` with Redis hash operations:

| Operation | Redis command |
|---|---|
| `create_task(id)` | `HSET ytdl:task:{id} ... EX 7200` |
| `get_task(id)` | `HGETALL ytdl:task:{id}` → deserialize |
| `update_task(id, **fields)` | `HSET ytdl:task:{id} field value` |
| `remove_task(id)` | `DEL ytdl:task:{id}` |
| `cleanup_stale()` | `SCAN` for `ytdl:task:*` keys + check `created_at` |

The `DownloadTask` dataclass is serialized to/from a flat Redis hash (all fields as strings, typed on read).

Background thread writes progress to Redis directly via `update_task()` using the sync Redis client (`redis.Redis`, not asyncio) since the thread runs outside the event loop.

### Modified: `backend/app/services/yt_dlp_service.py`
Replace `cachetools.TTLCache` with Redis:

- Cache key: `ytdl:formats:{sha256(url)}`
- On `fetch_formats()`: `GET` key → if hit, deserialize and return; if miss, call yt-dlp → `SETEX key TTL json`
- Uses sync Redis client (called from thread pool via `asyncio.to_thread`)

### Modified: `backend/Dockerfile`
```
UVICORN_WORKERS=1  →  UVICORN_WORKERS=4
```

### Modified: `docker-compose.yml`
Add Redis service:
```yaml
redis:
  image: redis:7-alpine
  restart: unless-stopped
  command: redis-server --appendonly yes --maxmemory 128mb --maxmemory-policy allkeys-lru
  volumes:
    - redis_data:/data
  mem_limit: 192m
```
Add resource limits to backend service (memory: 1g, cpus: 1.0).

### Modified: `frontend/lib/api-client.ts`
Wrap `fetchFormats` and `startDownload` with `AbortController`:
```typescript
const controller = new AbortController()
const timeoutId = setTimeout(() => controller.abort(), 30_000)
// pass signal to fetch()
// catch AbortError → throw ApiError('INTERNAL_ERROR', 'Request timed out')
// finally: clearTimeout(timeoutId)
```

---

## Data Flow: Download Lifecycle

```
POST /videos/download/start
  → validate input
  → create Redis task {status: pending, ...} with 2h TTL
  → spawn background thread(task_id)
      → yt-dlp subprocess runs
      → thread parses stdout → update_task() → Redis every ~500ms
      → on complete: set status=completed, file_path=...
      → on error: set status=failed, error=...
  → return {download_id, filename}

GET /videos/download/{id}/progress  (SSE)
  → any worker → HGETALL Redis → serialize → stream to browser
  → (all workers see same state)

GET /videos/download/{id}/file
  → HGET file_path from Redis
  → stream local file (same machine, all workers share disk)
  → DEL task key after stream completes
```

---

## Error Handling

| Scenario | Behavior |
|---|---|
| Redis unreachable at startup | Log warning, fall back to in-memory store, start normally |
| Redis connection lost mid-request | `get_task()` returns `None` → 404; download continues on disk |
| Redis error during progress update | Log warning, skip update (download not affected) |
| Format cache Redis error | Cache miss → call yt-dlp fresh (safe, correct) |
| Frontend request timeout (30s) | `AbortError` caught → `ApiError('INTERNAL_ERROR', 'Request timed out')` |

**Health endpoint** reports Redis connectivity status alongside existing checks.

---

## Testing

**Existing tests** remain green — public API of `download_tasks.py` (`create_task`, `get_task`, `remove_task`, `cleanup_stale`) is unchanged.

**New tests:**
- `backend/tests/test_download_tasks_redis.py` — mocks `redis.Redis` to verify task CRUD, TTL set, field updates
- `backend/tests/test_yt_dlp_service_cache.py` — verifies Redis cache hit skips yt-dlp, cache miss calls yt-dlp and stores result
- `backend/tests/test_redis_fallback.py` — verifies app starts and functions when Redis is unreachable (in-memory fallback)

---

## Files Changed

| File | Change |
|---|---|
| `backend/app/core/redis.py` | **New** — connection pool |
| `backend/app/core/config.py` | Add `REDIS_URL`, `REDIS_ENABLED` |
| `backend/app/services/download_tasks.py` | Replace in-memory dict with Redis |
| `backend/app/services/yt_dlp_service.py` | Replace TTLCache with Redis |
| `backend/app/main.py` | Init/close Redis in lifespan |
| `backend/app/core/health.py` | Add Redis health check |
| `backend/Dockerfile` | `UVICORN_WORKERS=4` |
| `backend/.env.example` | Add `REDIS_URL` |
| `docker-compose.yml` | Add Redis service + resource limits |
| `frontend/lib/api-client.ts` | Add `AbortController` timeouts |

---

## Out of Scope

- Celery / distributed task queue (not needed at this scale)
- Shared object storage for temp files (not needed — single machine)
- Authentication / access control
- Prometheus metrics / OpenTelemetry
