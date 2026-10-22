"""Tests for application settings."""

import pytest
from pydantic import ValidationError

from app.core.config import Settings

REQUIRED = {
    "keycloak_server_url": "https://sso.test",
    "keycloak_realm": "test-realm",
    "keycloak_audience": "test-api",
}


def make_settings(**overrides) -> Settings:
    return Settings(_env_file=None, **{**REQUIRED, **overrides})


@pytest.mark.parametrize(
    "raw,expected",
    [
        ("true", True),
        ("True", True),
        ("1", True),
        ("yes", True),
        ("on", True),
        ("false", False),
        ("0", False),
        ("no", False),
        ("anything", False),
        (True, True),
        (False, False),
    ],
)
def test_app_debug_parsing(raw, expected):
    assert make_settings(app_debug=raw).app_debug is expected


def test_log_level_is_uppercased():
    assert make_settings(app_log_level="debug").app_log_level == "DEBUG"


def test_app_recording_path_defaults_to_fusionpbx_recording_path():
    settings = make_settings(
        fusionpbx_recording_path="/srv/recordings", app_recording_path=None
    )
    assert settings.app_recording_path == "/srv/recordings"


def test_explicit_app_recording_path_wins():
    settings = make_settings(
        fusionpbx_recording_path="/srv/recordings", app_recording_path="/mnt/rec"
    )
    assert settings.app_recording_path == "/mnt/rec"


def test_missing_both_recording_paths_is_rejected():
    with pytest.raises(ValidationError, match="APP_RECORDING_PATH"):
        make_settings(fusionpbx_recording_path=None, app_recording_path=None)


def test_database_url_uses_asyncpg():
    settings = make_settings(
        fusionpbx_db_host="db.local",
        fusionpbx_db_port=6543,
        fusionpbx_db_name="fusionpbx",
        fusionpbx_db_user="user",
        fusionpbx_db_password="pw",
    )
    assert settings.database_url == "postgresql+asyncpg://user:pw@db.local:6543/fusionpbx"


@pytest.mark.parametrize(
    "missing", ["fusionpbx_db_name", "fusionpbx_db_user", "fusionpbx_db_password"]
)
def test_database_url_requires_credentials(missing):
    credentials = {
        "fusionpbx_db_name": "fusionpbx",
        "fusionpbx_db_user": "user",
        "fusionpbx_db_password": "pw",
    }
    settings = make_settings(**{**credentials, missing: None})
    with pytest.raises(ValueError, match=missing.upper()):
        settings.database_url
