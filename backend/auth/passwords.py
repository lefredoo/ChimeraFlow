"""
Password hashing with scrypt (hashlib, no dependency).

A hash is one self-describing string, so the parameters can change later
without invalidating stored hashes:

    scrypt:<N>:<r>:<p>:<salt>:<key>

`salt` and `key` are unpadded URL-safe base64. The separator is `:` (not the
`$` of the PHC format) so the value survives shells, compose and Doppler
without escaping.

This module must not import `config`: the hash CLI runs before any
configuration exists.
"""
import base64
import binascii
import hashlib
import hmac
import secrets
from dataclasses import dataclass

SCHEME = "scrypt"

# Parameters of new hashes: 32 MiB of memory per hash (128 * N * r bytes)
DEFAULT_N = 2**15
DEFAULT_R = 8
DEFAULT_P = 1
SALT_BYTES = 16
KEY_BYTES = 32

# Bounds accepted when reading a hash: a bad value cannot make the server
# allocate gigabytes or spin for minutes
MIN_N, MAX_N = 2**14, 2**17
MIN_R, MAX_R = 1, 16
MIN_P, MAX_P = 1, 4
MIN_SALT_BYTES, MAX_SALT_BYTES = 16, 64
MIN_KEY_BYTES, MAX_KEY_BYTES = 16, 64


@dataclass(frozen=True)
class PasswordHash:
    """Parsed form of a stored password hash."""

    n: int
    r: int
    p: int
    salt: bytes
    key: bytes


def _b64encode(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


def _b64decode(text: str) -> bytes:
    """Decode unpadded URL-safe base64, strictly (one text per byte string).

    Raises:
        ValueError: If the text is not canonical unpadded URL-safe base64.
    """
    try:
        data = base64.urlsafe_b64decode(text + "=" * (-len(text) % 4))
    except (binascii.Error, ValueError) as exc:
        raise ValueError("invalid base64") from exc
    if _b64encode(data) != text:
        raise ValueError("non-canonical base64")
    return data


def _derive(password: str, n: int, r: int, p: int, salt: bytes, key_length: int) -> bytes:
    # maxmem: OpenSSL refuses scrypt above 32 MiB by default.
    # surrogatepass: a lone surrogate in a JSON string must not raise (no 500)
    return hashlib.scrypt(
        password.encode("utf-8", errors="surrogatepass"), salt=salt, n=n, r=r, p=p, dklen=key_length, maxmem=256 * n * r
    )


def hash_password(password: str) -> str:
    """Hash a password with a fresh random salt.

    Args:
        password: Clear-text password.

    Returns:
        Self-describing hash string (see module docstring).
    """
    salt = secrets.token_bytes(SALT_BYTES)
    key = _derive(password, DEFAULT_N, DEFAULT_R, DEFAULT_P, salt, KEY_BYTES)
    return ":".join(
        [SCHEME, str(DEFAULT_N), str(DEFAULT_R), str(DEFAULT_P), _b64encode(salt), _b64encode(key)]
    )


def parse_password_hash(encoded: str) -> PasswordHash:
    """Parse and validate a stored hash.

    Args:
        encoded: Hash string produced by `hash_password`.

    Returns:
        The parsed hash.

    Raises:
        ValueError: If the format or a parameter is invalid. The message never
            contains the value.
    """
    parts = encoded.split(":")
    if len(parts) != 6 or parts[0] != SCHEME:
        raise ValueError(f"password hash must have the format {SCHEME}:<N>:<r>:<p>:<salt>:<key>")
    try:
        n, r, p = int(parts[1]), int(parts[2]), int(parts[3])
        salt, key = _b64decode(parts[4]), _b64decode(parts[5])
    except ValueError as exc:
        raise ValueError("password hash has a malformed parameter, salt or key") from exc
    if n & (n - 1) != 0 or not MIN_N <= n <= MAX_N:
        raise ValueError(f"password hash parameter N must be a power of two in [{MIN_N}, {MAX_N}]")
    if not MIN_R <= r <= MAX_R or not MIN_P <= p <= MAX_P:
        raise ValueError("password hash parameter r or p is out of range")
    if not MIN_SALT_BYTES <= len(salt) <= MAX_SALT_BYTES or not MIN_KEY_BYTES <= len(key) <= MAX_KEY_BYTES:
        raise ValueError("password hash salt or key has an unsupported length")
    return PasswordHash(n=n, r=r, p=p, salt=salt, key=key)


def verify_password(password: str, parsed: PasswordHash) -> bool:
    """Check a password against a parsed hash in constant time.

    Args:
        password: Clear-text password to check.
        parsed: Result of `parse_password_hash`.

    Returns:
        True when the password matches.
    """
    candidate = _derive(password, parsed.n, parsed.r, parsed.p, parsed.salt, len(parsed.key))
    return hmac.compare_digest(candidate, parsed.key)
