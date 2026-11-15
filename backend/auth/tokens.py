"""
Signed access tokens (HMAC-SHA256, no dependency).

Format: `<payload>.<signature>`, both unpadded URL-safe base64. The payload is
JSON `{"v": 1, "sub": <email>, "iat": <epoch seconds>, "exp": <epoch seconds>}`.
The signature covers the encoded payload. The algorithm is fixed (there is no
header to tamper with), and the signature is checked before the payload is
parsed or its expiry read.

A token is valid until it expires: there is no revocation.
"""
import base64
import binascii
import hashlib
import hmac
import json
import time
from dataclasses import dataclass
from typing import Optional

TOKEN_TTL_SECONDS = 3600
TOKEN_VERSION = 1
# A genuine token is about 150 characters; anything longer is rejected before decoding
MAX_TOKEN_LENGTH = 1024


class InvalidTokenError(Exception):
    """The token is malformed or its signature does not match."""


class ExpiredTokenError(Exception):
    """The token is genuine but past its expiry."""


@dataclass(frozen=True)
class TokenClaims:
    """Verified content of a token."""

    subject: str
    issued_at: int
    expires_at: int


def _b64encode(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


def _b64decode(text: str) -> bytes:
    try:
        data = base64.urlsafe_b64decode(text + "=" * (-len(text) % 4))
    except (binascii.Error, ValueError) as exc:
        raise InvalidTokenError("malformed token") from exc
    if _b64encode(data) != text:
        raise InvalidTokenError("malformed token")
    return data


def _sign(payload: str, secret: str) -> bytes:
    return hmac.new(secret.encode("utf-8"), payload.encode("utf-8"), hashlib.sha256).digest()


def issue_token(
    subject: str,
    secret: str,
    now: Optional[float] = None,
    ttl_seconds: int = TOKEN_TTL_SECONDS,
) -> str:
    """Sign a token for a subject.

    Args:
        subject: Who the token is for (the account email).
        secret: Signing secret.
        now: Issue time in epoch seconds (the clock when None).
        ttl_seconds: Lifetime of the token.

    Returns:
        The compact token.
    """
    issued_at = int(time.time() if now is None else now)
    claims = {"v": TOKEN_VERSION, "sub": subject, "iat": issued_at, "exp": issued_at + ttl_seconds}
    payload = _b64encode(json.dumps(claims, separators=(",", ":")).encode("utf-8"))
    return f"{payload}.{_b64encode(_sign(payload, secret))}"


def verify_token(token: str, secret: str, now: Optional[float] = None) -> TokenClaims:
    """Verify a token's signature and expiry.

    Args:
        token: Compact token received from a client.
        secret: Signing secret.
        now: Current time in epoch seconds (the clock when None).

    Returns:
        The verified claims.

    Raises:
        InvalidTokenError: Malformed token or wrong signature.
        ExpiredTokenError: Genuine token past its expiry.
    """
    if len(token) > MAX_TOKEN_LENGTH:
        raise InvalidTokenError("token too long")
    parts = token.split(".")
    if len(parts) != 2:
        raise InvalidTokenError("malformed token")
    payload, signature = parts
    if not hmac.compare_digest(_b64decode(signature), _sign(payload, secret)):
        raise InvalidTokenError("bad signature")
    try:
        claims = json.loads(_b64decode(payload))
        subject, issued_at, expires_at = claims["sub"], claims["iat"], claims["exp"]
        version = claims["v"]
    except (ValueError, KeyError, TypeError) as exc:
        raise InvalidTokenError("malformed payload") from exc
    if (
        version != TOKEN_VERSION
        or not isinstance(subject, str)
        or isinstance(issued_at, bool)
        or isinstance(expires_at, bool)
        or not isinstance(issued_at, int)
        or not isinstance(expires_at, int)
    ):
        raise InvalidTokenError("malformed payload")
    if issued_at > expires_at:
        raise InvalidTokenError("malformed payload")
    if (time.time() if now is None else now) >= expires_at:
        raise ExpiredTokenError("token expired")
    return TokenClaims(subject=subject, issued_at=issued_at, expires_at=expires_at)
