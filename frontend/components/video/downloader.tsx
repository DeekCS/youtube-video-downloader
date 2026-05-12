'use client'

import { useState } from 'react'
import { useMutation } from '@tanstack/react-query'
import { AlertCircle, Download, RefreshCw } from 'lucide-react'

import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert'
import { UrlForm } from './url-form'
import { FormatsTable } from './formats-table'
import { FileDrop } from './file-drop'
import { fetchFormats, getErrorMessage, type VideoInfo } from '@/lib/api-client'

type Tab = 'download' | 'convert'

export function Downloader() {
  const [tab, setTab] = useState<Tab>('download')
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
    <div className="space-y-6">
      {/* Tab bar */}
      <div className="flex rounded-lg border border-border overflow-hidden">
        <button
          type="button"
          onClick={() => setTab('download')}
          className={[
            'flex-1 flex items-center justify-center gap-2 px-4 py-2.5 text-sm font-medium transition-colors',
            tab === 'download'
              ? 'bg-primary text-primary-foreground'
              : 'hover:bg-muted/60 text-muted-foreground',
          ].join(' ')}
        >
          <Download className="h-4 w-4" />
          Download from URL
        </button>
        <button
          type="button"
          onClick={() => setTab('convert')}
          className={[
            'flex-1 flex items-center justify-center gap-2 px-4 py-2.5 text-sm font-medium transition-colors border-l border-border',
            tab === 'convert'
              ? 'bg-primary text-primary-foreground'
              : 'hover:bg-muted/60 text-muted-foreground',
          ].join(' ')}
        >
          <RefreshCw className="h-4 w-4" />
          Convert File
        </button>
      </div>

      {/* Tab content */}
      {tab === 'download' ? (
        <div className="space-y-8">
          <UrlForm onSubmit={handleFetchFormats} isLoading={formatsMutation.isPending} />

          {formatsMutation.isError && (
            <Alert variant="destructive">
              <AlertCircle className="h-4 w-4" />
              <AlertTitle>Error</AlertTitle>
              <AlertDescription>{getErrorMessage(formatsMutation.error)}</AlertDescription>
            </Alert>
          )}

          <FormatsTable
            videoInfo={videoInfo}
            originalUrl={originalUrl}
            isLoading={formatsMutation.isPending}
          />
        </div>
      ) : (
        <FileDrop />
      )}
    </div>
  )
}

