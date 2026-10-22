"""Tests for Keycloak JWT validation and domain extraction."""

import base64
import time

import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from fastapi import HTTPException
from jose import jwt

from app.core import security
from app.core.security import KeycloakJWTBearer, TokenData, get_user_domain

ISSUER = "https://sso.test/realms/test-realm"
KID = "test-kid"


def _b64url_uint(value: int) -> str:
    raw = value.to_bytes((value.bit_length() + 7) // 8, "big")
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode()


@pytest.fixture(scope="module")
def rsa_private_key():
    return rsa.generate_private_key(public_exponent=65537, key_size=2048)


@pytest.fixture(scope="module")
def jwks(rsa_private_key):
    numbers = rsa_private_key.public_key().public_numbers()
    return {
        "keys": [
            {
                "kty": "RSA",
                "kid": KID,
                "use": "sig",
                "alg": "RS256",
                "n": _b64url_uint(numbers.n),
                "e": _b64url_uint(numbers.e),
            }
        ]
    }


@pytest.fixture
def make_token(rsa_private_key):
    """Factory that signs tokens with the test key."""
    pem = rsa_private_key.private_bytes(
        serialization.Encoding.PEM,
        serialization.PrivateFormat.PKCS8,
        serialization.NoEncryption(),
    )

    def _make_token(kid: str = KID, **claims) -> str:
        payload = {
            "sub": "service-account-customer-acme-m2m",
            "iss": ISSUER,
            "exp": int(time.time()) + 300,
            "sip_domain": "example.com",
        }
        payload.update(claims)
        payload = {k: v for k, v in payload.items() if v is not None}
        return jwt.encode(payload, pem, algorithm="RS256", headers={"kid": kid})

    return _make_token


@pytest.fixture
def validator(jwks) -> KeycloakJWTBearer:
    instance = KeycloakJWTBearer()
    instance._jwks = jwks
    return instance


@pytest.mark.asyncio
async def test_valid_token_returns_claims(validator, make_token):
    data = await validator.verify_token(make_token(aud="test-api"))

    assert data.sub == "service-account-customer-acme-m2m"
    assert data.sip_domain == "example.com"
    assert data.aud == "test-api"


@pytest.mark.asyncio
async def test_token_without_audience_from_allowed_client_is_accepted(
    validator, make_token, app_settings, monkeypatch, caplog
):
    """Legacy M2M tokens without aud pass only when azp is allow-listed."""
    monkeypatch.setattr(
        app_settings, "keycloak_allowed_clients", "customer-acme-m2m,customer-b-m2m"
    )

    data = await validator.verify_token(make_token(aud=None, azp="customer-acme-m2m"))

    assert data.aud is None
    assert "customer-acme-m2m" in caplog.text


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "allowed,azp",
    [
        pytest.param("", "customer-acme-m2m", id="empty-allow-list"),
        pytest.param("customer-acme-m2m", "other-client", id="azp-not-allowed"),
        pytest.param("customer-acme-m2m", None, id="no-azp"),
    ],
)
async def test_token_without_audience_is_rejected(
    validator, make_token, app_settings, monkeypatch, allowed, azp
):
    monkeypatch.setattr(app_settings, "keycloak_allowed_clients", allowed)

    with pytest.raises(HTTPException) as exc_info:
        await validator.verify_token(make_token(aud=None, azp=azp))

    assert exc_info.value.status_code == 401
    assert exc_info.value.detail == "Invalid audience"


@pytest.mark.asyncio
async def test_allowed_client_with_wrong_audience_is_rejected(
    validator, make_token, app_settings, monkeypatch
):
    """The allow-list only covers tokens with no aud at all."""
    monkeypatch.setattr(app_settings, "keycloak_allowed_clients", "customer-acme-m2m")

    with pytest.raises(HTTPException) as exc_info:
        await validator.verify_token(
            make_token(aud="other-api", azp="customer-acme-m2m")
        )

    assert exc_info.value.status_code == 401


@pytest.mark.asyncio
async def test_audience_list_containing_expected_value_is_accepted(
    validator, make_token
):
    data = await validator.verify_token(make_token(aud=["account", "test-api"]))
    assert data.aud == ["account", "test-api"]


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "claims,detail",
    [
        pytest.param({"aud": "other-api"}, "Invalid audience", id="wrong-aud-string"),
        pytest.param({"aud": ["account"]}, "Invalid audience", id="wrong-aud-list"),
        pytest.param(
            {"exp": int(time.time()) - 10}, "Invalid token", id="expired"
        ),
        pytest.param(
            {"iss": "https://evil.test/realms/test-realm"},
            "Invalid token",
            id="wrong-issuer",
        ),
    ],
)
async def test_invalid_claims_are_rejected(validator, make_token, claims, detail):
    with pytest.raises(HTTPException) as exc_info:
        await validator.verify_token(make_token(**claims))

    assert exc_info.value.status_code == 401
    assert detail in exc_info.value.detail


@pytest.mark.asyncio
async def test_unknown_kid_is_rejected(validator, make_token):
    with pytest.raises(HTTPException) as exc_info:
        await validator.verify_token(make_token(kid="rotated-key"))

    assert exc_info.value.status_code == 401
    assert exc_info.value.detail == "Unable to find appropriate key"


@pytest.mark.asyncio
async def test_token_signed_with_another_key_is_rejected(jwks, make_token):
    other_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    pem = other_key.private_bytes(
        serialization.Encoding.PEM,
        serialization.PrivateFormat.PKCS8,
        serialization.NoEncryption(),
    )
    forged = jwt.encode(
        {"sub": "x", "iss": ISSUER, "exp": int(time.time()) + 300},
        pem,
        algorithm="RS256",
        headers={"kid": KID},
    )
    validator = KeycloakJWTBearer()
    validator._jwks = jwks

    with pytest.raises(HTTPException) as exc_info:
        await validator.verify_token(forged)

    assert exc_info.value.status_code == 401


@pytest.mark.asyncio
async def test_malformed_token_is_rejected(validator):
    with pytest.raises(HTTPException) as exc_info:
        await validator.verify_token("not-a-jwt")

    assert exc_info.value.status_code == 401
    assert exc_info.value.detail == "Invalid token header"


@pytest.mark.asyncio
async def test_jwks_is_fetched_once_and_cached(monkeypatch, jwks):
    calls = []

    class FakeResponse:
        def raise_for_status(self):
            pass

        def json(self):
            return jwks

    class FakeAsyncClient:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *exc):
            return False

        async def get(self, url):
            calls.append(url)
            return FakeResponse()

    monkeypatch.setattr(security.httpx, "AsyncClient", FakeAsyncClient)
    validator = KeycloakJWTBearer()

    assert await validator.get_jwks() == jwks
    assert await validator.get_jwks() == jwks
    assert calls == [f"{ISSUER}/protocol/openid-connect/certs"]


def test_get_user_domain_returns_sip_domain():
    user = TokenData(sub="u", sip_domain="example.com", exp=0)
    assert get_user_domain(user) == "example.com"


def test_get_user_domain_without_sip_domain_is_forbidden():
    with pytest.raises(HTTPException) as exc_info:
        get_user_domain(TokenData(sub="u", exp=0))

    assert exc_info.value.status_code == 403


def test_me_endpoint_returns_token_claims(client, monkeypatch, jwks, make_token):
    monkeypatch.setattr(security.keycloak_validator, "_jwks", jwks)

    response = client.get(
        "/v1/me", headers={"Authorization": f"Bearer {make_token(aud='test-api')}"}
    )

    assert response.status_code == 200
    body = response.json()
    assert body["sub"] == "service-account-customer-acme-m2m"
    assert body["sip_domain"] == "example.com"


def test_me_endpoint_requires_bearer_token(client):
    assert client.get("/v1/me").status_code == 403
