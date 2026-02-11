# Video Downloader Frontend

Next.js 16 frontend application for the video downloader.

## Setup

```bash
# Install pnpm if not already installed
npm install -g pnpm

# Install dependencies
pnpm install

# Copy environment template
cp .env.example .env.local

# Edit .env.local and set NEXT_PUBLIC_API_BASE to your backend URL

# Run development server
pnpm dev
```

## Development

```bash
# Run dev server (with hot reload)
pnpm dev

# Build for production
pnpm build

# Start production server
pnpm start

# Lint code
pnpm lint

# Type check
pnpm typecheck

# Format code
pnpm format
```

## Project Structure

```
frontend/
├── app/
│   ├── layout.tsx          # Root layout with providers
│   ├── page.tsx            # Main downloader page
│   ├── providers.tsx       # Client-side providers (React Query, Theme)
│   └── globals.css         # Global styles (Tailwind + CSS variables)
├── components/
│   ├── video/              # Video-related components
│   │   ├── downloader.tsx  # Main client component
│   │   ├── url-form.tsx    # URL input form
│   │   └── formats-table.tsx # Formats display table
│   └── ui/                 # shadcn/ui components
│       ├── button.tsx
│       ├── card.tsx
│       ├── input.tsx
│       └── ...
├── lib/
│   ├── api-client.ts       # API client + zod schemas
│   ├── env.ts              # Typed environment variables
│   └── utils.ts            # Utility functions (cn helper, etc.)
├── public/                 # Static assets
├── package.json            # Dependencies
├── tsconfig.json           # TypeScript configuration
├── tailwind.config.ts      # Tailwind configuration
└── next.config.ts          # Next.js configuration
```

## Environment Variables

- `NEXT_PUBLIC_API_BASE`: Backend API base URL (must include `/api/v1` prefix)
  - Development: `http://localhost:8000/api/v1`
  - Production: `https://your-backend.up.railway.app/api/v1`

## Adding shadcn/ui Components

This project uses shadcn/ui components. To add new components:

```bash
# Example: Add a dialog component
npx shadcn@latest add dialog
```

Components will be added to `components/ui/`.
