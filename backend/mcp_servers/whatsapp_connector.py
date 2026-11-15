"""
WhatsApp Connector - MCP Server
Parses WhatsApp export files (Android/iOS formats)
"""
from typing import List
from pathlib import Path
from datetime import datetime
import re

from .base import BaseConnector, UnifiedRecord

# Common product keywords from ZOBO (normalized: lowercase, no accents)
_PRODUCT_KEYWORDS = frozenset({
    "ciment", "pointe", "vis", "tuyau", "pvc", "cable", "peinture",
    "marteau", "perceuse", "cadenas", "serrure",
})
# Unit tokens that may follow a product keyword ("50 kg", "32 mm")
_UNIT_TOKENS = frozenset({"kg", "g", "l", "litre", "litres", "m", "mm", "cm", "w"})
# Max tokens consumed after a keyword (quantity, unit, qualifier)
_MAX_FOLLOWING_TOKENS = 4
_MAX_PRODUCTS_PER_MESSAGE = 3


class WhatsAppConnector(BaseConnector):
    """WhatsApp export parser (R6 from connectors-spec.md)"""

    def __init__(self, file_path: str):
        super().__init__("whatsapp")
        self.file_path = Path(file_path)
        self.parse_errors = 0

    async def fetch_records(self, limit: int = 100) -> List[UnifiedRecord]:
        """Parse WhatsApp export file

        Lines that do not match the export format or carry an invalid date
        are skipped and counted as parse errors.
        """
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

                    try:
                        timestamp_iso = datetime.strptime(timestamp_str, "%d/%m/%Y, %H:%M:%S").isoformat()
                    except ValueError:
                        self.logger.warning(f"WhatsApp line {line_no}: invalid date '{timestamp_str}', skipped")
                        self.parse_errors += 1
                        continue

                    # Detect language (simple heuristic)
                    lang = "fr" if any(w in message.lower() for w in ["bonjour", "bsr", "svp", "merci"]) else "en"

                    # Extract product mentions (simple keyword matching for now)
                    products = self._extract_products(message)
                    entities = [{"type": "product", "raw": p, "norm": self.normalize_text(p)} for p in products]

                    records.append(UnifiedRecord(
                        id=f"wa-{line_no}",
                        source="whatsapp",
                        source_ref=f"{self.file_path.name}#L{line_no}",
                        timestamp=timestamp_iso,
                        lang=lang,
                        entities=entities,
                        payload={"author": author, "text": message}
                    ))

        except (OSError, UnicodeDecodeError) as e:
            self.logger.error(f"Failed to read WhatsApp file: {e}")
            raise

        self.logger.info(f"Parsed {len(records)} messages, {self.parse_errors} errors")
        return records

    def _extract_products(self, text: str) -> List[str]:
        """Extract product mentions from a message (simple keywords for MVP)

        A mention is a product keyword followed by its quantity/unit tokens,
        so "prix du ciment 50kg svp?" yields "ciment 50kg" and
        "ciment (50kg)" yields "ciment (50kg)".

        Args:
            text: Raw message text.

        Returns:
            Raw mention strings, in order of appearance (max 3).
        """
        tokens = [(m.start(), m.end(), self._token_head(m.group())) for m in re.finditer(r"\S+", text)]
        mentions: List[str] = []
        i = 0
        while i < len(tokens) and len(mentions) < _MAX_PRODUCTS_PER_MESSAGE:
            if tokens[i][2] not in _PRODUCT_KEYWORDS:
                i += 1
                continue

            last = i
            while (
                last + 1 < len(tokens)
                and last - i < _MAX_FOLLOWING_TOKENS
                and self._is_quantity_or_keyword(text[tokens[last + 1][0]:tokens[last + 1][1]], tokens[last + 1][2])
            ):
                last += 1

            mentions.append(text[tokens[i][0]:tokens[last][1]].rstrip(".,;:!?"))
            i = last + 1
        return mentions

    def _token_head(self, token: str) -> str:
        """First normalized word of a token, with a plural 's' removed.

        "Ciment50kg" -> "ciment", "cimént" -> "ciment", "pointes" -> "pointe".
        """
        normalized = self.normalize_text(token)
        head = normalized.split(" ", 1)[0] if normalized else ""
        if head not in _PRODUCT_KEYWORDS and head.endswith("s") and head[:-1] in _PRODUCT_KEYWORDS:
            return head[:-1]
        return head

    def _is_quantity_or_keyword(self, token: str, head: str) -> bool:
        """True if a token continues a product mention (digits, unit or keyword)."""
        normalized = self.normalize_text(token)
        return (
            head in _PRODUCT_KEYWORDS
            or normalized in _UNIT_TOKENS
            or any(c.isdigit() for c in normalized)
        )

    async def _perform_health_check(self):
        """Check if WhatsApp file exists"""
        if not self.file_path.exists():
            return {"status": "error", "source": self.source_name,
                   "message": f"File not found: {self.file_path}", "last_fetch": None}
        return {"status": "ok", "source": self.source_name,
               "message": "File readable", "last_fetch": datetime.now().isoformat()}
