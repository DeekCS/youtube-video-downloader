#!/usr/bin/env bash
# One-shot Railway setup after you have logged in and linked the project.
#
#   cd /path/to/youtube-video-downloader
#   railway login
#   railway link
#   ./scripts/railway-bootstrap.sh
#
# Optional: RAILWAY_TOKEN in the environment (Railway dashboard → Account → Tokens).

set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"
# shellcheck source=/dev/null
source "$ROOT/scripts/railway-common.sh"

if ! command -v railway >/dev/null 2>&1; then
  echo "Install the Railway CLI: npm i -g @railway/cli" >&2
  exit 1
fi

if ! railway whoami >/dev/null 2>&1; then
  echo "Not logged in. Run in this terminal (interactive):" >&2
  echo "  railway login" >&2
  echo "Or set RAILWAY_TOKEN from https://railway.com/account/tokens" >&2
  exit 1
fi

echo "Railway account: $(railway whoami)"
if ! railway status >/dev/null 2>&1; then
  echo "No project linked. From $ROOT run:" >&2
  echo "  railway link" >&2
  exit 1
fi
railway status
echo ""

bash "$ROOT/scripts/railway-set-env.sh"

railway_load_service_slugs

echo "Ensuring public domains (no-op if already set)..."
railway domain -s "$BACKEND_SLUG" 2>/dev/null || true
railway domain -s "$FRONTEND_SLUG" 2>/dev/null || true

echo ""
echo "Redeploying $BACKEND_SLUG and $FRONTEND_SLUG..."
railway redeploy -y -s "$BACKEND_SLUG" || true
railway redeploy -y -s "$FRONTEND_SLUG" || true

echo ""
echo "Done. Check:"
echo "  railway logs -s $BACKEND_SLUG"
echo "  railway logs -s $FRONTEND_SLUG"
