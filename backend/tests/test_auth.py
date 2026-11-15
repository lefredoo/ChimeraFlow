"""
Authentication: demo account login, token protection of /api/v1, configuration.

The demo account of the tests is defined in conftest.py.
"""
import base64
import json
import logging
import os
import re
import subprocess
import sys
import time
from pathlib import Path

import pytest
from fastapi.routing import APIRoute

import config
from auth.tokens import issue_token
from main import app, docs_urls
from tests.demo_account import TEST_DEMO_EMAIL, TEST_DEMO_PASSWORD

LOGIN_URL = "/api/v1/auth/login"
ME_URL = "/api/v1/auth/me"
RULES_URL = "/api/v1/rules"
BACKEND_DIR = Path(__file__).resolve().parent.parent
PUBLIC_API_PATHS = {LOGIN_URL}

# Every route under /api/v1 except login, as (method, path with placeholders filled)
PROTECTED_ROUTES = sorted(
    (method, re.sub(r"\{[^}]+\}", "x", route.path))
    for route in app.routes
    if isinstance(route, APIRoute) and route.path.startswith("/api/v1/") and route.path not in PUBLIC_API_PATHS
    for method in route.methods
)


def _credentials(email: str = TEST_DEMO_EMAIL, password: str = TEST_DEMO_PASSWORD) -> dict:
    return {"email": email, "password": password}


def _bearer(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def _b64(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


class TestLogin:
    def test_should_return_a_bearer_token_when_credentials_are_correct(self, anonymous_client):
        response = anonymous_client.post(LOGIN_URL, json=_credentials())

        body = response.json()
        assert (response.status_code, body["token_type"], body["expires_in"]) == (200, "bearer", 3600)

    def test_should_accept_the_token_when_calling_a_protected_endpoint(self, anonymous_client):
        token = anonymous_client.post(LOGIN_URL, json=_credentials()).json()["access_token"]

        response = anonymous_client.get(RULES_URL, headers=_bearer(token))

        assert response.status_code == 200

    def test_should_accept_the_login_when_the_email_differs_in_case_and_spaces(self, anonymous_client):
        response = anonymous_client.post(LOGIN_URL, json=_credentials(email=f"  {TEST_DEMO_EMAIL.upper()} "))

        assert response.status_code == 200

    def test_should_return_401_with_a_stable_code_when_the_password_is_wrong(self, anonymous_client):
        response = anonymous_client.post(LOGIN_URL, json=_credentials(password="wrong password"))

        assert response.status_code == 401
        assert response.json()["detail"]["code"] == "auth_invalid_credentials"

    def test_should_return_the_same_response_when_the_email_is_unknown_or_the_password_is_wrong(
        self, anonymous_client
    ):
        wrong_password = anonymous_client.post(LOGIN_URL, json=_credentials(password="wrong password"))

        unknown_email = anonymous_client.post(LOGIN_URL, json=_credentials(email="nobody@example.test"))

        assert (unknown_email.status_code, unknown_email.json()) == (
            wrong_password.status_code,
            wrong_password.json(),
        )

    def test_should_return_422_when_the_body_has_an_unexpected_field(self, anonymous_client):
        response = anonymous_client.post(LOGIN_URL, json={**_credentials(), "admin": True})

        assert response.status_code == 422

    def test_should_return_422_when_the_password_is_too_long(self, anonymous_client):
        response = anonymous_client.post(LOGIN_URL, json=_credentials(password="x" * 257))

        assert response.status_code == 422

    def test_should_not_fail_with_a_server_error_when_the_password_contains_a_lone_surrogate(
        self, anonymous_client
    ):
        response = anonymous_client.post(
            LOGIN_URL,
            content=b'{"email": "a@example.test", "password": "\\ud800"}',
            headers={"Content-Type": "application/json"},
        )

        assert response.status_code == 422

    def test_should_not_echo_the_password_when_the_body_is_rejected(self, anonymous_client):
        response = anonymous_client.post(LOGIN_URL, json={**_credentials(password="a very secret guess"), "x": 1})

        assert "a very secret guess" not in response.text

    def test_should_not_log_the_credentials_when_logging_in(self, anonymous_client, caplog):
        with caplog.at_level(logging.DEBUG):
            anonymous_client.post(LOGIN_URL, json=_credentials(password="a very secret guess"))

        assert "a very secret guess" not in caplog.text
        assert TEST_DEMO_EMAIL not in caplog.text

    def test_should_not_echo_the_credentials_when_the_login_is_refused(self, anonymous_client):
        response = anonymous_client.post(LOGIN_URL, json=_credentials(password="a very secret guess"))

        assert "a very secret guess" not in response.text


class TestLoginRateLimit:
    def test_should_return_429_when_login_attempts_exceed_the_limit(self, anonymous_client, monkeypatch):
        monkeypatch.setattr(config, "RATE_LIMIT_LOGIN_PER_IP", 2)

        statuses = [
            anonymous_client.post(LOGIN_URL, json=_credentials(password="wrong password")).status_code
            for _ in range(3)
        ]

        assert statuses == [401, 401, 429]

    def test_should_refuse_the_correct_password_when_the_limit_is_exceeded(self, anonymous_client, monkeypatch):
        monkeypatch.setattr(config, "RATE_LIMIT_LOGIN_PER_IP", 1)
        anonymous_client.post(LOGIN_URL, json=_credentials(password="wrong password"))

        response = anonymous_client.post(LOGIN_URL, json=_credentials())

        assert response.status_code == 429

    def test_should_send_retry_after_when_login_is_limited(self, anonymous_client, monkeypatch):
        monkeypatch.setattr(config, "RATE_LIMIT_LOGIN_PER_IP", 1)
        anonymous_client.post(LOGIN_URL, json=_credentials(password="wrong password"))

        response = anonymous_client.post(LOGIN_URL, json=_credentials())

        assert 1 <= int(response.headers["Retry-After"]) <= config.RATE_LIMIT_WINDOW_SECONDS

    def test_should_expose_retry_after_to_the_frontend_when_login_is_limited(self, anonymous_client, monkeypatch):
        monkeypatch.setattr(config, "RATE_LIMIT_LOGIN_PER_IP", 1)
        anonymous_client.post(LOGIN_URL, json=_credentials(password="wrong password"))

        response = anonymous_client.post(
            LOGIN_URL, json=_credentials(), headers={"Origin": "http://localhost:3000"}
        )

        assert "Retry-After" in response.headers["Access-Control-Expose-Headers"]

    def test_should_derive_a_stricter_login_limit_when_it_is_not_configured(self):
        assert config.RATE_LIMIT_LOGIN_PER_IP == 500  # 1000 (RATE_LIMIT_PER_IP of conftest.py) // 2


class TestProtection:
    @pytest.mark.parametrize("method, path", PROTECTED_ROUTES)
    def test_should_return_401_when_an_api_endpoint_is_called_without_a_token(
        self, anonymous_client, method, path
    ):
        response = anonymous_client.request(method, path)

        assert response.status_code == 401
        assert response.json()["detail"]["code"] == "auth_required"

    def test_should_ask_for_a_bearer_token_when_the_request_is_unauthenticated(self, anonymous_client):
        response = anonymous_client.get(RULES_URL)

        assert response.headers["WWW-Authenticate"] == "Bearer"

    def test_should_return_auth_required_when_the_scheme_is_not_bearer(self, anonymous_client):
        response = anonymous_client.get(RULES_URL, headers={"Authorization": "Basic ZGVtbzpkZW1v"})

        assert response.json()["detail"]["code"] == "auth_required"

    def test_should_return_200_when_an_endpoint_is_called_with_a_valid_token(self, anonymous_client, auth_token):
        response = anonymous_client.get(RULES_URL, headers=_bearer(auth_token))

        assert response.status_code == 200

    def test_should_return_token_expired_when_the_token_is_past_its_expiry(self, anonymous_client):
        expired = issue_token(config.DEMO_LOGIN_EMAIL, config.AUTH_TOKEN_SECRET, now=time.time() - 7200)

        response = anonymous_client.get(RULES_URL, headers=_bearer(expired))

        assert response.status_code == 401
        assert response.json()["detail"]["code"] == "auth_token_expired"

    def test_should_return_token_invalid_when_the_signature_is_tampered_with(self, anonymous_client, auth_token):
        payload, signature = auth_token.split(".")
        tampered = f"{payload}.{signature[:-2]}AA"

        response = anonymous_client.get(RULES_URL, headers=_bearer(tampered))

        assert response.json()["detail"]["code"] == "auth_token_invalid"

    def test_should_return_token_invalid_when_the_payload_is_swapped_under_the_old_signature(
        self, anonymous_client, auth_token
    ):
        _payload, signature = auth_token.split(".")
        forged_claims = {"v": 1, "sub": config.DEMO_LOGIN_EMAIL, "iat": 0, "exp": 9_999_999_999}
        forged = _b64(json.dumps(forged_claims).encode())

        response = anonymous_client.get(RULES_URL, headers=_bearer(f"{forged}.{signature}"))

        assert response.json()["detail"]["code"] == "auth_token_invalid"

    def test_should_return_token_invalid_when_the_token_is_signed_with_another_secret(self, anonymous_client):
        foreign = issue_token(config.DEMO_LOGIN_EMAIL, "another-secret-0123456789abcdef-0123456789")

        response = anonymous_client.get(RULES_URL, headers=_bearer(foreign))

        assert response.json()["detail"]["code"] == "auth_token_invalid"

    def test_should_return_token_invalid_when_the_token_is_garbage(self, anonymous_client):
        response = anonymous_client.get(RULES_URL, headers=_bearer("not-a-token"))

        assert response.json()["detail"]["code"] == "auth_token_invalid"

    def test_should_return_token_invalid_when_the_token_belongs_to_another_account(self, anonymous_client):
        other = issue_token("someone@example.test", config.AUTH_TOKEN_SECRET)

        response = anonymous_client.get(RULES_URL, headers=_bearer(other))

        assert response.json()["detail"]["code"] == "auth_token_invalid"

    def test_should_keep_health_public_when_no_token_is_sent(self, anonymous_client):
        assert anonymous_client.get("/health").status_code == 200


class TestMe:
    def test_should_return_the_account_email_when_the_token_is_valid(self, api_client):
        response = api_client.get(ME_URL)

        assert response.json() == {"email": TEST_DEMO_EMAIL}

    def test_should_return_401_when_no_token_is_sent(self, anonymous_client):
        assert anonymous_client.get(ME_URL).status_code == 401


class TestCrossOrigin:
    def test_should_allow_the_authorization_header_when_the_frontend_sends_a_preflight(self, anonymous_client):
        response = anonymous_client.options(
            RULES_URL,
            headers={
                "Origin": "http://localhost:3000",
                "Access-Control-Request-Method": "GET",
                "Access-Control-Request-Headers": "authorization",
            },
        )

        assert response.status_code == 200
        assert "authorization" in response.headers["Access-Control-Allow-Headers"].lower()

    def test_should_not_require_a_token_when_the_browser_sends_a_preflight(self, anonymous_client):
        response = anonymous_client.options(
            RULES_URL,
            headers={"Origin": "http://localhost:3000", "Access-Control-Request-Method": "POST"},
        )

        assert response.status_code == 200


class TestDocsExposure:
    def test_should_disable_the_documentation_when_running_in_production(self):
        assert docs_urls("production") == {"docs_url": None, "redoc_url": None, "openapi_url": None}

    @pytest.mark.parametrize("node_env", ["development", "test", None])
    def test_should_keep_the_documentation_when_not_running_in_production(self, node_env):
        assert docs_urls(node_env) == {}


class TestAuthConfiguration:
    @staticmethod
    def _import_config(**changes):
        env = {**os.environ}
        for name, value in changes.items():
            if value is None:
                env.pop(name, None)
            else:
                env[name] = value
        return subprocess.run(
            [sys.executable, "-c", "import config"],
            cwd=BACKEND_DIR, env=env, capture_output=True, text=True,
        )

    @pytest.mark.parametrize("name", ["AUTH_TOKEN_SECRET", "DEMO_LOGIN_EMAIL", "DEMO_LOGIN_PASSWORD_HASH"])
    def test_should_fail_fast_when_a_required_auth_variable_is_missing(self, name):
        result = self._import_config(**{name: None})

        assert result.returncode != 0
        assert name in result.stderr

    @pytest.mark.parametrize("name", ["AUTH_TOKEN_SECRET", "DEMO_LOGIN_EMAIL", "DEMO_LOGIN_PASSWORD_HASH"])
    def test_should_fail_fast_when_a_required_auth_variable_is_blank(self, name):
        result = self._import_config(**{name: "  "})

        assert result.returncode != 0
        assert name in result.stderr

    def test_should_fail_fast_when_the_token_secret_is_too_short(self):
        result = self._import_config(AUTH_TOKEN_SECRET="short")

        assert result.returncode != 0
        assert "at least 32 bytes" in result.stderr

    def test_should_fail_fast_when_the_password_hash_is_malformed(self):
        result = self._import_config(DEMO_LOGIN_PASSWORD_HASH="plain-text-password")

        assert result.returncode != 0
        assert "DEMO_LOGIN_PASSWORD_HASH" in result.stderr

    def test_should_not_print_the_password_hash_when_it_is_malformed(self):
        result = self._import_config(DEMO_LOGIN_PASSWORD_HASH="plain-text-password")

        assert "plain-text-password" not in result.stderr

    def test_should_fail_fast_when_the_login_limit_is_not_positive(self):
        result = self._import_config(RATE_LIMIT_LOGIN_PER_IP="0")

        assert result.returncode != 0
        assert "RATE_LIMIT_LOGIN_PER_IP" in result.stderr
