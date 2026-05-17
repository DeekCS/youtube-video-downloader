# Playlist and Single-Track Download Design

> **Goal:** Support downloading either a single track or an entire playlist from SoundCloud and other yt-dlp-supported platforms.

**Architecture:** Keep the existing formats lookup and single-track download path, but add an explicit download mode that distinguishes `track` from `playlist`. Track mode preserves the current format picker and stream-to-file flow. Playlist mode resolves playlist metadata separately, downloads each entry server-side into a temporary folder using a best-available single-file selector, then packages the result as a single zip for the browser.

**Tech Stack:** FastAPI, yt-dlp, Python 3.11+, Next.js 16, TypeScript, React Query, zod, zipfile/stdlib.

---

## Problem

The app currently handles individual videos well, but playlist URLs are treated inconsistently. Some SoundCloud URLs resolve to playlist-like payloads, and the current code only exposes a single-track download action in the UI. Users need to be able to:

1. Download one track from a supported URL.
2. Download all tracks from a playlist URL.
3. Receive playlist downloads as one browser-friendly file.

## Proposed Behavior

### Track mode

- User pastes a URL.
- The app fetches formats for the resolved playable item.
- The user selects one format and downloads that single track.
- Existing behavior stays the default when the URL is a single video or track.

### Playlist mode

- User pastes a playlist URL.
- The app resolves the playlist entries with yt-dlp and shows the playlist title plus entry count.
- The backend downloads each entry into a dedicated temp directory.
- The backend creates a zip archive containing one file per track.
- The browser receives the zip as a single download.

## Design Approaches

### Option A: Auto-detect and always do the right thing

Infer playlist vs track automatically from the URL and extractor response.

**Pros:** minimal UI changes.
**Cons:** ambiguous for URLs that can resolve both ways; hard for users to intentionally choose one track from a playlist.

### Option B: Separate track and playlist modes in the UI and API

Expose an explicit mode selector and pass it through the backend.

**Pros:** clear intent, predictable downloads, easy to explain.
**Cons:** slightly more UI and API work.

### Option C: Two-step playlist selection

Fetch playlist entries, let the user choose one track or all tracks.

**Pros:** most flexible.
**Cons:** larger scope, more UI complexity, more branching in backend logic.

**Recommendation:** Option B. It is the smallest design that cleanly supports both single-track and playlist downloads without surprising behavior.

## Backend Design

### Request model

Add a `download_mode` field to the download start request:

- `track`
- `playlist`

The existing `url` and `format_id` fields remain unchanged for track mode. Playlist mode ignores `format_id` and downloads each playlist entry with the best available single-file selector, so the browser receives a zip instead of many individual transfers.

### Metadata resolution

The yt-dlp service keeps the current `fetch_formats()` behavior for track-like items. It also exposes a playlist inspection path that returns playlist title, entry list, and whether the URL is playlist-shaped so the UI can choose between track and playlist actions without guessing.

### Download execution

- Track mode keeps the current progress-tracked file download path.
- Playlist mode iterates over entries, downloads each item to disk, and writes each file into a temp folder.
- After all entries complete, the backend builds a zip archive from that folder.
- The existing progress endpoint should report playlist progress as a higher-level task with entry counts and current entry status.

### File naming

- Single tracks keep the current `{title}.{ext}` style.
- Playlist entries should use stable per-entry filenames derived from track title and item id to avoid collisions.
- The zip filename should use the playlist title.

## Frontend Design

### Download UI

- Keep the current format table for track downloads.
- Add a playlist action when the resolved URL is a playlist.
- For playlists, show a single “Download playlist” action that starts the playlist job and downloads the resulting zip.

### State handling

- Track downloads continue to use the current SSE progress flow.
- Playlist downloads reuse the same connection pattern but show playlist-aware progress text.
- The UI should clearly distinguish “single track” from “playlist” so users know what they are downloading.

## Error Handling

- Invalid or blocked URLs still return `INVALID_URL`.
- Unsupported platforms still return `UNSUPPORTED_PLATFORM`.
- Missing playlist entries or empty playlists should return `NOT_FOUND`.
- Playlist jobs should fail if any entry cannot be resolved and the failure should be surfaced in the progress stream.

## Testing Strategy

### Backend tests

- Resolve a playlist URL to playlist metadata.
- Resolve a SoundCloud playlist-like payload to the first playable track for track mode.
- Start a playlist download job and verify it creates a zip output with one file per entry.
- Verify track mode still uses the existing single-file path.

### Frontend tests

- Render a playlist action when the backend reports playlist content.
- Keep the existing track format table for single-track URLs.
- Verify playlist download progress and completion states.

## Scope Notes

- This design does not add bulk multi-select across individual playlist entries.
- This design does not change the current single-track format picker behavior.
- This design keeps the browser download to a single file for playlists by zipping the downloaded tracks.
