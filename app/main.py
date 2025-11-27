"""Main FastAPI application."""

import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.v1.api import api_router
from app.core.config import APP_NAME, APP_VERSION, settings

# Configure logging based on settings
logging.basicConfig(
    level=getattr(logging, settings.app_log_level.upper(), logging.INFO),
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)

# Create FastAPI application
app = FastAPI(
    title=APP_NAME,
    version=APP_VERSION,
    description="FusionPBX CDR API with Keycloak authentication",
    openapi_url="/openapi.json",
    docs_url="/docs",
    redoc_url="/redoc",
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include API routes
app.include_router(api_router, prefix="/v1")


@app.get("/")
async def root():
    """Root endpoint."""
    return {
        "message": APP_NAME,
        "version": APP_VERSION,
        "docs": "/docs",
    }


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "healthy"}
