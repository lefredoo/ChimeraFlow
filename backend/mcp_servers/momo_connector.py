"""
Mobile Money Connector - MCP Server
Reads Mobile Money transaction CSV files
"""
from typing import List
from pathlib import Path
from datetime import datetime
import csv

from .base import BaseConnector, UnifiedRecord


class MobileMoneyConnector(BaseConnector):
    """
    Mobile Money CSV connector (R7 from connectors-spec.md)
    Expected fields: transaction_id, phone, amount, status, timestamp
    """
    
    def __init__(self, file_path: str):
        super().__init__("momo")
        self.file_path = Path(file_path)
        self.parse_errors = 0
        
    async def fetch_records(self, limit: int = 100) -> List[UnifiedRecord]:
        """Fetch Mobile Money transactions from CSV"""
        records = []
        limit = min(limit, 1000)
        
        try:
            with open(self.file_path, 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                
                for idx, row in enumerate(reader, 1):
                    if len(records) >= limit:
                        break
                    
                    try:
                        transaction_id = row.get("transaction_id", "").strip()
                        phone = row.get("phone", "").strip()
                        amount = row.get("amount", "0")
                        status = row.get("status", "").strip()
                        timestamp_str = row.get("timestamp", "").strip()
                        
                        if not transaction_id:
                            self.parse_errors += 1
                            continue
                        
                        # Parse timestamp
                        try:
                            dt = datetime.fromisoformat(timestamp_str)
                            timestamp_iso = dt.isoformat()
                        except:
                            timestamp_iso = datetime.now().isoformat()
                        
                        # Parse amount
                        try:
                            amount_float = float(amount)
                        except:
                            amount_float = 0.0
                        
                        record = UnifiedRecord(
                            id=f"momo-{transaction_id}",
                            source="momo",
                            source_ref=f"{self.file_path.name}#row{idx}",
                            timestamp=timestamp_iso,
                            lang="fr",
                            entities=[{
                                "type": "payment",
                                "raw": f"{amount} FCFA",
                                "norm": f"{amount_float}"
                            }],
                            payload={
                                "transaction_id": transaction_id,
                                "phone": phone,
                                "amount": amount_float,
                                "status": status,
                                "provider": "mobile_money"
                            }
                        )
                        records.append(record)
                        
                    except Exception as e:
                        self.logger.warning(f"Failed to parse Mobile Money row {idx}: {e}")
                        self.parse_errors += 1
                        continue
            
            self.logger.info(f"Fetched {len(records)} Mobile Money records, {self.parse_errors} errors")
            return records
            
        except Exception as e:
            self.logger.error(f"Failed to read Mobile Money CSV: {e}")
            raise
    
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
            else:
                return {
                    "status": "degraded",
                    "source": self.source_name,
                    "message": "CSV is empty",
                    "last_fetch": None
                }
                
        except Exception as e:
            return {
                "status": "error",
                "source": self.source_name,
                "message": str(e),
                "last_fetch": None
            }
