import type { Metadata, Viewport } from 'next'
import { Inter } from 'next/font/google'
import './globals.css'
import { Providers } from './providers'
import { validateEnv } from '@/lib/env'

const inter = Inter({ subsets: ['latin'] })

// Validate environment at build time
validateEnv()

export const viewport: Viewport = {
  width: 'device-width',
  initialScale: 1,
  maximumScale: 1,
}

export const metadata: Metadata = {
  title: {
    default: 'Video Downloader',
    template: '%s · Video Downloader',
  },
  description:
    'Self-hosted multi-platform video downloader. Fetch formats and download with yt-dlp.',
  keywords: ['video downloader', 'yt-dlp', 'self-hosted', 'YouTube'],
  robots: { index: true, follow: true },
  openGraph: {
    title: 'Video Downloader',
    description: 'Self-hosted multi-platform video downloader',
    type: 'website',
  },
}

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode
}>) {
  return (
    <html lang="en" suppressHydrationWarning>
      <body className={inter.className}>
        <Providers>{children}</Providers>
      </body>
    </html>
  )
}
