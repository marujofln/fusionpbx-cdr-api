"""Application configuration settings."""

import os
from pathlib import Path
from typing import List, Optional

from pydantic import Field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

try:
    from importlib.metadata import version
except ImportError:
    # Python < 3.8
    from importlib_metadata import version

from app import __version__ as app_version


class Settings(BaseSettings):
    """Application settings configuration."""

    # Keycloak Configuration
    keycloak_server_url: str = Field(..., env="KEYCLOAK_SERVER_URL")
    keycloak_realm: str = Field(..., env="KEYCLOAK_REALM")
    keycloak_audience: str = Field(..., env="KEYCLOAK_AUDIENCE")
    keycloak_algorithms: str = Field("RS256", env="KEYCLOAK_ALGORITHMS")

    # Database Configuration
    fusionpbx_db_host: str = Field("localhost", env="FUSIONPBX_DB_HOST")
    fusionpbx_db_port: int = Field(5432, env="FUSIONPBX_DB_PORT")
    fusionpbx_db_name: Optional[str] = Field(None, env="FUSIONPBX_DB_NAME")
    fusionpbx_db_user: Optional[str] = Field(None, env="FUSIONPBX_DB_USER")
    fusionpbx_db_password: Optional[str] = Field(None, env="FUSIONPBX_DB_PASSWORD")
    fusionpbx_db_schema: str = Field("public", env="FUSIONPBX_DB_SCHEMA")

    # Application Configuration
    app_debug: bool = Field(False, env="APP_DEBUG")
    app_log_level: str = Field("INFO", env="APP_LOG_LEVEL")
    app_port: int = Field(3001, env="APP_PORT")
    app_server_uri: Optional[str] = Field(None, env="APP_SERVER_URI")
    fusionpbx_recording_path: Optional[str] = Field(
        "/var/lib/freeswitch/recordings", env="FUSIONPBX_RECORDING_PATH"
    )
    app_recording_path: Optional[str] = Field(None, env="APP_RECORDING_PATH")

    @field_validator("app_debug", mode="before")
    @classmethod
    def parse_app_debug(cls, v):
        """Parse APP_DEBUG from string to boolean."""
        if isinstance(v, bool):
            return v
        if isinstance(v, str):
            return v.lower() in ("true", "1", "yes", "on")
        return bool(v)

    @field_validator("app_log_level", mode="before")
    @classmethod
    def normalize_log_level(cls, v):
        """Normalize log level to uppercase."""
        if isinstance(v, str):
            return v.upper()
        return v

    @model_validator(mode="after")
    def set_app_recording_path_default(self):
        """Set app_recording_path to fusionpbx_recording_path if not provided."""
        if self.app_recording_path is None:
            if self.fusionpbx_recording_path is None:
                raise ValueError(
                    "Either APP_RECORDING_PATH or FUSIONPBX_RECORDING_PATH must be set"
                )
            self.app_recording_path = self.fusionpbx_recording_path
        return self

    # CORS Configuration
    allowed_origins: List[str] = Field(["http://localhost:3000"], env="ALLOWED_ORIGINS")

    # Resolve .env file path - check current directory and project root
    _env_file_path = None
    if os.path.exists(".env"):
        _env_file_path = os.path.abspath(".env")
    else:
        # Try project root (where this file is located)
        project_root = Path(__file__).parent.parent.parent
        env_file_path = project_root / ".env"
        if env_file_path.exists():
            _env_file_path = str(env_file_path.absolute())

    model_config = SettingsConfigDict(
        env_file=_env_file_path or ".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",  # Ignore extra fields (like old AUTH0_* vars) instead of raising errors
    )

    @property
    def database_url(self) -> str:
        """Generate database URL from components."""
        if not self.fusionpbx_db_name:
            raise ValueError("FUSIONPBX_DB_NAME is required for database operations")
        if not self.fusionpbx_db_user:
            raise ValueError("FUSIONPBX_DB_USER is required for database operations")
        if not self.fusionpbx_db_password:
            raise ValueError(
                "FUSIONPBX_DB_PASSWORD is required for database operations"
            )
        return (
            f"postgresql://{self.fusionpbx_db_user}:{self.fusionpbx_db_password}"
            f"@{self.fusionpbx_db_host}:{self.fusionpbx_db_port}/{self.fusionpbx_db_name}"
        )


def get_version() -> str:
    """Get application version from package metadata or fallback to __version__."""
    try:
        return version("fusionpbx-cdr-api")
    except Exception:
        # Fallback to __version__ for development when package is not installed
        return app_version


# Application metadata constants
APP_NAME = "FusionPBX CDR API"
APP_VERSION = get_version()

# Global settings instance (lazy initialization)
_settings: Settings | None = None


def get_settings() -> Settings:
    """Get the global settings instance, initializing it if necessary."""
    global _settings
    if _settings is None:
        _settings = Settings()
    return _settings


# For backward compatibility, provide settings as a proxy object
# This allows the same import pattern while deferring initialization
class _SettingsProxy:
    """Proxy object that lazily initializes Settings on first attribute access."""

    def __getattr__(self, name: str):
        return getattr(get_settings(), name)


settings = _SettingsProxy()
