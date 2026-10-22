"""Shared fixtures.

The settings and DB engine are created at import time (``app.database.session``),
so the environment must be prepared before anything else from ``app`` is imported.
"""

import os
from datetime import datetime, timezone
from typing import Callable

import pytest

from app.core import config

# Never read the developer's .env during tests
config.Settings.model_config["env_file"] = None

TEST_ENV = {
    "KEYCLOAK_SERVER_URL": "https://sso.test",
    "KEYCLOAK_REALM": "test-realm",
    "KEYCLOAK_AUDIENCE": "test-api",
    "KEYCLOAK_ALGORITHMS": "RS256",
    "FUSIONPBX_DB_HOST": "localhost",
    "FUSIONPBX_DB_PORT": "5432",
    "FUSIONPBX_DB_NAME": "fusionpbx",
    "FUSIONPBX_DB_USER": "fusionpbx",
    "FUSIONPBX_DB_PASSWORD": "secret",
    "FUSIONPBX_RECORDING_PATH": "/var/lib/freeswitch/recordings",
    "APP_DEBUG": "false",
    "APP_LOG_LEVEL": "INFO",
}
for _key, _value in TEST_ENV.items():
    os.environ[_key] = _value
for _key in ("APP_SERVER_URI", "APP_RECORDING_PATH", "ALLOWED_ORIGINS"):
    os.environ.pop(_key, None)

from fastapi.testclient import TestClient  # noqa: E402

from app.core.security import get_user_domain  # noqa: E402
from app.database.session import get_db  # noqa: E402
from app.main import app  # noqa: E402
from app.models.cdr import CDR  # noqa: E402

TEST_DOMAIN = "example.com"


@pytest.fixture
def app_settings() -> config.Settings:
    """The live settings instance; change it with ``monkeypatch.setattr``."""
    return config.get_settings()


@pytest.fixture
def client():
    """Unauthenticated test client with no dependency overrides."""
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


@pytest.fixture
def auth_client():
    """Test client authenticated as TEST_DOMAIN, with the DB session stubbed out."""

    async def _fake_db():
        yield None

    app.dependency_overrides[get_user_domain] = lambda: TEST_DOMAIN
    app.dependency_overrides[get_db] = _fake_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


@pytest.fixture
def make_cdr() -> Callable[..., CDR]:
    """Factory for transient CDR model instances."""
    counter = 0

    def _make_cdr(**overrides) -> CDR:
        nonlocal counter
        counter += 1
        fields = {
            "xml_cdr_uuid": f"00000000-0000-0000-0000-{counter:012d}",
            "domain_name": TEST_DOMAIN,
            "caller_id_name": "Alice",
            "caller_id_number": "+5511999990000",
            "destination_number": "+5511888880000",
            "start_stamp": datetime(2024, 1, 1, 10, 0, 0, tzinfo=timezone.utc),
            "duration": 300,
            "billsec": 290,
            "hangup_cause": "NORMAL_CLEARING",
            "direction": "inbound",
            "record_path": None,
            "record_name": None,
        }
        fields.update(overrides)
        return CDR(**fields)

    return _make_cdr
