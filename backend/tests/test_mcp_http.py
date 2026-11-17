"""
Hosted MCP service: the four sources over Streamable HTTP behind a bearer token.

A real uvicorn server runs in a thread on a free local port and is called with the
SDK client and with plain HTTP requests: nothing internal is replaced.
"""
import asyncio
import json
import os
import threading
import time
from contextlib import asynccontextmanager
from pathlib import Path
from typing import AsyncIterator, Dict, Iterator, Optional

import httpx
import httpx2
import pytest
import uvicorn
from mcp import Client
from mcp.client.streamable_http import streamable_http_client

from mcp_servers.mcp_http_app import FixedWindowLimiter, create_http_app, resolve_client
from mcp_servers.mcp_settings import SOURCES, load_http_settings

TOKEN = "test-only-mcp-token-0123456789abcdef-0123456789"
SOURCE_NAMES = sorted(SOURCES)
RATE_LIMIT = 40
STARTUP_TIMEOUT_SECONDS = 60
CALL_TIMEOUT_SECONDS = 60


def _http_env(overrides: Optional[Dict[str, Optional[str]]] = None) -> Dict[str, str]:
    env = {
        "MCP_HTTP_TOKEN": TOKEN,
        "MCP_RATE_LIMIT_PER_IP": str(RATE_LIMIT),
        "RATE_LIMIT_WINDOW_SECONDS": "60",
        "DATA_DIR": os.environ["DATA_DIR"],
        "ACCESS_READER": os.environ["ACCESS_READER"],
    }
    for name, value in (overrides or {}).items():
        if value is None:
            env.pop(name)
        else:
            env[name] = value
    return env


@pytest.fixture
def server_url() -> Iterator[str]:
    """Base URL of a hosted MCP service listening on a free local port."""
    app = create_http_app(load_http_settings(_http_env()))
    server = uvicorn.Server(uvicorn.Config(app, host="127.0.0.1", port=0, log_level="warning", access_log=False))
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()
    deadline = time.monotonic() + STARTUP_TIMEOUT_SECONDS
    while not server.started and thread.is_alive() and time.monotonic() < deadline:
        time.sleep(0.05)
    assert server.started, "the MCP HTTP server did not start"
    port = server.servers[0].sockets[0].getsockname()[1]
    try:
        yield f"http://127.0.0.1:{port}"
    finally:
        server.should_exit = True
        thread.join(10)


@asynccontextmanager
async def open_http(url: str, token: Optional[str] = TOKEN) -> AsyncIterator[Client]:
    """Connect the SDK client to one endpoint, with the bearer token unless it is None."""
    headers = {} if token is None else {"Authorization": f"Bearer {token}"}
    async with httpx2.AsyncClient(headers=headers) as http_client:
        transport = streamable_http_client(url, http_client=http_client)
        async with asyncio.timeout(CALL_TIMEOUT_SECONDS):
            async with Client(transport, mode="legacy") as client:
                yield client


class TestHealth:
    async def test_should_answer_ok_without_token_when_calling_health(self, server_url):
        async with httpx.AsyncClient() as http:
            response = await http.get(f"{server_url}/health")

        assert response.status_code == 200
        assert response.json() == {"status": "ok"}


class TestAuthentication:
    @pytest.mark.parametrize("headers", [{}, {"Authorization": "Bearer wrong"}, {"Authorization": f"Basic {TOKEN}"}])
    async def test_should_answer_401_when_token_is_missing_or_wrong(self, server_url, headers):
        async with httpx.AsyncClient() as http:
            response = await http.post(f"{server_url}/mcp/excel", headers=headers, json={})

        assert response.status_code == 401
        assert response.headers["www-authenticate"] == "Bearer"

    async def test_should_not_reach_a_source_when_token_is_wrong(self, server_url):
        with pytest.raises(Exception):
            async with open_http(f"{server_url}/mcp/excel", token="wrong") as client:
                await client.list_tools()


class TestRateLimit:
    async def test_should_answer_429_when_a_client_exceeds_the_limit(self, server_url):
        async with httpx.AsyncClient() as http:
            statuses = [
                (await http.post(f"{server_url}/mcp/excel", json={})).status_code for _ in range(RATE_LIMIT + 1)
            ]

        assert statuses[:RATE_LIMIT] == [401] * RATE_LIMIT
        assert statuses[RATE_LIMIT] == 429

    async def test_should_not_count_health_when_limiting(self, server_url):
        async with httpx.AsyncClient() as http:
            statuses = {(await http.get(f"{server_url}/health")).status_code for _ in range(RATE_LIMIT + 5)}

        assert statuses == {200}


class TestTools:
    @pytest.mark.parametrize("source", SOURCE_NAMES)
    async def test_should_list_fetch_records_and_health_check_when_connecting(self, server_url, source):
        async with open_http(f"{server_url}/mcp/{source}") as client:
            listing = await client.list_tools()

        assert sorted(tool.name for tool in listing.tools) == ["fetch_records", "health_check"]

    @pytest.mark.parametrize("source", SOURCE_NAMES)
    async def test_should_report_ok_when_checking_health_over_http(self, server_url, source):
        async with open_http(f"{server_url}/mcp/{source}") as client:
            result = await client.call_tool("health_check", {})

        assert not result.is_error
        assert result.structured_content["status"] == "ok"
        assert result.structured_content["source"] == source

    @pytest.mark.parametrize("source", SOURCE_NAMES)
    async def test_should_return_records_of_the_source_when_fetching_over_http(self, server_url, source):
        async with open_http(f"{server_url}/mcp/{source}") as client:
            result = await client.call_tool("fetch_records", {"limit": 3})

        assert not result.is_error
        content = result.structured_content
        assert content["source"] == source
        assert 1 <= content["count"] <= 3
        assert all(record["source"] == source for record in content["records"])


class TestClientResolution:
    @staticmethod
    def _scope(peer: str, forwarded: Optional[str] = None) -> dict:
        headers = [] if forwarded is None else [(b"x-forwarded-for", forwarded.encode())]
        return {"client": (peer, 5000), "headers": headers}

    def test_should_ignore_forwarded_header_when_peer_is_not_trusted(self):
        settings = load_http_settings(_http_env({"TRUSTED_PROXIES": "10.0.0.0/24"}))

        client = resolve_client(self._scope("203.0.113.9", "198.51.100.7"), settings.trusted_proxies)

        assert client == "203.0.113.9"

    def test_should_read_the_client_from_the_right_when_peer_is_a_trusted_proxy(self):
        settings = load_http_settings(_http_env({"TRUSTED_PROXIES": "10.0.0.0/24,172.18.0.1/32"}))

        client = resolve_client(self._scope("172.18.0.1", "198.51.100.1, 198.51.100.7, 10.0.0.5"), settings.trusted_proxies)

        assert client == "198.51.100.7"

    def test_should_key_an_ipv6_client_by_its_64_prefix(self):
        settings = load_http_settings(_http_env())

        client = resolve_client(self._scope("2001:db8:1:2:aaaa:bbbb:cccc:dddd"), settings.trusted_proxies)

        assert client == "2001:db8:1:2::/64"


class TestLimiter:
    def test_should_allow_requests_again_when_the_window_has_elapsed(self):
        limiter = FixedWindowLimiter(limit=2, window_seconds=10)

        results = [limiter.hit("a", now=0), limiter.hit("a", now=1), limiter.hit("a", now=2), limiter.hit("a", now=11)]

        assert results[:2] == [None, None]
        assert results[2] is not None
        assert results[3] is None


KIRO_REMOTE_CONFIG = Path(__file__).resolve().parents[2] / ".kiro" / "settings" / "mcp.json"


def _kiro_remote_servers() -> Dict[str, Dict[str, object]]:
    return json.loads(KIRO_REMOTE_CONFIG.read_text(encoding="utf-8"))["mcpServers"]


@pytest.mark.skipif(
    not KIRO_REMOTE_CONFIG.is_file(), reason="repository root not available (Docker test image holds backend/ only)"
)
class TestKiroRemoteConfiguration:
    """The committed workspace config points to the hosted servers and carries no secret."""

    def test_should_register_one_server_per_source_when_reading_the_workspace_config(self):
        assert sorted(_kiro_remote_servers()) == [f"chimeraflow-{name}" for name in SOURCE_NAMES]

    @pytest.mark.parametrize("source", SOURCE_NAMES)
    def test_should_target_the_endpoint_of_the_source_over_https_when_reading_its_entry(self, source):
        url = _kiro_remote_servers()[f"chimeraflow-{source}"]["url"]

        assert url == f"https://chimeraflow-mcp.linguasolution.com/mcp/{source}"

    @pytest.mark.parametrize("source", SOURCE_NAMES)
    def test_should_reference_the_token_by_variable_when_reading_its_entry(self, source):
        headers = _kiro_remote_servers()[f"chimeraflow-{source}"]["headers"]

        assert headers == {"Authorization": "Bearer ${CHIMERAFLOW_MCP_TOKEN}"}

    @pytest.mark.parametrize("source", SOURCE_NAMES)
    def test_should_auto_approve_read_only_tools_only_when_reading_its_entry(self, source):
        approved = _kiro_remote_servers()[f"chimeraflow-{source}"]["autoApprove"]

        assert sorted(approved) == ["fetch_records", "health_check"]


class TestHttpSettings:
    @pytest.mark.parametrize(
        "missing", ["MCP_HTTP_TOKEN", "MCP_RATE_LIMIT_PER_IP", "RATE_LIMIT_WINDOW_SECONDS", "DATA_DIR", "ACCESS_READER"]
    )
    def test_should_refuse_to_start_when_a_required_variable_is_missing(self, missing):
        with pytest.raises(ValueError, match=missing):
            load_http_settings(_http_env({missing: None}))

    def test_should_refuse_a_short_token(self):
        with pytest.raises(ValueError, match="MCP_HTTP_TOKEN"):
            load_http_settings(_http_env({"MCP_HTTP_TOKEN": "short"}))

    def test_should_refuse_an_invalid_rate_limit(self):
        with pytest.raises(ValueError, match="MCP_RATE_LIMIT_PER_IP"):
            load_http_settings(_http_env({"MCP_RATE_LIMIT_PER_IP": "0"}))

    def test_should_not_echo_the_token_when_it_is_refused(self):
        with pytest.raises(ValueError) as error:
            load_http_settings(_http_env({"MCP_HTTP_TOKEN": "short-secret"}))

        assert "short-secret" not in str(error.value)
