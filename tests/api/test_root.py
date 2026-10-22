"""Tests for unauthenticated top-level endpoints."""

from app.core.config import APP_NAME, APP_VERSION


def test_root(client):
    assert client.get("/").json() == {
        "message": APP_NAME,
        "version": APP_VERSION,
        "docs": "/docs",
    }


def test_health(client):
    assert client.get("/health").json() == {"status": "healthy"}


def test_openapi_lists_v1_routes(client):
    paths = client.get("/openapi.json").json()["paths"]

    assert {"/v1/me", "/v1/cdr", "/v1/cdr_compat", "/v1/recording/{file_path}"} <= set(
        paths
    )
