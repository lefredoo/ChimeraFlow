"""
Shared pytest configuration.

Sets the environment variables required by config.py BEFORE any test module
imports the application, and registers the Hypothesis profiles.
"""
import os
from pathlib import Path
from typing import Iterator

import pytest
from fastapi.testclient import TestClient
from hypothesis import settings

from auth.passwords import hash_password
from tests.demo_account import TEST_DEMO_EMAIL, TEST_DEMO_PASSWORD

# Test-only environment. Assigned (not setdefault) so tests never reach a
# developer's real database or data directory.
os.environ["BACKEND_NODE_ENV"] = "test"
os.environ["DATA_DIR"] = str(Path(__file__).resolve().parents[2] / "data")
os.environ["DATABASE_URL"] = "sqlite://"
os.environ["CORS_ORIGINS"] = "http://localhost:3000"
# Pure Python reader: runs everywhere. Tests of the mdbtools reader build it explicitly.
os.environ["ACCESS_READER"] = "access-parser"
# High enough that no functional test hits the limit; the 429 tests lower it explicitly.
# BACKEND_NODE_ENV=test makes the limiter use memory storage (explicit, not a fallback).
os.environ["RATE_LIMIT_PER_IP"] = "1000"
os.environ["RATE_LIMIT_WINDOW_SECONDS"] = "60"
# Demo account of the authentication tests. The values are public test data; the hash
# is computed once per run with a fresh salt, so no hash is committed.
os.environ["AUTH_TOKEN_SECRET"] = "test-only-secret-0123456789abcdef-0123456789abcdef"
os.environ["DEMO_LOGIN_EMAIL"] = TEST_DEMO_EMAIL
os.environ["DEMO_LOGIN_PASSWORD_HASH"] = hash_password(TEST_DEMO_PASSWORD)
# The NL->rule feature is configured per test (settings dependency), never from the environment
for _name in (
    "LITELLM_API_KEY",
    "LITELLM_BASE_URL",
    "LITELLM_MODEL",
    "LITELLM_BUDGET_USD",
    "TRUSTED_PROXIES",
    "RESEND_API_KEY",  # the e-mail alert is enabled per test
    "ALERT_EMAIL_FROM",
    "ALERT_EMAIL_TO",
    "RATE_LIMIT_NL_PER_IP",  # unset: the derived default is what test_rate_limit.py checks
    "RATE_LIMIT_LOGIN_PER_IP",  # unset: the derived default is what test_auth.py checks
):
    os.environ.pop(_name, None)

settings.register_profile("dev", max_examples=100, deadline=None)
settings.register_profile("ci", max_examples=500, deadline=5000)


@pytest.fixture
def anonymous_client() -> Iterator[TestClient]:
    """Test client without credentials, with a fresh in-memory database.

    The tables are created here (production runs `alembic upgrade head`
    before startup; test_migrations.py checks both give the same schema).
    Entering the client runs the application lifespan, which seeds the
    predefined rules, exactly like a real startup.
    """
    from api.rate_limit import limiter
    from main import app
    from models.base import Base, engine

    limiter.reset()
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    with TestClient(app) as client:
        yield client
    Base.metadata.drop_all(bind=engine)


@pytest.fixture
def auth_token() -> str:
    """Valid access token of the demo account."""
    import config
    from auth.tokens import issue_token

    return issue_token(config.DEMO_LOGIN_EMAIL, config.AUTH_TOKEN_SECRET)


@pytest.fixture
def api_client(anonymous_client: TestClient, auth_token: str) -> TestClient:
    """Test client authenticated as the demo account (every /api/v1 endpoint needs a token)."""
    anonymous_client.headers["Authorization"] = f"Bearer {auth_token}"
    return anonymous_client
