"""Pydantic models for video-related API contracts."""
from typing import Literal

from pydantic import BaseModel, Field, HttpUrl, field_validator


class FormatsRequest(BaseModel):
    """Request model for fetching video formats."""

    url: str = Field(
        ...,
        description="URL of the video to fetch formats for",
        min_length=10,
        max_length=2048,
        examples=["https://www.youtube.com/watch?v=dQw4w9WgXcQ"],
    )

    @field_validator("url")
    @classmethod
    def validate_url(cls, v: str) -> str:
        """Basic URL validation."""
        v = v.strip()
        if not v:
            raise ValueError("URL cannot be empty")
        return v


class DownloadRequest(BaseModel):
    """Request model for downloading a video."""

    url: str = Field(
        ...,
        description="URL of the video to download",
        min_length=10,
        max_length=2048,
    )
    format_id: str = Field(
        ...,
        description="Format ID from the formats list (e.g., '22', '140', 'bestvideo[height<=1080]+bestaudio/best')",
        min_length=1,
        max_length=200,
        examples=["22", "140", "best", "bestvideo[height<=1080]+bestaudio/best"],
    )

    @field_validator("url", "format_id")
    @classmethod
    def validate_not_empty(cls, v: str) -> str:
        """Ensure fields are not empty after stripping."""
        v = v.strip()
        if not v:
            raise ValueError("Field cannot be empty")
        return v


class Format(BaseModel):
    """Model representing a single video format."""

    id: str = Field(
        ...,
        description="Unique format identifier (e.g., itag for YouTube)",
    )
    quality_label: str = Field(
        ...,
        description="Human-readable quality label (e.g., '720p', '1080p', 'audio only')",
    )
    mime_type: str = Field(
        ...,
        description="MIME type of the format (e.g., 'video/mp4', 'audio/webm')",
    )
    filesize_bytes: int | None = Field(
        default=None,
        description="File size in bytes (may be None if not available)",
        ge=0,
    )
    is_audio_only: bool = Field(
        default=False,
        description="True if this format contains only audio",
    )
    is_video_only: bool = Field(
        default=False,
        description="True if this format contains only video (no audio)",
    )

    class Config:
        """Pydantic config."""
        json_schema_extra = {
            "example": {
                "id": "22",
                "quality_label": "720p",
                "mime_type": "video/mp4",
                "filesize_bytes": 12345678,
                "is_audio_only": False,
                "is_video_only": False,
            }
        }


class VideoInfo(BaseModel):
    """Model representing video metadata and available formats."""

    title: str = Field(
        ...,
        description="Video title",
        min_length=1,
    )
    thumbnail_url: str | None = Field(
        default=None,
        description="URL of the video thumbnail image",
    )
    duration_seconds: int | None = Field(
        default=None,
        description="Video duration in seconds",
        ge=0,
    )
    formats: list[Format] = Field(
        ...,
        description="List of available formats",
        min_length=1,
    )

    class Config:
        """Pydantic config."""
        json_schema_extra = {
            "example": {
                "title": "Example Video Title",
                "thumbnail_url": "https://example.com/thumb.jpg",
                "duration_seconds": 180,
                "formats": [
                    {
                        "id": "22",
                        "quality_label": "720p",
                        "mime_type": "video/mp4",
                        "filesize_bytes": 12345678,
                        "is_audio_only": False,
                        "is_video_only": False,
                    }
                ],
            }
        }


class ErrorResponse(BaseModel):
    """Standard error response model."""

    code: Literal[
        "INVALID_URL",
        "UNSUPPORTED_PLATFORM",
        "NOT_FOUND",
        "FORMAT_NOT_AVAILABLE",
        "YTDLP_FAILED",
        "INTERNAL_ERROR",
    ] = Field(
        ...,
        description="Stable error code for programmatic handling",
    )
    message: str = Field(
        ...,
        description="Human-readable error message",
        min_length=1,
    )

    class Config:
        """Pydantic config."""
        json_schema_extra = {
            "example": {
                "code": "INVALID_URL",
                "message": "The provided URL is invalid or blocked",
            }
        }


class HealthResponse(BaseModel):
    """Health check response model."""

    status: Literal["healthy", "unhealthy"] = Field(
        default="healthy",
        description="Health status of the service",
    )
    version: str = Field(
        default="0.1.0",
        description="API version",
    )
