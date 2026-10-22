"""Tests for the legacy-compatible CDR response format."""

from datetime import datetime, timezone
from decimal import Decimal

import pytest

from app.schemas.cdr import CDRCompatResponse

PREFIX = "/var/lib/freeswitch/recordings"
SERVER = "https://cdr.example.com"

# (record_path, record_name, prefix, server_uri, expected_url)
# Shared with the /v1/cdr endpoint tests, which duplicate this URL logic.
RECORDING_URL_CASES = [
    pytest.param(
        f"{PREFIX}/example.com/archive/2024/Jan/01", "a.mp3", PREFIX, SERVER,
        f"{SERVER}/v1/recording/example.com/archive/2024/Jan/01/a.mp3",
        id="strips-prefix",
    ),
    pytest.param(
        f"{PREFIX}/example.com/archive/2024/Jan/01", "a.mp3", f"{PREFIX}/", SERVER,
        f"{SERVER}/v1/recording/example.com/archive/2024/Jan/01/a.mp3",
        id="prefix-with-trailing-slash",
    ),
    pytest.param(
        f"{PREFIX}/example.com/archive/", "a.mp3", PREFIX, SERVER,
        f"{SERVER}/v1/recording/example.com/archive/a.mp3",
        id="path-with-trailing-slash",
    ),
    pytest.param(
        "/other/place", "a.mp3", PREFIX, SERVER,
        f"{SERVER}/v1/recording/other/place/a.mp3",
        id="prefix-mismatch-keeps-path",
    ),
    pytest.param(
        f"{PREFIX}/example.com/a.mp3", None, PREFIX, SERVER,
        f"{SERVER}/v1/recording/example.com/a.mp3",
        id="path-only",
    ),
    pytest.param(
        None, "a.mp3", PREFIX, SERVER,
        f"{SERVER}/v1/recording/a.mp3",
        id="name-only",
    ),
    pytest.param(
        f"{PREFIX}/example.com", "a.mp3", PREFIX, f"{SERVER}/",
        f"{SERVER}/v1/recording/example.com/a.mp3",
        id="server-with-trailing-slash",
    ),
    pytest.param(None, None, PREFIX, SERVER, None, id="no-recording"),
]


@pytest.mark.parametrize(
    "record_path,record_name,prefix,server_uri,expected", RECORDING_URL_CASES
)
def test_audio_url(make_cdr, record_path, record_name, prefix, server_uri, expected):
    cdr = make_cdr(record_path=record_path, record_name=record_name)

    result = CDRCompatResponse.from_cdr(cdr, prefix, server_uri)

    assert result.audio == expected


def test_audio_url_without_server_uri_is_relative(make_cdr):
    cdr = make_cdr(record_path=f"{PREFIX}/example.com", record_name="a.mp3")

    assert CDRCompatResponse.from_cdr(cdr, PREFIX, None).audio == "example.com/a.mp3"


@pytest.mark.parametrize(
    "duration,expected",
    [
        (None, "00:00:00"),
        (0, "00:00:00"),
        (59, "00:00:59"),
        (61, "00:01:01"),
        (3661, "01:01:01"),
        (300.9, "00:05:00"),
        (Decimal("7322"), "02:02:02"),
    ],
)
def test_duration_formatting(make_cdr, duration, expected):
    assert CDRCompatResponse.from_cdr(make_cdr(duration=duration)).duration == expected


def test_compat_fields(make_cdr):
    cdr = make_cdr(
        start_stamp=datetime(2024, 3, 5, 7, 8, 9, tzinfo=timezone.utc),
        direction="outbound",
        caller_id_number="100",
        destination_number="200",
        hangup_cause="USER_BUSY",
    )

    result = CDRCompatResponse.from_cdr(cdr)

    assert result.model_dump() == {
        "date": "05/03/2024 07:08:09",
        "type": "outbound",
        "origin": "100",
        "destination": "200",
        "duration": "00:05:00",
        "cost": "R$ 0.00",
        "status": "USER_BUSY",
        "audio": None,
    }


def test_missing_start_stamp_gives_empty_date(make_cdr):
    assert CDRCompatResponse.from_cdr(make_cdr(start_stamp=None)).date == ""
