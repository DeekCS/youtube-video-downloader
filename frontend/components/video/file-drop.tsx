'use client'

import { useState, useRef, useCallback, useEffect } from 'react'
import { Upload, FileVideo, X, CheckCircle, XCircle, ArrowRight } from 'lucide-react'

import { Button } from '@/components/ui/button'
import { Progress } from '@/components/ui/progress'
import { Alert, AlertDescription } from '@/components/ui/alert'
import {
  startConversion,
  subscribeToConversionProgress,
  buildConversionFileUrl,
  type DownloadProgress,
  getErrorMessage,
} from '@/lib/api-client'

// ---------------------------------------------------------------------------
// Format catalogue
// ---------------------------------------------------------------------------

const OUTPUT_FORMATS = [
  { value: 'mp4',  label: 'MP4',  description: 'Video — best compatibility' },
  { value: 'mkv',  label: 'MKV',  description: 'Video — lossless stream copy' },
  { value: 'webm', label: 'WebM', description: 'Video — open web format' },
  { value: 'avi',  label: 'AVI',  description: 'Video — legacy' },
  { value: 'mov',  label: 'MOV',  description: 'Video — Apple / QuickTime' },
  { value: 'mp3',  label: 'MP3',  description: 'Audio — universal' },
  { value: 'aac',  label: 'AAC',  description: 'Audio — high efficiency' },
  { value: 'm4a',  label: 'M4A',  description: 'Audio — Apple / iTunes' },
  { value: 'wav',  label: 'WAV',  description: 'Audio — lossless PCM' },
  { value: 'ogg',  label: 'OGG',  description: 'Audio — open format' },
  { value: 'flac', label: 'FLAC', description: 'Audio — lossless compressed' },
] as const

type OutputFormat = (typeof OUTPUT_FORMATS)[number]['value']

const ACCEPTED_EXTENSIONS = [
  'mp4', 'mkv', 'webm', 'avi', 'mov', 'flv', 'wmv', 'mpeg', 'mpg',
  '3gp', 'm4v', 'ts', 'mp3', 'aac', 'm4a', 'wav', 'ogg', 'flac', 'opus',
]

const MAX_SIZE_BYTES = 2 * 1024 * 1024 * 1024 // 2 GB

function fmtBytes(bytes: number): string {
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(0)} KB`
  if (bytes < 1024 * 1024 * 1024) return `${(bytes / (1024 * 1024)).toFixed(1)} MB`
  return `${(bytes / (1024 * 1024 * 1024)).toFixed(2)} GB`
}

// ---------------------------------------------------------------------------
// State types
// ---------------------------------------------------------------------------

type Stage = 'idle' | 'uploading' | 'converting' | 'completed' | 'failed'

interface ConvertState {
  stage: Stage
  progress: number
  label: string
  error?: string
}

const INITIAL: ConvertState = { stage: 'idle', progress: 0, label: '' }

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

export function FileDrop() {
  const [dragging, setDragging] = useState(false)
  const [file, setFile] = useState<File | null>(null)
  const [targetFormat, setTargetFormat] = useState<OutputFormat>('mp4')
  const [state, setState] = useState<ConvertState>(INITIAL)

  const inputRef = useRef<HTMLInputElement>(null)
  const cleanupRef = useRef<(() => void) | null>(null)

  useEffect(() => {
    return () => { cleanupRef.current?.() }
  }, [])

  // -------------------------------------------------------------------------
  // File validation
  // -------------------------------------------------------------------------

  const validateFile = (f: File): string | null => {
    const ext = f.name.split('.').pop()?.toLowerCase() ?? ''
    if (!ACCEPTED_EXTENSIONS.includes(ext)) return `Unsupported file type .${ext}`
    if (f.size > MAX_SIZE_BYTES) return 'File too large (max 2 GB)'
    return null
  }

  const selectFile = useCallback((f: File) => {
    const err = validateFile(f)
    if (err) {
      setState({ stage: 'failed', progress: 0, label: '', error: err })
      return
    }
    setFile(f)
    setState(INITIAL)
    cleanupRef.current?.()
    cleanupRef.current = null
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  // -------------------------------------------------------------------------
  // Drag-and-drop handlers
  // -------------------------------------------------------------------------

  const onDragOver = useCallback((e: React.DragEvent) => {
    e.preventDefault()
    setDragging(true)
  }, [])

  const onDragLeave = useCallback((e: React.DragEvent) => {
    if (!e.currentTarget.contains(e.relatedTarget as Node)) {
      setDragging(false)
    }
  }, [])

  const onDrop = useCallback(
    (e: React.DragEvent) => {
      e.preventDefault()
      setDragging(false)
      const dropped = e.dataTransfer.files[0]
      if (dropped) selectFile(dropped)
    },
    [selectFile],
  )

  // -------------------------------------------------------------------------
  // Conversion
  // -------------------------------------------------------------------------

  const handleConvert = async () => {
    if (!file) return

    cleanupRef.current?.()
    cleanupRef.current = null

    setState({ stage: 'uploading', progress: 0, label: `Uploading ${file.name}…` })

    let taskId: string
    let filename: string
    try {
      ;({ taskId, filename } = await startConversion(file, targetFormat))
    } catch (err) {
      setState({ stage: 'failed', progress: 0, label: '', error: getErrorMessage(err) })
      return
    }

    setState({ stage: 'converting', progress: 0, label: 'Starting conversion…' })

    const cleanup = subscribeToConversionProgress(
      taskId,
      (p: DownloadProgress) => {
        if (p.status === 'completed') {
          setState({ stage: 'completed', progress: 100, label: 'Saved ✓' })
          const link = document.createElement('a')
          link.href = buildConversionFileUrl(taskId)
          link.download = filename
          link.style.display = 'none'
          document.body.appendChild(link)
          link.click()
          setTimeout(() => document.body.removeChild(link), 3000)
          cleanupRef.current?.()
          cleanupRef.current = null
          return
        }
        if (p.status === 'failed') {
          setState({
            stage: 'failed',
            progress: 0,
            label: '',
            error: p.error ?? 'Conversion failed',
          })
          cleanupRef.current?.()
          cleanupRef.current = null
          return
        }
        const label =
          p.status === 'converting'
            ? `Converting… ${Math.round(p.progress)}%`
            : 'Preparing…'
        setState({ stage: 'converting', progress: p.progress, label })
      },
      () => {
        setState({ stage: 'failed', progress: 0, label: '', error: 'Connection lost' })
        cleanupRef.current = null
      },
    )

    cleanupRef.current = cleanup
  }

  const reset = () => {
    cleanupRef.current?.()
    cleanupRef.current = null
    setFile(null)
    setState(INITIAL)
    setDragging(false)
  }

  // -------------------------------------------------------------------------
  // Render
  // -------------------------------------------------------------------------

  const busy = state.stage === 'uploading' || state.stage === 'converting'

  return (
    <div className="space-y-6">
      {/* Drop zone */}
      <div
        role="button"
        tabIndex={0}
        aria-label="Drop a video or audio file here to convert it"
        onDragOver={onDragOver}
        onDragLeave={onDragLeave}
        onDrop={onDrop}
        onKeyDown={(e) => {
          if ((e.key === 'Enter' || e.key === ' ') && !busy) inputRef.current?.click()
        }}
        onClick={() => { if (!busy) inputRef.current?.click() }}
        className={[
          'relative border-2 border-dashed rounded-xl p-10 text-center transition-colors select-none',
          busy ? 'cursor-default opacity-70' : 'cursor-pointer',
          dragging
            ? 'border-primary bg-primary/10'
            : 'border-muted-foreground/30 hover:border-primary/50',
        ].join(' ')}
      >
        <input
          ref={inputRef}
          type="file"
          accept={ACCEPTED_EXTENSIONS.map((e) => `.${e}`).join(',')}
          className="sr-only"
          onChange={(e) => {
            const f = e.target.files?.[0]
            if (f) selectFile(f)
            // reset so the same file can be re-selected after reset
            e.target.value = ''
          }}
        />

        {file ? (
          <div className="flex items-center justify-center gap-3">
            <FileVideo className="h-8 w-8 text-primary shrink-0" />
            <div className="text-left min-w-0">
              <p className="font-medium truncate max-w-[260px]">{file.name}</p>
              <p className="text-sm text-muted-foreground">{fmtBytes(file.size)}</p>
            </div>
            {!busy && (
              <button
                type="button"
                aria-label="Remove file"
                onClick={(e) => { e.stopPropagation(); reset() }}
                className="ml-2 text-muted-foreground hover:text-foreground transition-colors"
              >
                <X className="h-4 w-4" />
              </button>
            )}
          </div>
        ) : (
          <div className="flex flex-col items-center gap-3 text-muted-foreground">
            <Upload className="h-10 w-10" />
            <div>
              <p className="font-medium text-foreground">Drop a video or audio file here</p>
              <p className="text-sm mt-1">
                or click to browse &mdash; MP4, MKV, WebM, AVI, MOV, MP3, WAV&hellip;
              </p>
              <p className="text-xs mt-2">Max 2 GB</p>
            </div>
          </div>
        )}
      </div>

      {/* Format selector */}
      {file && !busy && state.stage !== 'completed' && (
        <div className="space-y-2">
          <p className="text-sm font-medium">Output format</p>
          <div className="grid grid-cols-4 sm:grid-cols-6 gap-2">
            {OUTPUT_FORMATS.map((fmt) => (
              <button
                key={fmt.value}
                type="button"
                title={fmt.description}
                onClick={() => setTargetFormat(fmt.value)}
                className={[
                  'rounded-lg border px-3 py-2 text-sm font-medium transition-colors',
                  targetFormat === fmt.value
                    ? 'border-primary bg-primary text-primary-foreground'
                    : 'border-border hover:border-primary/60',
                ].join(' ')}
              >
                {fmt.label}
              </button>
            ))}
          </div>
          <p className="text-xs text-muted-foreground">
            {OUTPUT_FORMATS.find((f) => f.value === targetFormat)?.description}
          </p>
        </div>
      )}

      {/* Progress */}
      {(state.stage === 'uploading' || state.stage === 'converting') && (
        <div className="space-y-2">
          <div className="flex items-center justify-between text-sm">
            <span className="text-muted-foreground">{state.label}</span>
            {state.stage === 'converting' && (
              <span className="text-muted-foreground">{Math.round(state.progress)}%</span>
            )}
          </div>
          {state.stage === 'uploading' ? (
            /* indeterminate — pulse the full bar */
            <div className="h-2 w-full rounded-full bg-primary/20 overflow-hidden">
              <div className="h-full w-full bg-primary animate-pulse" />
            </div>
          ) : (
            <Progress value={state.progress} className="h-2" />
          )}
        </div>
      )}

      {/* Completed */}
      {state.stage === 'completed' && (
        <div className="flex items-center gap-2 text-green-600 dark:text-green-400">
          <CheckCircle className="h-5 w-5 shrink-0" />
          <span className="text-sm font-medium">
            Conversion complete — your download has started.
          </span>
          <Button size="sm" variant="outline" className="ml-auto" onClick={reset}>
            Convert another
          </Button>
        </div>
      )}

      {/* Error */}
      {state.stage === 'failed' && state.error && (
        <Alert variant="destructive">
          <XCircle className="h-4 w-4" />
          <AlertDescription className="flex items-center justify-between gap-2">
            <span>{state.error}</span>
            <Button size="sm" variant="ghost" onClick={reset}>
              Try again
            </Button>
          </AlertDescription>
        </Alert>
      )}

      {/* Convert button */}
      {file && !busy && state.stage !== 'completed' && (
        <Button className="w-full" onClick={handleConvert} disabled={busy}>
          <ArrowRight className="h-4 w-4 mr-2" />
          Convert to {targetFormat.toUpperCase()}
        </Button>
      )}
    </div>
  )
}
