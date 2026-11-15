"""
E-mail alert digest for new warning and error correlations (Resend HTTP API).

Enabled only when RESEND_API_KEY, ALERT_EMAIL_FROM and ALERT_EMAIL_TO are all
set. One digest is sent per execution, from a background task: a slow or
failing provider never delays or fails the request. Recipients, the API key
and the message bodies are never logged. Correlation messages come from source
text (untrusted): control characters are stripped, the length is bounded, and
the HTML part is escaped.
"""
import asyncio
import html
import logging
import unicodedata
from dataclasses import dataclass, field
from typing import List, Optional, Sequence, Tuple

import httpx

import config

logger = logging.getLogger(__name__)

RESEND_URL = "https://api.resend.com/emails"
SEND_TIMEOUT_SECONDS = 5.0
SEND_ATTEMPTS = 2
RETRY_DELAY_SECONDS = 0.5
MAX_ITEMS_PER_DIGEST = 50
MAX_MESSAGE_CHARS = 300
ALERT_SEVERITIES = ("warning", "error")

DEFAULT_LANGUAGE = "fr"
# Texts of the digest. {count} is the number of correlations; "more" counts those not listed.
ALERT_TEXTS = {
    "fr": {
        "subject_one": "ChimeraFlow : 1 nouvelle alerte",
        "subject_other": "ChimeraFlow : {count} nouvelles alertes",
        "heading": "Nouvelles corrélations à surveiller",
        "more": "… et {more} autre(s)",
        "severity_info": "Information",
        "severity_warning": "Avertissement",
        "severity_error": "Erreur",
    },
    "en": {
        "subject_one": "ChimeraFlow: 1 new alert",
        "subject_other": "ChimeraFlow: {count} new alerts",
        "heading": "New correlations to watch",
        "more": "… and {more} more",
        "severity_info": "Information",
        "severity_warning": "Warning",
        "severity_error": "Error",
    },
}

# Test seam: transport of the HTTP client (None means the network)
_TRANSPORT: Optional[httpx.AsyncBaseTransport] = None


@dataclass(frozen=True)
class AlertSettings:
    """Resend connection and addressing."""

    api_key: str = field(repr=False)
    sender: str = field(repr=False)
    recipients: Tuple[str, ...] = field(repr=False)


@dataclass(frozen=True)
class AlertItem:
    """One correlation worth an e-mail."""

    rule_id: str
    severity: str
    message: str


def alert_settings_from_config() -> Optional[AlertSettings]:
    """Settings of the alert e-mail, or None when the feature is disabled.

    Returns:
        The settings when the API key, the sender and a recipient are all set.
    """
    if not config.RESEND_API_KEY or not config.ALERT_EMAIL_FROM or not config.ALERT_EMAIL_TO:
        return None
    return AlertSettings(
        api_key=config.RESEND_API_KEY,
        sender=config.ALERT_EMAIL_FROM,
        recipients=tuple(config.ALERT_EMAIL_TO),
    )


def select_alert_items(correlations: Sequence[dict]) -> List[AlertItem]:
    """Keep the warning and error correlations, in order.

    Args:
        correlations: Correlation dicts of the engine (rule_id, severity, message).
    """
    return [
        AlertItem(rule_id=c["rule_id"], severity=c["severity"], message=c["message"])
        for c in correlations
        if c["severity"] in ALERT_SEVERITIES
    ]


def _clean(text: str) -> str:
    """One line of printable text: control and format characters become spaces, length bounded."""
    printable = "".join(" " if unicodedata.category(c) in ("Cc", "Cf", "Zl", "Zp") else c for c in text)
    collapsed = " ".join(printable.split())
    if len(collapsed) > MAX_MESSAGE_CHARS:
        return collapsed[: MAX_MESSAGE_CHARS - 1] + "…"
    return collapsed


def build_digest(items: Sequence[AlertItem], language: str = DEFAULT_LANGUAGE) -> Tuple[str, str, str]:
    """Build the subject, the plain text and the HTML of a digest.

    Args:
        items: Correlations to report (at least one).
        language: "fr" or "en".

    Returns:
        (subject, text, html). The HTML is built from escaped text only.
    """
    texts = ALERT_TEXTS[language]
    count = len(items)
    subject = texts["subject_one"] if count == 1 else texts["subject_other"].format(count=count)
    listed = items[:MAX_ITEMS_PER_DIGEST]
    lines = [
        f"[{texts['severity_' + item.severity]}] {_clean(item.rule_id)}: {_clean(item.message)}"
        for item in listed
    ]
    if count > len(listed):
        lines.append(texts["more"].format(more=count - len(listed)))

    text = "\n".join([texts["heading"], "", *lines])
    list_items = "".join(f"<li>{html.escape(line)}</li>" for line in lines)
    body = f"<h1>{html.escape(texts['heading'])}</h1><ul>{list_items}</ul>"
    return subject, text, body


async def send_digest(settings: AlertSettings, items: Sequence[AlertItem], language: str = DEFAULT_LANGUAGE) -> bool:
    """Send one digest through Resend (2 attempts, 5 s each).

    Args:
        settings: Resend connection and addressing.
        items: Correlations to report; nothing is sent when empty.
        language: "fr" or "en".

    Returns:
        True if the provider accepted the e-mail. Failures are logged without
        recipients or content, and never raised.
    """
    if not items:
        return False
    subject, text, body = build_digest(items, language)
    payload = {
        "from": settings.sender,
        "to": list(settings.recipients),
        "subject": subject,
        "text": text,
        "html": body,
    }
    headers = {"Authorization": f"Bearer {settings.api_key}"}

    for attempt in range(SEND_ATTEMPTS):
        try:
            async with httpx.AsyncClient(timeout=SEND_TIMEOUT_SECONDS, transport=_TRANSPORT) as client:
                response = await client.post(RESEND_URL, json=payload, headers=headers)
            if response.is_success:
                logger.info("alert_email outcome=sent items=%d", len(items))
                return True
            logger.warning("alert_email outcome=rejected status=%d attempt=%d", response.status_code, attempt + 1)
            if response.status_code < 500 and response.status_code != 429:
                return False
        except httpx.HTTPError as error:
            logger.warning("alert_email outcome=error kind=%s attempt=%d", type(error).__name__, attempt + 1)
        if attempt + 1 < SEND_ATTEMPTS:
            await asyncio.sleep(RETRY_DELAY_SECONDS * 2 ** attempt)
    return False


async def dispatch_alerts(items: Sequence[AlertItem]) -> None:
    """Background task: send the digest when the feature is configured.

    Never raises, so a failure cannot surface in the request that scheduled it.
    """
    settings = alert_settings_from_config()
    if settings is None or not items:
        return
    try:
        await send_digest(settings, items)
    except Exception:
        logger.exception("alert_email outcome=failed")
