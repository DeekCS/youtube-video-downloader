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
  formats: z.array(FormatSchema),
})

export type VideoInfo = z.infer<typeof VideoInfoSchema>

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

/**
 * Fetch video formats from the backend.
 */
export async function fetchFormats(url: string): Promise<VideoInfo> {
  // Validate input
  const validatedInput = FormatsRequestSchema.parse({ url })

  try {
    const response = await fetch(`${env.API_BASE}/videos/formats`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({ url: validatedInput.url }),
    })

    const data = await response.json()

    // Handle error responses
    if (!response.ok) {
      const errorData = ErrorResponseSchema.safeParse(data)
      if (errorData.success) {
        throw new ApiError(errorData.data.code, errorData.data.message, response.status)
      }
      throw new ApiError('INTERNAL_ERROR', 'An unexpected error occurred', response.status)
    }

    // Validate and parse successful response
    return VideoInfoSchema.parse(data)
  } catch (error) {
    // Re-throw ApiError as-is
    if (error instanceof ApiError) {
      throw error
    }

    // Re-throw zod validation errors as ApiError
    if (error instanceof z.ZodError) {
      throw new ApiError('INTERNAL_ERROR', 'Invalid response from server')
    }

    // Network or other errors
    if (error instanceof Error) {
      throw new ApiError('INTERNAL_ERROR', error.message)
    }

    throw new ApiError('INTERNAL_ERROR', 'An unexpected error occurred')
  }
}

/**
 * Download a video in the specified format.
 * Uses GET endpoint with URL parameters for browser-native download handling.
 */
export async function downloadVideo(
  url: string,
  formatId: string,
  filename: string
): Promise<void> {
  // Build the GET URL and trigger a browser-native download
  const downloadUrl = buildDownloadUrl(url, formatId)

  const link = document.createElement('a')
  link.href = downloadUrl
  link.download = filename
  link.style.display = 'none'
  document.body.appendChild(link)
  link.click()
  setTimeout(() => document.body.removeChild(link), 200)

  // Return a promise that resolves when the tab regains focus (the user
  // returned from the browser's "Save As" or download shelf) or after a
  // 45-second safety timeout.  This lets callers display a meaningful
  // "browser is downloading…" message rather than clearing state immediately.
  return new Promise<void>((resolve) => {
    const TIMEOUT_MS = 45_000
    let settled = false

    const finish = () => {
      if (settled) return
      settled = true
      document.removeEventListener('visibilitychange', onVisible)
      window.removeEventListener('focus', onVisible)
      resolve()
    }

    const onVisible = () => {
      if (document.visibilityState === 'visible') finish()
    }

    document.addEventListener('visibilitychange', onVisible)
    window.addEventListener('focus', onVisible)
    setTimeout(finish, TIMEOUT_MS)
  })
}

/**
 * Progress update from SSE download endpoint.
 */
export interface DownloadProgress {
  status: 'pending' | 'downloading' | 'merging' | 'completed' | 'failed'
  progress: number
  phase: string
  speed: string
  eta: string
  file_size: number
  downloaded_bytes: number
  total_bytes: number
  error?: string
}

/**
 * Start a progress-tracked download (merged formats).
 */
export async function startDownload(
  url: string,
  formatId: string
): Promise<{ downloadId: string; filename: string }> {
  const response = await fetch(`${env.API_BASE}/videos/download/start`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ url, format_id: formatId }),
  })

  if (!response.ok) {
    const data = await response.json().catch(() => ({}))
    throw new ApiError(
      data.code || 'INTERNAL_ERROR',
      data.message || 'Failed to start download',
      response.status
    )
  }

  const data = await response.json()
  return { downloadId: data.download_id, filename: data.filename }
}

/**
 * Subscribe to download progress events via SSE.
 * Returns a cleanup function to close the connection.
 */
export function subscribeToProgress(
  downloadId: string,
  onProgress: (progress: DownloadProgress) => void,
  onError?: (error: Error) => void
): () => void {
  const url = `${env.API_BASE}/videos/download/${downloadId}/progress`

  let eventSource: EventSource | null = null
  let retryCount = 0
  const MAX_RETRIES = 3
  const RETRY_DELAYS = [1000, 2000, 4000]
  let closed = false
  let retryTimer: ReturnType<typeof setTimeout> | null = null

  const cleanup = () => {
    closed = true
    if (retryTimer !== null) clearTimeout(retryTimer)
    eventSource?.close()
  }

  const connect = () => {
    if (closed) return
    eventSource = new EventSource(url)

    eventSource.addEventListener('progress', (event: MessageEvent) => {
      try {
        const progress: DownloadProgress = JSON.parse(event.data)
        retryCount = 0 // reset on successful message
        onProgress(progress)
        if (progress.status === 'completed' || progress.status === 'failed') {
          cleanup()
        }
      } catch {
        // ignore parse errors
      }
    })

    eventSource.onerror = () => {
      eventSource?.close()
      eventSource = null

      if (closed) return

      if (retryCount < MAX_RETRIES) {
        const delay = RETRY_DELAYS[retryCount] ?? 4000
        retryCount++
        retryTimer = setTimeout(connect, delay)
      } else {
        // Exhausted retries — propagate error
        cleanup()
        onError?.(new Error('Progress connection lost'))
      }
    }
  }

  connect()
  return cleanup
}

/**
 * Build URL to fetch the completed file for a download task.
 */
export function buildTaskFileUrl(downloadId: string): string {
  return `${env.API_BASE}/videos/download/${downloadId}/file`
}

/**
 * Check whether a format ID represents a merged (video+audio) download.
 */
export function isMergedFormat(formatId: string): boolean {
  return (
    formatId.includes('+') ||
    formatId === 'best' ||
    formatId === 'bestvideo' ||
    formatId.startsWith('best[') ||
    formatId.startsWith('bestvideo[')
  )
}

/**
 * Build download URL for a specific format (legacy GET method).
 */
export function buildDownloadUrl(url: string, formatId: string): string {
  const params = new URLSearchParams({
    url,
    format_id: formatId,
  })
  return `${env.API_BASE}/videos/download?${params.toString()}`
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
