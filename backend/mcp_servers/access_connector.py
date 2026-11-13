"""
Access Connector - MCP Server
Reads .mdb (Microsoft Access) databases using mdbtools
"""
from typing import List
from pathlib import Path
from datetime import datetime
import subprocess
import csv
from io import StringIO

from .base import BaseConnector, UnifiedRecord


class AccessConnector(BaseConnector):
    """
    Access database connector (R5 from connectors-spec.md)
    Uses mdbtools CLI (mdb-export) to read .mdb files
    """
    
    def __init__(self, file_path: str, table_name: str = "Articles"):
        super().__init__("access")
        self.file_path = Path(file_path)
        self.table_name = table_name
        self.parse_errors = 0
        
    async def fetch_records(self, limit: int = 100) -> List[UnifiedRecord]:
        """
        Fetch records from Access database table
        Expected columns: id, designation, unite, qty_stock
        """
        records = []
        limit = min(limit, 1000)
        
        try:
            # Use mdb-export to dump table as CSV
            result = subprocess.run(
                ["mdb-export", str(self.file_path), self.table_name],
                capture_output=True,
                text=True,
                timeout=5  # 5s timeout from connectors.md
            )
            
            if result.returncode != 0:
                self.logger.error(f"mdb-export failed: {result.stderr}")
                raise Exception(f"Failed to read Access table: {result.stderr}")
            
            # Parse CSV output
            csv_data = StringIO(result.stdout)
            reader = csv.DictReader(csv_data)
            
            for idx, row in enumerate(reader):
                if len(records) >= limit:
                    break
                
                try:
                    # Extract fields
                    article_id = row.get("id", "")
                    designation = row.get("designation", "").strip()
                    unite = row.get("unite", "").strip()
                    qty_stock = row.get("qty_stock", "0")
                    
                    if not designation:
                        self.parse_errors += 1
                        continue
                    
                    # Normalize product designation
                    designation_norm = self.normalize_text(designation)
                    
                    record = UnifiedRecord(
                        id=f"access-{article_id or idx}",
                        source="access",
                        source_ref=f"{self.file_path.name}#{self.table_name}#{article_id}",
                        timestamp=datetime.now().isoformat(),
                        lang="fr",
                        entities=[{
                            "type": "product",
                            "raw": designation,
                            "norm": designation_norm
                        }],
                        payload={
                            "id": article_id,
                            "designation": designation,
                            "unite": unite,
                            "qty_stock": int(qty_stock) if qty_stock.isdigit() else 0,
                            "table": self.table_name
                        }
                    )
                    records.append(record)
                    
                except Exception as e:
                    self.logger.warning(f"Failed to parse Access row {idx}: {e}")
                    self.parse_errors += 1
                    continue
            
            self.logger.info(f"Fetched {len(records)} Access records, {self.parse_errors} errors")
            return records
            
        except subprocess.TimeoutExpired:
            self.logger.error("mdb-export timeout (5s)")
            raise
        except Exception as e:
            self.logger.error(f"Failed to read Access database: {e}")
            raise
    
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
            
        except Exception as e:
            return {
                "status": "error",
                "source": self.source_name,
                "message": str(e),
                "last_fetch": None
            }
