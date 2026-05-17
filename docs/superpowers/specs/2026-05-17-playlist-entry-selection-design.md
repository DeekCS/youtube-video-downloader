# Playlist Entry Selection UX Design

> **Goal:** Replace the track/playlist toggle with an auto-detected playlist explorer that lets users download one track or all available tracks with better UX.

**Architecture:** The URL submit flow auto-detects whether the resolved resource is a single track or playlist. Single tracks continue through the current formats-table workflow. Playlists render a dedicated explorer view with searchable entries, per-entry download actions, and a primary download-all flow that packages available tracks into one zip.

**Tech Stack:** Next.js 16, React, TypeScript, React Query, zod, FastAPI playlist endpoints, existing SSE progress pipeline.

---

## Problem

The current UI forces the user to choose Track vs Playlist before the system resolves the URL. This creates friction and hides useful playlist actions. Users want a playlist URL to directly show playlist entries and let them choose one item or all items without mode switching.

## Approved UX Direction

1. Remove the Track/Playlist toggle from the form.
2. Auto-detect playlist URLs after submit.
3. For playlists, show:
   - Playlist title + counts
   - Search/filter input
   - Entry list (lazy-loaded)
   - `Download all available` button
   - Per-entry `Download track` buttons
4. Keep the existing track format table for non-playlist URLs.

## Behavior Rules

### URL resolution

- Submit URL once.
- If resolved as single track: show existing format picker.
- If resolved as playlist: switch to playlist explorer view automatically.

### Playlist list behavior

- Show first 50 entries initially.
- Provide search/filter by title.
- Lazy-load additional entries on demand.
- Unavailable entries (private/deleted/blocked) are shown disabled with an `Unavailable` badge.

### Download actions

- **Download all available**: uses existing playlist zip job (`download_mode=playlist`) and skips unavailable items.
- **Download track**: starts the existing single-track pipeline for the selected entry URL.

### Progress and errors

- All-download progress: show `completed / total` and current track title.
- Per-track progress: reuse current track progress UI.
- If all-download hits unavailable items, they are skipped instead of failing the full playlist job.
- If no entries are downloadable, show clear empty-state message.

## UI Layout

### Desktop

- Two-column layout:
  - Left: summary card + primary actions + all-download progress
  - Right: searchable list with per-entry actions

### Mobile

- Single-column stacked layout.
- Sticky action area for `Download all available`.
- Compact entry rows optimized for touch.

## Data/API Requirements

### Frontend state model

- `resolvedMediaType: 'track' | 'playlist'`
- `playlistState`: entries, visibleCount, searchQuery, all-download status
- `trackState`: existing format/progress state

### API usage

- Continue using `POST /api/v1/videos/playlist` for playlist metadata.
- Continue using `POST /api/v1/videos/download/start`.
  - all-download: `download_mode=playlist`
  - single-entry download: track mode using selected entry URL
- Continue using SSE progress endpoint for both action types.

## Testing Strategy

- Auto-detect playlist URL and render playlist explorer.
- Search/filter works on entry list.
- `Download track` triggers single-track flow from playlist entry.
- `Download all available` triggers playlist zip flow.
- Unavailable entries render disabled and are excluded from all-download.
- Existing single-track format table flow remains unchanged.

## Scope Boundaries

- No multi-select arbitrary subset in this iteration.
- No backend rewrite of core download pipeline.
- No removal of current track format table behavior.

## Rationale

This design removes a user decision that the system can infer, improves discoverability for playlist actions, and keeps implementation risk low by reusing existing backend endpoints and progress mechanisms.
