import type { Format } from '@/lib/api-client'

export interface UserFriendlyFormat extends Format {
  friendlyLabel: string
  friendlyType: string
  priority: number
}

/**
 * Curate a small set of human-friendly format rows from raw yt-dlp formats.
 */
export function getCommonFormats(formats: Format[]): UserFriendlyFormat[] {
  const formatted: UserFriendlyFormat[] = []

  const mergedFormats = formats.filter(
    (f) =>
      f.id.includes('+') ||
      f.quality_label.toLowerCase().includes('merged') ||
      f.id.startsWith('bestvideo') ||
      f.id === 'best'
  )
  const audioOnly = formats.filter((f) => f.is_audio_only)

  let priority = 1

  const mergedTiers = [
    {
      label: 'Best Quality (Video + Audio)',
      match: (f: Format) => f.quality_label.toLowerCase().includes('best available'),
    },
    {
      label: '4K Ultra HD (2160p) — Video + Audio',
      match: (f: Format) => f.quality_label.includes('2160'),
    },
    {
      label: 'QHD (1440p) — Video + Audio',
      match: (f: Format) => f.quality_label.includes('1440'),
    },
    {
      label: 'Full HD (1080p) — Video + Audio',
      match: (f: Format) => f.quality_label.includes('1080'),
    },
    {
      label: 'HD (720p) — Video + Audio',
      match: (f: Format) => f.quality_label.includes('720'),
    },
    {
      label: 'SD (480p) — Video + Audio',
      match: (f: Format) => f.quality_label.includes('480'),
    },
  ]

  mergedTiers.forEach(({ label, match }) => {
    const format = mergedFormats.find((f) => match(f))
    if (format) {
      formatted.push({
        ...format,
        friendlyLabel: label,
        friendlyType: 'Video + Audio (MP4)',
        priority: priority++,
      })
    }
  })

  if (audioOnly.length > 0) {
    const bestAudio = audioOnly.sort((a, b) => {
      const aSize = a.filesize_bytes || 0
      const bSize = b.filesize_bytes || 0
      return bSize - aSize
    })[0]

    const isWebm = bestAudio.mime_type.includes('webm')
    formatted.push({
      ...bestAudio,
      friendlyLabel: 'Audio Only (Best Quality)',
      friendlyType: isWebm ? 'Audio (WebM) — may need VLC' : 'Audio (M4A)',
      priority: 100,
    })
  }

  const unique = formatted.filter(
    (format, index, self) => index === self.findIndex((f) => f.id === format.id)
  )

  return unique.sort((a, b) => a.priority - b.priority)
}
