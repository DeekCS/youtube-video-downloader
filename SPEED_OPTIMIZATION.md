# Download Speed Optimization Guide

This document explains all the speed optimizations implemented in the video downloader and how to tune them for maximum performance.

## Quick Start: Maximum Speed Configuration

The following settings in `docker-compose.yml` are already configured for best performance:

```yaml
environment:
  # Aggressive parallel downloads (DASH/HLS)
  - YTDLP_CONCURRENT_FRAGMENTS=32

  # Large streaming buffer (2MB chunks)
  - YTDLP_STREAM_CHUNK_SIZE=2097152

  # Large internal buffer
  - YTDLP_BUFFER_SIZE=1M

  # Anti-throttling
  - YTDLP_THROTTLED_RATE=50K
  - YTDLP_USE_IOS_CLIENT=true
  - YTDLP_PREFER_FREE_FORMATS=true

  # iOS user agent
  - YTDLP_USER_AGENT=Mozilla/5.0 (iPad; CPU OS 16_6 like Mac OS X) AppleWebKit/605.1.15
```

## Architecture Improvements

### 1. Non-Blocking Async Streaming
- **What**: Download subprocess runs in background threads
- **Why**: Prevents FastAPI event loop blocking
- **Impact**: Server stays responsive, higher sustained throughput
- **Code**: `backend/app/api/v1/endpoints/videos.py` uses `asyncio.to_thread()`

### 2. Format Metadata Caching
- **What**: 10-minute TTL cache for format info
- **Why**: Avoids double `extract_info()` call before download
- **Impact**: Faster download start (saves 2-5 seconds)
- **Defaults**: 600s TTL, 128 entries max

### 3. Stderr Pipe Draining
- **What**: Background thread reads stderr continuously
- **Why**: Prevents subprocess stall on full pipe buffer
- **Impact**: Eliminates random hangs during downloads

## Speed Options Explained

### Fragment Concurrency (DASH/HLS videos)
```yaml
YTDLP_CONCURRENT_FRAGMENTS=32  # Default: 8, Range: 1-32
```
- Higher = faster for fragmented formats (most YouTube videos)
- Too high can trigger throttling or overload network
- **Recommended**: 16-32 for good internet, 8-16 for slower

### HTTP Chunk Size
```yaml
YTDLP_HTTP_CHUNK_SIZE=  # Empty = disabled, or "10M", "50M"
```
- Some servers throttle large chunk requests
- Empty string disables chunked mode (often faster)
- **Try if slow**: Set empty first, then try "10M" if still slow

### Streaming Buffer
```yaml
YTDLP_STREAM_CHUNK_SIZE=2097152  # 2MB
```
- Size of chunks read from yt-dlp and sent to browser
- Larger = higher throughput, more memory
- **Range**: 512KB to 16MB

## Anti-Throttling Techniques

### 1. iOS Client Impersonation
```yaml
YTDLP_USE_IOS_CLIENT=true
```
- **YouTube-specific**: Uses mobile app API endpoints
- **Why effective**: Mobile clients less throttled than desktop/bots
- **Alternative**: Try `player_client=android` by editing service code

### 2. Throttling Auto-Bypass
```yaml
YTDLP_THROTTLED_RATE=50K
```
- If speed drops below this rate, yt-dlp re-extracts video info
- Gets fresh download URL, often bypassing throttle
- **Lower = more aggressive**, but more API calls

### 3. Browser Cookie Authentication (Most Effective)
```yaml
YTDLP_COOKIES_FROM_BROWSER=chrome  # or firefox, edge, safari
```
- **Requires**: Browser installed on Docker host (Mac in your case)
- **How**: yt-dlp reads cookies from your logged-in browser session
- **Why best**: Authenticated requests rarely throttled
- **Limitation**: Requires volume mount or cookie file sharing

**To enable**:
1. Install Chrome/Firefox on your Mac
2. Log into YouTube
3. Add to `docker-compose.yml`:
   ```yaml
   - YTDLP_COOKIES_FROM_BROWSER=chrome
   volumes:
     - ~/.config/google-chrome:/root/.config/google-chrome:ro
   ```
4. Restart: `docker compose restart backend`

### 4. User Agent Spoofing
```yaml
YTDLP_USER_AGENT=Mozilla/5.0 (iPad; CPU OS 16_6...)
```
- Pretends to be an iPad
- Matches iOS client for consistency

### 5. Prefer Free Formats
```yaml
YTDLP_PREFER_FREE_FORMATS=true
```
- Chooses WebM/MP4 over proprietary codecs
- Free formats often served from faster CDNs

### 6. SponsorBlock (Optional - Reduces Download Size)
```yaml
YTDLP_SPONSORBLOCK_REMOVE=sponsor,intro,outro
```
- Skips downloading sponsor segments
- Reduces total download size/time
- **Note**: Requires SponsorBlock database lookup (adds small delay upfront)

## Recommended Preset Configurations

### For YouTube (Most Users)
```yaml
- YTDLP_CONCURRENT_FRAGMENTS=32
- YTDLP_HTTP_CHUNK_SIZE=
- YTDLP_THROTTLED_RATE=50K
- YTDLP_USE_IOS_CLIENT=true
- YTDLP_COOKIES_FROM_BROWSER=chrome  # If you have Chrome
```

### For Other Platforms (Vimeo, Dailymotion, etc.)
```yaml
- YTDLP_CONCURRENT_FRAGMENTS=16
- YTDLP_HTTP_CHUNK_SIZE=10M
- YTDLP_USE_IOS_CLIENT=false
```

### For Slow/Throttled Connections
```yaml
- YTDLP_CONCURRENT_FRAGMENTS=8
- YTDLP_HTTP_CHUNK_SIZE=
- YTDLP_THROTTLED_RATE=20K
- YTDLP_SLEEP_REQUESTS=1  # Wait 1s between requests
```

## Troubleshooting

### Still Getting ~100 KB/s?

**Likely causes:**

1. **Platform throttling** (most common with YouTube)
   - Enable browser cookies: `YTDLP_COOKIES_FROM_BROWSER=chrome`
   - Try different format (720p vs 1080p merged)
   - Try audio-only format to confirm

2. **ISP throttling specific domains**
   - Test with different video platform
   - Try with VPN

3. **Server-side limitation**
   - Some videos are just slow from source
   - Try popular/recent videos (better CDN)

### Downloads Start Slow Then Speed Up
- Normal behavior (TCP slow-start)
- Increase buffer: `YTDLP_BUFFER_SIZE=2M`
- Increase stream chunk: `YTDLP_STREAM_CHUNK_SIZE=4194304`

### Downloads Keep Restarting
- `YTDLP_THROTTLED_RATE` too high
- Lower it: `YTDLP_THROTTLED_RATE=20K`
- Or disable: `YTDLP_THROTTLED_RATE=0`

### High Memory Usage
- Reduce: `YTDLP_STREAM_CHUNK_SIZE=524288` (512KB)
- Reduce: `YTDLP_CONCURRENT_FRAGMENTS=16`

## Monitoring & Debugging

### Check Current Settings
```bash
docker exec youtube-video-downloader-backend-1 env | grep YTDLP
```

### Watch Live Logs
```bash
docker logs youtube-video-downloader-backend-1 -f
```

### Test Specific Format
In the UI, try downloading:
1. **Audio-only** format first (fastest, rarely throttled)
2. **Single-file** format like "720p" (not merged)
3. **Merged** format like "1080p (merged)"

If audio is fast but video is slow → platform throttling video streams

### Verify Settings Active
```bash
docker exec youtube-video-downloader-backend-1 env | grep YTDLP
```

## Advanced: Manual Testing

Test yt-dlp command directly in container:
```bash
docker exec -it youtube-video-downloader-backend-1 bash

# Test with current optimizations
yt-dlp -f 22 --concurrent-fragments 32 --throttled-rate 50K \
  --extractor-args "youtube:player_client=ios" \
  "https://www.youtube.com/watch?v=VIDEO_ID"
```

## Configuration Summary

All env vars available:

| Variable | Default | Description |
|----------|---------|-------------|
| `YTDLP_CONCURRENT_FRAGMENTS` | 8 | Parallel fragment downloads |
| `YTDLP_BUFFER_SIZE` | 128K | Internal buffer size |
| `YTDLP_HTTP_CHUNK_SIZE` | 50M | Chunked HTTP mode |
| `YTDLP_SOCKET_TIMEOUT` | 30 | Socket timeout (seconds) |
| `YTDLP_STREAM_CHUNK_SIZE` | 524288 | Response stream chunks |
| `YTDLP_THROTTLED_RATE` | 100K | Auto-bypass threshold |
| `YTDLP_USE_IOS_CLIENT` | false | iOS client impersonation |
| `YTDLP_COOKIES_FROM_BROWSER` | - | Browser for cookies |
| `YTDLP_USER_AGENT` | - | Custom user agent |
| `YTDLP_PREFER_FREE_FORMATS` | true | Prefer WebM/MP4 |
| `YTDLP_SPONSORBLOCK_REMOVE` | - | Skip segments |
| `YTDLP_SLEEP_REQUESTS` | 0 | Delay between requests |

## Applying Changes

After editing `docker-compose.yml`:
```bash
docker compose restart backend
```

After editing Python code:
```bash
docker compose up --build -d backend
```

---

**Last Updated**: February 11, 2026
**Tested With**: yt-dlp 2026.2.4
