"""
Access Connector - MCP Server
Reads .mdb (Microsoft Access) databases with one of two readers, chosen
explicitly by the ACCESS_READER setting (no silent fallback, AGENTS.md §7):

- mdbtools: CLI (mdb-export), used in Docker and production
- access-parser: pure Python, used for local development on Windows
"""
from typing import Callable, Dict, List, Optional
from pathlib import Path
from datetime import datetime
from decimal import Decimal
import math
import subprocess
import csv
from io import StringIO

from .base import BaseConnector, UnifiedRecord

# mdb-export default date format first, then ISO 8601
_DATE_FORMATS = ("%m/%d/%y %H:%M:%S", "%m/%d/%Y %H:%M:%S", "%Y-%m-%d %H:%M:%S", "%Y-%m-%d")

# Jet/Access column type code of Currency; access-parser returns it as an
# integer scaled by 10,000 whereas mdb-export prints the decimal value
_JET_CURRENCY_TYPE = 5
_CURRENCY_SCALE = Decimal(10000)

# One table row, every value as the text mdb-export would print
Row = Dict[str, str]


def _parse_access_date(value: str) -> Optional[datetime]:
    """Parse a date exported by mdb-export.

    Args:
        value: Raw date string from the CSV export.

    Returns:
        Parsed datetime, or None if no known format matches.
    """
    value = value.strip()
    for fmt in _DATE_FORMATS:
        try:
            return datetime.strptime(value, fmt)
        except ValueError:
            continue
    return None


def _read_rows_mdbtools(file_path: Path, table_name: str) -> List[Row]:
    """Read a table with the mdb-export CLI.

    Args:
        file_path: Path of the .mdb file.
        table_name: Table to export.

    Returns:
        Table rows, values as exported text.

    Raises:
        subprocess.TimeoutExpired: If the export exceeds 5 seconds.
        OSError: If mdb-export cannot be run.
        RuntimeError: If mdb-export exits with an error.
    """
    result = subprocess.run(
        ["mdb-export", str(file_path), table_name],
        capture_output=True,
        text=True,
        timeout=5  # 5s timeout from connectors.md
    )
    if result.returncode != 0:
        raise RuntimeError(f"Failed to read Access table: {result.stderr}")
    return list(csv.DictReader(StringIO(result.stdout)))


def _cell_to_text(value: object, is_currency: bool) -> str:
    """Render an access-parser cell like mdb-export would print it.

    Args:
        value: Cell value returned by access-parser.
        is_currency: Whether the column is of Currency type.

    Returns:
        Text for the cell, empty for NULL.
    """
    if value is None:
        return ""
    if is_currency and isinstance(value, int):
        return f"{Decimal(value) / _CURRENCY_SCALE:.4f}"
    if isinstance(value, datetime):
        return value.strftime("%Y-%m-%d %H:%M:%S")
    return str(value)


def _read_rows_access_parser(file_path: Path, table_name: str) -> List[Row]:
    """Read a table with the pure Python access-parser library.

    Args:
        file_path: Path of the .mdb file.
        table_name: Table to read.

    Returns:
        Table rows, values as the text mdb-export would print.

    Raises:
        OSError: If the file cannot be opened.
        RuntimeError: If the file or the table cannot be parsed.
    """
    # Imported here: the library is only needed when this reader is selected
    from access_parser import AccessParser

    try:
        database = AccessParser(str(file_path))
        table = database.get_table(table_name)
        columns = table.parse()
        currency_columns = {
            column.col_name_str
            for column in table.columns.values()
            if column.type == _JET_CURRENCY_TYPE
        }
    except OSError:
        raise
    except Exception as exc:  # third-party parser: any failure means an unreadable table
        raise RuntimeError(f"Failed to read Access table: {exc}") from exc

    row_count = max((len(values) for values in columns.values()), default=0)
    return [
        {
            name: _cell_to_text(values[index], name in currency_columns)
            for name, values in columns.items()
        }
        for index in range(row_count)
    ]


def _list_tables_mdbtools(file_path: Path) -> List[str]:
    """List user tables with mdb-tables.

    Raises:
        OSError: If mdb-tables cannot be run.
        subprocess.SubprocessError: If mdb-tables hangs.
        RuntimeError: If mdbtools is unavailable or the file unreadable.
    """
    result = subprocess.run(
        ["mdb-tables", str(file_path)],
        capture_output=True,
        text=True,
        timeout=3
    )
    if result.returncode != 0:
        raise RuntimeError("mdbtools not available or file unreadable")
    return result.stdout.strip().split()


def _list_tables_access_parser(file_path: Path) -> List[str]:
    """List user tables with access-parser (system tables excluded).

    Raises:
        RuntimeError: If the file cannot be parsed.
    """
    from access_parser import AccessParser

    try:
        catalog = AccessParser(str(file_path)).catalog
    except Exception as exc:  # third-party parser: any failure means an unreadable file
        raise RuntimeError(f"Access file unreadable: {exc}") from exc
    return [name for name in catalog if not name.startswith("MSys")]


_ROW_READERS: Dict[str, Callable[[Path, str], List[Row]]] = {
    "mdbtools": _read_rows_mdbtools,
    "access-parser": _read_rows_access_parser,
}
_TABLE_LISTERS: Dict[str, Callable[[Path], List[str]]] = {
    "mdbtools": _list_tables_mdbtools,
    "access-parser": _list_tables_access_parser,
}

# Supported readers (config.ACCESS_READERS lists the same two; config is not
# imported here so the standalone MCP servers do not need the API settings)
ACCESS_READERS = tuple(_ROW_READERS)


class AccessConnector(BaseConnector):
    """
    Access database connector (R5 from connectors-spec.md)
    Reads .mdb files with the reader selected by ACCESS_READER

    Both readers feed the same parsing code, so they produce identical
    records. The payload keeps the original column names (id, designation,
    unite, qty_stock, prix_achat, date_modif) so rules can reference source
    fields.
    """

    def __init__(self, file_path: str, table_name: str = "Articles", reader: Optional[str] = None):
        """
        Args:
            file_path: Path of the .mdb file.
            table_name: Table holding the articles.
            reader: "mdbtools" or "access-parser". Defaults to the ACCESS_READER setting.

        Raises:
            ValueError: If reader is not one of the supported readers.
        """
        super().__init__("access")
        self.file_path = Path(file_path)
        self.table_name = table_name
        if reader is None:
            # Imported here: config requires every API setting at import time
            from config import ACCESS_READER

            reader = ACCESS_READER
        self.reader = reader
        if self.reader not in ACCESS_READERS:
            raise ValueError(
                f"Unknown Access reader '{self.reader}', expected one of: {', '.join(ACCESS_READERS)}"
            )
        self.parse_errors = 0

    async def fetch_records(self, limit: int = 100) -> List[UnifiedRecord]:
        """
        Fetch records from Access database table
        Expected columns: id, designation, unite, qty_stock, prix_achat, date_modif

        Rows with an empty designation, a non-integer qty_stock or an
        unparseable date_modif are skipped and counted as parse errors.
        The record timestamp comes from date_modif (deterministic, P4).
        """
        records: List[UnifiedRecord] = []
        limit = min(limit, 1000)
        self.parse_errors = 0  # counts the errors of this fetch only

        try:
            rows = _ROW_READERS[self.reader](self.file_path, self.table_name)
        except subprocess.TimeoutExpired:
            self.logger.error("mdb-export timeout (5s)")
            raise
        except (OSError, RuntimeError) as e:
            self.logger.error(f"Failed to read Access table with {self.reader}: {e}")
            raise

        for idx, row in enumerate(rows):
            if len(records) >= limit:
                break

            article_id = (row.get("id") or "").strip()
            designation = (row.get("designation") or "").strip()
            unite = (row.get("unite") or "").strip()

            if not designation:
                self.parse_errors += 1
                continue

            try:
                qty_stock = int((row.get("qty_stock") or "").strip())
            except ValueError:
                self.logger.warning(f"Access row {idx}: invalid qty_stock, skipped")
                self.parse_errors += 1
                continue

            modified = _parse_access_date(row.get("date_modif") or "")
            if modified is None:
                self.logger.warning(f"Access row {idx}: missing or invalid date_modif, skipped")
                self.parse_errors += 1
                continue

            try:
                prix_achat: Optional[float] = float((row.get("prix_achat") or "").strip())
            except ValueError:
                prix_achat = None

            if prix_achat is not None and not math.isfinite(prix_achat):
                self.logger.warning(f"Access row {idx}: non-finite prix_achat, skipped")
                self.parse_errors += 1
                continue

            records.append(UnifiedRecord(
                id=f"access-{article_id or idx}",
                source="access",
                source_ref=f"{self.file_path.name}#{self.table_name}#{article_id}",
                timestamp=modified.isoformat(),
                lang="fr",
                entities=[{
                    "type": "product",
                    "raw": designation,
                    "norm": self.normalize_text(designation)
                }],
                payload={
                    "id": article_id,
                    "designation": designation,
                    "unite": unite,
                    "qty_stock": qty_stock,
                    "prix_achat": prix_achat,
                    "date_modif": modified.isoformat(),
                    "table": self.table_name
                }
            ))

        self.logger.info(f"Fetched {len(records)} Access records, {self.parse_errors} errors")
        return records

    async def _perform_health_check(self):
        """Check if the .mdb file exists and the selected reader can open it"""
        if not self.file_path.exists():
            return {
                "status": "error",
                "source": self.source_name,
                "message": f"File not found: {self.file_path}",
                "last_fetch": None
            }

        try:
            tables = _TABLE_LISTERS[self.reader](self.file_path)
        except (OSError, RuntimeError, subprocess.SubprocessError) as e:
            return {
                "status": "error",
                "source": self.source_name,
                "message": str(e),
                "last_fetch": None
            }

        return {
            "status": "ok",
            "source": self.source_name,
            "message": f"Database readable, {len(tables)} tables found",
            "last_fetch": datetime.now().isoformat(),
            "tables": tables
        }
