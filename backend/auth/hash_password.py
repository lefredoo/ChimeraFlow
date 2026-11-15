"""
Command line tool: hash a password for DEMO_LOGIN_PASSWORD_HASH.

    python -m auth.hash_password

The password is read from stdin (never from an argument, which would end up in
the shell history and the process list) and the hash is printed on stdout:

    echo -n 'the password' | python -m auth.hash_password
"""
import getpass
import sys
from typing import Optional, TextIO

from auth.passwords import hash_password

MIN_PASSWORD_LENGTH = 8


def main(stdin: Optional[TextIO] = None, stdout: Optional[TextIO] = None, stderr: Optional[TextIO] = None) -> int:
    """Read a password and print its hash.

    Args:
        stdin: Input stream (sys.stdin when None). On a terminal the password is
            asked without echo.
        stdout: Stream receiving the hash (sys.stdout when None).
        stderr: Stream receiving error messages (sys.stderr when None).

    Returns:
        Process exit code: 0 on success, 1 when the password is too short.
    """
    stdin = sys.stdin if stdin is None else stdin
    stdout = sys.stdout if stdout is None else stdout
    stderr = sys.stderr if stderr is None else stderr

    if stdin.isatty():
        password = getpass.getpass("Password: ", stream=stderr)
    else:
        password = stdin.readline().rstrip("\r\n")

    if len(password) < MIN_PASSWORD_LENGTH:
        stderr.write(f"The password must have at least {MIN_PASSWORD_LENGTH} characters.\n")
        return 1
    stdout.write(hash_password(password) + "\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
