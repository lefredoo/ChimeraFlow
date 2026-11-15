"""
Settings of the standalone MCP servers (one process per data source).

Deliberately independent from `config.py`: importing it requires every API
setting (database, Redis, auth secrets), which a stdio server launched by Kiro
must not need. Same rule as AGENTS.md §7: a required variable that is missing
stops the process, there is no fallback.
"""
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Mapping, Optional

from .access_connector import ACCESS_READERS


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
