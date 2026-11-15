"""
Validate rule files against the RuleCreate schema.

Usage (from backend/):
    python -m engine.validate_rules [directory]

Without argument, validates `<DATA_DIR>/rules` (DATA_DIR must be set).
Exit code 0 when every file is valid, 1 otherwise.
"""
import os
import sys
from pathlib import Path
from typing import List, Optional

from engine.rule_files import collect_rule_files


def main(argv: Optional[List[str]] = None) -> int:
    """Validate a rule directory and print one line per problem.

    Args:
        argv: Command-line arguments (without the program name).

    Returns:
        Process exit code.
    """
    args = sys.argv[1:] if argv is None else argv
    if len(args) > 1:
        print("Usage: python -m engine.validate_rules [directory]", file=sys.stderr)
        return 2
    if args:
        directory = Path(args[0])
    else:
        data_dir = os.getenv("DATA_DIR")
        if data_dir is None:
            print("Pass a directory or set DATA_DIR", file=sys.stderr)
            return 2
        directory = Path(data_dir) / "rules"

    rules, problems = collect_rule_files(directory)
    for problem in problems:
        print(problem, file=sys.stderr)
    if problems:
        return 1
    print(f"{len(rules)} rule file(s) valid in {directory}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
