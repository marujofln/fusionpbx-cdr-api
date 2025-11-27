"""User endpoints."""

import logging

from fastapi import APIRouter, Depends

from app.core.config import settings
from app.core.security import get_current_user
from app.schemas.user import UserResponse

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/me", response_model=UserResponse)
async def get_current_user_info(current_user=Depends(get_current_user)) -> UserResponse:
    """Get current authenticated user information."""
    # Debug: Log userinfo if debug mode is enabled
    if settings.app_debug:
        logger.debug(
            f"Userinfo - sub: {current_user.sub}, sip_domain: {current_user.sip_domain}, aud: {current_user.aud}, exp: {current_user.exp}"
        )

    return current_user
