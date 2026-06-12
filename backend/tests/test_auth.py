from __future__ import annotations

from datetime import datetime, timedelta, timezone

import jwt
import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa

from app.auth import AuthenticationError, ClerkAuthenticator


def _key_pair() -> tuple[str, str]:
    private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    private_pem = private_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    ).decode()
    public_pem = private_key.public_key().public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo,
    ).decode()
    return private_pem, public_pem


def _token(
    private_key: str,
    *,
    user_id: str = "user_123",
    authorized_party: str | None = "http://localhost:3000",
    expires_in: timedelta = timedelta(minutes=5),
) -> str:
    now = datetime.now(timezone.utc)
    claims = {
        "sub": user_id,
        "sid": "sess_123",
        "iat": now,
        "nbf": now - timedelta(seconds=1),
        "exp": now + expires_in,
    }
    if authorized_party is not None:
        claims["azp"] = authorized_party
    return jwt.encode(claims, private_key, algorithm="RS256")


def test_clerk_authenticator_accepts_valid_session_token() -> None:
    private_key, public_key = _key_pair()
    authenticator = ClerkAuthenticator(
        jwt_key=public_key,
        authorized_parties=("http://localhost:3000",),
    )

    identity = authenticator.authenticate(
        authorization=f"Bearer {_token(private_key)}",
        visitor_id="11111111-1111-4111-8111-111111111111",
    )

    assert identity.user_id == "user_123"
    assert identity.anonymous_id == "11111111-1111-4111-8111-111111111111"
    assert identity.is_authenticated is True


def test_clerk_authenticator_keeps_unsigned_visitor_anonymous() -> None:
    _, public_key = _key_pair()
    authenticator = ClerkAuthenticator(
        jwt_key=public_key,
        authorized_parties=("http://localhost:3000",),
    )

    identity = authenticator.authenticate(
        authorization=None,
        visitor_id="11111111-1111-4111-8111-111111111111",
    )

    assert identity.user_id is None
    assert identity.anonymous_id == "11111111-1111-4111-8111-111111111111"
    assert identity.is_authenticated is False


@pytest.mark.parametrize(
    ("authorized_party", "expires_in"),
    [
        ("https://attacker.example", timedelta(minutes=5)),
        ("http://localhost:3000", timedelta(minutes=-5)),
        (None, timedelta(minutes=5)),
    ],
)
def test_clerk_authenticator_rejects_invalid_session_token(
    authorized_party: str | None,
    expires_in: timedelta,
) -> None:
    private_key, public_key = _key_pair()
    authenticator = ClerkAuthenticator(
        jwt_key=public_key,
        authorized_parties=("http://localhost:3000",),
    )

    with pytest.raises(AuthenticationError):
        authenticator.authenticate(
            authorization=f"Bearer {_token(private_key, authorized_party=authorized_party, expires_in=expires_in)}",
            visitor_id="11111111-1111-4111-8111-111111111111",
        )
