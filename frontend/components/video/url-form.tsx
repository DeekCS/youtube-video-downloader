'use client'

import { useState } from 'react'
import { Download, AlertCircle } from 'lucide-react'
import { z } from 'zod'

import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Alert, AlertDescription } from '@/components/ui/alert'
import { FormatsRequestSchema } from '@/lib/api-client'

interface UrlFormProps {
  onSubmit: (url: string) => void
  isLoading?: boolean
}

export function UrlForm({ onSubmit, isLoading = false }: UrlFormProps) {
  const [url, setUrl] = useState('')
  const [error, setError] = useState<string | null>(null)

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault()
    setError(null)

    // Validate URL
    try {
      const validated = FormatsRequestSchema.parse({ url: url.trim() })
      onSubmit(validated.url)
    } catch (err) {
      if (err instanceof z.ZodError) {
        setError(err.errors[0]?.message || 'Invalid URL')
      } else {
        setError('An error occurred while validating the URL')
      }
    }
  }

  return (
    <form onSubmit={handleSubmit} className="space-y-4">
      <div className="space-y-2">
        <div className="flex gap-2">
          <Input
            type="text"
            placeholder="https://www.youtube.com/watch?v=..."
            value={url}
            onChange={(e) => {
              setUrl(e.target.value)
              setError(null)
            }}
            disabled={isLoading}
            className="flex-1"
            aria-label="Video URL"
          />
          <Button type="submit" disabled={isLoading || !url.trim()} className="min-w-[140px]">
            {isLoading ? (
              <>
                <div className="h-4 w-4 animate-spin rounded-full border-2 border-current border-t-transparent" />
                Loading...
              </>
            ) : (
              <>
                <Download className="h-4 w-4" />
                Fetch Formats
              </>
            )}
          </Button>
        </div>

        {error && (
          <Alert variant="destructive">
            <AlertCircle className="h-4 w-4" />
            <AlertDescription>{error}</AlertDescription>
          </Alert>
        )}
      </div>

      <p className="text-sm text-muted-foreground">
        Paste a video URL above to see available download formats
      </p>
    </form>
  )
}
