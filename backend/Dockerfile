# Use Python 3.11 slim image
FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Install system dependencies (including yt-dlp and ffmpeg)
# Note: aria2 is not installed because Railway bans it for security reasons
RUN apt-get update && apt-get install -y \
    curl \
    ffmpeg \
    && rm -rf /var/lib/apt/lists/*

# Install yt-dlp
RUN curl -L https://github.com/yt-dlp/yt-dlp/releases/latest/download/yt-dlp -o /usr/local/bin/yt-dlp \
    && chmod a+rx /usr/local/bin/yt-dlp

# Install uv for faster dependency management
RUN pip install --no-cache-dir uv

# Copy dependency files
COPY pyproject.toml README.md ./

# Install Python dependencies
RUN uv pip install --system --no-cache -e .

# Copy application code
COPY app ./app

# Expose port (Railway injects PORT env var)
EXPOSE 8000

# Set environment variables
ENV PYTHONUNBUFFERED=1
ENV ENV=production
ENV PORT=8000

# Health check (uses PORT env var)
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD curl -f http://localhost:${PORT:-8000}/health || exit 1

# Run the application with uvicorn (Railway injects PORT, defaults to 8000)
CMD sh -c "uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000} --workers 2"
