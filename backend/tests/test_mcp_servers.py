"""
MCP servers: each data source is served by a stdio server (`python mcp_main.py --source <name>`).

Most tests drive the server in-process with the SDK client (fast, same protocol
code). TestStdioLaunch starts the real launcher as a subprocess, the way Kiro
does: every process is stopped when its `async with` block ends.
"""
import asyncio
import json
import os
import subprocess
import sys
from contextlib import asynccontextmanager
from pathlib import Path
import time
from typing import Any, AsyncIterator, Dict, List, Optional

import pytest
from mcp import Client, StdioServerParameters

from mcp_servers import mcp_app
from mcp_servers.base import BaseConnector, UnifiedRecord
from mcp_servers.mcp_app import create_server
from mcp_servers.mcp_settings import SOURCES, load_settings

BACKEND_DIR = Path(__file__).resolve().parent.parent
SOURCE_NAMES = sorted(SOURCES)
# Cold start of a server process imports pandas, openpyxl and the MCP SDK
PROCESS_TIMEOUT_SECONDS = 120
RECORD_KEYS = {"id", "source", "source_ref", "timestamp", "lang", "entities", "payload"}


def _server_env(overrides: Optional[Dict[str, Optional[str]]] = None) -> Dict[str, str]:
    """Environment a Kiro entry gives to a server: the data settings only, no API settings.

    A None value removes the variable.
    """
    env = {"DATA_DIR": os.environ["DATA_DIR"], "ACCESS_READER": os.environ["ACCESS_READER"]}
    for name, value in (overrides or {}).items():
        if value is None:
            env.pop(name)
        else:
            env[name] = value
    return env


def _system_env() -> Dict[str, str]:
    """Variables a Python process needs to start (the API settings stay out)."""
    return {name: os.environ[name] for name in ("PATH", "SYSTEMROOT") if name in os.environ}


def _launcher_args(source: str) -> List[str]:
    return ["mcp_main.py", "--source", source]


class ScriptedConnector(BaseConnector):
    """Stand-in for a source that fails a given number of times, or answers slowly."""

    def __init__(self, failures: int = 0, delay_seconds: float = 0.0):
        super().__init__("momo")
        self.failures = failures
        self.delay_seconds = delay_seconds
        self.calls = 0
        self.parse_errors = 0

    async def fetch_records(self, limit: int = 100) -> List[UnifiedRecord]:
        self.calls += 1
        time.sleep(self.delay_seconds)
        if self.calls <= self.failures:
            raise OSError("scripted failure")
        return []

    async def _perform_health_check(self) -> Dict[str, Any]:
        return {"status": "ok", "source": "momo", "message": None, "last_fetch": None}


@asynccontextmanager
async def open_in_process(
    source: str, data_dir: Optional[Path] = None, connector: Optional[BaseConnector] = None
) -> AsyncIterator[Client]:
    """Connect a client to the server of a source running in this process (legacy handshake, as Kiro)."""
    overrides: Dict[str, Optional[str]] = {} if data_dir is None else {"DATA_DIR": str(data_dir)}
    server = create_server(load_settings(source, _server_env(overrides)), connector)
    async with Client(server, mode="legacy") as client:
        yield client


@asynccontextmanager
async def open_stdio(source: str) -> AsyncIterator[Client]:
    """Launch the server of a source as a subprocess and connect to it over stdio."""
    params = StdioServerParameters(
        command=sys.executable,
        args=_launcher_args(source),
        cwd=BACKEND_DIR,
        env=_server_env(),
    )
    async with asyncio.timeout(PROCESS_TIMEOUT_SECONDS):
        async with Client(params, mode="legacy") as client:
            yield client


def _run_launcher(source: str, overrides: Dict[str, Optional[str]]) -> subprocess.CompletedProcess:
    """Run the launcher to completion (configuration errors exit before serving)."""
    return subprocess.run(
        [sys.executable, *_launcher_args(source)],
        cwd=BACKEND_DIR,
        env={**_server_env(overrides), **_system_env()},
        capture_output=True,
        text=True,
        stdin=subprocess.DEVNULL,
        timeout=PROCESS_TIMEOUT_SECONDS,
    )


class TestServerTools:
    @pytest.mark.parametrize("source", SOURCE_NAMES)
    async def test_should_list_fetch_records_and_health_check_when_connecting(self, source):
        async with open_in_process(source) as client:
            listing = await client.list_tools()

        assert sorted(tool.name for tool in listing.tools) == ["fetch_records", "health_check"]

    @pytest.mark.parametrize("source", SOURCE_NAMES)
    async def test_should_declare_tools_read_only_when_listing(self, source):
        async with open_in_process(source) as client:
            listing = await client.list_tools()

        assert [tool.annotations.read_only_hint for tool in listing.tools] == [True, True]

    @pytest.mark.parametrize("source", SOURCE_NAMES)
    async def test_should_return_unified_records_when_fetching(self, source):
        async with open_in_process(source) as client:
            result = await client.call_tool("fetch_records", {"limit": 5})

        assert result.is_error is False
        assert result.structured_content["source"] == source
        assert result.structured_content["count"] == len(result.structured_content["records"])
        assert result.structured_content["count"] > 0
        assert set(result.structured_content["records"][0]) == RECORD_KEYS
        assert result.structured_content["records"][0]["source"] == source

    @pytest.mark.parametrize("source", SOURCE_NAMES)
    async def test_should_return_at_most_limit_records_when_limit_is_given(self, source):
        async with open_in_process(source) as client:
            result = await client.call_tool("fetch_records", {"limit": 3})

        assert result.structured_content["count"] == 3

    @pytest.mark.parametrize("source", SOURCE_NAMES)
    async def test_should_use_default_limit_when_limit_is_omitted(self, source):
        async with open_in_process(source) as client:
            result = await client.call_tool("fetch_records", {})

        assert 0 < result.structured_content["count"] <= 100

    @pytest.mark.parametrize("source", SOURCE_NAMES)
    async def test_should_report_ok_when_checking_health(self, source):
        async with open_in_process(source) as client:
            result = await client.call_tool("health_check", {})

        assert result.is_error is False
        assert (result.structured_content["status"], result.structured_content["source"]) == ("ok", source)

    @pytest.mark.parametrize("limit", [0, -1, 1001])
    async def test_should_reject_limit_when_it_is_out_of_range(self, limit):
        async with open_in_process("momo") as client:
            result = await client.call_tool("fetch_records", {"limit": limit})

        assert result.is_error is True

    async def test_should_reject_limit_when_it_is_not_an_integer(self):
        async with open_in_process("momo") as client:
            result = await client.call_tool("fetch_records", {"limit": "many"})

        assert result.is_error is True

    async def test_should_accept_limit_when_it_is_the_maximum(self):
        async with open_in_process("momo") as client:
            result = await client.call_tool("fetch_records", {"limit": 1000})

        assert result.is_error is False

    async def test_should_serve_concurrent_calls_when_a_client_sends_several_at_once(self):
        async with open_in_process("excel") as client:
            results = await asyncio.gather(
                client.call_tool("fetch_records", {"limit": 2}),
                client.call_tool("health_check", {}),
                client.call_tool("fetch_records", {"limit": 3}),
            )

        assert [result.is_error for result in results] == [False, False, False]


class TestServerResilience:
    async def test_should_retry_once_when_the_first_read_fails(self):
        connector = ScriptedConnector(failures=1)

        async with open_in_process("momo", connector=connector) as client:
            result = await client.call_tool("fetch_records", {"limit": 5})

        assert (result.is_error, connector.calls) == (False, 2)

    async def test_should_stop_after_two_attempts_when_every_read_fails(self):
        connector = ScriptedConnector(failures=10)

        async with open_in_process("momo", connector=connector) as client:
            result = await client.call_tool("fetch_records", {"limit": 5})

        assert (result.is_error, connector.calls) == (True, 2)

    async def test_should_return_tool_error_without_retry_when_the_read_times_out(self, monkeypatch):
        monkeypatch.setattr(mcp_app, "OPERATION_TIMEOUT_SECONDS", 0.2)
        connector = ScriptedConnector(delay_seconds=1.0)

        async with open_in_process("momo", connector=connector) as client:
            result = await client.call_tool("fetch_records", {"limit": 5})

        assert (result.is_error, connector.calls, "did not answer" in result.content[0].text) == (True, 1, True)


class TestServerMetadata:
    @pytest.mark.parametrize("source", SOURCE_NAMES)
    async def test_should_describe_source_when_reading_metadata_resource(self, source):
        async with open_in_process(source) as client:
            resources = await client.list_resources()
            content = await client.read_resource(resources.resources[0].uri)

        metadata = json.loads(content.contents[0].text)
        assert (metadata["source"], metadata["file"], metadata["read_only"]) == (
            source,
            SOURCES[source].file_name,
            True,
        )

    async def test_should_name_server_after_source_when_initializing(self):
        async with open_in_process("excel") as client:
            name = client.server_info.name

        assert name == "chimeraflow-excel"


class TestServerWithMissingFile:
    async def test_should_report_error_status_when_source_file_is_missing(self, tmp_path):
        async with open_in_process("momo", tmp_path) as client:
            result = await client.call_tool("health_check", {})

        assert (result.is_error, result.structured_content["status"]) == (False, "error")

    async def test_should_return_tool_error_when_fetching_a_missing_file(self, tmp_path):
        async with open_in_process("momo", tmp_path) as client:
            result = await client.call_tool("fetch_records", {"limit": 5})

        assert result.is_error is True

    async def test_should_not_leak_file_path_when_fetching_a_missing_file(self, tmp_path):
        async with open_in_process("momo", tmp_path) as client:
            result = await client.call_tool("fetch_records", {"limit": 5})

        assert str(tmp_path) not in result.content[0].text


class TestServerConfiguration:
    def test_should_fail_fast_when_data_dir_is_missing(self):
        result = _run_launcher("excel", {"DATA_DIR": None})

        assert (result.returncode, "DATA_DIR" in result.stderr, result.stdout) == (2, True, "")

    def test_should_fail_fast_when_access_reader_is_missing(self):
        result = _run_launcher("access", {"ACCESS_READER": None})

        assert (result.returncode, "ACCESS_READER" in result.stderr, result.stdout) == (2, True, "")

    def test_should_fail_fast_when_data_dir_is_not_a_directory(self, tmp_path):
        with pytest.raises(ValueError, match="DATA_DIR"):
            load_settings("excel", {"DATA_DIR": str(tmp_path / "absent")})

    def test_should_fail_fast_when_access_reader_is_unsupported(self, tmp_path):
        with pytest.raises(ValueError, match="must be one of"):
            load_settings("access", {"DATA_DIR": str(tmp_path), "ACCESS_READER": "jackcess"})

    def test_should_not_require_access_reader_when_source_is_not_access(self, tmp_path):
        settings = load_settings("excel", {"DATA_DIR": str(tmp_path)})

        assert settings.access_reader is None

    def test_should_reject_source_when_it_is_unknown(self):
        with pytest.raises(ValueError, match="Unknown source"):
            load_settings("sap", {"DATA_DIR": "."})


class TestStdioLaunch:
    @pytest.mark.parametrize("source", SOURCE_NAMES)
    async def test_should_serve_records_when_launching_the_server_over_stdio(self, source):
        async with open_stdio(source) as client:
            result = await client.call_tool("fetch_records", {"limit": 2})

        assert (result.is_error, result.structured_content["source"], result.structured_content["count"]) == (
            False,
            source,
            2,
        )


KIRO_CONFIG_PATH = BACKEND_DIR / "mcp_servers" / "kiro-mcp.json"


def _kiro_servers() -> Dict[str, Dict[str, object]]:
    return json.loads(KIRO_CONFIG_PATH.read_text(encoding="utf-8"))["mcpServers"]


class TestKiroConfiguration:
    """Local stdio entries (optional alternative to the hosted servers) must match what the launcher serves."""

    def test_should_register_one_server_per_source_when_reading_kiro_config(self):
        assert sorted(_kiro_servers()) == [f"chimeraflow-{name}" for name in SOURCE_NAMES]

    @pytest.mark.parametrize("source", SOURCE_NAMES)
    def test_should_launch_the_source_when_reading_its_entry(self, source):
        args = _kiro_servers()[f"chimeraflow-{source}"]["args"]

        assert (Path(args[0]).name, args[1:]) == ("mcp_main.py", ["--source", source])

    @pytest.mark.parametrize("source", SOURCE_NAMES)
    def test_should_point_to_an_existing_launcher_when_reading_its_entry(self, source):
        args = _kiro_servers()[f"chimeraflow-{source}"]["args"]

        assert (BACKEND_DIR / Path(args[0]).name).is_file()

    @pytest.mark.parametrize("source", SOURCE_NAMES)
    def test_should_pass_only_data_settings_when_reading_its_entry(self, source):
        env = _kiro_servers()[f"chimeraflow-{source}"]["env"]

        assert sorted(env) == ["ACCESS_READER", "DATA_DIR"]

    @pytest.mark.parametrize("source", SOURCE_NAMES)
    def test_should_auto_approve_read_only_tools_only_when_reading_its_entry(self, source):
        approved = _kiro_servers()[f"chimeraflow-{source}"]["autoApprove"]

        assert sorted(approved) == ["fetch_records", "health_check"]
