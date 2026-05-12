"""API v1 router aggregation."""
from fastapi import APIRouter

from app.api.v1.endpoints import convert, videos

# Create v1 router
api_router = APIRouter()

# Include endpoint routers
api_router.include_router(videos.router, prefix="/videos", tags=["videos"])
api_router.include_router(convert.router, prefix="/convert", tags=["convert"])
