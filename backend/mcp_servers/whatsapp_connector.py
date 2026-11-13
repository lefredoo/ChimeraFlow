"""
WhatsApp Connector - MCP Server
Parses WhatsApp export files (Android/iOS formats)
"""
from typing import List
from pathlib import Path
from datetime import datetime
import re

from .base import BaseConnector, UnifiedRecord


class WhatsAppConnector(BaseConnector):
    """WhatsApp export parser (R6 from connectors-spec.md)"""
    
    def __init__(self, file_path: str):
        super().__init__("whatsapp")
        self.file_path = Path(file_path)
        self.parse_errors = 0
        
    async def fetch_records(self, limit: int = 100) -> List[UnifiedRecord]:
        """Parse WhatsApp export file"""
        records = []
        limit = min(limit, 1000)
        
        # Android format: [DD/MM/YYYY, HH:MM:SS] Author: Message
        pattern = r'\[(\d{2}/\d{2}/\d{4}, \d{2}:\d{2}:\d{2})\] ([^:]+): (.+)'
        
        try:
            with open(self.file_path, 'r', encoding='utf-8') as f:
                for line_no, line in enumerate(f, 1):
                    if len(records) >= limit:
                        break
                    
                    match = re.match(pattern, line.strip())
                    if not match:
                        self.parse_errors += 1
                        continue
                    
                    timestamp_str, author, message = match.groups()
                    
                    # Parse timestamp
                    try:
                        dt = datetime.strptime(timestamp_str, "%d/%m/%Y, %H:%M:%S")
                        timestamp_iso = dt.isoformat()
                    except:
                        timestamp_iso = datetime.now().isoformat()
                    
                    # Detect language (simple heuristic)
                    lang = "fr" if any(w in message.lower() for w in ["bonjour", "bsr", "svp", "merci"]) else "en"
                    
                    # Extract product mentions (simple keyword matching for now)
                    products = self._extract_products(message)
                    entities = [{"type": "product", "raw": p, "norm": self.normalize_text(p)} for p in products]
                    
                    record = UnifiedRecord(
                        id=f"wa-{line_no}",
                        source="whatsapp",
                        source_ref=f"{self.file_path.name}#L{line_no}",
                        timestamp=timestamp_iso,
                        lang=lang,
                        entities=entities,
                        payload={"author": author, "text": message}
                    )
                    records.append(record)
            
            self.logger.info(f"Parsed {len(records)} messages, {self.parse_errors} errors")
            return records
            
        except Exception as e:
            self.logger.error(f"Failed to read WhatsApp file: {e}")
            raise
    
    def _extract_products(self, text: str) -> List[str]:
        """Extract product names from message (simple keywords for MVP)"""
        # Common product keywords from ZOBO
        keywords = ["ciment", "pointe", "vis", "tuyau", "pvc", "câble", "peinture", 
                   "marteau", "perceuse", "cadenas", "serrure"]
        products = []
        text_lower = text.lower()
        for kw in keywords:
            if kw in text_lower:
                # Extract surrounding context
                idx = text_lower.find(kw)
                start = max(0, idx - 10)
                end = min(len(text), idx + 30)
                products.append(text[start:end].strip())
        return products[:3]  # Max 3 products per message
    
    async def _perform_health_check(self):
        """Check if WhatsApp file exists"""
        if not self.file_path.exists():
            return {"status": "error", "source": self.source_name, 
                   "message": f"File not found: {self.file_path}", "last_fetch": None}
        return {"status": "ok", "source": self.source_name, 
               "message": "File readable", "last_fetch": datetime.now().isoformat()}
