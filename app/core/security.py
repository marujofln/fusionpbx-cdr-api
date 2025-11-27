"""Security and authentication utilities."""

import json
from typing import Optional, Union

import httpx
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError, jwt
from pydantic import BaseModel

from app.core.config import settings

# Security scheme
security = HTTPBearer()


class TokenData(BaseModel):
    """Token data model."""

    sub: str
    sip_domain: Optional[str] = None
    aud: Optional[Union[str, list[str]]] = None
    exp: int


class KeycloakJWTBearer:
    """Keycloak JWT token validator."""

    def __init__(self):
        """Initialize the Keycloak JWT validator."""
        self.server_url = settings.keycloak_server_url
        self.realm = settings.keycloak_realm
        self.audience = settings.keycloak_audience
        self.algorithms = [settings.keycloak_algorithms]
        self._jwks = None

    async def get_jwks(self) -> dict:
        """Fetch JSON Web Key Set from Keycloak."""
        if self._jwks is None:
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"{self.server_url}/realms/{self.realm}/protocol/openid-connect/certs"
                )
                response.raise_for_status()
                self._jwks = response.json()
        return self._jwks

    def get_public_key(self, token: str) -> str:
        """Get the public key for token verification."""
        try:
            unverified_header = jwt.get_unverified_header(token)
        except JWTError:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token header",
            )

        jwks = self._jwks
        rsa_key = {}
        for key in jwks["keys"]:
            if key["kid"] == unverified_header["kid"]:
                rsa_key = {
                    "kty": key["kty"],
                    "kid": key["kid"],
                    "use": key["use"],
                    "n": key["n"],
                    "e": key["e"],
                }
                break

        if not rsa_key:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Unable to find appropriate key",
            )

        return rsa_key

    async def verify_token(self, token: str) -> TokenData:
        """Verify and decode the JWT token."""
        try:
            jwks = await self.get_jwks()
            self._jwks = jwks

            # For M2M tokens, audience might not be present, so we decode without
            # audience validation first, then validate manually if audience is configured
            decode_options = {
                "verify_signature": True,
                "verify_exp": True,
                "verify_iat": False,
                "verify_nbf": False,
                "verify_iss": True,
                "verify_aud": False,  # Disable automatic audience verification
            }

            payload = jwt.decode(
                token,
                self.get_public_key(token),
                algorithms=self.algorithms,
                options=decode_options,
                issuer=f"{self.server_url}/realms/{self.realm}",
            )

            # Manual audience validation if configured and present in token
            if self.audience and payload.get("aud"):
                token_aud = payload.get("aud")
                # Handle both string and list audiences
                if isinstance(token_aud, str):
                    if token_aud != self.audience:
                        raise HTTPException(
                            status_code=status.HTTP_401_UNAUTHORIZED,
                            detail=f"Invalid audience: expected {self.audience}, got {token_aud}",
                        )
                elif isinstance(token_aud, list):
                    if self.audience not in token_aud:
                        raise HTTPException(
                            status_code=status.HTTP_401_UNAUTHORIZED,
                            detail=f"Invalid audience: {self.audience} not in {token_aud}",
                        )

            return TokenData(**payload)
        except JWTError as e:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail=f"Invalid token: {str(e)}",
            )


# Global Keycloak validator instance
keycloak_validator = KeycloakJWTBearer()


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
) -> TokenData:
    """Get current authenticated user from JWT token."""
    token = credentials.credentials
    return await keycloak_validator.verify_token(token)


def get_user_domain(user: TokenData = Depends(get_current_user)) -> str:
    """Extract domain from user token."""
    if not user.sip_domain:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="SIP domain attribute not found in token",
        )
    return user.sip_domain
