# Playlist and Single-Track Download Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Support downloading a single track or an entire playlist from yt-dlp-supported URLs, with playlist downloads delivered to the browser as one zip file.

**Architecture:** Keep the current single-track formats flow intact and add an explicit download mode for `track` vs `playlist`. Track mode continues to use the existing format picker and streamed download task. Playlist mode resolves playlist metadata, downloads each entry server-side, zips the results, and returns one browser download while reusing the existing progress/task plumbing.

**Tech Stack:** FastAPI, yt-dlp, Python 3.11+, zipfile/stdlib, Next.js 16, TypeScript, React Query, zod, pytest, pnpm.

---

### Task 1: Add playlist-aware backend contracts and resolution helpers

**Files:**
- Modify: `backend/app/models/video.py`
- Modify: `backend/app/services/yt_dlp_service.py`
- Modify: `backend/app/api/v1/endpoints/videos.py`
- Test: `backend/tests/test_services.py`
- Test: `backend/tests/test_api.py`

- [ ] **Step 1: Write the failing tests**

```python
def test_fetch_playlist_metadata_returns_entries(mock_ydl_class):
    mock_info = {
        "_type": "playlist",
        "title": "Demo Playlist",
        "extractor_key": "Soundcloud:playlist",
        "entries": [
            {
                "id": "111",
                "title": "Track One",
                "thumbnail": None,
                "duration": 120,
                "extractor_key": "Soundcloud",
                "formats": [
                    {
                        "format_id": "hls_aac_160k",
                        "ext": "m4a",
                        "abr": 160,
                        "vcodec": "none",
                        "acodec": "aac",
                    }
                ],
            }
        ],
    }
    result = YtDlpService.fetch_playlist_info("https://soundcloud.com/user/sets/demo")
    assert result.title == "Demo Playlist"
    assert result.entry_count == 1
    assert result.entries[0].title == "Track One"
```

```python
def test_playlist_endpoint_returns_playlist_info(client, mocker):
    mocker.patch(
        "app.api.v1.endpoints.videos.YtDlpService.fetch_playlist_info",
        return_value=PlaylistInfo(
            title="Demo Playlist",
            entry_count=1,
            entries=[PlaylistEntry(id="111", title="Track One", url="https://example.com/1")],
        ),
    )
    response = client.post("/api/v1/videos/playlist", json={"url": "https://soundcloud.com/user/sets/demo"})
    assert response.status_code == 200
    assert response.json()["entry_count"] == 1
```

```python
def test_download_request_requires_format_id_for_track_mode():
    with pytest.raises(ValidationError):
        DownloadRequest(
            url="https://www.youtube.com/watch?v=test",
            download_mode=DownloadMode.track,
        )
```

```python
def test_download_request_accepts_playlist_mode_without_format_id():
    request = DownloadRequest(
        url="https://soundcloud.com/user/sets/demo",
        download_mode=DownloadMode.playlist,
    )
    assert request.format_id is None
```

```python
def test_start_download_rejects_missing_format_id_for_track_mode(client):
    response = client.post(
        "/api/v1/videos/download/start",
        json={"url": "https://www.youtube.com/watch?v=test"},
    )
    assert response.status_code == 422
    assert response.json()["detail"][0]["type"] == "missing"
```

- [ ] **Step 2: Run the tests and verify they fail**

Run:

```bash
cd backend
uv run pytest tests/test_services.py -k playlist -v
uv run pytest tests/test_api.py -k download_start -v
```

Expected: failures for missing playlist metadata support and missing mode-aware validation.

- [ ] **Step 3: Implement the minimal backend contract**

```python
class DownloadMode(str, Enum):
    track = "track"
    playlist = "playlist"

class PlaylistEntry(BaseModel):
    id: str
    title: str
    url: str | None = None

class PlaylistInfo(BaseModel):
    title: str
    entry_count: int
    entries: list[PlaylistEntry]
```

```python
@classmethod
def fetch_playlist_info(cls, url: str) -> PlaylistInfo:
    normalized_url = cls.normalize_url(url)
    ydl_opts = cls._build_ydl_options()
    ydl_opts["noplaylist"] = False
    ydl_opts["extract_flat"] = True
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(normalized_url, download=False)
    if not info or not isinstance(info, dict):
        raise VideoNotFoundError()
    entries: list[PlaylistEntry] = []
    for entry in info.get("entries", []):
        if isinstance(entry, dict):
            entries.append(
                PlaylistEntry(
                    id=str(entry.get("id") or entry.get("url") or ""),
                    title=str(entry.get("title") or "Unknown Title"),
                    url=entry.get("webpage_url") or entry.get("url"),
                )
            )
    if not entries:
        raise VideoNotFoundError("Playlist has no playable entries")
    return PlaylistInfo(
        title=str(info.get("title") or "Untitled Playlist"),
        entry_count=len(entries),
        entries=entries,
    )
```

```python
class DownloadRequest(BaseModel):
    url: str
    format_id: str | None = None
    download_mode: DownloadMode = DownloadMode.track

    @model_validator(mode="after")
    def validate_mode_fields(self) -> "DownloadRequest":
        if self.download_mode == DownloadMode.track and not self.format_id:
            raise ValueError("format_id is required for track downloads")
        return self
```

- [ ] **Step 4: Run the tests and verify they pass**

Run:

```bash
cd backend
uv run pytest backend/tests/test_services.py -k playlist -v
uv run pytest backend/tests/test_api.py -k download_start -v
```

Expected: playlist metadata test passes and the API validates the new request contract.

- [ ] **Step 5: Commit**

```bash
git add backend/app/models/video.py backend/app/services/yt_dlp_service.py backend/app/api/errors.py backend/app/services/errors.py backend/tests/test_services.py backend/tests/test_api.py
git commit -m "feat: add playlist-aware backend contracts"
```

### Task 2: Implement playlist downloads and zip packaging

**Files:**
- Modify: `backend/app/services/yt_dlp_service.py`
- Modify: `backend/app/services/download_tasks.py`
- Modify: `backend/app/api/v1/endpoints/videos.py`
- Modify: `backend/app/models/video.py`
- Test: `backend/tests/test_services.py`
- Test: `backend/tests/test_api.py`

- [ ] **Step 1: Write the failing tests**

```python
def test_playlist_download_creates_zip(mock_ydl_class, tmp_path):
    task = create_task("abc123", filename="Demo Playlist.zip")
    YtDlpService.download_playlist_to_zip("https://soundcloud.com/user/sets/demo", task)
    assert task.status == "completed"
    assert task.file_path.endswith(".zip")
```

```python
def test_download_progress_reports_playlist_entries(client):
    response = client.get("/api/v1/videos/download/abc123/progress")
    assert response.status_code in (200, 404)
```

- [ ] **Step 2: Run the tests and verify they fail**

Run:

```bash
cd backend
uv run pytest tests/test_services.py -k "playlist_download or playlist" -v
uv run pytest tests/test_api.py -k progress -v
```

Expected: missing playlist download implementation and playlist-aware progress fields.

- [ ] **Step 3: Implement playlist download execution**

```python
@classmethod
def download_playlist_to_zip(cls, url: str, task: DownloadTask) -> None:
    info = cls.fetch_playlist_info(url)
    temp_dir = tempfile.mkdtemp(prefix="ytdl_playlist_")
    tracks_dir = os.path.join(temp_dir, "tracks")
    os.makedirs(tracks_dir, exist_ok=True)
    for index, entry in enumerate(info.entries, start=1):
        update_task(
            task.task_id,
            status="downloading",
            current_entry=entry.title,
            completed_entries=index - 1,
            total_entries=info.entry_count,
        )
        downloaded = cls.download_to_directory(entry.url or url, tracks_dir)
        final_name = (
            f"{index:03d} - {cls._sanitize_cli_filename(entry.title)}"
            f"{os.path.splitext(downloaded)[1]}"
        )
        os.replace(downloaded, os.path.join(tracks_dir, final_name))
    zip_path = os.path.join(temp_dir, f"{cls._sanitize_cli_filename(info.title)}.zip")
    with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for root, _dirs, files in os.walk(tracks_dir):
            for file_name in files:
                full_path = os.path.join(root, file_name)
                zf.write(full_path, arcname=file_name)
    task.file_path = zip_path
    task.content_type = "application/zip"
    task.status = "completed"
```

```python
class DownloadTask:
    playlist_title: str = ""
    total_entries: int = 0
    completed_entries: int = 0
    current_entry: str = ""
```

```python
@router.post("/download/start")
async def start_download(request: Request, body: DownloadRequest) -> DownloadStartResponse:
    normalized_url = YtDlpService.normalize_url(body.url)
    if body.download_mode == "playlist":
        playlist_info = await asyncio.to_thread(
            YtDlpService.fetch_playlist_info,
            normalized_url,
        )
        task_id = uuid.uuid4().hex[:16]
        task = create_task(
            task_id,
            filename=f"{playlist_info.title}.zip",
            content_type="application/zip",
        )
        task.playlist_title = playlist_info.title
        task.total_entries = playlist_info.entry_count
        thread = threading.Thread(
            target=lambda: YtDlpService.download_playlist_to_zip(normalized_url, task),
            daemon=True,
        )
        thread.start()
        return DownloadStartResponse(download_id=task_id, filename=task.filename)
    video_info = await asyncio.to_thread(YtDlpService.fetch_formats, normalized_url)
    selected_format = next(
        (fmt for fmt in video_info.formats if fmt.id == body.format_id),
        None,
    )
    if selected_format is None:
        raise FormatNotAvailableError(
            f"Format '{body.format_id}' not found in available formats"
        )
    task_id = uuid.uuid4().hex[:16]
    task = create_task(
        task_id,
        filename=f"{video_info.title}.mp4",
        content_type=selected_format.mime_type,
    )
    thread = threading.Thread(
        target=lambda: YtDlpService.download_single_with_progress(
            normalized_url,
            body.format_id or "",
            task,
        ),
        daemon=True,
    )
    thread.start()
    return DownloadStartResponse(download_id=task_id, filename=task.filename)

@router.post("/playlist", response_model=PlaylistInfo)
async def fetch_playlist(request: Request, body: FormatsRequest) -> PlaylistInfo:
    return await asyncio.to_thread(YtDlpService.fetch_playlist_info, body.url)
```

- [ ] **Step 4: Run the tests and verify they pass**

Run:

```bash
cd backend
uv run pytest backend/tests/test_services.py backend/tests/test_api.py -v
```

Expected: playlist download job creates a zip and progress still works for track jobs.

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/yt_dlp_service.py backend/app/services/download_tasks.py backend/app/api/v1/endpoints/videos.py backend/app/models/video.py backend/tests/test_services.py backend/tests/test_api.py
git commit -m "feat: add playlist zip downloads"
```

### Task 3: Add playlist mode to the frontend download flow

**Files:**
- Modify: `frontend/lib/api-client.ts`
- Modify: `frontend/components/video/downloader.tsx`
- Modify: `frontend/components/video/formats-table.tsx`
- Test: `frontend` lint/typecheck via existing scripts

- [ ] **Step 1: Write the failing tests**

```tsx
it("shows playlist action when playlist metadata is returned", () => {
  render(<Downloader />)
  expect(screen.getByText("Download playlist")).toBeInTheDocument()
})
```

```ts
it("passes playlist mode to startDownload", async () => {
  await startDownload("https://soundcloud.com/user/sets/demo", "playlist")
})
```

- [ ] **Step 2: Run the checks and verify they fail**

Run:

```bash
cd frontend
pnpm lint
pnpm typecheck
```

Expected: type errors for the new request/response shape and missing playlist UI state.

- [ ] **Step 3: Implement the UI and API client changes**

```ts
export const StartDownloadRequestSchema = z.object({
  url: z.string().min(10).max(2048),
  format_id: z.string().min(1).max(500).optional(),
  download_mode: z.enum(['track', 'playlist']),
})

export const PlaylistEntrySchema = z.object({
  id: z.string(),
  title: z.string(),
  url: z.string().nullable().optional(),
})

export const PlaylistInfoSchema = z.object({
  title: z.string(),
  entry_count: z.number(),
  entries: z.array(PlaylistEntrySchema),
})

export type PlaylistInfo = z.infer<typeof PlaylistInfoSchema>

export async function fetchPlaylistInfo(url: string): Promise<PlaylistInfo> {
  const response = await fetch(`${env.API_BASE}/videos/playlist`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ url }),
  })
  const data = await response.json()
  return PlaylistInfoSchema.parse(data)
}

export async function startDownload(
  url: string,
  formatId?: string,
  downloadMode: 'track' | 'playlist' = 'track'
): Promise<{ downloadId: string; filename: string }> {
  const response = await fetch(`${env.API_BASE}/videos/download/start`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      url,
      format_id: formatId?.trim() || undefined,
      download_mode: downloadMode,
    }),
  })
  const data = await response.json()
  return { downloadId: data.download_id, filename: data.filename }
}
```

```tsx
function Downloader() {
  const [downloadMode, setDownloadMode] = useState<'track' | 'playlist'>('track')
  const [playlistInfo, setPlaylistInfo] = useState<PlaylistInfo | null>(null)
  const handlePlaylistDownload = async () => {
    const info = await fetchPlaylistInfo(originalUrl)
    setPlaylistInfo(info)
    await startDownload(originalUrl, undefined, 'playlist')
  }

  {downloadMode === 'playlist' ? (
    <Button onClick={handlePlaylistDownload}>Download playlist</Button>
  ) : (
    <FormatsTable videoInfo={videoInfo} originalUrl={originalUrl} />
  )}
}
```

```tsx
function FormatsTable({ videoInfo, originalUrl }) {
  const handleDownload = (format) => startDownload(originalUrl, format.id, 'track')
}
```

- [ ] **Step 4: Run the checks and verify they pass**

Run:

```bash
cd frontend
pnpm lint
pnpm typecheck
```

Expected: no TypeScript or lint errors in the updated download flow.

- [ ] **Step 5: Commit**

```bash
git add frontend/lib/api-client.ts frontend/components/video/downloader.tsx frontend/components/video/formats-table.tsx
git commit -m "feat: add playlist mode to download UI"
```

### Task 4: Update docs and run full verification

**Files:**
- Modify: `README.md`
- Modify: `backend/README.md`
- Modify: `frontend/README.md`
- Modify: `docs/superpowers/specs/2026-05-17-playlist-download-design.md` only if implementation forces a spec correction
- Test: `backend/tests/test_api.py`
- Test: `backend/tests/test_services.py`
- Test: `frontend` existing lint/typecheck scripts

- [ ] **Step 1: Write the verification commands in the docs updates**

```bash
cd backend && uv run pytest
cd frontend && pnpm lint && pnpm typecheck
```

- [ ] **Step 2: Run the full test set**

Run:

```bash
cd backend
uv run pytest
uv run ruff check .
uv run mypy app
cd ../frontend
pnpm lint
pnpm typecheck
```

Expected: all commands pass.

- [ ] **Step 3: Update the docs**

```md
## Playlist downloads

Paste a playlist URL and choose **Download playlist** to receive a zip file containing one file per track.
```

- [ ] **Step 4: Commit**

```bash
git add README.md backend/README.md frontend/README.md
git commit -m "docs: document playlist downloads"
```

## Spec Coverage Check

- Single-track downloads remain the default and are covered in Task 1, Task 2, and Task 3.
- Playlist metadata discovery is covered in Task 1.
- Playlist zip downloads are covered in Task 2.
- Frontend playlist actions and mode selection are covered in Task 3.
- Documentation updates and final verification are covered in Task 4.

## Notes

- Keep the current track download path intact; do not rewrite the existing progress model unless the playlist path needs one extra field.
- Prefer the smallest API change that supports both modes: a `download_mode` flag plus optional playlist metadata.
- Preserve existing error codes so the frontend error handling does not need a separate migration.
