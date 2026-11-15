"""
Configuration management for ChimeraFlow Backend
Follows AGENTS.md §7: No fallback values, fail fast on missing required vars
"""
import math
import os
import re
from ipaddress import IPv4Network, IPv6Network, ip_network
from typing import Optional, Tuple, Union

from auth.credentials import normalize_email
from auth.passwords import PasswordHash, parse_password_hash

IPNetwork = Union[IPv4Network, IPv6Network]


def require_env(name: str, description: str) -> str:
    """Require an environment variable. Fails fast if missing.

    Args:
        name: Variable name.
        description: Human-readable description of what this variable is for.

    Returns:
        Variable value.

    Raises:
        ValueError: If variable is not set.
    """
    value = os.getenv(name)
    if value is None:
        raise ValueError(
            f"Required environment variable '{name}' is not set.\n"
            f"Purpose: {description}\n"
            f"Set it in .env file or via Doppler."
        )
    return value


def optional_env(name: str) -> Optional[str]:
    """Get an optional environment variable.

    An empty value is unset: Doppler and compose pass declared-but-empty
    variables, and an empty API key must disable a feature, not enable it.

    Args:
        name: Variable name.

    Returns:
        Variable value, or None if unset or empty.
    """
    return os.getenv(name) or None


def _optional_int(name: str) -> Optional[int]:
    """Parse an optional integer environment variable.

    Args:
        name: Variable name.

    Returns:
        Parsed integer, or None if the variable is not set.

    Raises:
        ValueError: If the variable is set but is not an integer.
    """
    value = optional_env(name)
    if value is None:
        return None
    try:
        return int(value)
    except ValueError as exc:
        raise ValueError(f"Environment variable '{name}' must be an integer, got '{value}'") from exc


def _optional_float(name: str) -> Optional[float]:
    """Parse an optional float environment variable.

    Args:
        name: Variable name.

    Returns:
        Parsed float, or None if the variable is not set.

    Raises:
        ValueError: If the variable is set but is not a number.
    """
    value = optional_env(name)
    if value is None:
        return None
    try:
        return float(value)
    except ValueError as exc:
        raise ValueError(f"Environment variable '{name}' must be a number, got '{value}'") from exc


# Backend Configuration (None when unset: callers branch on None)
NODE_ENV = optional_env("BACKEND_NODE_ENV")
PORT = _optional_int("BACKEND_PORT")
LOG_LEVEL = optional_env("BACKEND_LOG_LEVEL")

# CORS (comma-separated list of allowed origins)
CORS_ORIGINS = require_env("CORS_ORIGINS", "Comma-separated list of allowed CORS origins")

# Redis (required for rate limiting, optional in test environment)
# In test environment, features that depend on Redis are disabled
REDIS_URL = (
    optional_env("REDIS_URL")
    if NODE_ENV == "test"
    else require_env("REDIS_URL", "Redis connection for rate limiting and cache")
)

# Data Directory (read-only synthetic data files)
DATA_DIR = require_env("DATA_DIR", "Directory containing the synthetic data source files")

def normalize_database_url(url: str) -> str:
    """Select the psycopg 3 driver for PostgreSQL URLs.

    Neon and Doppler provide `postgresql://...`, which SQLAlchemy resolves to
    the psycopg2 driver (not installed). This is the only place that rewrites it.

    Args:
        url: Database URL as configured.

    Returns:
        URL using the `postgresql+psycopg` driver for PostgreSQL, unchanged otherwise.
    """
    for prefix in ("postgresql://", "postgres://"):
        if url.startswith(prefix):
            return "postgresql+psycopg://" + url[len(prefix):]
    return url


def get_database_url() -> str:
    """Read DATABASE_URL (required) and normalize it for SQLAlchemy.

    Returns:
        SQLAlchemy database URL.

    Raises:
        ValueError: If DATABASE_URL is not set.
    """
    return normalize_database_url(require_env("DATABASE_URL", "SQLAlchemy database connection string"))


# Access reader: explicit choice, no fallback from one reader to the other
ACCESS_READERS = ("mdbtools", "access-parser")


def _require_access_reader() -> str:
    """Read the ACCESS_READER setting and check it is a supported reader.

    Returns:
        "mdbtools" or "access-parser".

    Raises:
        ValueError: If the variable is missing or has another value.
    """
    value = require_env(
        "ACCESS_READER",
        f"Reader for .mdb files, one of: {', '.join(ACCESS_READERS)}",
    )
    if value not in ACCESS_READERS:
        raise ValueError(
            f"Environment variable 'ACCESS_READER' must be one of "
            f"{', '.join(ACCESS_READERS)}, got '{value}'"
        )
    return value


ACCESS_READER = _require_access_reader()

def _require_positive_int(name: str, description: str) -> int:
    """Read a required environment variable as a strictly positive integer.

    Args:
        name: Variable name.
        description: Human-readable description of what this variable is for.

    Returns:
        Parsed integer.

    Raises:
        ValueError: If the variable is missing, not an integer, or not positive.
    """
    raw = require_env(name, description)
    try:
        value = int(raw)
    except ValueError as exc:
        raise ValueError(f"Environment variable '{name}' must be an integer, got '{raw}'") from exc
    if value < 1:
        raise ValueError(f"Environment variable '{name}' must be at least 1, got '{raw}'")
    return value


def _parse_trusted_proxies(raw: Optional[str]) -> Tuple[IPNetwork, ...]:
    """Parse the comma-separated TRUSTED_PROXIES list (addresses or CIDR networks).

    Args:
        raw: Raw variable value, or None when unset.

    Returns:
        Networks of the proxies allowed to set X-Forwarded-For (empty when unset).

    Raises:
        ValueError: If an entry is not an IP address or a CIDR network.
    """
    if raw is None:
        return ()
    networks = []
    for entry in (item.strip() for item in raw.split(",")):
        if not entry:
            continue
        try:
            networks.append(ip_network(entry, strict=False))
        except ValueError as exc:
            raise ValueError(
                f"Environment variable 'TRUSTED_PROXIES' has an invalid entry '{entry}' "
                "(expected an IP address or a CIDR network)"
            ) from exc
    return tuple(networks)


# Rate limiting: mutation endpoints are limited per client IP
RATE_LIMIT_PER_IP = _require_positive_int(
    "RATE_LIMIT_PER_IP", "Mutation requests allowed per client IP and window"
)
RATE_LIMIT_WINDOW_SECONDS = _require_positive_int(
    "RATE_LIMIT_WINDOW_SECONDS", "Length in seconds of the rate limit window"
)
# NL->rule requests cost money, so they get their own (stricter) limit.
# When unset it is derived from RATE_LIMIT_PER_IP (a fifth, at least 1): a deliberate
# exception to AGENTS.md §7, see docs/decisions/DECISIONS_LOG.md.
_RATE_LIMIT_NL_PER_IP = _optional_int("RATE_LIMIT_NL_PER_IP")
RATE_LIMIT_NL_PER_IP = (
    _RATE_LIMIT_NL_PER_IP if _RATE_LIMIT_NL_PER_IP is not None else max(1, RATE_LIMIT_PER_IP // 5)
)
if RATE_LIMIT_NL_PER_IP < 1:
    raise ValueError("Environment variable 'RATE_LIMIT_NL_PER_IP' must be at least 1")

# Login attempts are limited per client IP, more strictly than the mutations (each
# attempt costs a scrypt hash). When unset: half of RATE_LIMIT_PER_IP, at least 3
# (a deliberate exception to AGENTS.md §7, see docs/decisions/DECISIONS_LOG.md).
_RATE_LIMIT_LOGIN_PER_IP = _optional_int("RATE_LIMIT_LOGIN_PER_IP")
RATE_LIMIT_LOGIN_PER_IP = (
    _RATE_LIMIT_LOGIN_PER_IP
    if _RATE_LIMIT_LOGIN_PER_IP is not None
    else max(3, RATE_LIMIT_PER_IP // 2)
)
if RATE_LIMIT_LOGIN_PER_IP < 1:
    raise ValueError("Environment variable 'RATE_LIMIT_LOGIN_PER_IP' must be at least 1")

# Proxies whose X-Forwarded-For header is trusted (Traefik). Without it the
# socket peer is the client address.
TRUSTED_PROXIES = _parse_trusted_proxies(optional_env("TRUSTED_PROXIES"))

# Limiter storage: memory only in the explicit test environment, Redis otherwise
# (REDIS_URL is required outside tests, see above)
RATE_LIMIT_STORAGE_URI = "memory://" if NODE_ENV == "test" else REDIS_URL

# Demo account authentication (all required, no fallback: a missing secret must
# stop the process, not open the API)
MIN_AUTH_SECRET_BYTES = 32


def _require_non_empty(name: str, description: str) -> str:
    """Read a required environment variable that must not be blank.

    Raises:
        ValueError: If the variable is missing or blank.
    """
    value = require_env(name, description)
    if value.strip() == "":
        raise ValueError(f"Environment variable '{name}' must not be empty")
    return value


def _require_auth_secret() -> str:
    """Read AUTH_TOKEN_SECRET and check its length.

    Raises:
        ValueError: If the secret is missing or shorter than MIN_AUTH_SECRET_BYTES bytes.
    """
    value = _require_non_empty("AUTH_TOKEN_SECRET", "Secret signing the access tokens (random, 32 bytes or more)")
    if len(value.encode("utf-8")) < MIN_AUTH_SECRET_BYTES:
        raise ValueError(
            f"Environment variable 'AUTH_TOKEN_SECRET' must be at least {MIN_AUTH_SECRET_BYTES} bytes long"
        )
    return value


def _require_password_hash() -> PasswordHash:
    """Read and parse DEMO_LOGIN_PASSWORD_HASH.

    Raises:
        ValueError: If the variable is missing or is not a valid hash (never echoed).
    """
    value = _require_non_empty(
        "DEMO_LOGIN_PASSWORD_HASH",
        "scrypt hash of the demo account password (python -m auth.hash_password)",
    )
    try:
        return parse_password_hash(value.strip())
    except ValueError as exc:
        raise ValueError(f"Environment variable 'DEMO_LOGIN_PASSWORD_HASH' is invalid: {exc}") from exc


AUTH_TOKEN_SECRET = _require_auth_secret()
DEMO_LOGIN_EMAIL = normalize_email(_require_non_empty("DEMO_LOGIN_EMAIL", "Email of the demo account"))
DEMO_LOGIN_PASSWORD_HASH = _require_password_hash()

# LiteLLM NL->rule conversion (optional: the feature is disabled unless the
# API key, proxy URL, model and budget are all set)
LITELLM_API_KEY = optional_env("LITELLM_API_KEY")
LITELLM_BASE_URL = optional_env("LITELLM_BASE_URL")
LITELLM_MODEL = optional_env("LITELLM_MODEL")
LITELLM_BUDGET_USD = _optional_float("LITELLM_BUDGET_USD")
# A cap that is NaN (every comparison false), infinite or not positive is no cap
if LITELLM_BUDGET_USD is not None and not (math.isfinite(LITELLM_BUDGET_USD) and LITELLM_BUDGET_USD > 0):
    raise ValueError("Environment variable 'LITELLM_BUDGET_USD' must be a finite number greater than 0")


# E-mail alert digest through Resend (optional: disabled unless the API key, the
# sender and at least one recipient are all set)
MAX_ALERT_RECIPIENTS = 5
_EMAIL_ADDRESS = re.compile(r"^[^@\s<>,;]+@[^@\s<>,;]+\.[^@\s<>,;]+$")
# "Name <address>" or a bare address, on one line
_EMAIL_SENDER = re.compile(r"^(?:[^<>\r\n@]{1,100} )?<?[^@\s<>,;]+@[^@\s<>,;]+\.[^@\s<>,;]+>?$")


def _parse_alert_recipients(raw: Optional[str]) -> Tuple[str, ...]:
    """Parse the comma-separated ALERT_EMAIL_TO list.

    Args:
        raw: Raw variable value, or None when unset.

    Returns:
        Recipient addresses (empty when unset).

    Raises:
        ValueError: If an entry is not an e-mail address or there are too many (never echoed).
    """
    if raw is None:
        return ()
    recipients = tuple(item.strip() for item in raw.split(",") if item.strip())
    if len(recipients) > MAX_ALERT_RECIPIENTS:
        raise ValueError(f"Environment variable 'ALERT_EMAIL_TO' accepts at most {MAX_ALERT_RECIPIENTS} addresses")
    if not all(_EMAIL_ADDRESS.match(address) for address in recipients):
        raise ValueError("Environment variable 'ALERT_EMAIL_TO' must hold comma-separated e-mail addresses")
    return recipients


def _optional_alert_sender() -> Optional[str]:
    """Read ALERT_EMAIL_FROM (an address or "Name <address>").

    Raises:
        ValueError: If the value is not a one-line sender (never echoed).
    """
    value = optional_env("ALERT_EMAIL_FROM")
    if value is None:
        return None
    if not _EMAIL_SENDER.match(value.strip()):
        raise ValueError("Environment variable 'ALERT_EMAIL_FROM' must be an e-mail address")
    return value.strip()


RESEND_API_KEY = optional_env("RESEND_API_KEY")
ALERT_EMAIL_FROM = _optional_alert_sender()
ALERT_EMAIL_TO = _parse_alert_recipients(optional_env("ALERT_EMAIL_TO"))
