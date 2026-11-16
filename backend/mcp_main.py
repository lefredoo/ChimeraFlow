"""
Launcher of the MCP servers: `python mcp_main.py --source excel|access|whatsapp|momo`.

Lives at the backend root (like main.py) so the `mcp_servers` package is
importable whatever the working directory of the caller (Kiro, Docker).
The configuration is validated before the server module is imported: pandas
and the MCP SDK are slow to load, and a bad setting must stop the process fast.
stdout carries the protocol, so every message goes to stderr.
"""
import argparse
import logging
import sys
from typing import Optional, Sequence

from mcp_servers.mcp_settings import SOURCES, load_settings


def parse_args(argv: Optional[Sequence[str]] = None) -> argparse.Namespace:
    """Parse the command line (`--source` is required)."""
    parser = argparse.ArgumentParser(description="ChimeraFlow MCP server (stdio), one data source per process")
    parser.add_argument("--source", required=True, choices=sorted(SOURCES))
    return parser.parse_args(argv)


def main(argv: Optional[Sequence[str]] = None) -> int:
    """Start the stdio server of one source.

    Returns:
        Process exit code: 0 after a normal shutdown, 2 for an invalid configuration.
    """
    args = parse_args(argv)
    try:
        settings = load_settings(args.source)
    except ValueError as exc:
        print(f"MCP server configuration error: {exc}", file=sys.stderr)
        return 2
    logging.basicConfig(
        stream=sys.stderr,
        level=(settings.log_level or "INFO").upper(),
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )
    from mcp_servers.mcp_app import create_server

    create_server(settings).run(transport="stdio")
    return 0


if __name__ == "__main__":
    sys.exit(main())
