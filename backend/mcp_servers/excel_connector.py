"""
Excel Connector - MCP Server
Reads tarifs_fournisseurs.xlsx with intentional imperfections
"""
from typing import List
from pathlib import Path
from datetime import datetime
import pandas as pd

from .base import BaseConnector, UnifiedRecord


class ExcelConnector(BaseConnector):
    """
    Excel connector for supplier price lists
    Handles merged cells and imperfect formatting (R4 from connectors-spec.md)

    The payload keeps the original column names (Produit, Prix_Unitaire,
    Fournisseur, Date_MAJ) so rules can reference source fields directly.
    """

    def __init__(self, file_path: str):
        super().__init__("excel")
        self.file_path = Path(file_path)
        self.parse_errors = 0

    async def fetch_records(self, limit: int = 100) -> List[UnifiedRecord]:
        """
        Fetch records from Excel file

        Expected columns: Produit, Prix_Unitaire, Fournisseur, Date_MAJ.
        Rows without a product or a valid Date_MAJ are skipped and counted
        as parse errors (the record timestamp comes from Date_MAJ so that
        the same file always yields the same records, property P4).
        """
        records: List[UnifiedRecord] = []
        limit = min(limit, 1000)  # Max 1000

        try:
            # Read Excel with openpyxl engine (handles merged cells better)
            df = pd.read_excel(self.file_path, sheet_name="Tarifs", engine="openpyxl")
        except (OSError, ValueError, KeyError) as e:
            self.logger.error(f"Failed to read Excel file: {e}")
            raise

        for idx, row in df.iterrows():
            if len(records) >= limit:
                break

            try:
                product_cell = row.get("Produit")
                product = "" if pd.isna(product_cell) else str(product_cell).strip()
                if not product:
                    self.parse_errors += 1
                    continue

                updated = pd.to_datetime(row.get("Date_MAJ"), errors="coerce")
                if pd.isna(updated):
                    self.logger.warning(f"Row {idx}: missing or invalid Date_MAJ, skipped")
                    self.parse_errors += 1
                    continue
                updated_iso = updated.to_pydatetime().isoformat()

                price_cell = row.get("Prix_Unitaire")
                supplier_cell = row.get("Fournisseur")

                records.append(UnifiedRecord(
                    id=f"excel-{idx}",
                    source="excel",
                    source_ref=f"{self.file_path.name}#row{idx + 2}",  # +2 for header
                    timestamp=updated_iso,
                    lang="fr",  # Assume French
                    entities=[{
                        "type": "product",
                        "raw": product,
                        "norm": self.normalize_text(product)
                    }],
                    payload={
                        "Produit": product,
                        "Prix_Unitaire": float(price_cell) if pd.notna(price_cell) else None,
                        "Fournisseur": "" if pd.isna(supplier_cell) else str(supplier_cell).strip(),
                        "Date_MAJ": updated_iso,
                        "row_index": int(idx)
                    }
                ))

            except (ValueError, TypeError) as e:
                # Log and skip bad rows (R3 from connectors-spec.md)
                self.logger.warning(f"Failed to parse row {idx}: {e}")
                self.parse_errors += 1

        self.logger.info(f"Fetched {len(records)} records, {self.parse_errors} parse errors")
        return records

    async def _perform_health_check(self):
        """Check if Excel file exists and is readable"""
        if not self.file_path.exists():
            return {
                "status": "error",
                "source": self.source_name,
                "message": f"File not found: {self.file_path}",
                "last_fetch": None
            }

        try:
            # Try reading first row
            df = pd.read_excel(self.file_path, sheet_name="Tarifs", nrows=1)
            return {
                "status": "ok",
                "source": self.source_name,
                "message": f"File readable, {len(df.columns)} columns",
                "last_fetch": datetime.now().isoformat()
            }
        except (OSError, ValueError, KeyError) as e:
            return {
                "status": "error",
                "source": self.source_name,
                "message": str(e),
                "last_fetch": None
            }
