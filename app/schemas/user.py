"""User response schemas."""

from typing import Optional, Union

from pydantic import BaseModel


class UserResponse(BaseModel):
    """User response model."""

    sub: str
    sip_domain: Optional[str] = None
    aud: Optional[Union[str, list[str]]] = None
    exp: int

    class Config:
        """Pydantic configuration."""

        from_attributes = True
