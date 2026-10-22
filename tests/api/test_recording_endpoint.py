"""Tests for /v1/recording/{file_path}."""

from email.utils import formatdate

import pytest

from app.api.v1.endpoints.recording import parse_range_header

CONTENT = b"0123456789"
URL = "/v1/recording/example.com/archive/2024/Jan/01/call.mp3"


@pytest.fixture
def recordings(tmp_path, app_settings, monkeypatch):
    """A recordings tree under tmp_path, configured as APP_RECORDING_PATH."""
    base = tmp_path / "recordings"
    day = base / "example.com" / "archive" / "2024" / "Jan" / "01"
    day.mkdir(parents=True)
    (day / "call.mp3").write_bytes(CONTENT)
    monkeypatch.setattr(app_settings, "app_recording_path", str(base))
    return base


@pytest.mark.parametrize(
    "header,size,expected",
    [
        pytest.param(None, 10, None, id="missing"),
        pytest.param("items=0-1", 10, None, id="wrong-unit"),
        pytest.param("bytes=0-4", 10, (0, 4), id="closed"),
        pytest.param("bytes=5-", 10, (5, 9), id="open-ended"),
        pytest.param("bytes=-3", 10, (7, 9), id="suffix"),
        pytest.param("bytes=-50", 10, (0, 9), id="suffix-larger-than-file"),
        pytest.param("bytes=0-10", 10, None, id="end-past-file"),
        pytest.param("bytes=6-2", 10, None, id="start-after-end"),
        pytest.param("bytes=0-1,4-5", 10, None, id="multiple-ranges"),
        pytest.param("bytes=abc", 10, None, id="no-dash"),
        pytest.param("bytes=a-b", 10, None, id="not-numbers"),
    ],
)
def test_parse_range_header(header, size, expected):
    assert parse_range_header(header, size) == expected


def test_does_not_require_authentication(client, recordings):
    assert client.get(URL).status_code == 200


def test_full_file(client, recordings):
    response = client.get(URL)

    assert response.status_code == 200
    assert response.content == CONTENT
    assert response.headers["content-type"] == "audio/mpeg"
    assert response.headers["content-length"] == str(len(CONTENT))
    assert response.headers["accept-ranges"] == "bytes"
    assert response.headers["content-disposition"] == 'inline; filename="call.mp3"'
    assert response.headers["etag"].startswith('"')


@pytest.mark.parametrize(
    "suffix,media_type",
    [
        (".wav", "audio/wav"),
        (".MP3", "audio/mpeg"),
        (".ogg", "audio/ogg"),
        (".m4a", "audio/mp4"),
        (".flac", "audio/flac"),
        (".bin", "audio/mpeg"),
    ],
)
def test_media_type_by_extension(client, recordings, suffix, media_type):
    (recordings / f"clip{suffix}").write_bytes(CONTENT)

    response = client.get(f"/v1/recording/clip{suffix}")

    assert response.headers["content-type"].split(";")[0] == media_type


@pytest.mark.parametrize(
    "range_header,body,content_range",
    [
        ("bytes=2-5", b"2345", "bytes 2-5/10"),
        ("bytes=7-", b"789", "bytes 7-9/10"),
        ("bytes=-3", b"789", "bytes 7-9/10"),
    ],
)
def test_range_request_returns_partial_content(
    client, recordings, range_header, body, content_range
):
    response = client.get(URL, headers={"Range": range_header})

    assert response.status_code == 206
    assert response.content == body
    assert response.headers["content-range"] == content_range
    assert response.headers["content-length"] == str(len(body))


def test_unsatisfiable_range_falls_back_to_full_file(client, recordings):
    response = client.get(URL, headers={"Range": "bytes=5-100"})

    assert response.status_code == 200
    assert response.content == CONTENT


def test_matching_etag_returns_not_modified(client, recordings):
    etag = client.get(URL).headers["etag"]

    response = client.get(URL, headers={"If-None-Match": etag})

    assert response.status_code == 304
    assert response.content == b""


def test_stale_etag_returns_file(client, recordings):
    response = client.get(URL, headers={"If-None-Match": '"stale"'})

    assert response.status_code == 200


def test_etag_changes_when_file_changes(client, recordings):
    before = client.get(URL).headers["etag"]
    (recordings / URL.removeprefix("/v1/recording/")).write_bytes(CONTENT * 2)

    assert client.get(URL).headers["etag"] != before


@pytest.mark.parametrize(
    "offset,expected_status", [(3600, 304), (-3600, 200)], ids=["after", "before"]
)
def test_if_modified_since(client, recordings, offset, expected_status):
    mtime = (recordings / URL.removeprefix("/v1/recording/")).stat().st_mtime
    header = formatdate(mtime + offset, usegmt=True)

    response = client.get(URL, headers={"If-Modified-Since": header})

    assert response.status_code == expected_status


def test_invalid_if_modified_since_is_ignored(client, recordings):
    response = client.get(URL, headers={"If-Modified-Since": "not a date"})

    assert response.status_code == 200


def test_missing_file_returns_404(client, recordings):
    assert client.get("/v1/recording/example.com/nope.mp3").status_code == 404


def test_directory_returns_400(client, recordings):
    assert client.get("/v1/recording/example.com/archive").status_code == 400


def test_symlink_escaping_base_path_is_forbidden(client, recordings, tmp_path):
    secret = tmp_path / "secret.txt"
    secret.write_text("top secret")
    (recordings / "escape.mp3").symlink_to(secret)

    response = client.get("/v1/recording/escape.mp3")

    assert response.status_code == 403
    assert "top secret" not in response.text


@pytest.mark.parametrize(
    "path",
    ["%2E%2E/secret.txt", "example.com/%2E%2E/%2E%2E/secret.txt"],
    ids=["parent", "nested-parent"],
)
def test_encoded_dot_dot_traversal_is_forbidden(client, recordings, tmp_path, path):
    (tmp_path / "secret.txt").write_text("top secret")

    response = client.get(f"/v1/recording/{path}")

    assert response.status_code in (403, 404)
    assert "top secret" not in response.text


def test_unconfigured_recording_path_returns_500(client, app_settings, monkeypatch):
    monkeypatch.setattr(app_settings, "app_recording_path", None)

    assert client.get(URL).status_code == 500
