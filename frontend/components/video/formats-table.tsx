'use client'

import Image from 'next/image'
import { Download, Loader2 } from 'lucide-react'
import { useState } from 'react'

import { Button } from '@/components/ui/button'
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table'
import { Skeleton } from '@/components/ui/skeleton'
import { type VideoInfo, type Format } from '@/lib/api-client'
import { formatFileSize, formatDuration } from '@/lib/utils'
import { downloadVideo } from '@/lib/api-client'

interface FormatsTableProps {
  videoInfo: VideoInfo | null
  originalUrl: string
  isLoading?: boolean
}

interface UserFriendlyFormat extends Format {
  friendlyLabel: string
  friendlyType: string
  priority: number
}

function getCommonFormats(formats: Format[]): UserFriendlyFormat[] {
  const formatted: UserFriendlyFormat[] = []

  // Separate merged formats (yt-dlp auto-merge selectors) from regular formats
  const mergedFormats = formats.filter(f =>
    f.id.includes('+') ||
    f.quality_label.toLowerCase().includes('merged') ||
    f.id.startsWith('bestvideo') ||
    f.id === 'best'
  )
  const videoOnly = formats.filter(f => f.is_video_only)
  const audioOnly = formats.filter(f => f.is_audio_only)

  let priority = 1

  // Merged quality tiers (these download video+audio and merge via ffmpeg)
  const mergedTiers = [
    { pattern: 'best available', label: 'Best Quality (Video + Audio)', match: (f: Format) => f.quality_label.toLowerCase().includes('best available') },
    { pattern: '2160', label: '4K Ultra HD (2160p) — Video + Audio', match: (f: Format) => f.quality_label.includes('2160') },
    { pattern: '1440', label: 'QHD (1440p) — Video + Audio', match: (f: Format) => f.quality_label.includes('1440') },
    { pattern: '1080', label: 'Full HD (1080p) — Video + Audio', match: (f: Format) => f.quality_label.includes('1080') },
    { pattern: '720', label: 'HD (720p) — Video + Audio', match: (f: Format) => f.quality_label.includes('720') },
    { pattern: '480', label: 'SD (480p) — Video + Audio', match: (f: Format) => f.quality_label.includes('480') },
  ]

  mergedTiers.forEach(({ label, match }) => {
    const format = mergedFormats.find(f => match(f))
    if (format) {
      formatted.push({
        ...format,
        friendlyLabel: label,
        friendlyType: '🎬 Video + Audio (MP4)',
        priority: priority++
      })
    }
  })

  // Best audio only
  if (audioOnly.length > 0) {
    const bestAudio = audioOnly.sort((a, b) => {
      const aSize = a.filesize_bytes || 0
      const bSize = b.filesize_bytes || 0
      return bSize - aSize
    })[0]

    formatted.push({
      ...bestAudio,
      friendlyLabel: 'Audio Only (Best Quality)',
      friendlyType: '🎵 Audio (M4A/WebM)',
      priority: 100
    })
  }

  // Remove duplicates and sort by priority
  const unique = formatted.filter((format, index, self) =>
    index === self.findIndex(f => f.id === format.id)
  )

  return unique.sort((a, b) => a.priority - b.priority)
}

export function FormatsTable({ videoInfo, originalUrl, isLoading = false }: FormatsTableProps) {
  const [downloadingIds, setDownloadingIds] = useState<Set<string>>(new Set())

  const handleDownload = async (formatId: string, filename: string) => {
    try {
      // Mark as downloading
      setDownloadingIds(prev => new Set(prev).add(formatId))

      // Trigger download via browser
      await downloadVideo(originalUrl, formatId, filename)

      // Keep showing downloading state for a moment
      setTimeout(() => {
        setDownloadingIds(prev => {
          const newSet = new Set(prev)
          newSet.delete(formatId)
          return newSet
        })
      }, 2000)
    } catch (error) {
      console.error('Download failed:', error)
      alert('Download failed. Please try again.')
      setDownloadingIds(prev => {
        const newSet = new Set(prev)
        newSet.delete(formatId)
        return newSet
      })
    }
  }

  const commonFormats = videoInfo ? getCommonFormats(videoInfo.formats) : []

  if (isLoading) {
    return (
      <div className="space-y-4">
        <div className="flex gap-4">
          <Skeleton className="h-32 w-48 rounded-lg" />
          <div className="space-y-2 flex-1">
            <Skeleton className="h-6 w-3/4" />
            <Skeleton className="h-4 w-1/4" />
          </div>
        </div>
        <Skeleton className="h-64 w-full" />
      </div>
    )
  }

  if (!videoInfo) {
    return null
  }

  return (
    <div className="space-y-6">
      {/* Video metadata */}
      <div className="flex gap-4 items-start">
        {videoInfo.thumbnail_url && (
          <div className="relative h-32 w-48 flex-shrink-0 rounded-lg overflow-hidden bg-muted">
            <Image
              src={videoInfo.thumbnail_url}
              alt={videoInfo.title}
              fill
              className="object-cover"
              unoptimized
            />
          </div>
        )}
        <div className="flex-1 min-w-0">
          <h2 className="text-xl font-semibold mb-2 break-words">{videoInfo.title}</h2>
          {videoInfo.duration_seconds && (
            <p className="text-sm text-muted-foreground">
              Duration: {formatDuration(videoInfo.duration_seconds)}
            </p>
          )}
        </div>
      </div>

      {/* Formats table */}
      <div className="space-y-2">
        <div className="border rounded-lg">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Format</TableHead>
                <TableHead>Details</TableHead>
                <TableHead>Size</TableHead>
                <TableHead className="text-right">Download</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {commonFormats.length === 0 ? (
                <TableRow>
                  <TableCell colSpan={4} className="text-center text-muted-foreground py-8">
                    No common formats available. Please try a different video.
                  </TableCell>
                </TableRow>
              ) : (
                commonFormats.map((format) => {
                  const isDownloading = downloadingIds.has(format.id)

                  return (
                    <TableRow key={format.id}>
                      <TableCell className="font-medium">{format.friendlyLabel}</TableCell>
                      <TableCell>
                        <div className="flex flex-col gap-1">
                          <span className="text-sm">{format.friendlyType}</span>
                          <span className="text-xs text-muted-foreground">
                            {format.quality_label}
                          </span>
                        </div>
                      </TableCell>
                      <TableCell>{formatFileSize(format.filesize_bytes)}</TableCell>
                      <TableCell className="text-right">
                        <Button
                          size="sm"
                          variant="outline"
                          onClick={() => {
                            const ext = format.is_audio_only ? 'm4a' : 'mp4'
                            const filename = `${videoInfo?.title}.${ext}`
                            handleDownload(format.id, filename)
                          }}
                          disabled={isDownloading}
                        >
                          {isDownloading ? (
                            <>
                              <Loader2 className="h-4 w-4 animate-spin mr-1" />
                              Starting...
                            </>
                          ) : (
                            <>
                              <Download className="h-4 w-4" />
                              Download
                            </>
                          )}
                        </Button>
                      </TableCell>
                    </TableRow>
                  )
                })
              )}
            </TableBody>
          </Table>
        </div>
        {commonFormats.some(f => f.friendlyType.includes('Video + Audio')) ? (
          <p className="text-xs text-muted-foreground px-2">
            ✨ Merged formats automatically combine the best video and audio streams into a single MP4 file using ffmpeg.
          </p>
        ) : null}
      </div>
    </div>
  )
}
