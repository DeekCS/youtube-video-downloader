#!/usr/bin/env bash
# Upload a Netscape cookies.txt to Railway in ≤32KB chunks (Railway env var limit).
# Requires: railway login, backend service name matching -s (default: Backend).
#
# 1. In Railway: remove or clear YTDLP_COOKIES_BASE64 if it blocks deploy (too long).
# 2. Run from repo root:
#    ./scripts/railway-cookies-chunks.sh /path/to/cookies.txt
#    RAILWAY_BACKEND_SERVICE=Backend ./scripts/railway-cookies-chunks.sh ./cookies.txt
#
# Optional: --delete-single  →  railway variable delete YTDLP_COOKIES_BASE64 first (ignore errors)

set -euo pipefail

_SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=/dev/null
source "$_SCRIPT_DIR/railway-common.sh"

CHUNK_SIZE=31000
DELETE_SINGLE=0

while [[ "${1:-}" == -* ]]; do
  case "$1" in
    --delete-single) DELETE_SINGLE=1 ;;
    -h|--help)
      echo "Usage: $0 [--delete-single] <cookies.txt>"
      exit 0
      ;;
    *) echo "Unknown option: $1" >&2; exit 1 ;;
  esac
  shift
done

COOKIES_FILE="${1:-}"
if [[ -z "$COOKIES_FILE" || ! -f "$COOKIES_FILE" ]]; then
  echo "Usage: $0 [--delete-single] <cookies.txt>" >&2
  exit 1
fi

railway_load_service_slugs
SERVICE="${RAILWAY_BACKEND_SERVICE:-$BACKEND_SLUG}"

if ! command -v railway >/dev/null 2>&1; then
  echo "Install: npm i -g @railway/cli" >&2
  exit 1
fi

if [[ "$DELETE_SINGLE" -eq 1 ]]; then
  railway variable delete YTDLP_COOKIES_BASE64 -s "$SERVICE" 2>/dev/null || true
fi

B64=$(base64 < "$COOKIES_FILE" | tr -d '\n')
LEN=${#B64}
echo "Base64 length: $LEN (Railway max per variable: 32768)"

if [[ "$LEN" -le 32768 ]]; then
  echo "Fits in one variable. Uploading YTDLP_COOKIES_BASE64 ..."
  printf '%s' "$B64" | railway variable set YTDLP_COOKIES_BASE64 --stdin -s "$SERVICE"
  echo "Done."
  exit 0
fi

echo "Splitting into chunks of $CHUNK_SIZE characters → YTDLP_COOKIES_BASE64_1, _2, ..."
i=1
pos=0
while [ "$pos" -lt "$LEN" ]; do
  chunk="${B64:$pos:$CHUNK_SIZE}"
  clen=${#chunk}
  [ "$clen" -eq 0 ] && break
  echo "  Uploading YTDLP_COOKIES_BASE64_$i ($clen chars) ..."
  printf '%s' "$chunk" | railway variable set "YTDLP_COOKIES_BASE64_$i" --stdin -s "$SERVICE"
  pos=$((pos + clen))
  i=$((i + 1))
done

count=$((i - 1))
echo ""
echo "Done ($count chunks). Redeploy the Backend service."
echo ""
echo "If deploy was blocked: open Railway → Backend → Variables, DELETE variable"
echo "YTDLP_COOKIES_BASE64 (the single huge one), then Deploy. Chunked vars do not use that key."
