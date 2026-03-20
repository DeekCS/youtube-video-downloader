# Production Dockerfile for Next.js frontend
FROM node:20-alpine AS base

# Install dependencies only when needed
FROM base AS deps
RUN apk add --no-cache libc6-compat
WORKDIR /app

# Install pnpm
RUN npm install -g pnpm

# Copy package files
COPY package.json pnpm-lock.yaml* ./
RUN pnpm install --frozen-lockfile

# Rebuild the source code only when needed
FROM base AS builder
WORKDIR /app
COPY --from=deps /app/node_modules ./node_modules
COPY . .

# Build arguments for environment variables (must be set for production; see docker-compose / Railway)
ARG NEXT_PUBLIC_API_BASE
ENV NEXT_PUBLIC_API_BASE=$NEXT_PUBLIC_API_BASE

RUN npm install -g pnpm
# Fail fast with a clear error instead of a vague runtime crash
RUN if [ -z "$NEXT_PUBLIC_API_BASE" ]; then \
  echo "ERROR: NEXT_PUBLIC_API_BASE build-arg is empty. Set it to your backend URL including /api/v1 (Railway: service variable + dockerfileArgs)."; \
  exit 1; \
fi
RUN pnpm build

# Production image, copy all the files and run next
FROM base AS runner
WORKDIR /app

# Same URL at runtime (SSR / server); must repeat ARG in this stage for Docker
ARG NEXT_PUBLIC_API_BASE
ENV NEXT_PUBLIC_API_BASE=${NEXT_PUBLIC_API_BASE}
ENV NODE_ENV=production

RUN addgroup --system --gid 1001 nodejs
RUN adduser --system --uid 1001 nextjs

COPY --from=builder /app/public ./public

# Set the correct permission for prerender cache
RUN mkdir .next
RUN chown nextjs:nodejs .next

# Automatically leverage output traces to reduce image size
COPY --from=builder --chown=nextjs:nodejs /app/.next/standalone ./
COPY --from=builder --chown=nextjs:nodejs /app/.next/static ./.next/static

USER nextjs

EXPOSE 3000

ENV PORT=3000
# Bind to all interfaces so Railway/Docker can route traffic
ENV HOSTNAME=0.0.0.0

CMD ["node", "server.js"]
