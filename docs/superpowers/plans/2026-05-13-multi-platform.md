# Multi-Platform Support Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Surface yt-dlp's 1,000+ platform support in the UI — platform detected from backend and shown as a badge; frontend updated with multi-platform branding and an icon strip.

**Architecture:** Backend adds a `platform` field to `VideoInfo` populated from yt-dlp's `extractor_key`. Frontend extends the Zod schema to accept `platform`, updates the URL form with new copy and a static icon strip, and renders a platform badge next to the video title.

**Tech Stack:** Python/FastAPI/Pydantic (backend), Next.js/TypeScript/Tailwind/Zod (frontend)

---

### Task 1: Add `platform` field to `VideoInfo` model + tests

**Files:**
- Modify: `backend/app/models/video.py`
- Modify: `backend/tests/test_services.py`

- [ ] **Step 1: Write the failing test**

Add to `backend/tests/test_services.py` in the `TestFetchFormats` class:

```python
@patch("app.services.yt_dlp_service.yt_dlp.YoutubeDL")
def test_fetch_formats_includes_platform(self, mock_ydl_class: MagicMock) -> None:
    """Test that VideoInfo includes platform from extractor_key."""
    mock_info = {
        "title": "Test Video",
        "thumbnail": None,
        "duration": 60,
        "extractor_key": "Youtube",
        "formats": [
            {
                "format_id": "22",
                "ext": "mp4",
                "height": 720,
                "vcodec": "avc1",
                "acodec": "mp4a",
                "filesize": 1000,
            }
        ],
    }
    mock_ydl = MagicMock()
    mock_ydl.extract_info.return_value = mock_info
    mock_ydl_class.return_value.__enter__.return_value = mock_ydl

    result = YtDlpService.fetch_formats("https://www.youtube.com/watch?v=test")

    assert result.platform == "Youtube"

@patch("app.services.yt_dlp_service.yt_dlp.YoutubeDL")
def test_fetch_formats_platform_none_when_missing(self, mock_ydl_class: MagicMock) -> None:
    """Test that platform is None when extractor_key is absent."""
    mock_info = {
        "title": "Test Video",
        "thumbnail": None,
        "duration": 60,
        "formats": [
            {
                "format_id": "22",
                "ext": "mp4",
                "height": 720,
                "vcodec": "avc1",
                "acodec": "mp4a",
                "filesize": 1000,
            }
        ],
    }
    mock_ydl = MagicMock()
    mock_ydl.extract_info.return_value = mock_info
    mock_ydl_class.return_value.__enter__.return_value = mock_ydl

    result = YtDlpService.fetch_formats("https://www.youtube.com/watch?v=test")

    assert result.platform is None
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd backend
python -m pytest tests/test_services.py::TestFetchFormats::test_fetch_formats_includes_platform tests/test_services.py::TestFetchFormats::test_fetch_formats_platform_none_when_missing -v
```

Expected: FAIL — `VideoInfo` has no `platform` attribute / assertion error.

- [ ] **Step 3: Add `platform` field to `VideoInfo`**

In `backend/app/models/video.py`, add after `video_id`:

```python
platform: str | None = Field(
    default=None,
    description="Platform name as reported by yt-dlp (e.g. 'Youtube', 'TikTok', 'Vimeo')",
)
```

The full `VideoInfo` class becomes:

```python
class VideoInfo(BaseModel):
    """Model representing video metadata and available formats."""

    title: str = Field(
        ...,
        description="Video title",
        min_length=1,
    )
    thumbnail_url: str | None = Field(
        default=None,
        description="URL of the video thumbnail image",
    )
    duration_seconds: int | None = Field(
        default=None,
        description="Video duration in seconds",
        ge=0,
    )
    video_id: str | None = Field(
        default=None,
        description="Platform-specific video identifier when available (e.g. YouTube id)",
    )
    platform: str | None = Field(
        default=None,
        description="Platform name as reported by yt-dlp (e.g. 'Youtube', 'TikTok', 'Vimeo')",
    )
    formats: list[Format] = Field(
        ...,
        description="List of available formats",
        min_length=1,
    )

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "title": "Example Video Title",
                "thumbnail_url": "https://example.com/thumb.jpg",
                "duration_seconds": 180,
                "platform": "Youtube",
                "formats": [
                    {
                        "id": "22",
                        "quality_label": "720p",
                        "mime_type": "video/mp4",
                        "filesize_bytes": 12345678,
                        "is_audio_only": False,
                        "is_video_only": False,
                    }
                ],
            }
        }
    )
```

- [ ] **Step 4: Run tests to verify they still fail (service not updated yet)**

```bash
cd backend
python -m pytest tests/test_services.py::TestFetchFormats::test_fetch_formats_includes_platform -v
```

Expected: FAIL — `result.platform` is `None`, not `"Youtube"`.

- [ ] **Step 5: Commit model change**

```bash
git add backend/app/models/video.py backend/tests/test_services.py
git commit -m "test(models): add platform field tests to VideoInfo"
```

---

### Task 2: Populate `platform` in `_extract_video_info`

**Files:**
- Modify: `backend/app/services/yt_dlp_service.py` (around line 420)

- [ ] **Step 1: Update `_extract_video_info` to extract platform**

Find the `_extract_video_info` method in `backend/app/services/yt_dlp_service.py` (around line 420). Replace:

```python
    @classmethod
    def _extract_video_info(cls, info: dict[str, Any]) -> VideoInfo:
        """Extract and normalize video information from yt-dlp output."""
        title = info.get("title", "Unknown Title")
        thumbnail = info.get("thumbnail")
        duration = cls._extract_duration(info.get("duration"))

        formats = cls._normalize_formats(info.get("formats", []))
        merged_formats = cls._create_merged_formats(formats)
        all_formats = merged_formats + formats
        cls._sort_formats(all_formats)

        vid = info.get("id")
        video_id = str(vid) if vid is not None else None

        return VideoInfo(
            title=title,
            thumbnail_url=thumbnail,
            duration_seconds=duration,
            video_id=video_id,
            formats=all_formats,
        )
```

With:

```python
    @classmethod
    def _extract_video_info(cls, info: dict[str, Any]) -> VideoInfo:
        """Extract and normalize video information from yt-dlp output."""
        title = info.get("title", "Unknown Title")
        thumbnail = info.get("thumbnail")
        duration = cls._extract_duration(info.get("duration"))

        formats = cls._normalize_formats(info.get("formats", []))
        merged_formats = cls._create_merged_formats(formats)
        all_formats = merged_formats + formats
        cls._sort_formats(all_formats)

        vid = info.get("id")
        video_id = str(vid) if vid is not None else None

        raw_platform = info.get("extractor_key") or info.get("extractor") or None
        platform = raw_platform.split(":")[0].strip() if raw_platform else None

        return VideoInfo(
            title=title,
            thumbnail_url=thumbnail,
            duration_seconds=duration,
            video_id=video_id,
            platform=platform,
            formats=all_formats,
        )
```

Note: `.split(":")[0]` strips playlist suffixes like `"Youtube:playlist"` → `"Youtube"`.

- [ ] **Step 2: Run the two new tests — expect both to pass**

```bash
cd backend
python -m pytest tests/test_services.py::TestFetchFormats::test_fetch_formats_includes_platform tests/test_services.py::TestFetchFormats::test_fetch_formats_platform_none_when_missing -v
```

Expected: both PASS.

- [ ] **Step 3: Run the full test suite — no regressions**

```bash
cd backend
python -m pytest -v 2>&1 | tail -20
```

Expected: all previously passing tests still pass.

- [ ] **Step 4: Run ruff + mypy**

```bash
cd backend
python -m ruff check app/services/yt_dlp_service.py app/models/video.py
python -m mypy app/services/yt_dlp_service.py app/models/video.py --ignore-missing-imports
```

Expected: no errors.

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/yt_dlp_service.py
git commit -m "feat(backend): populate platform field in VideoInfo from yt-dlp extractor_key"
```

---

### Task 3: Frontend — Zod schema + URL form branding + platform icon strip

**Files:**
- Modify: `frontend/lib/api-client.ts`
- Modify: `frontend/components/video/url-form.tsx`

- [ ] **Step 1: Extend `VideoInfoSchema` in `api-client.ts`**

Find `VideoInfoSchema` in `frontend/lib/api-client.ts` and add `platform`:

```ts
export const VideoInfoSchema = z.object({
  title: z.string(),
  thumbnail_url: z.string().nullable(),
  duration_seconds: z.number().nullable(),
  video_id: z.string().nullable().optional(),
  platform: z.string().nullable().optional(),
  formats: z.array(FormatSchema),
})
```

- [ ] **Step 2: Update `url-form.tsx` — placeholder, subtitle, and platform icon strip**

Replace the entire content of `frontend/components/video/url-form.tsx` with:

```tsx
'use client'

import { useState } from 'react'
import { Download, AlertCircle } from 'lucide-react'
import { z } from 'zod'

import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Alert, AlertDescription } from '@/components/ui/alert'
import { FormatsRequestSchema } from '@/lib/api-client'

interface UrlFormProps {
  onSubmit: (url: string) => void
  isLoading?: boolean
}

const PLATFORMS = [
  {
    name: 'YouTube',
    href: 'https://youtube.com',
    svg: (
      <svg viewBox="0 0 24 24" className="h-4 w-4" fill="currentColor" aria-hidden="true">
        <path d="M23.5 6.19a3.02 3.02 0 0 0-2.12-2.14C19.54 3.5 12 3.5 12 3.5s-7.54 0-9.38.55A3.02 3.02 0 0 0 .5 6.19C0 8.04 0 12 0 12s0 3.96.5 5.81a3.02 3.02 0 0 0 2.12 2.14C4.46 20.5 12 20.5 12 20.5s7.54 0 9.38-.55a3.02 3.02 0 0 0 2.12-2.14C24 15.96 24 12 24 12s0-3.96-.5-5.81zM9.75 15.52V8.48L15.82 12l-6.07 3.52z" />
      </svg>
    ),
  },
  {
    name: 'TikTok',
    href: 'https://tiktok.com',
    svg: (
      <svg viewBox="0 0 24 24" className="h-4 w-4" fill="currentColor" aria-hidden="true">
        <path d="M19.59 6.69a4.83 4.83 0 0 1-3.77-4.25V2h-3.45v13.67a2.89 2.89 0 0 1-2.88 2.5 2.89 2.89 0 0 1-2.89-2.89 2.89 2.89 0 0 1 2.89-2.89c.28 0 .54.04.79.1V9.01a6.33 6.33 0 0 0-.79-.05 6.34 6.34 0 0 0-6.34 6.34 6.34 6.34 0 0 0 6.34 6.34 6.34 6.34 0 0 0 6.33-6.34V8.69a8.18 8.18 0 0 0 4.78 1.52V6.75a4.85 4.85 0 0 1-1.01-.06z" />
      </svg>
    ),
  },
  {
    name: 'Twitter/X',
    href: 'https://twitter.com',
    svg: (
      <svg viewBox="0 0 24 24" className="h-4 w-4" fill="currentColor" aria-hidden="true">
        <path d="M18.244 2.25h3.308l-7.227 8.26 8.502 11.24H16.17l-5.214-6.817L4.99 21.75H1.68l7.73-8.835L1.254 2.25H8.08l4.713 6.231zm-1.161 17.52h1.833L7.084 4.126H5.117z" />
      </svg>
    ),
  },
  {
    name: 'Instagram',
    href: 'https://instagram.com',
    svg: (
      <svg viewBox="0 0 24 24" className="h-4 w-4" fill="currentColor" aria-hidden="true">
        <path d="M12 2.163c3.204 0 3.584.012 4.85.07 3.252.148 4.771 1.691 4.919 4.919.058 1.265.069 1.645.069 4.849 0 3.205-.012 3.584-.069 4.849-.149 3.225-1.664 4.771-4.919 4.919-1.266.058-1.644.07-4.85.07-3.204 0-3.584-.012-4.849-.07-3.26-.149-4.771-1.699-4.919-4.92-.058-1.265-.07-1.644-.07-4.849 0-3.204.013-3.583.07-4.849.149-3.227 1.664-4.771 4.919-4.919 1.266-.057 1.645-.069 4.849-.069zM12 0C8.741 0 8.333.014 7.053.072 2.695.272.273 2.69.073 7.052.014 8.333 0 8.741 0 12c0 3.259.014 3.668.072 4.948.2 4.358 2.618 6.78 6.98 6.98C8.333 23.986 8.741 24 12 24c3.259 0 3.668-.014 4.948-.072 4.354-.2 6.782-2.618 6.979-6.98.059-1.28.073-1.689.073-4.948 0-3.259-.014-3.667-.072-4.947-.196-4.354-2.617-6.78-6.979-6.98C15.668.014 15.259 0 12 0zm0 5.838a6.162 6.162 0 1 0 0 12.324 6.162 6.162 0 0 0 0-12.324zM12 16a4 4 0 1 1 0-8 4 4 0 0 1 0 8zm6.406-11.845a1.44 1.44 0 1 0 0 2.881 1.44 1.44 0 0 0 0-2.881z" />
      </svg>
    ),
  },
  {
    name: 'Vimeo',
    href: 'https://vimeo.com',
    svg: (
      <svg viewBox="0 0 24 24" className="h-4 w-4" fill="currentColor" aria-hidden="true">
        <path d="M23.977 6.416c-.105 2.338-1.739 5.543-4.894 9.609-3.268 4.247-6.026 6.37-8.29 6.37-1.409 0-2.578-1.294-3.553-3.881L5.322 11.4C4.603 8.816 3.834 7.522 3.01 7.522c-.179 0-.806.378-1.881 1.132L0 7.197c1.185-1.044 2.351-2.084 3.501-3.128C5.08 2.701 6.266 1.984 7.055 1.91c1.867-.18 3.016 1.1 3.447 3.838.465 2.953.789 4.789.971 5.507.539 2.45 1.131 3.674 1.776 3.674.502 0 1.256-.796 2.265-2.385 1.004-1.589 1.54-2.797 1.612-3.628.144-1.371-.395-2.061-1.612-2.061-.574 0-1.167.121-1.777.391 1.186-3.868 3.434-5.757 6.762-5.637 2.473.06 3.628 1.664 3.478 4.807z" />
      </svg>
    ),
  },
  {
    name: 'SoundCloud',
    href: 'https://soundcloud.com',
    svg: (
      <svg viewBox="0 0 24 24" className="h-4 w-4" fill="currentColor" aria-hidden="true">
        <path d="M11.56 8.87V17h8.76a2.74 2.74 0 0 0 .58-5.42 4.27 4.27 0 0 0-8.34-2.71zm-1.1 8.13H9.3V9.5a4.3 4.3 0 0 1 1.16.23v7.27zm-2.27 0H7.06V11.3a4.37 4.37 0 0 1 1.13.69v5.01zm-2.26 0H4.8v-4.05a4.35 4.35 0 0 1 1.13-.47v4.52zm-2.27 0H2.53v-3.2a2.7 2.7 0 0 1 1.13-.39v3.59zm-2.27 0H.27v-2.26a1.37 1.37 0 0 1 1.12.1v2.16z" />
      </svg>
    ),
  },
]

export function UrlForm({ onSubmit, isLoading = false }: UrlFormProps) {
  const [url, setUrl] = useState('')
  const [error, setError] = useState<string | null>(null)

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault()
    setError(null)

    try {
      const validated = FormatsRequestSchema.parse({ url: url.trim() })
      onSubmit(validated.url)
    } catch (err) {
      if (err instanceof z.ZodError) {
        setError(err.errors[0]?.message || 'Invalid URL')
      } else {
        setError('An error occurred while validating the URL')
      }
    }
  }

  return (
    <form onSubmit={handleSubmit} className="space-y-4">
      <div className="space-y-2">
        <div className="flex flex-col sm:flex-row gap-2">
          <Input
            type="text"
            placeholder="Paste a YouTube, TikTok, Instagram, or any supported URL"
            value={url}
            onChange={(e) => {
              setUrl(e.target.value)
              setError(null)
            }}
            disabled={isLoading}
            className="flex-1"
            aria-label="Video URL"
          />
          <Button type="submit" disabled={isLoading || !url.trim()} className="w-full sm:w-auto sm:min-w-[140px]">
            {isLoading ? (
              <>
                <div className="h-4 w-4 animate-spin rounded-full border-2 border-current border-t-transparent" />
                Loading...
              </>
            ) : (
              <>
                <Download className="h-4 w-4" />
                Fetch Formats
              </>
            )}
          </Button>
        </div>

        {error && (
          <Alert variant="destructive">
            <AlertCircle className="h-4 w-4" />
            <AlertDescription>{error}</AlertDescription>
          </Alert>
        )}
      </div>

      {/* Platform icon strip */}
      <div className="flex flex-wrap items-center gap-3">
        {PLATFORMS.map((p) => (
          <a
            key={p.name}
            href={p.href}
            target="_blank"
            rel="noopener noreferrer"
            title={p.name}
            className="text-muted-foreground/50 hover:text-foreground transition-colors"
            tabIndex={-1}
            aria-label={p.name}
          >
            {p.svg}
          </a>
        ))}
        <a
          href="https://github.com/yt-dlp/yt-dlp/blob/master/supportedsites.md"
          target="_blank"
          rel="noopener noreferrer"
          className="text-xs text-muted-foreground hover:text-foreground transition-colors"
        >
          and 1,000+ more →
        </a>
      </div>

      <p className="text-sm text-muted-foreground">
        Download videos from YouTube, TikTok, Twitter, Instagram, Vimeo, and 1,000+ sites
      </p>
    </form>
  )
}
```

- [ ] **Step 3: Run TypeScript type-check**

```bash
cd frontend
npx tsc --noEmit 2>&1 | head -30
```

Expected: no errors related to `platform` or `url-form.tsx`.

- [ ] **Step 4: Commit**

```bash
git add frontend/lib/api-client.ts frontend/components/video/url-form.tsx
git commit -m "feat(frontend): add platform to VideoInfoSchema; update URL form copy and platform icon strip"
```

---

### Task 4: Frontend — platform badge next to video title

**Files:**
- Modify: `frontend/components/video/formats-table.tsx`

- [ ] **Step 1: Add platform badge in the video metadata section**

In `frontend/components/video/formats-table.tsx`, find the video title block (around line 272):

```tsx
<div className="flex-1 min-w-0 text-center sm:text-left w-full">
  <h2 className="text-lg sm:text-xl font-semibold mb-1 sm:mb-2 break-words">{videoInfo.title}</h2>
  {videoInfo.duration_seconds && (
    <p className="text-xs sm:text-sm text-muted-foreground">
      Duration: {formatDuration(videoInfo.duration_seconds)}
    </p>
  )}
</div>
```

Replace with:

```tsx
<div className="flex-1 min-w-0 text-center sm:text-left w-full">
  <div className="flex flex-wrap items-start justify-center sm:justify-start gap-2 mb-1 sm:mb-2">
    <h2 className="text-lg sm:text-xl font-semibold break-words">{videoInfo.title}</h2>
    {videoInfo.platform && (
      <span className="inline-flex items-center gap-1 bg-muted text-muted-foreground text-xs rounded-full px-2 py-0.5 shrink-0 mt-0.5 sm:mt-1">
        <span className="h-1.5 w-1.5 rounded-full bg-current opacity-60" />
        {videoInfo.platform}
      </span>
    )}
  </div>
  {videoInfo.duration_seconds && (
    <p className="text-xs sm:text-sm text-muted-foreground">
      Duration: {formatDuration(videoInfo.duration_seconds)}
    </p>
  )}
</div>
```

- [ ] **Step 2: Run TypeScript type-check**

```bash
cd frontend
npx tsc --noEmit 2>&1 | head -30
```

Expected: no errors.

- [ ] **Step 3: Run full backend test suite one final time**

```bash
cd backend
python -m pytest -v 2>&1 | tail -10
```

Expected: all tests pass.

- [ ] **Step 4: Commit and push**

```bash
git add frontend/components/video/formats-table.tsx
git commit -m "feat(frontend): show platform badge next to video title"
git push origin main
```

---

## Self-Review

- **Spec coverage:**
  - ✅ `platform: str | None` added to `VideoInfo` model (Task 1)
  - ✅ `_extract_video_info` extracts `extractor_key` (Task 2)
  - ✅ `VideoInfoSchema` extended with `platform` (Task 3)
  - ✅ Subtitle updated to "Download videos from YouTube, TikTok, Twitter, Instagram, Vimeo, and 1,000+ sites" (Task 3)
  - ✅ Placeholder updated (Task 3)
  - ✅ Platform icon strip: YouTube, TikTok, Twitter/X, Instagram, Vimeo, SoundCloud + "1,000+ more →" link (Task 3)
  - ✅ Platform badge next to video title (Task 4)
  - ✅ Badge only rendered when `platform` is truthy (Task 4)
  - ✅ Tests for `platform` populated and `platform` null (Task 1–2)

- **No placeholders:** all steps include exact code.
- **Type consistency:** `platform: str | None` (Python) ↔ `z.string().nullable().optional()` (TS) ↔ `videoInfo.platform` (JSX) — consistent throughout.
