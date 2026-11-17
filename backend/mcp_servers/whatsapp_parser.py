"""
WhatsApp export parser (pure functions, no I/O) and its inverse `export_messages`.

Supported line shapes (the header is the date and time part before the author):

    [DD/MM/YYYY, HH:MM:SS] Author: text      Android (brackets) or iOS FR
    [DD/MM/YYYY HH:MM:SS] Author: text       iOS (no comma)
    DD/MM/YYYY HH:MM - Author: text          Android (no brackets), seconds optional
    [M/D/YY, h:mm:ss AM] Author: text        iOS EN (12 h clock)
    M/D/YY, h:mm AM - Author: text           Android EN (12 h clock)

Date order rule (D/M versus M/D), applied once per file:
1. A first field above 12 in any header means day-first (`dmy`).
2. Otherwise a second field above 12 in any header means month-first (`mdy`).
3. Otherwise every date is ambiguous and the `default_date_order` argument decides.
   The result reports `date_order_source == "default"` so the caller can log it.
If a file holds both kinds of evidence, rule 1 wins and the headers that do not fit
the chosen order are counted as parse errors. A two-digit year `yy` means 20yy.

Line classes:
- header with `Author: text`: a message; following lines that are not headers
  continue it (joined with "\\n", the final text is stripped);
- header without author (encryption notice, "X joined", ...): a system message,
  skipped and counted apart from parse errors, with its continuation lines;
- header with an impossible date or time, or an author and no text: one parse
  error, the continuation lines of an impossible date are dropped with it;
- a non-header line before any header: one parse error; a blank one is ignored.
"""
import re
from dataclasses import dataclass, field
from datetime import datetime
from typing import Iterable, List, Optional, Tuple

DATE_ORDERS = ("dmy", "mdy")

# Invisible marks WhatsApp writes before a line or a placeholder (LRM, RLM, embeddings, BOM)
_INVISIBLE = "\u200e\u200f\u202a\u202b\u202c\ufeff"

_DATE = r"(?P<a>\d{1,2})[/.](?P<b>\d{1,2})[/.](?P<y>\d{4}|\d{2})"
_TIME = r"(?P<h>\d{1,2}):(?P<m>\d{2})(?::(?P<s>\d{2}))?(?:\s?(?P<ap>[AaPp]\.?[Mm]\.?))?"
_BRACKET_HEADER = re.compile(rf"^\[{_DATE},?\s+{_TIME}\]\s?(?P<rest>.*)$")
_DASH_HEADER = re.compile(rf"^{_DATE},?\s+{_TIME}\s-\s(?P<rest>.*)$")
_AUTHOR_TEXT = re.compile(r"^(?P<author>[^:]+?):(?:\s+(?P<text>.*))?$", re.DOTALL)

# First line of a message that stands for a file, not for written text
_ATTACHMENT = re.compile(
    r"^(?:"
    r"<(?:media|médias?) (?:omitted|omis(?:es?)?)>"
    r"|(?:image|video|vidéo|audio|sticker|gif|document|contact card|carte de contact)"
    r" (?:omitted|omis|omise|absente?)"
    r"|<(?:attached|joint)\s*:[^>]*>"
    r"|.+\((?:file attached|fichier joint)\)"
    r")$",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class ParsedMessage:
    """One chat message. `line_no` (1-based, first line of the message) is not part of equality."""

    timestamp: datetime
    author: str
    text: str
    line_no: int = field(default=0, compare=False)

    @property
    def attachment(self) -> bool:
        """True when the message is a media placeholder such as `<Media omitted>`."""
        return is_attachment(self.text)


@dataclass
class ParseResult:
    """Messages of one export and the counters of the lines that were not messages."""

    messages: List[ParsedMessage]
    parse_errors: int
    system_skipped: int
    date_order: str
    date_order_source: str  # "detected" | "default"


@dataclass(frozen=True)
class _Header:
    first: int
    second: int
    year: int
    hour: int
    minute: int
    second_of_minute: int
    meridiem: Optional[str]
    rest: str


def is_attachment(text: str) -> bool:
    """True when the first line of `text` is a media placeholder (FR or EN)."""
    first_line = text.split("\n", 1)[0].strip(_INVISIBLE + " \t")
    return bool(_ATTACHMENT.match(first_line))


def _match_header(line: str) -> Optional[_Header]:
    """Split a line into its header fields, or None when the line is not a header."""
    stripped = line.lstrip(_INVISIBLE).rstrip("\r\n")
    match = _BRACKET_HEADER.match(stripped) or _DASH_HEADER.match(stripped)
    if match is None:
        return None
    meridiem = match.group("ap")
    return _Header(
        first=int(match.group("a")),
        second=int(match.group("b")),
        year=int(match.group("y")),
        hour=int(match.group("h")),
        minute=int(match.group("m")),
        second_of_minute=int(match.group("s") or 0),
        meridiem=re.sub(r"[.\s]", "", meridiem).upper() if meridiem else None,
        rest=match.group("rest"),
    )


def is_header_line(line: str) -> bool:
    """True when the line starts a new message or system message."""
    return _match_header(line) is not None


def detect_date_order(lines: Iterable[str], default_date_order: str) -> Tuple[str, str]:
    """Apply the per-file date order rule (see the module docstring).

    Args:
        lines: Lines of the export.
        default_date_order: `dmy` or `mdy`, used when no header settles it.

    Returns:
        (order, source) where source is "detected" or "default".
    """
    if default_date_order not in DATE_ORDERS:
        raise ValueError(f"date order must be one of {DATE_ORDERS}, got {default_date_order!r}")
    day_first = month_first = False
    for line in lines:
        header = _match_header(line)
        if header is None:
            continue
        day_first = day_first or header.first > 12
        month_first = month_first or header.second > 12
    if day_first:
        return "dmy", "detected"
    if month_first:
        return "mdy", "detected"
    return default_date_order, "default"


def _to_datetime(header: _Header, order: str) -> datetime:
    """Build the timestamp of a header.

    Raises:
        ValueError: If the date or the time does not exist.
    """
    day, month = (header.first, header.second) if order == "dmy" else (header.second, header.first)
    year = header.year if header.year >= 100 else 2000 + header.year
    hour = header.hour
    if header.meridiem is not None:
        if not 1 <= hour <= 12 or header.meridiem not in ("AM", "PM"):
            raise ValueError(f"invalid 12 h time: {hour} {header.meridiem}")
        hour = hour % 12 + (12 if header.meridiem == "PM" else 0)
    return datetime(year, month, day, hour, header.minute, header.second_of_minute)


def parse_export(lines: Iterable[str], default_date_order: str = "dmy") -> ParseResult:
    """Parse the lines of a WhatsApp export.

    Args:
        lines: Lines of the file, in order (line endings are ignored).
        default_date_order: `dmy` or `mdy`, applied only to a file whose dates
            are all ambiguous.

    Returns:
        The messages with their counters. Never raises on a bad line.

    Raises:
        ValueError: If `default_date_order` is not `dmy` or `mdy`.
    """
    all_lines = list(lines)
    order, order_source = detect_date_order(all_lines, default_date_order)

    messages: List[ParsedMessage] = []
    errors = 0
    system = 0
    # State of the last header: "message" | "system" | "error" | None (nothing yet)
    state: Optional[str] = None
    current: List[str] = []
    current_meta: Optional[tuple] = None  # (timestamp, author, line_no)

    def flush() -> None:
        nonlocal current, current_meta, errors
        if current_meta is not None:
            timestamp, author, line_no = current_meta
            text = "\n".join(current).strip()
            if text:
                messages.append(ParsedMessage(timestamp, author, text, line_no))
            else:
                errors += 1  # "Author:" with nothing after it carries no message
        current, current_meta = [], None

    for line_no, raw_line in enumerate(all_lines, 1):
        line = raw_line.rstrip("\r\n")
        header = _match_header(line)

        if header is None:
            if state == "message":
                current.append(line)
            elif state is None and line.strip():
                errors += 1
            continue

        flush()
        try:
            timestamp = _to_datetime(header, order)
        except ValueError:
            errors += 1
            state = "error"
            continue

        parts = _AUTHOR_TEXT.match(header.rest.lstrip(_INVISIBLE + " "))
        if parts is None:
            system += 1
            state = "system"
            continue

        state = "message"
        current = [parts.group("text") or ""]
        current_meta = (timestamp, parts.group("author").strip(), line_no)

    flush()
    return ParseResult(messages, errors, system, order, order_source)


# --- Export (inverse of parse_export), used by the round-trip property tests ---

EXPORT_FORMATS = ("android_fr", "android_nobracket_fr", "ios_fr", "ios_en", "android_en")
_FORMATS_WITHOUT_SECONDS = ("android_nobracket_fr", "android_en")
_FORMATS_MONTH_FIRST = ("ios_en", "android_en")


def _clock_12h(moment: datetime, with_seconds: bool) -> str:
    hour = moment.hour % 12 or 12
    suffix = "AM" if moment.hour < 12 else "PM"
    seconds = f":{moment.second:02d}" if with_seconds else ""
    return f"{hour}:{moment.minute:02d}{seconds} {suffix}"


def _header_text(moment: datetime, export_format: str) -> str:
    """Date and time part of a line, brackets and separators included."""
    day_month = f"{moment.day:02d}/{moment.month:02d}/{moment.year}"
    if export_format == "android_fr":
        return f"[{day_month}, {moment:%H:%M:%S}] "
    if export_format == "android_nobracket_fr":
        return f"{day_month} {moment:%H:%M} - "
    if export_format == "ios_fr":
        return f"[{day_month} {moment:%H:%M:%S}] "
    month_day = f"{moment.month}/{moment.day}/{moment.year % 100:02d}"
    if export_format == "ios_en":
        return f"[{month_day}, {_clock_12h(moment, True)}] "
    return f"{month_day}, {_clock_12h(moment, False)} - "


def export_messages(messages: Iterable[ParsedMessage], export_format: str) -> str:
    """Serialize messages to the text of a WhatsApp export (inverse of `parse_export`).

    A multi-line text keeps its continuation lines as they are. Month-first formats
    (`ios_en`, `android_en`) only round-trip when the file is parsed with
    `default_date_order="mdy"` or holds a day above 12.

    Args:
        messages: Messages to write; a text must be non-empty and stripped, and
            none of its lines may look like a header.
        export_format: One of `EXPORT_FORMATS`.

    Returns:
        The export, one trailing newline per message.

    Raises:
        ValueError: If the format is unknown, or a message has seconds that the
            format cannot hold, or a year that the format cannot hold.
    """
    if export_format not in EXPORT_FORMATS:
        raise ValueError(f"unknown export format {export_format!r}, expected one of {EXPORT_FORMATS}")
    chunks = []
    for message in messages:
        moment = message.timestamp
        if export_format in _FORMATS_WITHOUT_SECONDS and moment.second:
            raise ValueError(f"{export_format} cannot hold seconds: {moment.isoformat()}")
        if export_format in _FORMATS_MONTH_FIRST and not 2000 <= moment.year <= 2099:
            raise ValueError(f"{export_format} writes a two-digit year: {moment.isoformat()}")
        chunks.append(f"{_header_text(moment, export_format)}{message.author}: {message.text}\n")
    return "".join(chunks)
