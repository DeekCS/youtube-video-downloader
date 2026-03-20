/**
 * Backend API base URL for fetch calls.
 * Uses static `process.env.NEXT_PUBLIC_API_BASE` so Next.js can inline it in client bundles.
 */

function getApiBase(): string {
  const v = process.env.NEXT_PUBLIC_API_BASE?.trim()
  if (v) {
    return v
  }
  if (process.env.NODE_ENV === 'development') {
    return 'http://localhost:8000/api/v1'
  }
  throw new Error(
    'Missing NEXT_PUBLIC_API_BASE. Set it for the frontend Docker build and runtime ' +
      '(e.g. Railway → Frontend service → Variables → NEXT_PUBLIC_API_BASE = https://<backend>/api/v1), ' +
      'then redeploy so the image rebuilds.'
  )
}

/**
 * Validated environment variables.
 */
export const env = {
  /**
   * Backend API base URL (must include /api/v1 prefix).
   * Example: https://api.example.com/api/v1
   */
  get API_BASE(): string {
    return getApiBase()
  },
} as const

/**
 * Check environment at startup (layout / build).
 */
export function validateEnv(): void {
  const base = getApiBase()
  if (!base.startsWith('http')) {
    throw new Error('NEXT_PUBLIC_API_BASE must start with http:// or https://')
  }
  if (!base.endsWith('/api/v1')) {
    console.warn(
      'Warning: NEXT_PUBLIC_API_BASE should end with /api/v1 for proper API routing'
    )
  }
}
