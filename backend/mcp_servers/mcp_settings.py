"""
Settings of the standalone MCP servers (one process per data source).

Deliberately independent from `config.py`: importing it requires every API
setting (database, Redis, auth secrets), which a stdio server launched by Kiro
must not need. Same rule as AGENTS.md §7: a required variable that is missing
stops the process, there is no fallback.
"""
import os
from dataclasses import dataclass
from ipaddress import IPv4Network, IPv6Network, ip_network
from pathlib import Path
from typing import Mapping, Optional, Tuple, Union

from .access_connector import ACCESS_READERS

IPNetwork = Union[IPv4Network, IPv6Network]


@dataclass(frozen=True)
class SourceSpec:
    """Static description of one data source served over MCP."""

    name: str
    file_name: str
    file_format: str
    description: str


SOURCES = {
    spec.name: spec
    for spec in (
        SourceSpec("excel", "tarifs_fournisseurs.xlsx", "xlsx", "Supplier price list (sheet Tarifs)"),
        SourceSpec("access", "STOCK_ZOBO.mdb", "mdb", "Legacy stock database (table Articles)"),
        SourceSpec("whatsapp", "commandes_clients.txt", "txt", "Customer orders exported from WhatsApp"),
        SourceSpec("momo", "momo_transactions.csv", "csv", "Mobile Money payment confirmations"),
    )
}


@dataclass(frozen=True)
class McpSettings:
    """Validated settings of one MCP server process."""

    source: SourceSpec
    data_dir: Path
    access_reader: Optional[str]
    log_level: Optional[str]

    @property
    def file_path(self) -> Path:
        """Path of the data file of the source (read-only)."""
        return self.data_dir / self.source.file_name


def _require_env(environ: Mapping[str, str], name: str, description: str) -> str:
    """Read a required variable.

    Raises:
        ValueError: If the variable is missing or empty.
    """
    value = environ.get(name)
    if value is None or value.strip() == "":
        raise ValueError(
            f"Required environment variable '{name}' is not set.\n"
            f"Purpose: {description}"
        )
    return value


@dataclass(frozen=True)
class McpHttpSettings:
    """Validated settings of the hosted MCP service (all sources behind one HTTP port)."""

    token: str
    rate_limit_per_ip: int
    rate_limit_window_seconds: int
    trusted_proxies: Tuple[IPNetwork, ...]
    sources: Tuple[McpSettings, ...]
    log_level: Optional[str]


# A shorter bearer token is guessable; `openssl rand -hex 24` gives 48 characters
MIN_TOKEN_LENGTH = 32


def _require_positive_int(environ: Mapping[str, str], name: str, description: str) -> int:
    """Read a required integer >= 1.

    Raises:
        ValueError: If the variable is missing, empty or not an integer >= 1.
    """
    raw = _require_env(environ, name, description)
    try:
        value = int(raw)
    except ValueError:
        value = 0
    if value < 1:
        raise ValueError(f"Environment variable '{name}' must be an integer >= 1")
    return value


def _parse_trusted_proxies(raw: Optional[str]) -> Tuple[IPNetwork, ...]:
    """Parse TRUSTED_PROXIES (comma-separated IPs or CIDR networks; empty when unset).

    Raises:
        ValueError: If an entry is not an IP address or network (the entry is not echoed).
    """
    if raw is None or raw.strip() == "":
        return ()
    try:
        return tuple(ip_network(item.strip(), strict=False) for item in raw.split(",") if item.strip())
    except ValueError as exc:
        raise ValueError("Environment variable 'TRUSTED_PROXIES' must list IP addresses or CIDR networks") from exc


def load_http_settings(environ: Mapping[str, str] = os.environ) -> McpHttpSettings:
    """Build the settings of the hosted MCP service.

    Args:
        environ: Environment to read (the process environment by default).

    Returns:
        Validated settings, with the settings of the four sources.

    Raises:
        ValueError: If a required variable is missing or invalid (MCP_HTTP_TOKEN,
            MCP_RATE_LIMIT_PER_IP, RATE_LIMIT_WINDOW_SECONDS, DATA_DIR, ACCESS_READER).
    """
    token = _require_env(environ, "MCP_HTTP_TOKEN", "Bearer token that protects the hosted MCP endpoints")
    if len(token) < MIN_TOKEN_LENGTH:
        raise ValueError(f"Environment variable 'MCP_HTTP_TOKEN' must hold at least {MIN_TOKEN_LENGTH} characters")
    return McpHttpSettings(
        token=token,
        rate_limit_per_ip=_require_positive_int(
            environ, "MCP_RATE_LIMIT_PER_IP", "MCP requests allowed per client IP per window"
        ),
        rate_limit_window_seconds=_require_positive_int(
            environ, "RATE_LIMIT_WINDOW_SECONDS", "Length of the rate limit window in seconds"
        ),
        trusted_proxies=_parse_trusted_proxies(environ.get("TRUSTED_PROXIES")),
        sources=tuple(load_settings(name, environ) for name in SOURCES),
        log_level=environ.get("BACKEND_LOG_LEVEL") or None,
    )


def load_settings(source: str, environ: Mapping[str, str] = os.environ) -> McpSettings:
    """Build the settings of the server for one source.

    Args:
        source: Source name, one of SOURCES.
        environ: Environment to read (the process environment by default).

    Returns:
        Validated settings.

    Raises:
        ValueError: If the source is unknown, DATA_DIR is missing or is not a
            directory, or (access only) ACCESS_READER is missing or unsupported.
    """
    if source not in SOURCES:
        raise ValueError(f"Unknown source '{source}', expected one of: {', '.join(SOURCES)}")

    data_dir = Path(_require_env(environ, "DATA_DIR", "Directory containing the synthetic data source files"))
    if not data_dir.is_dir():
        raise ValueError("Environment variable 'DATA_DIR' must point to an existing directory")

    access_reader: Optional[str] = None
    if source == "access":
        access_reader = _require_env(
            environ, "ACCESS_READER", f"Reader for .mdb files, one of: {', '.join(ACCESS_READERS)}"
        )
        if access_reader not in ACCESS_READERS:
            raise ValueError(
                f"Environment variable 'ACCESS_READER' must be one of "
                f"{', '.join(ACCESS_READERS)}, got '{access_reader}'"
            )

    return McpSettings(
        source=SOURCES[source],
        data_dir=data_dir,
        access_reader=access_reader,
        log_level=environ.get("BACKEND_LOG_LEVEL") or None,
    )
