#!/usr/bin/env bash
# Apply standard environment variables to Railway services via CLI.
#
# Prerequisites:
#   npm i -g @railway/cli   # or: brew install railway
#   railway login
#   railway link            # from repo root, select your project
#
# Before running:
#   1. Create two services in the project (same GitHub repo), with root dirs backend / frontend.
#   2. Match BACKEND_REF / FRONTEND_REF to the names Railway uses in ${{ Service.RAILWAY_PUBLIC_DOMAIN }}
#      (often the display name, e.g. Backend / Frontend — check Variables UI when adding a reference).
#
# Usage (from monorepo root):
#   ./scripts/railway-set-env.sh
#   RAILWAY_BACKEND_SERVICE=my-api RAILWAY_FRONTEND_SERVICE=my-web ./scripts/railway-set-env.sh
#
# Service names are auto-detected from `railway status --json` (rootDirectory backend/frontend).
# Override with RAILWAY_BACKEND_SERVICE / RAILWAY_FRONTEND_SERVICE if needed.

set -euo pipefail

_SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=/dev/null
source "$_SCRIPT_DIR/railway-common.sh"

if ! command -v railway >/dev/null 2>&1; then
  echo "Install the Railway CLI: npm i -g @railway/cli" >&2
  exit 1
fi

railway_load_service_slugs
BACKEND_REF="${RAILWAY_BACKEND_REF:-$BACKEND_SLUG}"
FRONTEND_REF="${RAILWAY_FRONTEND_REF:-$FRONTEND_SLUG}"

echo "Using backend service slug: $BACKEND_SLUG (reference token: $BACKEND_REF)"
echo "Using frontend service slug: $FRONTEND_SLUG (reference token: $FRONTEND_REF)"
echo ""

railway variable set --skip-deploys -s "$BACKEND_SLUG" \
  ENV=production \
  API_V1_PREFIX=/api/v1 \
  LOG_LEVEL=INFO \
  BLOCK_PRIVATE_NETWORKS=true \
  ALLOWED_URL_SCHEMES=http,https \
  YTDLP_YOUTUBE_PLAYER_CLIENT=tv_embedded \
  YTDLP_USE_IOS_CLIENT=false \
  YTDLP_CONCURRENT_FRAGMENTS=32 \
  YTDLP_STREAM_CHUNK_SIZE=2097152 \
  YTDLP_BUFFER_SIZE=1M \
  YTDLP_SOCKET_TIMEOUT=60 \
  YTDLP_FILE_ACCESS_RETRIES=5 \
  YTDLP_THROTTLED_RATE=50K \
  YTDLP_PREFER_FREE_FORMATS=true

# Railway reference: ${{ ServiceName.RAILWAY_PUBLIC_DOMAIN }} (ServiceName must match dashboard)
CORS_VALUE='CORS_ORIGINS=https://${{'"${FRONTEND_REF}"'.RAILWAY_PUBLIC_DOMAIN}}'
railway variable set --skip-deploys -s "$BACKEND_SLUG" "$CORS_VALUE"

railway variable set --skip-deploys -s "$FRONTEND_SLUG" \
  'NEXT_PUBLIC_API_BASE=https://${{'"${BACKEND_REF}"'.RAILWAY_PUBLIC_DOMAIN}}/api/v1'

echo ""
echo "Variables applied (deploys skipped per flag). Redeploy to pick them up:"
echo "  railway redeploy -y -s $BACKEND_SLUG"
echo "  railway redeploy -y -s $FRONTEND_SLUG"
echo ""
echo "Generate public URLs if you have not yet:"
echo "  railway domain -s $BACKEND_SLUG"
echo "  railway domain -s $FRONTEND_SLUG"
echo ""
echo "Logs:"
echo "  railway logs -s $BACKEND_SLUG"
echo "  railway logs -s $FRONTEND_SLUG"
