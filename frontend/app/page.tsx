import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Downloader } from '@/components/video/downloader'
import { AlertTriangle } from 'lucide-react'
import { Alert, AlertDescription } from '@/components/ui/alert'

export default function Home() {
  return (
    <main className="min-h-screen bg-gradient-to-b from-background to-muted/20">
      <div className="container max-w-5xl mx-auto py-6 sm:py-12 px-4">
        {/* Header */}
        <div className="text-center mb-6 sm:mb-12">
          <h1 className="text-2xl sm:text-4xl font-bold tracking-tight mb-1 sm:mb-2">Video Downloader</h1>
          <p className="text-sm sm:text-base text-muted-foreground">
            Download videos from YouTube and other platforms
          </p>
        </div>

        {/* Main Card */}
        <Card className="shadow-lg">
          <CardHeader className="px-4 sm:px-6 py-4 sm:py-6">
            <CardTitle className="text-lg sm:text-xl">Download Video</CardTitle>
            <CardDescription className="text-xs sm:text-sm">
              Enter a video URL to see available formats and download options
            </CardDescription>
          </CardHeader>
          <CardContent className="px-4 sm:px-6 pb-4 sm:pb-6">
            <Downloader />
          </CardContent>
        </Card>

        {/* Legal Notice */}
        <Alert className="mt-6 sm:mt-8">
          <AlertTriangle className="h-4 w-4" />
          <AlertDescription className="text-xs sm:text-sm">
            <strong>Legal Notice:</strong> Only download content you own or have explicit rights to
            download. Users are responsible for complying with applicable copyright laws, terms of
            service, and platform policies. Misuse may violate laws in your jurisdiction.
          </AlertDescription>
        </Alert>

        {/* Footer */}
        <footer className="text-center mt-8 sm:mt-12 text-xs sm:text-sm text-muted-foreground">
          <p>
            Built with{' '}
            <a
              href="https://nextjs.org"
              target="_blank"
              rel="noopener noreferrer"
              className="underline hover:text-foreground"
            >
              Next.js
            </a>
            ,{' '}
            <a
              href="https://fastapi.tiangolo.com"
              target="_blank"
              rel="noopener noreferrer"
              className="underline hover:text-foreground"
            >
              FastAPI
            </a>
            , and{' '}
            <a
              href="https://github.com/yt-dlp/yt-dlp"
              target="_blank"
              rel="noopener noreferrer"
              className="underline hover:text-foreground"
            >
              yt-dlp
            </a>
          </p>
        </footer>
      </div>
    </main>
  )
}
