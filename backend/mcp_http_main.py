"""
Launcher of the hosted MCP service: `python mcp_http_main.py [--host H] [--port P]`.

Serves the four sources over Streamable HTTP (see mcp_servers/mcp_http_app.py).
The configuration is validated before the heavy imports: a missing token or data
directory stops the process at start, there is no fallback.
"""
import argparse
import logging
import sys
from typing import Optional, Sequence

from mcp_servers.mcp_settings import load_http_settings

DEFAULT_HOST = "0.0.0.0"
DEFAULT_PORT = 8001


def parse_args(argv: Optional[Sequence[str]] = None) -> argparse.Namespace:
    """Parse the command line."""
    parser = argparse.ArgumentParser(description="ChimeraFlow MCP service (Streamable HTTP), all sources")
    parser.add_argument("--host", default=DEFAULT_HOST)
    parser.add_argument("--port", type=int, default=DEFAULT_PORT)
    return parser.parse_args(argv)


def main(argv: Optional[Sequence[str]] = None) -> int:
    """Start the hosted MCP service.

    Returns:
        Process exit code: 0 after a normal shutdown, 2 for an invalid configuration.
    """
    args = parse_args(argv)
    try:
        settings = load_http_settings()
    except ValueError as exc:
        print(f"MCP service configuration error: {exc}", file=sys.stderr)
        return 2
    logging.basicConfig(
        stream=sys.stderr,
        level=(settings.log_level or "INFO").upper(),
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )
    import uvicorn

    from mcp_servers.mcp_http_app import create_http_app, log_started

    log_started(settings)
    # access_log off: uvicorn would log every client IP (personal data).
    # proxy_headers off: the client address is resolved by the app from TRUSTED_PROXIES.
    uvicorn.run(
        create_http_app(settings), host=args.host, port=args.port, access_log=False, proxy_headers=False
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
