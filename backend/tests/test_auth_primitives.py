"""
Password hashing, signed tokens and the hash CLI (no application, no configuration).
"""
import io
import os
import subprocess
import sys
from pathlib import Path

import pytest

from auth.credentials import credentials_match, normalize_email
from auth.hash_password import main as hash_cli
from auth.passwords import hash_password, parse_password_hash, verify_password
from auth.tokens import ExpiredTokenError, InvalidTokenError, issue_token, verify_token

BACKEND_DIR = Path(__file__).resolve().parent.parent
SECRET = "unit-test-secret-0123456789abcdef-0123456789"
PASSWORD = "correct horse battery"


@pytest.fixture(scope="module")
def encoded_hash() -> str:
    return hash_password(PASSWORD)


class TestPasswords:
    def test_should_verify_the_password_when_it_is_the_hashed_one(self, encoded_hash):
        assert verify_password(PASSWORD, parse_password_hash(encoded_hash)) is True

    def test_should_reject_the_password_when_it_differs(self, encoded_hash):
        assert verify_password("another password", parse_password_hash(encoded_hash)) is False

    def test_should_produce_different_hashes_when_hashing_twice(self, encoded_hash):
        assert hash_password(PASSWORD) != encoded_hash

    def test_should_describe_its_parameters_when_hashing(self, encoded_hash):
        assert encoded_hash.startswith("scrypt:32768:8:1:")

    @pytest.mark.parametrize(
        "malformed",
        [
            "",
            "plain",
            "bcrypt:32768:8:1:AAAAAAAAAAAAAAAAAAAAAA:AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA",
            "scrypt:32768:8:1:AAAAAAAAAAAAAAAAAAAAAA",
            "scrypt:abc:8:1:AAAAAAAAAAAAAAAAAAAAAA:AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA",
            "scrypt:32767:8:1:AAAAAAAAAAAAAAAAAAAAAA:AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA",
            "scrypt:1073741824:8:1:AAAAAAAAAAAAAAAAAAAAAA:AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA",
            "scrypt:32768:99:1:AAAAAAAAAAAAAAAAAAAAAA:AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA",
            "scrypt:32768:8:1:!!!!:AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA",
            "scrypt:32768:8:1:AA:AA",
        ],
    )
    def test_should_raise_when_the_stored_hash_is_malformed(self, malformed):
        with pytest.raises(ValueError):
            parse_password_hash(malformed)

    def test_should_not_echo_the_value_when_the_stored_hash_is_malformed(self):
        with pytest.raises(ValueError) as error:
            parse_password_hash("scrypt:secret-looking-value")

        assert "secret-looking-value" not in str(error.value)


class TestCredentials:
    def test_should_match_when_email_and_password_are_the_expected_ones(self, encoded_hash):
        assert credentials_match("Demo@Example.test ", PASSWORD, "demo@example.test", parse_password_hash(encoded_hash))

    def test_should_not_match_when_only_the_email_is_wrong(self, encoded_hash):
        assert not credentials_match("x@example.test", PASSWORD, "demo@example.test", parse_password_hash(encoded_hash))

    def test_should_not_match_when_only_the_password_is_wrong(self, encoded_hash):
        assert not credentials_match("demo@example.test", "nope", "demo@example.test", parse_password_hash(encoded_hash))

    def test_should_lowercase_and_trim_when_normalizing_an_email(self):
        assert normalize_email("  Demo@Example.TEST ") == "demo@example.test"


class TestTokens:
    def test_should_return_the_claims_when_the_token_is_valid(self):
        token = issue_token("demo@example.test", SECRET, now=1000)

        claims = verify_token(token, SECRET, now=1001)

        assert (claims.subject, claims.issued_at, claims.expires_at) == ("demo@example.test", 1000, 4600)

    def test_should_raise_expired_when_the_expiry_is_reached(self):
        token = issue_token("demo@example.test", SECRET, now=1000, ttl_seconds=60)

        with pytest.raises(ExpiredTokenError):
            verify_token(token, SECRET, now=1060)

    def test_should_accept_the_token_when_it_is_one_second_before_expiry(self):
        token = issue_token("demo@example.test", SECRET, now=1000, ttl_seconds=60)

        assert verify_token(token, SECRET, now=1059).subject == "demo@example.test"

    def test_should_raise_invalid_when_the_secret_differs(self):
        token = issue_token("demo@example.test", SECRET, now=1000)

        with pytest.raises(InvalidTokenError):
            verify_token(token, SECRET + "x", now=1001)

    def test_should_raise_invalid_when_an_expired_token_is_signed_with_another_secret(self):
        token = issue_token("demo@example.test", SECRET + "x", now=1000, ttl_seconds=60)

        with pytest.raises(InvalidTokenError):
            verify_token(token, SECRET, now=5000)

    @pytest.mark.parametrize("garbage", ["", ".", "a.b.c", "abc", "é.é", "....", "AA.AA", " . "])
    def test_should_raise_invalid_when_the_token_is_malformed(self, garbage):
        with pytest.raises(InvalidTokenError):
            verify_token(garbage, SECRET, now=1001)


class TestHashCli:
    def test_should_print_a_hash_that_verifies_when_the_password_comes_from_stdin(self):
        stdout = io.StringIO()

        code = hash_cli(stdin=io.StringIO(PASSWORD + "\n"), stdout=stdout, stderr=io.StringIO())

        assert code == 0
        assert verify_password(PASSWORD, parse_password_hash(stdout.getvalue().strip()))

    def test_should_fail_when_the_password_is_too_short(self):
        stdout = io.StringIO()

        code = hash_cli(stdin=io.StringIO("short\n"), stdout=stdout, stderr=io.StringIO())

        assert (code, stdout.getvalue()) == (1, "")

    def test_should_round_trip_when_run_as_a_module(self):
        result = subprocess.run(
            [sys.executable, "-m", "auth.hash_password"],
            cwd=BACKEND_DIR, input=PASSWORD + "\n", capture_output=True, text=True,
            env={**os.environ},
        )

        assert result.returncode == 0, result.stderr
        assert verify_password(PASSWORD, parse_password_hash(result.stdout.strip()))
