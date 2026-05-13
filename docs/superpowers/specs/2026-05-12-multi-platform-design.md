# Multi-Platform Support Design

**Date:** 2026-05-12  
**Status:** Approved

## Problem

The app UI presents itself as YouTube-only (subtitle, placeholder, title). The backend already uses yt-dlp which supports 1,000+ platforms (TikTok, Twitter/X, Instagram, Vimeo, SoundCloud, Facebook, etc.) with no code changes needed. The goal is to surface that capability in the UI without adding complexity.

## Approach

Approach B: backend returns the detected platform name; frontend shows a static platform icon strip and a dynamic platform badge on results.

---

## Backend Changes

### `backend/app/models/video.py`
Add `platform: str | None = None` to `VideoInfo`.

```python
class VideoInfo(BaseModel):
    title: str
    thumbnail_url: str | None
    duration_seconds: float | None
    video_id: str | None = None
    platform: str | None = None   # NEW — e.g. "YouTube", "TikTok", "Vimeo"
    formats: list[Format]
```

### `backend/app/services/yt_dlp_service.py`
In `_build_video_info()` (the method that constructs `VideoInfo` from raw yt-dlp info dict), extract:

```python
platform = info.get("extractor_key") or info.get("extractor") or None
# Normalize: title-case, strip trailing suffixes like ":playlist"
```

Pass `platform=platform` when constructing `VideoInfo`.

No other backend changes required.

---

## Frontend Changes

### `frontend/lib/api-client.ts`
Extend `VideoInfoSchema`:
```ts
platform: z.string().nullable().optional()
```

### `frontend/components/video/url-form.tsx`

**Subtitle:**  
`"Download videos from YouTube and other platforms"`  
→ `"Download videos from YouTube, TikTok, Twitter, Instagram, Vimeo, and 1,000+ sites"`

**Placeholder:**  
`"https://www.youtube.com/watch?v=..."`  
→ `"Paste a YouTube, TikTok, Instagram, or any supported URL"`

**Platform icon strip** (new, below the input field):  
Static row of small SVG/icon badges for: YouTube · TikTok · Twitter/X · Instagram · Vimeo · SoundCloud.  
Rendered in greyscale, colored on hover. Links to `https://github.com/yt-dlp/yt-dlp/blob/master/supportedsites.md` with `target="_blank"`.  
Label: `"and 1,000+ more →"`

### `frontend/components/video/formats-table.tsx` (or `url-form.tsx`)

**Platform badge** on the video info result — a small pill next to the video title:
```
● TikTok   (or whatever platform string was returned)
```
- Rendered only when `videoInfo.platform` is truthy
- Pill style: `bg-muted text-muted-foreground text-xs rounded-full px-2 py-0.5`
- No platform-specific colors; keep it neutral

---

## Data Flow

```
User pastes URL → POST /videos/formats
  → yt-dlp extracts info dict
  → _build_video_info() reads info["extractor_key"]
  → VideoInfo { platform: "TikTok", ... }
  → Frontend receives platform
  → Badge rendered next to title
```

---

## Error Handling

- If `platform` is `null`/missing, the badge is simply not rendered — no error state needed.
- No backend validation changes: yt-dlp itself raises `UnsupportedPlatformError` for truly unsupported URLs.

---

## Testing

- Unit test: `_build_video_info()` returns `platform="YouTube"` for a YouTube info dict.
- Unit test: `_build_video_info()` returns `platform=None` when `extractor_key` absent.
- Frontend: `VideoInfoSchema` parses correctly when `platform` is present, absent, or null.
- Manual: paste a TikTok URL → badge shows "TikTok"; paste a YouTube URL → badge shows "YouTube".

---

## Out of Scope

- Per-platform authentication (cookies, tokens) — yt-dlp handles this via existing cookie settings
- Curated platform catalogue / supported sites page
- Platform-specific format labeling (e.g. "Twitter 1080p" vs "YouTube 1080p")
