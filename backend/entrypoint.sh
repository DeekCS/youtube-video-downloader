#!/bin/sh
set -e

# Decode base64-encoded cookies file if the env var is set.
# Supports chunked cookies split across YTDLP_COOKIES_BASE64_1,
# YTDLP_COOKIES_BASE64_2, … for large cookie files that exceed
# Railway's 32KB env var limit.
if [ -n "$YTDLP_COOKIES_BASE64" ]; then
    echo "$YTDLP_COOKIES_BASE64" | base64 -d > /app/cookies.txt
    export YTDLP_COOKIES_FILE=/app/cookies.txt
    echo "Cookies file decoded from YTDLP_COOKIES_BASE64"
elif [ -n "$YTDLP_COOKIES_BASE64_1" ]; then
    COMBINED=""
    i=1
    while true; do
        CHUNK=$(eval echo "\$YTDLP_COOKIES_BASE64_$i" 2>/dev/null)
        [ -z "$CHUNK" ] && break
        COMBINED="${COMBINED}${CHUNK}"
        i=$((i + 1))
    done
    echo "$COMBINED" | base64 -d > /app/cookies.txt
    export YTDLP_COOKIES_FILE=/app/cookies.txt
    echo "Cookies file decoded from $((i - 1)) chunks"
fi

exec "$@"
