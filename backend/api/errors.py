"""
Error responses of the API.

Every error raised by the application has the body
`{"detail": {"code": "<stable_code>", "message": "<short English text>"}}`.
Clients map the stable `code` to their own (translated) text; `message` is a
developer hint and is not meant to be displayed. Request validation errors
(422 from FastAPI) keep FastAPI's own list format.
"""
from typing import Any

from fastapi import HTTPException

# Stable error codes
RULE_ALREADY_EXISTS = "rule_already_exists"
RULE_NOT_FOUND = "rule_not_found"
INVALID_STATUS = "invalid_status"
INVALID_SEVERITY = "invalid_severity"
SOURCE_NOT_FOUND = "source_not_found"
SOURCE_FETCH_FAILED = "source_fetch_failed"
RATE_LIMIT_EXCEEDED = "rate_limit_exceeded"
RATE_LIMIT_UNAVAILABLE = "rate_limit_unavailable"
NL_FEATURE_DISABLED = "nl_feature_disabled"
NL_BUDGET_EXCEEDED = "nl_budget_exceeded"
NL_BUDGET_UNAVAILABLE = "nl_budget_unavailable"
NL_PROVIDER_ERROR = "nl_provider_error"
NL_CONVERSION_FAILED = "nl_conversion_failed"


def error_detail(code: str, message: str, **extra: Any) -> dict:
    """Build the `detail` object of an error response.

    Args:
        code: Stable machine-readable error code.
        message: Short English developer message (no user text, no secret).
        **extra: Additional JSON-serializable fields (e.g. `fallback_rules`).

    Returns:
        The detail dictionary.
    """
    return {"code": code, "message": message, **extra}


def api_error(status_code: int, code: str, message: str, **extra: Any) -> HTTPException:
    """Build an HTTPException whose detail follows the error body convention.

    Args:
        status_code: HTTP status code.
        code: Stable machine-readable error code.
        message: Short English developer message.
        **extra: Additional JSON-serializable fields.

    Returns:
        Exception to raise.
    """
    return HTTPException(status_code=status_code, detail=error_detail(code, message, **extra))
