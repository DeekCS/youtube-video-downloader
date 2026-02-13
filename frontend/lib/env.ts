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
 * Determine the default API base URL based on the current environment.
 * In production (Railway), use the Railway backend domain.
 * In development, use localhost.
 */
function getDefaultApiBase(): string {
  if (typeof window !== 'undefined') {
    const host = window.location.hostname
    // If running on Railway or any non-localhost domain, use the backend Railway URL
    if (host !== 'localhost' && host !== '127.0.0.1') {
      return 'https://backend-production-46f2d.up.railway.app/api/v1'
    }
  }
  return 'http://localhost:8000/api/v1'
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
