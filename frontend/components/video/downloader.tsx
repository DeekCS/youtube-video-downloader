'use client'

import { useState } from 'react'
import { useMutation } from '@tanstack/react-query'
import { AlertCircle } from 'lucide-react'

import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert'
import { UrlForm } from './url-form'
import { FormatsTable } from './formats-table'
import { fetchFormats, getErrorMessage, type VideoInfo } from '@/lib/api-client'

export function Downloader() {
  const [videoInfo, setVideoInfo] = useState<VideoInfo | null>(null)
  const [originalUrl, setOriginalUrl] = useState<string>('')

  const formatsMutation = useMutation({
    mutationFn: fetchFormats,
    onSuccess: (data, url) => {
      setVideoInfo(data)
      setOriginalUrl(url)
    },
  })

  const handleFetchFormats = (url: string) => {
    formatsMutation.mutate(url)
  }

  return (
    <div className="space-y-8">
      {/* URL Form */}
      <UrlForm onSubmit={handleFetchFormats} isLoading={formatsMutation.isPending} />

      {/* Error Alert */}
      {formatsMutation.isError && (
        <Alert variant="destructive">
          <AlertCircle className="h-4 w-4" />
          <AlertTitle>Error</AlertTitle>
          <AlertDescription>{getErrorMessage(formatsMutation.error)}</AlertDescription>
        </Alert>
      )}

      {/* Formats Table */}
      <FormatsTable
        videoInfo={videoInfo}
        originalUrl={originalUrl}
        isLoading={formatsMutation.isPending}
      />
    </div>
  )
}
