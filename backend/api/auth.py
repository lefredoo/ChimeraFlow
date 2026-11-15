"""
Authentication API: demo account login and the dependency that protects the API.

POST /api/v1/auth/login, GET /api/v1/auth/me

Security:
- One demo account (DEMO_LOGIN_EMAIL, scrypt hash in DEMO_LOGIN_PASSWORD_HASH)
- Login is rate limited per IP and answers one generic 401 whatever is wrong
- Tokens are signed (HMAC-SHA256) and expire; they are never logged
- Neither emails nor passwords nor tokens are logged
"""
import logging
from typing import Optional

import anyio
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

import config
from api.errors import (
    AUTH_INVALID_CREDENTIALS,
    AUTH_REQUIRED,
    AUTH_TOKEN_EXPIRED,
    AUTH_TOKEN_INVALID,
    api_error,
    error_detail,
)
from api.rate_limit import limiter, login_limit
from auth.credentials import credentials_match
from auth.tokens import (
    TOKEN_TTL_SECONDS,
    ExpiredTokenError,
    InvalidTokenError,
    TokenClaims,
    issue_token,
    verify_token,
)
from schemas.auth import LoginRequest, MeResponse, TokenResponse

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/auth", tags=["auth"])

# One hash uses 32 MiB: at most two run at once, so a burst of logins from many
# IPs cannot exhaust the container memory (the others wait)
_HASH_LIMITER = anyio.CapacityLimiter(2)

# auto_error=False: the dependency answers with the API's own error body
_bearer_scheme = HTTPBearer(auto_error=False)


def _unauthorized(code: str, message: str) -> HTTPException:
    """401 with the standard error body and the Bearer challenge."""
    return HTTPException(
        status_code=401,
        detail=error_detail(code, message),
        headers={"WWW-Authenticate": "Bearer"},
    )


def require_auth(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(_bearer_scheme),
) -> TokenClaims:
    """Dependency: require a valid `Authorization: Bearer <token>` header.

    Returns:
        Verified claims of the token.

    Raises:
        HTTPException: 401 `auth_required` (no token), `auth_token_expired` or
            `auth_token_invalid` (bad signature, malformed, or another account).
    """
    if credentials is None or not credentials.credentials:
        raise _unauthorized(AUTH_REQUIRED, "Authentication required")
    try:
        claims = verify_token(credentials.credentials, config.AUTH_TOKEN_SECRET)
    except ExpiredTokenError as error:
        raise _unauthorized(AUTH_TOKEN_EXPIRED, "Token expired") from error
    except InvalidTokenError as error:
        raise _unauthorized(AUTH_TOKEN_INVALID, "Token invalid") from error
    # A token of a former account (the demo email changed) stops working at once
    if claims.subject != config.DEMO_LOGIN_EMAIL:
        raise _unauthorized(AUTH_TOKEN_INVALID, "Token invalid")
    return claims


@router.post("/login", response_model=TokenResponse)
@limiter.limit(login_limit)
async def login(payload: LoginRequest, request: Request) -> TokenResponse:
    """
    Exchange the demo credentials for an access token

    Security:
    - Rate limited per IP (stricter than the other mutations)
    - Same 401 whether the email or the password is wrong
    - The password hash is computed even for an unknown email (constant work)
    """
    matches = await anyio.to_thread.run_sync(
        credentials_match,
        payload.email,
        payload.password,
        config.DEMO_LOGIN_EMAIL,
        config.DEMO_LOGIN_PASSWORD_HASH,
        limiter=_HASH_LIMITER,
    )
    if not matches:
        logger.info("Login refused")
        raise api_error(401, AUTH_INVALID_CREDENTIALS, "Invalid credentials")

    logger.info("Login accepted")
    token = issue_token(config.DEMO_LOGIN_EMAIL, config.AUTH_TOKEN_SECRET)
    return TokenResponse(access_token=token, expires_in=TOKEN_TTL_SECONDS)


@router.get("/me", response_model=MeResponse)
async def me(claims: TokenClaims = Depends(require_auth)) -> MeResponse:
    """Account behind the presented token."""
    return MeResponse(email=claims.subject)
