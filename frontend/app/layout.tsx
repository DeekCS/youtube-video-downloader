import type { Metadata } from 'next'
import { Inter } from 'next/font/google'
import './globals.css'
import { Providers } from './providers'
import { validateEnv } from '@/lib/env'

const inter = Inter({ subsets: ['latin'] })

// Validate environment at build time
validateEnv()

export const metadata: Metadata = {
  title: 'Video Downloader',
  description: 'Self-hosted multi-platform video downloader',
}

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode
}>) {
  return (
    <html lang="en">
      <body className={inter.className}>
        <Providers>{children}</Providers>
      </body>
    </html>
  )
}
