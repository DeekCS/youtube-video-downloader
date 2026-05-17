'use client'

import { useEffect, useRef, useState, useCallback } from 'react'
import { CheckCircle, Download, Loader2, XCircle } from 'lucide-react'

import { Alert, AlertDescription } from '@/components/ui/alert'
import { Button } from '@/components/ui/button'
import { Progress } from '@/components/ui/progress'
import { Skeleton } from '@/components/ui/skeleton'
import {
  buildTaskFileUrl,
  startDownload,
  subscribeToProgress,
  type DownloadProgress,
  type PlaylistInfo,
} from '@/lib/api-client'

interface PlaylistSummaryProps {
  playlistInfo: PlaylistInfo | null
  originalUrl: string
  isLoading?: boolean
}

export function PlaylistSummary({ playlistInfo, originalUrl, isLoading = false }: PlaylistSummaryProps) {
  const [downloadState, setDownloadState] = useState<(DownloadProgress & { downloading?: boolean }) | null>(null)
  const cleanupRef = useRef<(() => void) | null>(null)
  const activeDownloadRef = useRef(false)

  useEffect(() => {
    return () => {
      cleanupRef.current?.()
      cleanupRef.current = null
    }
  }, [])

  const fmtBytes = useCallback((bytes: number): string => {
    if (bytes <= 0) return ''
    if (bytes < 1024) return `${bytes} B`
    if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(0)} KB`
    if (bytes < 1024 * 1024 * 1024) return `${(bytes / (1024 * 1024)).toFixed(1)} MB`
    return `${(bytes / (1024 * 1024 * 1024)).toFixed(2)} GB`
  }, [])

  const getOverallProgress = useCallback((p: DownloadProgress): number => {
    if (p.status === 'completed') return 100
    if (p.status === 'merging') return 92
    return p.progress
  }, [])

  const getStatusLabel = useCallback((p: DownloadProgress): string => {
    if (p.status === 'failed') return p.error || 'Download failed'
    if (p.status === 'completed') return 'Saved ✓'
    if (p.status === 'merging') return 'Packaging playlist…'
    if (p.status === 'downloading') return 'Downloading playlist…'
    return 'Preparing playlist…'
  }, [])

  const handleDownload = async () => {
    if (!playlistInfo || activeDownloadRef.current) return
    activeDownloadRef.current = true
    cleanupRef.current?.()
    cleanupRef.current = null

    setDownloadState({
      status: 'pending',
      progress: 0,
      phase: '',
      speed: '',
      eta: '',
      file_size: 0,
      downloaded_bytes: 0,
      total_bytes: 0,
      playlist_title: playlistInfo.title,
      total_entries: playlistInfo.entry_count,
      completed_entries: 0,
      current_entry: '',
      downloading: true,
    })

    const release = () => {
      activeDownloadRef.current = false
    }

    try {
      const { downloadId } = await startDownload(originalUrl, undefined, 'playlist')

      const cleanup = subscribeToProgress(
        downloadId,
        (progress) => {
          setDownloadState({ ...progress, downloading: true })

          if (progress.status === 'completed') {
            const link = document.createElement('a')
            link.href = buildTaskFileUrl(downloadId)
            link.style.display = 'none'
            document.body.appendChild(link)
            link.click()

            setTimeout(() => {
              document.body.removeChild(link)
              setDownloadState(null)
              release()
            }, 3000)
          }

          if (progress.status === 'failed') {
            setTimeout(() => {
              setDownloadState(null)
              release()
            }, 5000)
          }
        },
        () => {
          setDownloadState({
            status: 'failed',
            progress: 0,
            phase: '',
            speed: '',
            eta: '',
            file_size: 0,
            downloaded_bytes: 0,
            total_bytes: 0,
            playlist_title: playlistInfo.title,
            total_entries: playlistInfo.entry_count,
            completed_entries: 0,
            current_entry: '',
            error: 'Connection lost',
            downloading: true,
          })

          setTimeout(() => {
            setDownloadState(null)
            release()
          }, 5000)
        },
      )

      cleanupRef.current = cleanup
    } catch {
      setDownloadState({
        status: 'failed',
        progress: 0,
        phase: '',
        speed: '',
        eta: '',
        file_size: 0,
        downloaded_bytes: 0,
        total_bytes: 0,
        playlist_title: playlistInfo.title,
        total_entries: playlistInfo.entry_count,
        completed_entries: 0,
        current_entry: '',
        error: 'Failed to start',
        downloading: true,
      })

      setTimeout(() => {
        setDownloadState(null)
        release()
      }, 5000)
    }
  }

  if (isLoading) {
    return (
      <div className="space-y-4 border rounded-lg p-4 sm:p-6">
        <div className="space-y-2">
          <Skeleton className="h-6 w-3/5" />
          <Skeleton className="h-4 w-1/4" />
        </div>
        <Skeleton className="h-10 w-40" />
        <Skeleton className="h-2 w-full" />
      </div>
    )
  }

  if (!playlistInfo) {
    return null
  }

  const state = downloadState
  const isDownloading = Boolean(state?.downloading)

  return (
    <div className="space-y-4 border rounded-lg p-4 sm:p-6">
      <div className="space-y-1">
        <h2 className="text-lg sm:text-xl font-semibold break-words">{playlistInfo.title}</h2>
        <p className="text-sm text-muted-foreground">
          {playlistInfo.entry_count} {playlistInfo.entry_count === 1 ? 'track' : 'tracks'}
        </p>
      </div>

      <Button onClick={handleDownload} disabled={isDownloading} className="w-full sm:w-auto">
        <Download className="h-4 w-4 mr-2" />
        Download Playlist
      </Button>

      {state && (
        <div className="space-y-2">
          <Progress value={state.status === 'pending' ? undefined : getOverallProgress(state)} className="h-2" />
          <div className="flex flex-col gap-1 text-xs text-muted-foreground">
            <span className="flex items-center gap-1">
              {state.status === 'failed' ? (
                <XCircle className="h-3 w-3 text-red-500 flex-shrink-0" />
              ) : state.status === 'completed' ? (
                <CheckCircle className="h-3 w-3 text-green-500 flex-shrink-0" />
              ) : (
                <Loader2 className="h-3 w-3 animate-spin flex-shrink-0" />
              )}
              <span>{getStatusLabel(state)}</span>
            </span>
            {!state.error && state.current_entry ? (
              <span className="truncate">Current track: {state.current_entry}</span>
            ) : null}
            {state.total_entries > 0 ? (
              <span>
                {state.completed_entries} / {state.total_entries} tracks · {Math.round(getOverallProgress(state))}%
              </span>
            ) : null}
            {!state.error && state.total_bytes > 0 ? (
              <span>
                {fmtBytes(state.downloaded_bytes)} / {fmtBytes(state.total_bytes)}
                {state.speed ? ` · ${state.speed}` : ''}
              </span>
            ) : null}
          </div>
          {state.error && (
            <Alert variant="destructive">
              <AlertDescription>{state.error}</AlertDescription>
            </Alert>
          )}
        </div>
      )}
    </div>
  )
}
