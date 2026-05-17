/**
 * API client for video downloader backend.
 * Includes strict zod schemas for runtime validation of API responses.
 */

import { z } from 'zod'
import { env } from './env'

/**
 * Zod schema for a single video format.
 * Mirrors backend Format model.
 */
export const FormatSchema = z.object({
  id: z.string(),
  quality_label: z.string(),
  mime_type: z.string(),
  filesize_bytes: z.number().nullable(),
  is_audio_only: z.boolean(),
  is_video_only: z.boolean(),
})

export type Format = z.infer<typeof FormatSchema>

/**
 * Zod schema for video information.
 * Mirrors backend VideoInfo model.
 */
export const VideoInfoSchema = z.object({
  title: z.string(),
  thumbnail_url: z.string().nullable(),
  duration_seconds: z.number().nullable(),
  video_id: z.string().nullable().optional(),
  platform: z.string().nullable().optional(),
  formats: z.array(FormatSchema),
})

export type VideoInfo = z.infer<typeof VideoInfoSchema>

/**
 * Zod schema for a playlist entry.
 */
export const PlaylistEntrySchema = z.object({
  id: z.string(),
  title: z.string(),
  url: z.string().nullable(),
})

export type PlaylistEntry = z.infer<typeof PlaylistEntrySchema>

/**
 * Zod schema for playlist metadata.
 */
export const PlaylistInfoSchema = z.object({
  title: z.string(),
  entry_count: z.number(),
  entries: z.array(PlaylistEntrySchema),
})

export type PlaylistInfo = z.infer<typeof PlaylistInfoSchema>

export type ResolvedMedia =
  | { kind: 'track'; video: VideoInfo }
  | { kind: 'playlist'; playlist: PlaylistInfo }

/**
 * Zod schema for error responses.
 * Mirrors backend ErrorResponse model.
 */
export const ErrorResponseSchema = z.object({
  code: z.enum([
    'INVALID_URL',
    'UNSUPPORTED_PLATFORM',
    'NOT_FOUND',
    'FORMAT_NOT_AVAILABLE',
    'YTDLP_FAILED',
    'INTERNAL_ERROR',
    'RATE_LIMITED',
  ]),
  message: z.string(),
})

export type ErrorResponse = z.infer<typeof ErrorResponseSchema>

/**
 * Request schema for fetching formats.
 */
export const FormatsRequestSchema = z.object({
  url: z.string().url('Must be a valid URL'),
})

export type FormatsRequest = z.infer<typeof FormatsRequestSchema>

/**
 * Custom error class for API errors.
 */
export class ApiError extends Error {
  constructor(
    public code: string,
    message: string,
    public status?: number
  ) {
    super(message)
    this.name = 'ApiError'
  }
}

const API_TIMEOUT_MS = 30_000

/**
 * Fetch video formats from the backend.
 */
export async function fetchFormats(url: string): Promise<VideoInfo> {
  const validatedInput = FormatsRequestSchema.parse({ url })

  const controller = new AbortController()
  const timeoutId = setTimeout(() => controller.abort(), API_TIMEOUT_MS)

  try {
    const response = await fetch(`${env.API_BASE}/videos/formats`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ url: validatedInput.url }),
      signal: controller.signal,
    })

    const data = await response.json()

    if (!response.ok) {
      const errorData = ErrorResponseSchema.safeParse(data)
      if (errorData.success) {
        throw new ApiError(errorData.data.code, errorData.data.message, response.status)
      }
      throw new ApiError('INTERNAL_ERROR', 'An unexpected error occurred', response.status)
    }

    return VideoInfoSchema.parse(data)
  } catch (error) {
    if (error instanceof ApiError) throw error
    if (error instanceof z.ZodError) {
      throw new ApiError('INTERNAL_ERROR', 'Invalid response from server')
    }
    if (error instanceof DOMException && error.name === 'AbortError') {
      throw new ApiError('INTERNAL_ERROR', 'Request timed out after 30 seconds')
    }
    if (error instanceof Error) throw new ApiError('INTERNAL_ERROR', error.message)
    throw new ApiError('INTERNAL_ERROR', 'An unexpected error occurred')
  } finally {
    clearTimeout(timeoutId)
  }
}

/**
 * Fetch playlist metadata from the backend.
 */
export async function fetchPlaylist(url: string): Promise<PlaylistInfo> {
  const validatedInput = FormatsRequestSchema.parse({ url })

  const controller = new AbortController()
  const timeoutId = setTimeout(() => controller.abort(), API_TIMEOUT_MS)

  try {
    const response = await fetch(`${env.API_BASE}/videos/playlist`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ url: validatedInput.url }),
      signal: controller.signal,
    })

    const data = await response.json()

    if (!response.ok) {
      const errorData = ErrorResponseSchema.safeParse(data)
      if (errorData.success) {
        throw new ApiError(errorData.data.code, errorData.data.message, response.status)
      }
      throw new ApiError('INTERNAL_ERROR', 'An unexpected error occurred', response.status)
    }

    return PlaylistInfoSchema.parse(data)
  } catch (error) {
    if (error instanceof ApiError) throw error
    if (error instanceof z.ZodError) {
      throw new ApiError('INTERNAL_ERROR', 'Invalid response from server')
    }
    if (error instanceof DOMException && error.name === 'AbortError') {
      throw new ApiError('INTERNAL_ERROR', 'Request timed out after 30 seconds')
    }
    if (error instanceof Error) throw new ApiError('INTERNAL_ERROR', error.message)
    throw new ApiError('INTERNAL_ERROR', 'An unexpected error occurred')
  } finally {
    clearTimeout(timeoutId)
  }
}

function isLikelyPlaylistUrl(url: string): boolean {
  const loweredUrl = url.toLowerCase()
  const playlistPathHints = ['/playlist', '/sets/', '/album']

  try {
    const parsed = new URL(url)
    const loweredPath = parsed.pathname.toLowerCase()

    if (parsed.searchParams.has('list')) {
      return true
    }

    return playlistPathHints.some((hint) => loweredPath.includes(hint))
  } catch {
    if (loweredUrl.includes('list=')) {
      return true
    }

    return playlistPathHints.some((hint) => loweredUrl.includes(hint))
  }
}

export async function resolveMedia(url: string): Promise<ResolvedMedia> {
  const playlistFirst = isLikelyPlaylistUrl(url)

  if (playlistFirst) {
    try {
      const playlist = await fetchPlaylist(url)
      return { kind: 'playlist', playlist }
    } catch (error) {
      if (!(error instanceof ApiError) || error.code !== 'NOT_FOUND') {
        throw error
      }
    }

    const video = await fetchFormats(url)
    return { kind: 'track', video }
  }

  try {
    const video = await fetchFormats(url)
    return { kind: 'track', video }
  } catch (error) {
    if (!(error instanceof ApiError) || error.code !== 'NOT_FOUND') {
      throw error
    }
  }

  const playlist = await fetchPlaylist(url)
  return { kind: 'playlist', playlist }
}

/**
 * Build URL to fetch the completed file for a download task.
 */
export function buildTaskFileUrl(downloadId: string): string {
  return `${env.API_BASE}/videos/download/${downloadId}/file`
}

const StartDownloadResponseSchema = z.object({
  download_id: z.string(),
  filename: z.string(),
})

export type DownloadMode = 'track' | 'playlist'

/** Validates inputs before POST /download/start (mirrors backend DownloadRequest). */
export const StartDownloadRequestSchema = z.object({
  url: z.string().min(10).max(2048),
  format_id: z.string().min(1).max(500).optional(),
  download_mode: z.enum(['track', 'playlist']),
}).superRefine((data, ctx) => {
  if (data.download_mode === 'track' && !data.format_id) {
    ctx.addIssue({
      code: z.ZodIssueCode.custom,
      path: ['format_id'],
      message: 'format_id is required for track downloads',
    })
  }
})

export const DownloadProgressSchema = z.object({
  status: z.string(),
  progress: z.number(),
  phase: z.string(),
  speed: z.string(),
  eta: z.string(),
  file_size: z.number(),
  downloaded_bytes: z.number(),
  total_bytes: z.number(),
  playlist_title: z.string(),
  total_entries: z.number(),
  completed_entries: z.number(),
  current_entry: z.string(),
  error: z.string().optional(),
})

export type DownloadProgress = z.infer<typeof DownloadProgressSchema>

/**
 * Start a server-side download and receive a task id for SSE progress + file fetch.
 */
export async function startDownload(
  url: string,
  formatId?: string,
  downloadMode: DownloadMode = 'track'
): Promise<{ downloadId: string; filename: string }> {
  const payload = StartDownloadRequestSchema.parse({
    url: url.trim(),
    download_mode: downloadMode,
    ...(formatId ? { format_id: formatId.trim() } : {}),
  })

  const controller = new AbortController()
  const timeoutId = setTimeout(() => controller.abort(), API_TIMEOUT_MS)

  try {
    const response = await fetch(`${env.API_BASE}/videos/download/start`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        url: payload.url,
        download_mode: payload.download_mode,
        ...(payload.format_id ? { format_id: payload.format_id } : {}),
      }),
      signal: controller.signal,
    })

    const data: unknown = await response.json()

    if (!response.ok) {
      const parsed = ErrorResponseSchema.safeParse(data)
      if (parsed.success) {
        throw new ApiError(parsed.data.code, parsed.data.message, response.status)
      }
      throw new ApiError('INTERNAL_ERROR', 'Failed to start download', response.status)
    }

    const ok = StartDownloadResponseSchema.parse(data)
    return { downloadId: ok.download_id, filename: ok.filename }
  } catch (error) {
    if (error instanceof ApiError) throw error
    if (error instanceof DOMException && error.name === 'AbortError') {
      throw new ApiError('INTERNAL_ERROR', 'Request timed out after 30 seconds')
    }
    if (error instanceof z.ZodError) {
      throw new ApiError('INTERNAL_ERROR', 'Invalid response from server')
    }
    if (error instanceof Error) throw new ApiError('INTERNAL_ERROR', error.message)
    throw new ApiError('INTERNAL_ERROR', 'An unexpected error occurred')
  } finally {
    clearTimeout(timeoutId)
  }
}

/**
 * Subscribe to SSE progress events for a download task. Returns a cleanup function.
 */
export function subscribeToProgress(
  downloadId: string,
  onProgress: (progress: DownloadProgress) => void,
  onConnectionError: () => void
): () => void {
  const url = `${env.API_BASE}/videos/download/${downloadId}/progress`
  const es = new EventSource(url)

  let consecutiveErrors = 0
  const maxTransientErrors = 4

  const onMessage = (e: MessageEvent) => {
    try {
      const raw = JSON.parse(e.data as string) as unknown
      const parsed = DownloadProgressSchema.safeParse(raw)
      if (parsed.success) {
        consecutiveErrors = 0
        onProgress(parsed.data)
      }
    } catch {
      // ignore malformed chunks
    }
  }

  es.addEventListener('progress', onMessage as EventListener)

  es.onopen = () => {
    consecutiveErrors = 0
  }

  es.onerror = () => {
    consecutiveErrors += 1
    if (consecutiveErrors >= maxTransientErrors) {
      es.close()
      onConnectionError()
    }
  }

  return () => {
    es.removeEventListener('progress', onMessage as EventListener)
    es.close()
  }
}

// ---------------------------------------------------------------------------
// Conversion API
// ---------------------------------------------------------------------------

const StartConversionResponseSchema = z.object({
  task_id: z.string(),
  filename: z.string(),
})

/**
 * Upload a local file for conversion and return a task ID for progress tracking.
 * Reports real upload progress via onUploadProgress (0–100).
 */
export async function startConversion(
  file: File,
  targetFormat: string,
  onUploadProgress?: (pct: number) => void,
): Promise<{ taskId: string; filename: string }> {
  const body = new FormData()
  body.append('file', file)
  body.append('target_format', targetFormat)

  return new Promise((resolve, reject) => {
    const xhr = new XMLHttpRequest()
    xhr.open('POST', `${env.API_BASE}/convert/start`)

    if (onUploadProgress) {
      xhr.upload.onprogress = (e) => {
        if (e.lengthComputable) {
          onUploadProgress(Math.round((e.loaded / e.total) * 100))
        }
      }
    }

    xhr.onload = () => {
      let data: unknown
      try { data = JSON.parse(xhr.responseText) } catch { data = {} }

      if (xhr.status < 200 || xhr.status >= 300) {
        const parsed = ErrorResponseSchema.safeParse(data)
        if (parsed.success) {
          reject(new ApiError(parsed.data.code, parsed.data.message, xhr.status))
          return
        }
        const detail = (data as { detail?: string })?.detail
        reject(new ApiError('INTERNAL_ERROR', detail ?? 'Failed to start conversion', xhr.status))
        return
      }

      try {
        const ok = StartConversionResponseSchema.parse(data)
        resolve({ taskId: ok.task_id, filename: ok.filename })
      } catch {
        reject(new ApiError('INTERNAL_ERROR', 'Invalid response from server'))
      }
    }

    xhr.onerror = () => reject(new ApiError('INTERNAL_ERROR', 'Network error during upload'))
    xhr.ontimeout = () => reject(new ApiError('INTERNAL_ERROR', 'Upload timed out'))
    xhr.timeout = 30 * 60 * 1000 // 30 minutes for large files
    xhr.send(body)
  })
}

/**
 * Build the URL to fetch a completed converted file.
 */
export function buildConversionFileUrl(taskId: string): string {
  return `${env.API_BASE}/convert/${taskId}/file`
}

/**
 * Subscribe to SSE progress events for a conversion task.
 * Uses the same event schema as subscribeToProgress.
 */
export function subscribeToConversionProgress(
  taskId: string,
  onProgress: (progress: DownloadProgress) => void,
  onConnectionError: () => void,
): () => void {
  const url = `${env.API_BASE}/convert/${taskId}/progress`
  const es = new EventSource(url)

  let consecutiveErrors = 0
  const maxTransientErrors = 4

  const onMessage = (e: MessageEvent) => {
    try {
      const raw = JSON.parse(e.data as string) as unknown
      const parsed = DownloadProgressSchema.safeParse(raw)
      if (parsed.success) {
        consecutiveErrors = 0
        onProgress(parsed.data)
      }
    } catch {
      // ignore malformed chunks
    }
  }

  es.addEventListener('progress', onMessage as EventListener)
  es.onopen = () => { consecutiveErrors = 0 }
  es.onerror = () => {
    consecutiveErrors += 1
    if (consecutiveErrors >= maxTransientErrors) {
      es.close()
      onConnectionError()
    }
  }

  return () => {
    es.removeEventListener('progress', onMessage as EventListener)
    es.close()
  }
}

/**
 * Get user-friendly error message for an API error.
 */
export function getErrorMessage(error: unknown): string {
  if (error instanceof ApiError) {
    return error.message
  }

  if (error instanceof z.ZodError) {
    // TypeScript now knows error is z.ZodError
    return error.errors[0]?.message || 'Invalid input'
  }

  if (error instanceof Error) {
    return error.message
  }

  return 'An unexpected error occurred'
}
