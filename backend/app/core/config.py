"""Application configuration using pydantic-settings."""
import os
from typing import Literal

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # Environment
    ENV: Literal["development", "production", "test"] = "development"
    DEBUG: bool = False
    PORT: int = Field(default=8000, ge=1, le=65535)

    # API Configuration
    API_V1_PREFIX: str = "/api/v1"

    # CORS Configuration
    CORS_ORIGINS: str = Field(
        default="http://localhost:3000",
        description="Comma-separated list of allowed CORS origins",
    )

    # Logging
    LOG_LEVEL: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"] = "INFO"

    # Security
    BLOCK_PRIVATE_NETWORKS: bool = Field(
        default=True,
        description="Block URLs pointing to private networks (SSRF protection)",
    )
    ALLOWED_URL_SCHEMES: str = Field(
        default="http,https",
        description="Comma-separated list of allowed URL schemes",
    )

    @field_validator("CORS_ORIGINS")
    @classmethod
    def parse_cors_origins(cls, v: str) -> str:
        """Ensure CORS_ORIGINS is properly formatted."""
        return v.strip()

    @property
    def cors_origins_list(self) -> list[str]:
        """Get CORS origins as a list."""
        return [origin.strip() for origin in self.CORS_ORIGINS.split(",") if origin.strip()]

    @property
    def allowed_schemes_list(self) -> list[str]:
        """Get allowed URL schemes as a list."""
        return [scheme.strip().lower() for scheme in self.ALLOWED_URL_SCHEMES.split(",") if scheme.strip()]

    @property
    def is_development(self) -> bool:
        """Check if running in development mode."""
        return self.ENV == "development"

    @property
    def is_production(self) -> bool:
        """Check if running in production mode."""
        return self.ENV == "production"

    # yt-dlp tuning (download speed / robustness)
    YTDLP_CONCURRENT_FRAGMENTS: int = Field(
        default=8,
        ge=1,
        le=32,
        description="Number of fragments to download in parallel (DASH/HLS)"
    )
    YTDLP_THROTTLED_RATE: str = Field(
        default="100K",
        description="yt-dlp --throttled-rate: re-extract video if speed drops below this (e.g., 100K, 50K)"
    )
    YTDLP_BUFFER_SIZE: str = Field(
        default="128K",
        description="yt-dlp --buffer-size value (e.g., 64K, 1M)"
    )
    YTDLP_HTTP_CHUNK_SIZE: str | None = Field(
        default="50M",
        description="yt-dlp --http-chunk-size value (set empty/omit to disable)"
    )
    YTDLP_SOCKET_TIMEOUT: int = Field(
        default=30,
        ge=1,
        le=300,
        description="yt-dlp --socket-timeout value in seconds"
    )
    YTDLP_RETRIES: int = Field(default=10, ge=0, le=50)
    YTDLP_FRAGMENT_RETRIES: int = Field(default=10, ge=0, le=50)
    YTDLP_EXTRACTOR_RETRIES: int = Field(default=3, ge=0, le=50)
    YTDLP_STREAM_CHUNK_SIZE: int = Field(
        default=16777216,
        ge=65536,
        le=67108864,
        description="Chunk size for StreamingResponse reads (16MB for optimal streaming)"
    )
    YTDLP_USE_IOS_CLIENT: bool = Field(
        default=False,
        description="Use iOS player client for YouTube (often less throttled)"
    )
    YTDLP_COOKIES_FROM_BROWSER: str | None = Field(
        default=None,
        description="Browser to extract cookies from (chrome, firefox, edge, etc.)"
    )
    YTDLP_USE_ARIA2C: bool = Field(
        default=False,
        description="Use aria2c as external downloader for better speed"
    )
    YTDLP_ARIA2C_MAX_CONNECTIONS: int = Field(
        default=16,
        ge=1,
        le=32,
        description="aria2c max connections per server"
    )
    YTDLP_SPONSORBLOCK_REMOVE: str | None = Field(
        default=None,
        description="Remove sponsor segments (sponsor,intro,outro,selfpromo,preview,filler,interaction)"
    )
    YTDLP_USER_AGENT: str | None = Field(
        default=None,
        description="Custom user agent string to avoid detection"
    )
    YTDLP_PREFER_FREE_FORMATS: bool = Field(
        default=True,
        description="Prefer free containers like webm/mp4 over premium formats"
    )
    YTDLP_SLEEP_REQUESTS: float = Field(
        default=0,
        ge=0,
        le=10,
        description="Sleep N seconds between requests to avoid rate limiting"
    )
    YTDLP_FILE_ACCESS_RETRIES: int = Field(
        default=3,
        ge=1,
        le=10,
        description="Number of times to retry on file access errors"
    )
    YTDLP_USE_DASH_FORMATS: bool = Field(
        default=True,
        description="Force DASH formats which are often less throttled (YouTube)"
    )
    YTDLP_PROXY: str | None = Field(
        default=None,
        description="HTTP/HTTPS/SOCKS proxy URL (e.g., http://proxy:8080)"
    )

    # Cache formats to avoid duplicate extract_info calls between /formats and /download
    YTDLP_FORMATS_CACHE_TTL_SECONDS: int = Field(
        default=600,
        ge=0,
        le=3600,
        description="TTL for in-memory formats cache (0 disables)"
    )
    YTDLP_FORMATS_CACHE_MAXSIZE: int = Field(
        default=128,
        ge=0,
        le=2048,
        description="Max number of cached URLs (0 disables)"
    )


# Global settings instance
settings = Settings()
