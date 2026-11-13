"""
Access Connector - MCP Server
Reads .mdb (Microsoft Access) databases using mdbtools
"""
from typing import List, Optional
from pathlib import Path
from datetime import datetime
import subprocess
import csv
from io import StringIO

from .base import BaseConnector, UnifiedRecord

# mdb-export default date format first, then ISO 8601
_DATE_FORMATS = ("%m/%d/%y %H:%M:%S", "%m/%d/%Y %H:%M:%S", "%Y-%m-%d %H:%M:%S", "%Y-%m-%d")


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


class AccessConnector(BaseConnector):
    """
    Access database connector (R5 from connectors-spec.md)
    Uses mdbtools CLI (mdb-export) to read .mdb files

    The payload keeps the original column names (id, designation, unite,
    qty_stock, prix_achat, date_modif) so rules can reference source fields.
    """

    def __init__(self, file_path: str, table_name: str = "Articles"):
        super().__init__("access")
        self.file_path = Path(file_path)
        self.table_name = table_name
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

        try:
            # Use mdb-export to dump table as CSV
            result = subprocess.run(
                ["mdb-export", str(self.file_path), self.table_name],
                capture_output=True,
                text=True,
                timeout=5  # 5s timeout from connectors.md
            )
        except subprocess.TimeoutExpired:
            self.logger.error("mdb-export timeout (5s)")
            raise
        except OSError as e:
            self.logger.error(f"Failed to run mdb-export: {e}")
            raise

        if result.returncode != 0:
            self.logger.error(f"mdb-export failed: {result.stderr}")
            raise RuntimeError(f"Failed to read Access table: {result.stderr}")

        reader = csv.DictReader(StringIO(result.stdout))

        for idx, row in enumerate(reader):
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
        """Check if .mdb file exists and mdbtools is available"""
        if not self.file_path.exists():
            return {
                "status": "error",
                "source": self.source_name,
                "message": f"File not found: {self.file_path}",
                "last_fetch": None
            }

        try:
            # Check if mdbtools is available
            result = subprocess.run(
                ["mdb-tables", str(self.file_path)],
                capture_output=True,
                text=True,
                timeout=3
            )
        except (OSError, subprocess.SubprocessError) as e:
            return {
                "status": "error",
                "source": self.source_name,
                "message": str(e),
                "last_fetch": None
            }

        if result.returncode != 0:
            return {
                "status": "error",
                "source": self.source_name,
                "message": "mdbtools not available or file unreadable",
                "last_fetch": None
            }

        tables = result.stdout.strip().split()
        return {
            "status": "ok",
            "source": self.source_name,
            "message": f"Database readable, {len(tables)} tables found",
            "last_fetch": datetime.now().isoformat(),
            "tables": tables
        }
