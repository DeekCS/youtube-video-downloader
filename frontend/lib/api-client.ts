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
 * Build URL to fetch the completed file for a download task.
 */
export function buildTaskFileUrl(downloadId: string): string {
  return `${env.API_BASE}/videos/download/${downloadId}/file`
}

const StartDownloadResponseSchema = z.object({
  download_id: z.string(),
  filename: z.string(),
})

/** Validates inputs before POST /download/start (mirrors backend DownloadRequest). */
export const StartDownloadRequestSchema = z.object({
  url: z.string().min(10).max(2048),
  format_id: z.string().min(1).max(500),
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
  error: z.string().optional(),
})

export type DownloadProgress = z.infer<typeof DownloadProgressSchema>

/**
 * Start a server-side download and receive a task id for SSE progress + file fetch.
 */
export async function startDownload(
  url: string,
  formatId: string
): Promise<{ downloadId: string; filename: string }> {
  const payload = StartDownloadRequestSchema.parse({
    url: url.trim(),
    format_id: formatId.trim(),
  })

  const response = await fetch(`${env.API_BASE}/videos/download/start`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({ url: payload.url, format_id: payload.format_id }),
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
