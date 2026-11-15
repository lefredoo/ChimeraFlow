"""
Per-IP rate limiting for the mutation endpoints (slowapi).

Counters live in Redis (REDIS_URL) so that they are shared by every worker and
survive a restart. Memory storage is used only when BACKEND_NODE_ENV=test
(see config.RATE_LIMIT_STORAGE_URI).

The limit strings are built at request time from `config`, so the values come
from RATE_LIMIT_PER_IP / RATE_LIMIT_WINDOW_SECONDS and nothing is hardcoded.
"""
import logging
import math
import time
from ipaddress import IPv4Address, IPv6Address, IPv6Network, ip_address
from typing import Union

from fastapi import Request
from fastapi.responses import JSONResponse
from limits.errors import StorageError
from slowapi import Limiter
from slowapi.errors import RateLimitExceeded

import config
from api.errors import RATE_LIMIT_EXCEEDED, RATE_LIMIT_UNAVAILABLE, error_detail

logger = logging.getLogger(__name__)

# slowapi logs the limit key (the client IP, personal data) at WARNING when a
# limit is exceeded; the 429 itself is the signal, so only errors are kept.
logging.getLogger("slowapi").setLevel(logging.ERROR)

# Peer address used when the connection has no client information
UNKNOWN_CLIENT = "unknown"


# Prefix length that identifies one IPv6 subscriber: a client owns a whole /64
IPV6_KEY_PREFIX_LENGTH = 64


def _parse_address(address: str) -> Union[IPv4Address, IPv6Address]:
    """Parse an IP address, reading an IPv4-mapped IPv6 address (::ffff:a.b.c.d) as the IPv4 one.

    Raises:
        ValueError: If the text is not an IP address.
    """
    parsed = ip_address(address)
    if isinstance(parsed, IPv6Address) and parsed.ipv4_mapped is not None:
        return parsed.ipv4_mapped
    return parsed


def _limit_key(address: str) -> str:
    """Rate limit key of a client address.

    An IPv6 client is keyed by its /64, otherwise it would get a fresh counter
    from every address of its prefix. Anything that is not an IP address is
    returned unchanged.
    """
    try:
        parsed = _parse_address(address)
    except ValueError:
        return address
    if isinstance(parsed, IPv6Address):
        network = IPv6Network((parsed.packed, IPV6_KEY_PREFIX_LENGTH), strict=False)
        return str(network)
    return str(parsed)


def _is_trusted_proxy(address: str) -> bool:
    """Tell whether an address belongs to one of the TRUSTED_PROXIES networks."""
    try:
        parsed = _parse_address(address)
    except ValueError:
        return False
    return any(parsed in network for network in config.TRUSTED_PROXIES if network.version == parsed.version)


def client_ip(request: Request) -> str:
    """Resolve the client address used as rate limit key.

    X-Forwarded-For is a client-writable header, so it is read only when the
    socket peer is a trusted proxy (TRUSTED_PROXIES). The entries are then read
    from the right, which is where the trusted proxies append the address they
    saw: the first entry that is not a trusted proxy is the client. Anything
    unexpected (no header, invalid entry, only proxies) falls back to the peer.

    A request may carry several X-Forwarded-For lines (HTTP allows it, and a
    proxy appends to the last one or adds a line): they are read as one
    comma-separated list, in order.

    Addresses are normalized: an IPv4-mapped IPv6 address is the IPv4 one, and
    an IPv6 client is keyed by its /64.

    Args:
        request: Incoming request.

    Returns:
        Rate limit key of the client (the raw peer value when it is not an IP address).
    """
    peer = request.client.host if request.client else None
    if peer is None:
        return UNKNOWN_CLIENT
    if not config.TRUSTED_PROXIES or not _is_trusted_proxy(peer):
        return _limit_key(peer)

    forwarded = ",".join(request.headers.getlist("x-forwarded-for"))
    if not forwarded:
        return _limit_key(peer)
    for entry in reversed([item.strip() for item in forwarded.split(",")]):
        try:
            _parse_address(entry)
        except ValueError:
            return _limit_key(peer)
        if not _is_trusted_proxy(entry):
            return _limit_key(entry)
    return _limit_key(peer)


def mutation_limit() -> str:
    """Limit of the mutation endpoints, read from the configuration at request time."""
    return f"{config.RATE_LIMIT_PER_IP} per {config.RATE_LIMIT_WINDOW_SECONDS} second"


def nl_limit() -> str:
    """Stricter limit of the NL->rule endpoint (each request can spend LLM budget)."""
    return f"{config.RATE_LIMIT_NL_PER_IP} per {config.RATE_LIMIT_WINDOW_SECONDS} second"


def login_limit() -> str:
    """Limit of the login endpoint (each attempt costs a scrypt hash, and guesses are the threat)."""
    return f"{config.RATE_LIMIT_LOGIN_PER_IP} per {config.RATE_LIMIT_WINDOW_SECONDS} second"


# key_style="endpoint": one counter per endpoint function, not per URL
# (DELETE /rules/{id} must share a single counter whatever the id)
limiter = Limiter(
    key_func=client_ip,
    storage_uri=config.RATE_LIMIT_STORAGE_URI,
    key_style="endpoint",
)


def _retry_after_seconds(request: Request, exc: RateLimitExceeded) -> int:
    """Seconds until the exceeded limit allows a new request (at least 1)."""
    window = exc.limit.limit.get_expiry()
    current = getattr(request.state, "view_rate_limit", None)
    if current is None:
        return window
    try:
        reset_time = limiter.limiter.get_window_stats(current[0], *current[1])[0]
    except StorageError:
        return window
    return max(1, math.ceil(reset_time - time.time()))


def rate_limit_exceeded_handler(request: Request, exc: Exception) -> JSONResponse:
    """429 response with the standard error body and a Retry-After header."""
    if not isinstance(exc, RateLimitExceeded):
        raise exc
    return JSONResponse(
        status_code=429,
        content={"detail": error_detail(RATE_LIMIT_EXCEEDED, "Too many requests")},
        headers={"Retry-After": str(_retry_after_seconds(request, exc))},
    )


def rate_limit_storage_error_handler(_request: Request, exc: Exception) -> JSONResponse:
    """503 when the limiter storage (Redis) fails: mutations are refused, not unlimited."""
    logger.error("Rate limit storage failed: %s", type(exc).__name__)
    return JSONResponse(
        status_code=503,
        content={"detail": error_detail(RATE_LIMIT_UNAVAILABLE, "Rate limiter is unavailable")},
    )


def register_rate_limiting(app) -> None:
    """Attach the limiter and its error handlers to the application.

    Args:
        app: FastAPI application.
    """
    app.state.limiter = limiter
    app.add_exception_handler(RateLimitExceeded, rate_limit_exceeded_handler)
    app.add_exception_handler(StorageError, rate_limit_storage_error_handler)
