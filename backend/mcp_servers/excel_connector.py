"""
Excel Connector - MCP Server
Reads tarifs_fournisseurs.xlsx with intentional imperfections
"""
from typing import List
from pathlib import Path
from datetime import datetime
import pandas as pd

from .base import BaseConnector, UnifiedRecord, Entity


class ExcelConnector(BaseConnector):
    """
    Excel connector for supplier price lists
    Handles merged cells and imperfect formatting (R4 from connectors-spec.md)
    """
    
    def __init__(self, file_path: str):
        super().__init__("excel")
        self.file_path = Path(file_path)
        self.parse_errors = 0
        
    async def fetch_records(self, limit: int = 100) -> List[UnifiedRecord]:
        """
        Fetch records from Excel file
        
        Expected columns: Produit, Prix_Unitaire, Fournisseur, Date_MAJ
        """
        records = []
        limit = min(limit, 1000)  # Max 1000
        
        try:
            # Read Excel with openpyxl engine (handles merged cells better)
            df = pd.read_excel(self.file_path, sheet_name="Tarifs", engine="openpyxl")
            
            self.logger.info(f"Read {len(df)} rows from {self.file_path}")
            
            for idx, row in df.iterrows():
                if len(records) >= limit:
                    break
                
                try:
                    # Extract required fields
                    product = str(row.get("Produit", "")).strip()
                    price = row.get("Prix_Unitaire")
                    supplier = str(row.get("Fournisseur", "")).strip()
                    date_maj = row.get("Date_MAJ")
                    
                    if not product:
                        self.parse_errors += 1
                        continue
                    
                    # Normalize product name for entity matching
                    product_norm = self.normalize_text(product)
                    
                    # Create unified record
                    record = UnifiedRecord(
                        id=f"excel-{idx}",
                        source="excel",
                        source_ref=f"{self.file_path.name}#row{idx+2}",  # +2 for header
                        timestamp=datetime.now().isoformat(),
                        lang="fr",  # Assume French
                        entities=[{
                            "type": "product",
                            "raw": product,
                            "norm": product_norm
                        }],
                        payload={
                            "product": product,
                            "price": float(price) if pd.notna(price) else None,
                            "supplier": supplier,
                            "date_updated": str(date_maj) if pd.notna(date_maj) else None,
                            "row_index": int(idx)
                        }
                    )
                    
                    records.append(record)
                    
                except Exception as e:
                    # Log and skip bad rows (R3 from connectors-spec.md)
                    self.logger.warning(f"Failed to parse row {idx}: {e}")
                    self.parse_errors += 1
                    continue
            
            self.logger.info(f"Fetched {len(records)} records, {self.parse_errors} parse errors")
            return records
            
        except Exception as e:
            self.logger.error(f"Failed to read Excel file: {e}")
            raise
    
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
        except Exception as e:
            return {
                "status": "error",
                "source": self.source_name,
                "message": str(e),
                "last_fetch": None
            }
