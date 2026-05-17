# Playlist Download UI Design

> **Goal:** Let users choose between single-track downloads and playlist downloads from the frontend without changing the existing track download flow.

**Architecture:** Keep the current track formats workflow as the default path. Add an explicit download mode selector in the URL form, fetch playlist metadata when playlist mode is selected, and render a playlist summary with one download action instead of the format table. Track downloads continue to use the existing format list, progress stream, and file fetch flow. Playlist downloads call the new playlist metadata endpoint, start a playlist job, and surface overall playlist progress plus the current track name.

**Tech Stack:** Next.js 16, React, TypeScript, React Query, zod, existing UI components.

---

## Problem

The frontend currently assumes every supported URL should produce a format table and a single-track download action. That works for track URLs, but it does not give users a clear way to request a full playlist download. The UI needs to make the mode explicit so users can choose the right behavior before starting a download.

## Proposed Behavior

### Track mode

- User pastes a URL.
- The app fetches track formats and shows the existing formats table.
- The user picks a format and downloads a single track.
- Existing track progress and file download behavior stays unchanged.

### Playlist mode

- User switches the form to playlist mode.
- The app fetches playlist metadata for the URL.
- The UI shows playlist title, entry count, and a simple playlist summary.
- The user clicks one **Download Playlist** button.
- The backend returns one zip file, and the UI shows playlist-aware progress until the zip is ready.

## Design Approaches

### Option A: Auto-detect mode from the URL

Guess whether the URL is a playlist and switch the UI automatically.

**Pros:** fewer controls.
**Cons:** unclear for URLs that can behave both ways; harder for users to intentionally download one track from a playlist-shaped URL.

### Option B: Explicit track / playlist toggle in the form

Let the user choose the mode before fetching metadata.

**Pros:** predictable, simple to explain, matches the backend contract.
**Cons:** one extra UI control.

### Option C: Always show both track and playlist actions

Fetch both track formats and playlist metadata, then show both actions together.

**Pros:** maximum flexibility.
**Cons:** more API calls and more confusing UI.

**Recommendation:** Option B. It keeps the current track flow intact and adds the smallest clear path for playlist downloads.

## Frontend Design

### URL form

- Add a mode toggle for `Track` and `Playlist`.
- Keep the URL input and validation behavior.
- When playlist mode is selected, the form should signal that the URL will be treated as a playlist download request.

### API client

- Add a playlist metadata request helper for `POST /api/v1/videos/playlist`.
- Extend the start-download request to include `download_mode`.
- Make `format_id` optional for playlist mode in the client contract.
- Add zod schemas for playlist metadata and playlist entries.

### Downloader view

- Track mode keeps the current format lookup and format table.
- Playlist mode replaces the format table with a playlist summary card.
- The summary should show the playlist title, entry count, and a single download button.
- While the playlist job runs, show overall progress and the current track title.

### Formats table

- Keep the current table for track mode.
- Keep track-mode download actions unchanged.
- Do not add playlist-specific row actions to the table.

## Error Handling

- Invalid URLs should still show the existing validation and API errors.
- Playlist metadata failures should surface as a normal API error message.
- If the playlist job fails after starting, the UI should show the failure state in the existing progress area.
- Track-mode validation still requires a format selection.

## Testing Strategy

### Frontend checks

- Verify the URL form can switch between track and playlist mode.
- Verify playlist mode fetches playlist metadata and renders the summary state.
- Verify track mode still renders the format table.
- Verify playlist downloads call the start-download API with `download_mode=playlist`.

### Existing verification

- Run the frontend lint and typecheck scripts after implementation.

## Scope Notes

- This design does not add per-track selection inside playlists.
- This design does not change the existing track format ranking or table layout.
- This design keeps playlist downloads as a single zip file rather than separate browser downloads.
