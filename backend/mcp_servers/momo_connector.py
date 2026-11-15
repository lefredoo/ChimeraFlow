"""
Mobile Money Connector - MCP Server
Reads Mobile Money transaction CSV files
"""
from typing import List, Optional
from pathlib import Path
from datetime import datetime
import csv

from .base import BaseConnector, UnifiedRecord


class MobileMoneyConnector(BaseConnector):
    """
    Mobile Money CSV connector (R7 from connectors-spec.md)
    Expected fields: transaction_id, timestamp, phone, customer_name, operator,
    amount, currency, status, reference, quantity

    The payload keeps the original column names so rules can reference source
    fields directly. Each record carries a `payment` entity (amount) and a
    `product` entity (the `reference` column) so rules can trigger on products.
    """

    def __init__(self, file_path: str):
        super().__init__("momo")
        self.file_path = Path(file_path)
        self.parse_errors = 0

    async def fetch_records(self, limit: int = 100) -> List[UnifiedRecord]:
        """Fetch Mobile Money transactions from CSV

        Rows with a missing transaction_id, an invalid timestamp or an invalid
        amount are skipped and counted as parse errors (no invented values).
        """
        records: List[UnifiedRecord] = []
        limit = min(limit, 1000)
        self.parse_errors = 0  # counts the errors of this fetch only

        try:
            with open(self.file_path, 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f)

                for idx, row in enumerate(reader, 1):
                    if len(records) >= limit:
                        break

                    transaction_id = (row.get("transaction_id") or "").strip()
                    if not transaction_id:
                        self.parse_errors += 1
                        continue

                    try:
                        timestamp_iso = datetime.fromisoformat((row.get("timestamp") or "").strip()).isoformat()
                    except ValueError:
                        self.logger.warning(f"Mobile Money row {idx}: invalid timestamp, skipped")
                        self.parse_errors += 1
                        continue

                    try:
                        amount = float((row.get("amount") or "").strip())
                    except ValueError:
                        self.logger.warning(f"Mobile Money row {idx}: invalid amount, skipped")
                        self.parse_errors += 1
                        continue

                    reference = (row.get("reference") or "").strip()
                    entities = [{
                        "type": "payment",
                        "raw": f"{(row.get('amount') or '').strip()} {(row.get('currency') or '').strip()}".strip(),
                        "norm": f"{amount}"
                    }]
                    if reference:
                        entities.append({
                            "type": "product",
                            "raw": reference,
                            "norm": self.normalize_text(reference)
                        })

                    records.append(UnifiedRecord(
                        id=f"momo-{transaction_id}",
                        source="momo",
                        source_ref=f"{self.file_path.name}#row{idx}",
                        timestamp=timestamp_iso,
                        lang="fr",
                        entities=entities,
                        payload={
                            "transaction_id": transaction_id,
                            "timestamp": timestamp_iso,
                            "phone": (row.get("phone") or "").strip(),
                            "customer_name": (row.get("customer_name") or "").strip(),
                            "operator": (row.get("operator") or "").strip(),
                            "amount": amount,
                            "currency": (row.get("currency") or "").strip(),
                            "status": (row.get("status") or "").strip(),
                            "reference": reference,
                            "quantity": self._parse_quantity(row.get("quantity"))
                        }
                    ))

        except (OSError, csv.Error, UnicodeDecodeError) as e:
            self.logger.error(f"Failed to read Mobile Money CSV: {e}")
            raise

        self.logger.info(f"Fetched {len(records)} Mobile Money records, {self.parse_errors} errors")
        return records

    @staticmethod
    def _parse_quantity(value: Optional[str]) -> Optional[int]:
        """Parse the optional quantity column (None when empty or invalid)."""
        try:
            return int((value or "").strip())
        except ValueError:
            return None

    async def _perform_health_check(self):
        """Check if CSV file exists and is readable"""
        if not self.file_path.exists():
            return {
                "status": "error",
                "source": self.source_name,
                "message": f"File not found: {self.file_path}",
                "last_fetch": None
            }

        try:
            # Try reading first row
            with open(self.file_path, 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                first_row = next(reader, None)

            if first_row:
                return {
                    "status": "ok",
                    "source": self.source_name,
                    "message": f"CSV readable, {len(first_row)} columns",
                    "last_fetch": datetime.now().isoformat()
                }
            return {
                "status": "degraded",
                "source": self.source_name,
                "message": "CSV is empty",
                "last_fetch": None
            }

        except (OSError, csv.Error, UnicodeDecodeError) as e:
            return {
                "status": "error",
                "source": self.source_name,
                "message": str(e),
                "last_fetch": None
            }
