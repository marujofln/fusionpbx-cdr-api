"""Keycloak Machine-to-Machine (M2M) authentication service.

This service provides utilities for obtaining access tokens using Keycloak's
Client Credentials Grant flow for machine-to-machine authentication.

Note: In practice, customer machines will call Keycloak directly to obtain tokens.
This service is provided as a reference implementation/utility.
"""

import logging
from typing import Optional

import httpx

logger = logging.getLogger(__name__)


class KeycloakM2MService:
    """Service for obtaining M2M tokens from Keycloak using Client Credentials Grant."""

    def __init__(
        self,
        server_url: str,
        realm: str,
        client_id: str,
        client_secret: str,
    ):
        """Initialize the M2M service.

        Args:
            server_url: Keycloak server URL (e.g., "https://sso.example.com")
            realm: Keycloak realm name
            client_id: Client ID for M2M authentication
            client_secret: Client secret for M2M authentication
        """
        self.server_url = server_url.rstrip("/")
        self.realm = realm
        self.client_id = client_id
        self.client_secret = client_secret
        self.token_url = (
            f"{self.server_url}/realms/{self.realm}/protocol/openid-connect/token"
        )
        self._cached_token: Optional[str] = None
        self._token_expires_at: Optional[float] = None

    async def get_service_account_token(
        self, use_cache: bool = True
    ) -> str:
        """Get an access token using Client Credentials Grant.

        Args:
            use_cache: If True, return cached token if still valid.
                       If False, always request a new token.

        Returns:
            Access token string

        Raises:
            httpx.HTTPStatusError: If token request fails
        """
        # Check cache if enabled
        if use_cache and self._cached_token and self._token_expires_at:
            import time

            if time.time() < self._token_expires_at:
                logger.debug("Returning cached token")
                return self._cached_token

        # Request new token
        logger.info("Requesting new token from Keycloak")
        async with httpx.AsyncClient() as client:
            response = await client.post(
                self.token_url,
                data={
                    "grant_type": "client_credentials",
                    "client_id": self.client_id,
                    "client_secret": self.client_secret,
                },
                headers={"Content-Type": "application/x-www-form-urlencoded"},
            )
            response.raise_for_status()
            token_data = response.json()

        access_token = token_data.get("access_token")
        if not access_token:
            raise ValueError("No access_token in Keycloak response")

        expires_in = token_data.get("expires_in", 300)  # Default to 5 minutes if not provided

        # Update cache
        import time

        self._cached_token = access_token
        # Cache for slightly less than expires_in to avoid using expired tokens
        self._token_expires_at = time.time() + (expires_in * 0.9)

        logger.info(f"Token obtained, expires in {expires_in} seconds")
        return access_token

    def clear_cache(self) -> None:
        """Clear the cached token."""
        self._cached_token = None
        self._token_expires_at = None
        logger.debug("Token cache cleared")


async def get_service_account_token(
    server_url: str,
    realm: str,
    client_id: str,
    client_secret: str,
) -> str:
    """Convenience function to get a service account token.

    This is a simple wrapper that creates a service instance and gets a token.

    Args:
        server_url: Keycloak server URL
        realm: Keycloak realm name
        client_id: Client ID for M2M authentication
        client_secret: Client secret for M2M authentication

    Returns:
        Access token string
    """
    service = KeycloakM2MService(server_url, realm, client_id, client_secret)
    return await service.get_service_account_token()

