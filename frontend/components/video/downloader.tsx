'use client'

import { useState } from 'react'
import { useMutation } from '@tanstack/react-query'
import { AlertCircle, Download, RefreshCw } from 'lucide-react'

import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert'
import { UrlForm } from './url-form'
import { FormatsTable } from './formats-table'
import { FileDrop } from './file-drop'
import { PlaylistSummary } from './playlist-summary'
import {
  getErrorMessage,
  resolveMedia,
  type PlaylistInfo,
  type VideoInfo,
} from '@/lib/api-client'

type Tab = 'download' | 'convert'

export function Downloader() {
  const [tab, setTab] = useState<Tab>('download')
  const [videoInfo, setVideoInfo] = useState<VideoInfo | null>(null)
  const [playlistInfo, setPlaylistInfo] = useState<PlaylistInfo | null>(null)
  const [originalUrl, setOriginalUrl] = useState<string>('')

  const resolveMutation = useMutation({
    mutationFn: resolveMedia,
    onSuccess: (data, url) => {
      if (data.kind === 'playlist') {
        setPlaylistInfo(data.playlist)
        setVideoInfo(null)
        setOriginalUrl(url)
        return
      }

      setVideoInfo(data.video)
      setPlaylistInfo(null)
      setOriginalUrl(url)
    },
  })

  const handleSubmit = (url: string) => {
    setVideoInfo(null)
    setPlaylistInfo(null)
    setOriginalUrl(url)
    resolveMutation.reset()
    resolveMutation.mutate(url)
  }

  const isLoading = resolveMutation.isPending
  const activeError = resolveMutation.error

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
          <UrlForm
            onSubmit={handleSubmit}
            isLoading={isLoading}
          />

          {activeError && (
            <Alert variant="destructive">
              <AlertCircle className="h-4 w-4" />
              <AlertTitle>Error</AlertTitle>
              <AlertDescription>{getErrorMessage(activeError)}</AlertDescription>
            </Alert>
          )}

          {!playlistInfo ? (
            <FormatsTable videoInfo={videoInfo} originalUrl={originalUrl} isLoading={resolveMutation.isPending} />
          ) : (
            <PlaylistSummary
              playlistInfo={playlistInfo}
              originalUrl={originalUrl}
              isLoading={resolveMutation.isPending}
            />
          )}
        </div>
      ) : (
        <FileDrop />
      )}
    </div>
  )
}
