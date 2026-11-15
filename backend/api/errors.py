"""
Error responses of the API.

Every error raised by the application has the body
`{"detail": {"code": "<stable_code>", "message": "<short English text>"}}`.
Clients map the stable `code` to their own (translated) text; `message` is a
developer hint and is not meant to be displayed. Request validation errors
(422) are a list of `{loc, msg, type}`, FastAPI's format without the rejected input.
"""
from typing import Any

from fastapi import HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

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
STREAM_LIMIT_REACHED = "stream_limit_reached"
AUTH_INVALID_CREDENTIALS = "auth_invalid_credentials"
AUTH_REQUIRED = "auth_required"
AUTH_TOKEN_INVALID = "auth_token_invalid"
AUTH_TOKEN_EXPIRED = "auth_token_expired"


def validation_error_handler(_request: Request, exc: Exception) -> JSONResponse:
    """422 response listing `{loc, msg, type}` for each error, without the rejected input.

    FastAPI's default body echoes the rejected value (`input`): a password sent
    to the login endpoint would come back in the response. A lone surrogate in
    that echo also makes the default handler fail with a 500.
    """
    if not isinstance(exc, RequestValidationError):
        raise exc
    errors = [
        {"loc": list(error["loc"]), "msg": error["msg"], "type": error["type"]}
        for error in exc.errors()
    ]
    return JSONResponse(status_code=422, content={"detail": errors})


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
