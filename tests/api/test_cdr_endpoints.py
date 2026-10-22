"""Tests for /v1/cdr and /v1/cdr_compat."""

from datetime import datetime

import pytest

from app.schemas.cdr import CDRCompatResponse
from app.services.cdr_service import CDRService
from tests.conftest import TEST_DOMAIN
from tests.unit.test_cdr_schemas import PREFIX, RECORDING_URL_CASES


@pytest.fixture
def fake_service(monkeypatch):
    """Replace CDRService queries; records calls and returns ``rows``."""

    class Fake:
        rows: list = []
        calls: list = []

    async def by_period(db, domain, period=None):
        Fake.calls.append(("period", domain, period))
        return Fake.rows

    async def by_range(db, domain, start_date, end_date):
        Fake.calls.append(("range", domain, start_date, end_date))
        return Fake.rows

    Fake.rows, Fake.calls = [], []
    monkeypatch.setattr(CDRService, "get_cdrs_by_period", staticmethod(by_period))
    monkeypatch.setattr(CDRService, "get_cdrs_by_date_range", staticmethod(by_range))
    return Fake


@pytest.mark.parametrize("path", ["/v1/cdr", "/v1/cdr_compat"])
def test_requires_authentication(client, path):
    assert client.get(path).status_code == 403


@pytest.mark.parametrize("path", ["/v1/cdr", "/v1/cdr_compat"])
def test_unknown_period_is_not_validated(auth_client, fake_service, path):
    """Query(enum=...) only documents the values in OpenAPI; it does not validate.

    Unknown periods reach CDRService, which falls back to the last hour.
    """
    response = auth_client.get(path, params={"period": "forever"})

    assert response.status_code == 200
    assert fake_service.calls == [("period", TEST_DOMAIN, "forever")]


def test_cdr_defaults_to_last_hour(auth_client, fake_service):
    response = auth_client.get("/v1/cdr")

    assert response.status_code == 200
    assert response.json() == {"cdrs": [], "total": 0, "period": "last_hour"}
    assert fake_service.calls == [("period", TEST_DOMAIN, None)]


def test_cdr_passes_period_and_domain(auth_client, fake_service, make_cdr):
    fake_service.rows = [make_cdr(), make_cdr()]

    response = auth_client.get("/v1/cdr", params={"period": "this_month"})

    body = response.json()
    assert body["period"] == "this_month"
    assert body["total"] == 2
    assert [c["xml_cdr_uuid"] for c in body["cdrs"]] == [
        r.xml_cdr_uuid for r in fake_service.rows
    ]
    assert fake_service.calls == [("period", TEST_DOMAIN, "this_month")]


def test_cdr_custom_range_overrides_period(auth_client, fake_service):
    response = auth_client.get(
        "/v1/cdr",
        params={
            "period": "today",
            "start_date": "2024-01-01T00:00:00",
            "end_date": "2024-01-31T23:59:59",
        },
    )

    assert response.json()["period"] == "custom_range_2024-01-01_to_2024-01-31"
    assert fake_service.calls == [
        (
            "range",
            TEST_DOMAIN,
            datetime(2024, 1, 1),
            datetime(2024, 1, 31, 23, 59, 59),
        )
    ]


def test_cdr_with_only_start_date_falls_back_to_period(auth_client, fake_service):
    auth_client.get(
        "/v1/cdr", params={"period": "today", "start_date": "2024-01-01T00:00:00"}
    )

    assert fake_service.calls == [("period", TEST_DOMAIN, "today")]


@pytest.mark.parametrize(
    "record_path,record_name,prefix,server_uri,expected", RECORDING_URL_CASES
)
def test_cdr_recording_url_matches_compat_format(
    auth_client,
    fake_service,
    app_settings,
    monkeypatch,
    make_cdr,
    record_path,
    record_name,
    prefix,
    server_uri,
    expected,
):
    """/cdr duplicates CDRCompatResponse's URL logic; keep them in sync."""
    monkeypatch.setattr(app_settings, "fusionpbx_recording_path", prefix)
    monkeypatch.setattr(app_settings, "app_server_uri", server_uri)
    cdr = make_cdr(record_path=record_path, record_name=record_name)
    fake_service.rows = [cdr]

    recording = auth_client.get("/v1/cdr").json()["cdrs"][0]["recording"]

    assert recording == expected
    assert recording == CDRCompatResponse.from_cdr(cdr, prefix, server_uri).audio


@pytest.mark.parametrize("path,field", [("/v1/cdr", None), ("/v1/cdr_compat", "audio")])
def test_server_uri_is_derived_from_request_when_unset(
    auth_client, fake_service, make_cdr, path, field
):
    fake_service.rows = [
        make_cdr(record_path=f"{PREFIX}/example.com", record_name="a.mp3")
    ]

    body = auth_client.get(path).json()

    url = body["cdrs"][0]["recording"] if field is None else body[0][field]
    assert url == "http://testserver/v1/recording/example.com/a.mp3"


def test_server_uri_keeps_non_default_port(fake_service, make_cdr, auth_client):
    fake_service.rows = [make_cdr(record_name="a.mp3")]

    response = auth_client.get("http://api.local:8080/v1/cdr_compat")

    assert response.json()[0]["audio"] == "http://api.local:8080/v1/recording/a.mp3"


def test_cdr_compat_format(auth_client, fake_service, make_cdr):
    fake_service.rows = [make_cdr(duration=3661, direction="outbound")]

    response = auth_client.get("/v1/cdr_compat", params={"period": "today"})

    assert response.status_code == 200
    assert response.json() == [
        {
            "date": "01/01/2024 10:00:00",
            "type": "outbound",
            "origin": "+5511999990000",
            "destination": "+5511888880000",
            "duration": "01:01:01",
            "cost": "R$ 0.00",
            "status": "NORMAL_CLEARING",
            "audio": None,
        }
    ]
    assert fake_service.calls == [("period", TEST_DOMAIN, "today")]


def test_cdr_compat_custom_range(auth_client, fake_service):
    auth_client.get(
        "/v1/cdr_compat",
        params={"start_date": "2024-01-01T00:00:00", "end_date": "2024-01-02T00:00:00"},
    )

    assert fake_service.calls[0][0] == "range"
