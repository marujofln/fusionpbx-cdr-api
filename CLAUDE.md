# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

A read-only FastAPI service that exposes FusionPBX call detail records (the `v_xml_cdr` table in the FusionPBX PostgreSQL database) and serves call recording files from disk. Authentication is done with Keycloak JWTs. Each customer gets their own Keycloak client, usually an M2M client-credentials client with a 10-year token, and the token's `sip_domain` claim decides which domain's CDRs come back. One deployment serves all customers. `README.md` and `KEYCLOAK_REALM_IMPORT.md` cover Keycloak setup step by step.

## Commands

Dependencies are managed with `uv` (Python ≥3.12). Dev tools are an optional extra, so plain `uv sync` does not install them:

```bash
uv sync --extra dev                 # install runtime + dev tools (pytest, black, isort, flake8, mypy)
cp env.example .env                 # then fill in Keycloak + FusionPBX DB settings

uv run python run.py                # run locally on APP_PORT (default 3001); auto-reload when APP_DEBUG=true
uv run uvicorn app.main:app --reload --host 0.0.0.0 --port 3001   # alternative

uv run black . && uv run isort . && uv run flake8 . && uv run mypy .
```

Tests (no DB or Keycloak needed; coverage flags come from `addopts` in `pyproject.toml`):

```bash
uv run pytest                                                        # full suite
uv run pytest tests/api/test_recording_endpoint.py::test_full_file --no-cov   # single test
```

`tests/conftest.py` sets the env vars and disables `.env` loading *before* importing `app`; new test modules must not import `app` ahead of it. Endpoint tests use the `auth_client` fixture, which overrides `get_user_domain`/`get_db`, and monkeypatch `CDRService`. Auth tests sign real JWTs with a generated RSA key and inject the JWKS into the validator. Change settings with `monkeypatch.setattr(app_settings, ...)`.

Docker:

```bash
docker-compose up -d --build                           # api + Caddy (HTTPS on 80/443, hostname from API_HOST)
docker-compose logs -f api
```

The `Caddyfile` uses `{$API_HOST}` with automatic HTTPS on 80/443, proxying to `{$CADDY_UPSTREAM}` (default `api:3001`). The API container itself is never published to the host. `docker-compose.2.1.yml` (for Docker 1.13.1) is stale: it still maps port 3000 and doesn't pass `API_HOST`/`CADDY_UPSTREAM`, so it doesn't match the current Caddyfile.

## Architecture

Request flow: `app/main.py` mounts `app/api/v1/api.py` under `/v1`. It includes the `me`, `cdr` and `recording` routers from `app/api/v1/endpoints/`. `/` and `/health` are unauthenticated and are used by healthchecks.

**Auth and tenant isolation** (`app/core/security.py`):
- `get_current_user` validates the bearer token against the realm JWKS. The JWKS is fetched once and then cached in-process for the life of the process, with no refresh when keys rotate. The dependency also checks the issuer `{KEYCLOAK_SERVER_URL}/realms/{KEYCLOAK_REALM}`.
- Audience is checked by hand, and only when the token actually has an `aud` claim, because M2M tokens may not carry one.
- `get_user_domain` gets `sip_domain` from the token, returning 403 if it is missing. Every CDR query must filter on `CDR.domain_name == domain`, using this dependency. This filter is the only thing separating tenants.

**Recordings endpoint** (`/v1/recording/{file_path:path}`): **unauthenticated by design**. Its protection is a path-traversal guard: it resolves the path and checks `relative_to(APP_RECORDING_PATH)`. It supports HTTP Range (206), ETag/If-None-Match and If-Modified-Since. Keep the traversal check intact when editing it.

**Two recording-path settings with different meanings** (`app/core/config.py`):
- `FUSIONPBX_RECORDING_PATH` is the prefix FusionPBX stores in `v_xml_cdr.record_path`. It is stripped off when building public recording URLs.
- `APP_RECORDING_PATH` is where the files are actually mounted in this API's filesystem, and it is used to serve them. It defaults to `FUSIONPBX_RECORDING_PATH`.
- Recording URLs take the form `{APP_SERVER_URI or request scheme://host[:port]}/v1/recording/{record_path minus prefix}/{record_name}`.
- This URL-building logic is **duplicated** in `endpoints/cdr.py` (`/cdr`) and `schemas/cdr.py` (`CDRCompatResponse.from_cdr`, used by `/cdr_compat`). Change both together.

**CDR querying** (`app/services/cdr_service.py`): static async methods on `CDRService` built with SQLAlchemy 2.0 `select()` over `AsyncSession`. Named periods (`today`, `last_7_days`, `this_month`, …) are computed from `datetime.utcnow()`. With no period and no explicit date range, the service falls back to the **last hour**. The same happens for an unknown period: `Query(enum=...)` in the endpoints only documents the values, so nothing is validated (`test_unknown_period_is_not_validated` pins this). An explicit `start_date` + `end_date` overrides `period`.

**`/cdr_compat`** returns a flat legacy format: `DD/MM/YYYY HH:MM:SS` dates, `HH:MM:SS` durations and a hard-coded `cost: "R$ 0.00"`. Changing its shape will break legacy consumers.

**Database** (`app/database/session.py`): async engine (`postgresql+asyncpg`) built from `FUSIONPBX_DB_*` settings. The `CDR` model (`app/models/cdr.py`) maps a subset of columns of FusionPBX's existing `v_xml_cdr` table. The schema belongs to FusionPBX, so don't write migrations against it, even though `alembic` is listed as a dependency.

**Settings**: `settings` is a lazy proxy (`_SettingsProxy`) over a pydantic-settings `Settings` that reads `.env` from the CWD or the project root. `KEYCLOAK_SERVER_URL`, `KEYCLOAK_REALM` and `KEYCLOAK_AUDIENCE` are required. The DB engine is created when `app.database.session` is imported, so importing the endpoints or models requires the DB name/user/password env vars to be set. Expect this when writing tests.

`app/services/keycloak_m2m.py` is a reference client for getting client-credentials tokens. The API itself does not use it.
