# Use Python 3.11 slim image
FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Install system dependencies (including yt-dlp and ffmpeg)
RUN apt-get update && apt-get install -y \
    curl \
    ffmpeg \
    unzip \
    && rm -rf /var/lib/apt/lists/*

# Install deno (JS runtime required by yt-dlp for YouTube n-challenge solving)
RUN curl -fsSL https://deno.land/install.sh | sh \
    && ln -s /root/.deno/bin/deno /usr/local/bin/deno

# Install uv for faster dependency management
RUN pip install --no-cache-dir uv

# Copy dependency files
COPY pyproject.toml README.md ./

# Install Python dependencies
RUN uv pip install --system --no-cache -e .

# Install yt-dlp binary (always fetch latest – cache-bust via ADD)
ADD https://github.com/yt-dlp/yt-dlp/releases/latest/download/yt-dlp /usr/local/bin/yt-dlp
RUN chmod a+rx /usr/local/bin/yt-dlp

# Ensure the Python yt-dlp package is also the latest
RUN uv pip install --system --no-cache --upgrade yt-dlp

# Copy application code
COPY app ./app

# Copy entrypoint script (decodes cookies from env var)
COPY entrypoint.sh ./entrypoint.sh
RUN chmod +x /app/entrypoint.sh

# Expose port (Railway injects PORT env var)
EXPOSE 8000

# Set environment variables
ENV PYTHONUNBUFFERED=1
ENV ENV=production
ENV PORT=8000

# Health check (uses PORT env var)
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD curl -f http://localhost:${PORT:-8000}/health || exit 1

# Entrypoint decodes cookies, then runs the CMD
ENTRYPOINT ["/app/entrypoint.sh"]

# Run the application with uvicorn (Railway injects PORT, defaults to 8000)
CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000} --workers 2"]
