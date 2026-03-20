/**
 * Type-safe environment variable access.
 * Validates required environment variables at build/runtime.
 */

function getEnvVar(key: string, fallback?: string): string {
  // Handle both server and client-side access
  const value = process.env[key]
  if (!value) {
    if (fallback) {
      console.warn(`Environment variable ${key} not found, using fallback: ${fallback}`)
      return fallback
    }
    throw new Error(`Missing required environment variable: ${key}`)
  }
  return value
}

/**
 * Fallback API base when `NEXT_PUBLIC_API_BASE` is unset.
 * Production builds must set `NEXT_PUBLIC_API_BASE` at build time (Railway Variables → Build).
 */
function getDefaultApiBase(): string {
  if (process.env.NODE_ENV === 'development') {
    return 'http://localhost:8000/api/v1'
  }
  return ''
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
    return getEnvVar('NEXT_PUBLIC_API_BASE', getDefaultApiBase())
  },
} as const

/**
 * Check if environment is properly configured.
 */
export function validateEnv(): void {
  // Validate API_BASE format
  if (!env.API_BASE.startsWith('http')) {
    throw new Error('NEXT_PUBLIC_API_BASE must start with http:// or https://')
  }

  // Warn if API_BASE doesn't end with /api/v1
  if (!env.API_BASE.endsWith('/api/v1')) {
    console.warn(
      'Warning: NEXT_PUBLIC_API_BASE should end with /api/v1 for proper API routing'
    )
  }
}
