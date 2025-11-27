"""OAuth authentication endpoints."""

import logging
import secrets
from urllib.parse import urlencode

import httpx
from fastapi import APIRouter, HTTPException, Query, status
from fastapi.responses import RedirectResponse

from app.core.config import settings

logger = logging.getLogger(__name__)

router = APIRouter()

# In-memory state storage (use Redis or database in production)
_state_store: dict[str, str] = {}


@router.get("/auth/login")
async def login(redirect_after: str = Query("http://localhost:8000/v1/me", description="URL to redirect to after successful authentication")):
    """
    Initiate OAuth login flow by redirecting to Keycloak.
    
    This endpoint redirects the user to Keycloak for authentication.
    After successful authentication, Keycloak will redirect back to the callback endpoint.
    """
    if not settings.keycloak_client_id:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="OAuth not configured. Please set KEYCLOAK_CLIENT_ID and KEYCLOAK_CLIENT_SECRET",
        )
    
    # Generate a random state parameter for CSRF protection
    state = secrets.token_urlsafe(32)
    _state_store[state] = redirect_after
    
    # Build Keycloak authorization URL
    auth_url = (
        f"{settings.keycloak_server_url}/realms/{settings.keycloak_realm}"
        f"/protocol/openid-connect/auth"
    )
    
    params = {
        "client_id": settings.keycloak_client_id,
        "redirect_uri": settings.oauth_redirect_uri,
        "response_type": "code",
        "scope": "openid profile email",
        "state": state,
    }
    
    authorization_url = f"{auth_url}?{urlencode(params)}"
    
    logger.info(f"Redirecting to Keycloak: {authorization_url}")
    return RedirectResponse(url=authorization_url)


@router.get("/auth/callback")
async def callback(
    code: str = Query(..., description="Authorization code from Keycloak"),
    state: str = Query(..., description="State parameter for CSRF protection"),
):
    """
    OAuth callback endpoint that receives the authorization code from Keycloak.
    
    This endpoint:
    1. Validates the state parameter
    2. Exchanges the authorization code for an access token
    3. Returns the access token to the client
    """
    if not settings.keycloak_client_id or not settings.keycloak_client_secret:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="OAuth not configured. Please set KEYCLOAK_CLIENT_ID and KEYCLOAK_CLIENT_SECRET",
        )
    
    # Validate state parameter
    if state not in _state_store:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid state parameter. The authorization request may have expired.",
        )
    
    redirect_after = _state_store.pop(state)
    
    # Exchange authorization code for access token
    token_url = (
        f"{settings.keycloak_server_url}/realms/{settings.keycloak_realm}"
        f"/protocol/openid-connect/token"
    )
    
    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(
                token_url,
                data={
                    "grant_type": "authorization_code",
                    "client_id": settings.keycloak_client_id,
                    "client_secret": settings.keycloak_client_secret,
                    "code": code,
                    "redirect_uri": settings.oauth_redirect_uri,
                },
                headers={"Content-Type": "application/x-www-form-urlencoded"},
            )
            response.raise_for_status()
            token_data = response.json()
    except httpx.HTTPStatusError as e:
        logger.error(f"Token exchange failed: {e.response.text}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Failed to exchange authorization code: {e.response.text}",
        )
    except Exception as e:
        logger.error(f"Unexpected error during token exchange: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Unexpected error during token exchange: {str(e)}",
        )
    
    access_token = token_data.get("access_token")
    if not access_token:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No access token received from Keycloak",
        )
    
    # Return token information
    # In a real application, you might want to:
    # - Store the token in a secure HTTP-only cookie
    # - Redirect to a frontend page with the token
    # - Return JSON with the token (less secure)
    
    # For now, we'll return JSON with the token
    # You can modify this to redirect to redirect_after with the token as a query param or fragment
    return {
        "access_token": access_token,
        "token_type": token_data.get("token_type", "Bearer"),
        "expires_in": token_data.get("expires_in"),
        "refresh_token": token_data.get("refresh_token"),
        "redirect_after": redirect_after,
        "message": "Authentication successful. Use the access_token to call API endpoints.",
        "example": f"curl -H 'Authorization: Bearer {access_token}' {redirect_after}",
    }


@router.get("/auth/logout")
async def logout():
    """
    Logout endpoint that redirects to Keycloak logout.
    
    After logout, Keycloak will redirect back to the application.
    """
    if not settings.keycloak_client_id:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="OAuth not configured",
        )
    
    logout_url = (
        f"{settings.keycloak_server_url}/realms/{settings.keycloak_realm}"
        f"/protocol/openid-connect/logout"
    )
    
    params = {
        "client_id": settings.keycloak_client_id,
        "redirect_uri": settings.oauth_redirect_uri.replace("/callback", "/login"),
    }
    
    logout_redirect_url = f"{logout_url}?{urlencode(params)}"
    return RedirectResponse(url=logout_redirect_url)

