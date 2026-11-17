"""
WhatsApp Connector - MCP Server
Parses WhatsApp export files (Android/iOS formats, FR/EN dates, multi-line messages)
"""
from typing import List
from pathlib import Path
from datetime import datetime
import re
import time

from .base import BaseConnector, UnifiedRecord
from .whatsapp_parser import DATE_ORDERS, parse_export

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
    """WhatsApp export parser (R6 from connectors-spec.md)

    Date order of ambiguous files (every date has both fields <= 12) is
    `default_date_order`; see whatsapp_parser.py for the full rule.
    """

    def __init__(self, file_path: str, default_date_order: str = "dmy"):
        super().__init__("whatsapp")
        if default_date_order not in DATE_ORDERS:
            raise ValueError(f"default_date_order must be one of {DATE_ORDERS}, got {default_date_order!r}")
        self.file_path = Path(file_path)
        self.default_date_order = default_date_order
        self.parse_errors = 0
        self.system_skipped = 0
        self.date_order = default_date_order
        self.date_order_source = "default"

    async def fetch_records(self, limit: int = 100) -> List[UnifiedRecord]:
        """Parse WhatsApp export file

        The whole file is read so that the date order is settled per file. Lines
        that are not messages and not continuation lines, and headers with an
        invalid date, are skipped and counted in `parse_errors` (whole file).
        System messages (encryption notice, joins) are skipped and counted in
        `system_skipped`. Media placeholders are kept and flagged
        `payload["attachment"] = True`. At most `limit` messages are returned.
        """
        started = time.monotonic()
        limit = min(limit, 1000)
        self.parse_errors = 0  # counts the errors of this fetch only
        self.system_skipped = 0

        try:
            with open(self.file_path, 'r', encoding='utf-8-sig') as f:
                result = parse_export(f, self.default_date_order)
        except (OSError, UnicodeDecodeError) as e:
            self.logger.error(f"Failed to read WhatsApp file: {e}")
            raise

        self.parse_errors = result.parse_errors
        self.system_skipped = result.system_skipped
        self.date_order = result.date_order
        self.date_order_source = result.date_order_source

        records = []
        for message in result.messages[:limit]:
            text = message.text
            # Detect language (simple heuristic)
            lang = "fr" if any(w in text.lower() for w in ["bonjour", "bsr", "svp", "merci"]) else "en"

            # Extract product mentions (simple keyword matching for now)
            products = self._extract_products_of_message(text)
            entities = [{"type": "product", "raw": p, "norm": self.normalize_text(p)} for p in products]

            records.append(UnifiedRecord(
                id=f"wa-{message.line_no}",
                source="whatsapp",
                source_ref=f"{self.file_path.name}#L{message.line_no}",
                timestamp=message.timestamp.isoformat(),
                lang=lang,
                entities=entities,
                payload={"author": message.author, "text": text, "attachment": message.attachment},
            ))

        if self.date_order_source == "default":
            self.logger.info(
                "WhatsApp dates are ambiguous (every field <= 12): default order '%s' applied", self.date_order
            )
        self.logger.info(
            "connector=whatsapp operation=fetch_records records_count=%d errors_count=%d "
            "system_skipped=%d date_order=%s(%s) duration_ms=%d",
            len(records), self.parse_errors, self.system_skipped, self.date_order,
            self.date_order_source, int((time.monotonic() - started) * 1000),
        )
        return records

    def _extract_products_of_message(self, text: str) -> List[str]:
        """Product mentions of a message, line by line (a mention never spans two lines)."""
        mentions: List[str] = []
        for line in text.split("\n"):
            mentions.extend(self._extract_products(line))
        return mentions[:_MAX_PRODUCTS_PER_MESSAGE]

    def _extract_products_of_message(self, text: str) -> List[str]:
        """Product mentions of a message, line by line (a mention never spans two lines)."""
        mentions: List[str] = []
        for line in text.split("\n"):
            mentions.extend(self._extract_products(line))
        return mentions[:_MAX_PRODUCTS_PER_MESSAGE]

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
