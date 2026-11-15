"""
Check of the demo account credentials.

Does not import `config`: the expected values are passed by the caller.
"""
import hmac

from auth.passwords import PasswordHash, verify_password


def normalize_email(email: str) -> str:
    """Canonical form of an email for comparison (trimmed, lowercase)."""
    return email.strip().lower()


def credentials_match(
    email: str,
    password: str,
    expected_email: str,
    expected_hash: PasswordHash,
) -> bool:
    """Tell whether the credentials are the demo account's.

    The password hash is computed even when the email is wrong, and both checks
    are constant time, so neither the answer nor the response time tells which
    of the two was wrong (no user enumeration).

    Args:
        email: Email sent by the client.
        password: Password sent by the client.
        expected_email: Normalized email of the demo account.
        expected_hash: Parsed hash of the demo account password.

    Returns:
        True when both match.
    """
    email_matches = hmac.compare_digest(
        normalize_email(email).encode("utf-8", errors="surrogatepass"), expected_email.encode("utf-8")
    )
    password_matches = verify_password(password, expected_hash)
    return email_matches and password_matches
