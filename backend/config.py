"""
Configuration management for ChimeraFlow Backend
Follows AGENTS.md §7: No fallback values, fail fast on missing required vars
"""
import os
from typing import Optional


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

    Args:
        name: Variable name.

    Returns:
        Variable value or None if not set.
    """
    return os.getenv(name)


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

# Rate Limiting (None until the rate limiter is configured)
RATE_LIMIT_PER_IP = _optional_int("RATE_LIMIT_PER_IP")
RATE_LIMIT_WINDOW_SECONDS = _optional_int("RATE_LIMIT_WINDOW_SECONDS")

# LiteLLM (optional - feature disabled if not set)
LITELLM_API_KEY = optional_env("LITELLM_API_KEY")
LITELLM_BUDGET_USD = _optional_float("LITELLM_BUDGET_USD")
