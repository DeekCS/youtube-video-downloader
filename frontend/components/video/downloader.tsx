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
  fetchFormats,
  fetchPlaylist,
  getErrorMessage,
  type DownloadMode,
  type PlaylistInfo,
  type VideoInfo,
} from '@/lib/api-client'

type Tab = 'download' | 'convert'

export function Downloader() {
  const [tab, setTab] = useState<Tab>('download')
  const [downloadMode, setDownloadMode] = useState<DownloadMode>('track')
  const [videoInfo, setVideoInfo] = useState<VideoInfo | null>(null)
  const [playlistInfo, setPlaylistInfo] = useState<PlaylistInfo | null>(null)
  const [originalUrl, setOriginalUrl] = useState<string>('')

  const formatsMutation = useMutation({
    mutationFn: fetchFormats,
    onSuccess: (data, url) => {
      setVideoInfo(data)
      setPlaylistInfo(null)
      setOriginalUrl(url)
    },
  })

  const playlistMutation = useMutation({
    mutationFn: fetchPlaylist,
    onSuccess: (data, url) => {
      setPlaylistInfo(data)
      setVideoInfo(null)
      setOriginalUrl(url)
    },
  })

  const handleModeChange = (mode: DownloadMode) => {
    setDownloadMode(mode)
    setVideoInfo(null)
    setPlaylistInfo(null)
    setOriginalUrl('')
    formatsMutation.reset()
    playlistMutation.reset()
  }

  const handleSubmit = (url: string, mode: DownloadMode) => {
    setDownloadMode(mode)
    setVideoInfo(null)
    setPlaylistInfo(null)
    setOriginalUrl(url)
    formatsMutation.reset()
    playlistMutation.reset()

    if (mode === 'track') {
      formatsMutation.mutate(url)
      return
    }

    playlistMutation.mutate(url)
  }

  const isLoading = formatsMutation.isPending || playlistMutation.isPending
  const activeError = downloadMode === 'track' ? formatsMutation.error : playlistMutation.error

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
            mode={downloadMode}
            onModeChange={handleModeChange}
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

          {downloadMode === 'track' ? (
            <FormatsTable videoInfo={videoInfo} originalUrl={originalUrl} isLoading={formatsMutation.isPending} />
          ) : (
            <PlaylistSummary
              playlistInfo={playlistInfo}
              originalUrl={originalUrl}
              isLoading={playlistMutation.isPending}
            />
          )}
        </div>
      ) : (
        <FileDrop />
      )}
    </div>
  )
}
