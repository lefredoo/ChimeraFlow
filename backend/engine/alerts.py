"""
E-mail alert digest for new warning and error correlations (Cloudflare Email
Service REST API).

Enabled only when CF_EMAIL_ACCOUNT_ID, CF_EMAIL_API_TOKEN, ALERT_EMAIL_FROM and
ALERT_EMAIL_TO are all set. One digest is sent per execution, from a background task: a slow or
failing provider never delays or fails the request. A global cooldown
(ALERT_EMAIL_COOLDOWN_SECONDS, enforced in Redis with SET NX EX) allows at most
one digest per window, whatever the number of executions or workers; when Redis
is unavailable nothing is sent (fail closed). Recipients, the API token
and the message bodies are never logged. Correlation messages come from source
text (untrusted): control characters are stripped, the length is bounded, and
the HTML part is escaped.
"""
import asyncio
import html
import logging
import unicodedata
from dataclasses import dataclass, field
from functools import lru_cache
from typing import Any, List, Optional, Protocol, Sequence, Tuple

import httpx
from redis.exceptions import RedisError

import config

logger = logging.getLogger(__name__)
# httpx logs every request URL at INFO, and the URL carries the Cloudflare account id
logging.getLogger("httpx").setLevel(logging.WARNING)

CLOUDFLARE_EMAIL_URL = "https://api.cloudflare.com/client/v4/accounts/{account_id}/email/sending/send"
SEND_TIMEOUT_SECONDS = 5.0
SEND_ATTEMPTS = 2
RETRY_DELAY_SECONDS = 0.5
MAX_ITEMS_PER_DIGEST = 50
MAX_MESSAGE_CHARS = 300
ALERT_SEVERITIES = ("warning", "error")
COOLDOWN_KEY = "chimeraflow:alerts:cooldown"
REDIS_TIMEOUT_SECONDS = 2

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
    """Cloudflare Email Service connection and addressing."""

    account_id: str = field(repr=False)
    api_token: str = field(repr=False)
    sender: str = field(repr=False)
    recipients: Tuple[str, ...] = field(repr=False)
    cooldown_seconds: int


@dataclass(frozen=True)
class AlertItem:
    """One correlation worth an e-mail."""

    rule_id: str
    severity: str
    message: str


def alert_settings_from_config() -> Optional[AlertSettings]:
    """Settings of the alert e-mail, or None when the feature is disabled.

    Returns:
        The settings when the account id, the API token, the sender, a recipient and the cooldown are all set.
    """
    cooldown = config.ALERT_EMAIL_COOLDOWN_SECONDS
    if (
        not config.CF_EMAIL_ACCOUNT_ID
        or not config.CF_EMAIL_API_TOKEN
        or not config.ALERT_EMAIL_FROM
        or not config.ALERT_EMAIL_TO
        or cooldown is None
    ):
        return None
    return AlertSettings(
        account_id=config.CF_EMAIL_ACCOUNT_ID,
        api_token=config.CF_EMAIL_API_TOKEN,
        sender=config.ALERT_EMAIL_FROM,
        recipients=tuple(config.ALERT_EMAIL_TO),
        cooldown_seconds=cooldown,
    )


class CooldownStoreError(Exception):
    """The cooldown store (Redis) failed."""


class CooldownStore(Protocol):
    """Shared cooldown between digests."""

    async def acquire(self, seconds: int) -> bool:
        """Start a cooldown of `seconds` unless one is running.

        Returns:
            True if no cooldown was running (the caller may send), False otherwise.

        Raises:
            CooldownStoreError: If the store fails.
        """


class RedisCooldownStore:
    """Cooldown kept in Redis: one key set with NX and an expiry, atomic across workers."""

    def __init__(self, client: Any) -> None:
        """Create the store.

        Args:
            client: A `redis.asyncio.Redis` client (anything with an async `set`).
        """
        self._client = client

    async def acquire(self, seconds: int) -> bool:
        """See `CooldownStore.acquire`."""
        try:
            return bool(await self._client.set(COOLDOWN_KEY, "1", nx=True, ex=seconds))
        except RedisError as exc:
            raise CooldownStoreError("Cannot start the alert cooldown") from exc


@lru_cache
def _redis_cooldown_store() -> Optional[RedisCooldownStore]:
    """Create the Redis cooldown store once (None when REDIS_URL is not set, i.e. in tests)."""
    if config.REDIS_URL is None:
        return None
    from redis.asyncio import Redis

    client = Redis.from_url(
        config.REDIS_URL,
        socket_timeout=REDIS_TIMEOUT_SECONDS,
        socket_connect_timeout=REDIS_TIMEOUT_SECONDS,
    )
    return RedisCooldownStore(client)


def get_cooldown_store() -> Optional[CooldownStore]:
    """The cooldown store; the seam tests replace (no Redis in tests)."""
    return _redis_cooldown_store()


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


def _json_body(response: httpx.Response) -> Optional[dict]:
    """The JSON object of a response, or None when the body is not one."""
    try:
        body = response.json()
    except ValueError:
        return None
    return body if isinstance(body, dict) else None


def _body_reports_success(response: httpx.Response) -> bool:
    """True when the API answered `success: true` (an HTTP 2xx alone is not enough)."""
    body = _json_body(response)
    return body is not None and body.get("success") is True


def _error_codes(response: httpx.Response) -> str:
    """Error codes of a Cloudflare answer, comma-separated (never the messages, which may echo input)."""
    body = _json_body(response)
    errors = body.get("errors") if body is not None else None
    if not isinstance(errors, list):
        return "none"
    codes = [str(error["code"]) for error in errors if isinstance(error, dict) and isinstance(error.get("code"), int)]
    return ",".join(codes[:5]) or "none"


async def send_digest(settings: AlertSettings, items: Sequence[AlertItem], language: str = DEFAULT_LANGUAGE) -> bool:
    """Send one digest through Cloudflare Email Service (2 attempts, 5 s each).

    Args:
        settings: Cloudflare Email Service connection and addressing.
        items: Correlations to report; nothing is sent when empty.
        language: "fr" or "en".

    Returns:
        True if the provider accepted the e-mail (HTTP 2xx and `success: true`).
        Failures are logged with the provider error codes only, never with
        recipients or content, and never raised.
    """
    if not items:
        return False
    subject, text, body = build_digest(items, language)
    payload = {
        "to": list(settings.recipients),
        "from": settings.sender,
        "subject": subject,
        "text": text,
        "html": body,
    }
    url = CLOUDFLARE_EMAIL_URL.format(account_id=settings.account_id)
    headers = {"Authorization": f"Bearer {settings.api_token}", "Content-Type": "application/json"}

    for attempt in range(SEND_ATTEMPTS):
        try:
            async with httpx.AsyncClient(timeout=SEND_TIMEOUT_SECONDS, transport=_TRANSPORT) as client:
                response = await client.post(url, json=payload, headers=headers)
            if response.is_success and _body_reports_success(response):
                logger.info("alert_email outcome=sent items=%d", len(items))
                return True
            logger.warning(
                "alert_email outcome=rejected status=%d codes=%s attempt=%d",
                response.status_code,
                _error_codes(response),
                attempt + 1,
            )
            if response.status_code < 500 and response.status_code != 429:
                return False
        except httpx.HTTPError as error:
            logger.warning("alert_email outcome=error kind=%s attempt=%d", type(error).__name__, attempt + 1)
        if attempt + 1 < SEND_ATTEMPTS:
            await asyncio.sleep(RETRY_DELAY_SECONDS * 2 ** attempt)
    return False


async def dispatch_alerts(items: Sequence[AlertItem]) -> None:
    """Background task: send the digest when configured and outside the cooldown.

    Fails closed: with no cooldown store or a failing one, nothing is sent. The
    items of a skipped digest are not queued: they are new only once.
    Never raises, so a failure cannot surface in the request that scheduled it.
    """
    settings = alert_settings_from_config()
    if settings is None or not items:
        return
    try:
        store = get_cooldown_store()
        if store is None:
            logger.warning("alert_email outcome=skipped reason=no_cooldown_store items=%d", len(items))
            return
        if not await store.acquire(settings.cooldown_seconds):
            logger.info("alert_email outcome=skipped reason=cooldown items=%d", len(items))
            return
        await send_digest(settings, items)
    except CooldownStoreError:
        logger.warning("alert_email outcome=skipped reason=cooldown_store_unavailable items=%d", len(items))
    except Exception:
        logger.exception("alert_email outcome=failed")
