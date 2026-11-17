"""
Hosted MCP service: the four read-only sources over Streamable HTTP.

One ASGI app, one endpoint per source (`/mcp/excel`, `/mcp/access`, `/mcp/whatsapp`,
`/mcp/momo`), so Kiro lists the same four servers as with stdio and each keeps its
own tools. Every endpoint requires `Authorization: Bearer <MCP_HTTP_TOKEN>`; requests
are limited per client IP before the token is checked, which also bounds guessing.
`/health` is the only open path (no data, used by the container healthcheck).

The servers are stateless (no session kept between requests): a restart or a
redeploy never leaves a client with a dead session. DNS rebinding protection is
off because the Host header is the public hostname and access is decided by the
bearer token, not by the network position of the caller.
"""
import hashlib
import hmac
import json
import logging
import time
from contextlib import AsyncExitStack, asynccontextmanager
from ipaddress import IPv4Address, IPv6Address, IPv6Network, ip_address
from typing import AsyncIterator, Dict, List, Optional, Tuple, Union

from mcp.server.transport_security import TransportSecuritySettings
from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import JSONResponse
from starlette.routing import Route
from starlette.types import ASGIApp, Receive, Scope, Send

from .mcp_app import create_server
from .mcp_settings import IPNetwork, McpHttpSettings

logger = logging.getLogger("chimeraflow.mcp.http")

HEALTH_PATH = "/health"
UNKNOWN_CLIENT = "unknown"
# A client owns a whole IPv6 /64: keying by it stops one host from rotating addresses
IPV6_KEY_PREFIX_LENGTH = 64
# Upper bound of the limiter table; expired windows are dropped when it is reached
MAX_TRACKED_CLIENTS = 10_000


def _parse_address(address: str) -> Union[IPv4Address, IPv6Address]:
    """Parse an IP address, reading an IPv4-mapped IPv6 address as the IPv4 one."""
    parsed = ip_address(address)
    if isinstance(parsed, IPv6Address) and parsed.ipv4_mapped is not None:
        return parsed.ipv4_mapped
    return parsed


def _limit_key(address: str) -> str:
    """Rate limit key of a client address (an IPv6 client is keyed by its /64)."""
    try:
        parsed = _parse_address(address)
    except ValueError:
        return address
    if isinstance(parsed, IPv6Address):
        return str(IPv6Network((parsed.packed, IPV6_KEY_PREFIX_LENGTH), strict=False))
    return str(parsed)


def _is_trusted(address: str, trusted: Tuple[IPNetwork, ...]) -> bool:
    try:
        parsed = _parse_address(address)
    except ValueError:
        return False
    return any(parsed in network for network in trusted if network.version == parsed.version)


def resolve_client(scope: Scope, trusted_proxies: Tuple[IPNetwork, ...]) -> str:
    """Resolve the client address used as rate limit key.

    X-Forwarded-For is read only when the socket peer is a trusted proxy, from the
    right: the first entry that is not a trusted proxy is the client. Anything
    unexpected falls back to the peer. Same rule as the API (api/rate_limit.py),
    which cannot be imported here because it needs every API setting.
    """
    client = scope.get("client")
    if not client:
        return UNKNOWN_CLIENT
    peer = client[0]
    if not trusted_proxies or not _is_trusted(peer, trusted_proxies):
        return _limit_key(peer)
    forwarded = ",".join(
        value.decode("latin-1") for name, value in scope["headers"] if name == b"x-forwarded-for"
    )
    if not forwarded:
        return _limit_key(peer)
    for entry in reversed([item.strip() for item in forwarded.split(",")]):
        try:
            _parse_address(entry)
        except ValueError:
            return _limit_key(peer)
        if not _is_trusted(entry, trusted_proxies):
            return _limit_key(entry)
    return _limit_key(peer)


class FixedWindowLimiter:
    """Per-key request counter over fixed windows, in memory (one process serves the app)."""

    def __init__(self, limit: int, window_seconds: int):
        self._limit = limit
        self._window = window_seconds
        self._counters: Dict[str, Tuple[float, int]] = {}

    def hit(self, key: str, now: Optional[float] = None) -> Optional[int]:
        """Count a request.

        Returns:
            None when the request is allowed, else the seconds until the window resets.
        """
        current = time.monotonic() if now is None else now
        if len(self._counters) >= MAX_TRACKED_CLIENTS:
            self._counters = {k: v for k, v in self._counters.items() if current - v[0] < self._window}
        started, count = self._counters.get(key, (current, 0))
        if current - started >= self._window:
            started, count = current, 0
        count += 1
        self._counters[key] = (started, count)
        if count > self._limit:
            return max(1, int(started + self._window - current) + 1)
        return None


class GuardMiddleware:
    """Rate limit, then bearer token check, in front of every path except /health."""

    def __init__(self, app: ASGIApp, settings: McpHttpSettings):
        self._app = app
        self._trusted_proxies = settings.trusted_proxies
        # Compared as digests: equal length whatever the guess, compare_digest runs in constant time
        self._token_digest = hashlib.sha256(settings.token.encode("utf-8")).digest()
        self._limiter = FixedWindowLimiter(settings.rate_limit_per_ip, settings.rate_limit_window_seconds)

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http" or scope["path"] == HEALTH_PATH:
            await self._app(scope, receive, send)
            return
        retry_after = self._limiter.hit(resolve_client(scope, self._trusted_proxies))
        if retry_after is not None:
            logger.warning("mcp request refused: rate limit")
            response = JSONResponse(
                {"detail": "Too many requests"}, status_code=429, headers={"Retry-After": str(retry_after)}
            )
            await response(scope, receive, send)
            return
        if not self._is_authorized(scope):
            logger.warning("mcp request refused: missing or invalid token")
            response = JSONResponse(
                {"detail": "Missing or invalid bearer token"},
                status_code=401,
                headers={"WWW-Authenticate": "Bearer"},
            )
            await response(scope, receive, send)
            return
        await self._app(scope, receive, send)

    def _is_authorized(self, scope: Scope) -> bool:
        header = next((value for name, value in scope["headers"] if name == b"authorization"), b"")
        scheme, _, credential = header.decode("latin-1").partition(" ")
        if scheme.lower() != "bearer" or not credential:
            return False
        digest = hashlib.sha256(credential.strip().encode("utf-8")).digest()
        return hmac.compare_digest(digest, self._token_digest)


async def _health(_request: Request) -> JSONResponse:
    return JSONResponse({"status": "ok"})


def create_http_app(settings: McpHttpSettings) -> ASGIApp:
    """Build the hosted MCP app.

    Args:
        settings: Validated settings of the hosted service.

    Returns:
        ASGI app: `/mcp/<source>` for each source behind the bearer token, plus `/health`.
    """
    sub_apps: List[Starlette] = []
    for source_settings in settings.sources:
        server = create_server(source_settings)
        sub_apps.append(
            server.streamable_http_app(
                streamable_http_path=f"/mcp/{source_settings.source.name}",
                stateless_http=True,
                json_response=True,
                transport_security=TransportSecuritySettings(enable_dns_rebinding_protection=False),
            )
        )

    @asynccontextmanager
    async def lifespan(_app: Starlette) -> AsyncIterator[None]:
        # Each server owns a session manager that its own app starts in its lifespan
        async with AsyncExitStack() as stack:
            for sub_app in sub_apps:
                await stack.enter_async_context(sub_app.router.lifespan_context(sub_app))
            yield

    routes = [Route(HEALTH_PATH, _health)]
    for sub_app in sub_apps:
        routes.extend(sub_app.routes)
    app = Starlette(routes=routes, lifespan=lifespan)
    return GuardMiddleware(app, settings)


def log_started(settings: McpHttpSettings) -> None:
    """Log the served endpoints (no secret, no data)."""
    logger.info(json.dumps({"event": "mcp_http_started", "endpoints": [f"/mcp/{s.source.name}" for s in settings.sources]}))
