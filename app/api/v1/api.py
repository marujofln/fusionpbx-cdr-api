"""API v1 router."""

from fastapi import APIRouter

from app.api.v1.endpoints import cdr, me, recording

api_router = APIRouter()

# Include all endpoint routers
api_router.include_router(me.router, tags=["user"])
api_router.include_router(cdr.router, tags=["cdr"])
api_router.include_router(recording.router, tags=["recordings"])



