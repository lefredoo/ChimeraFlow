"""
Rule files: one JSON file per rule under `<DATA_DIR>/rules`.

Pure module (no configuration import) so the validation CLI and the tests can
point it at any directory. A file holds the fields of `RuleCreate` plus a
`status` (`active` or `inactive`).
"""
import json
from pathlib import Path
from typing import List, Literal, Tuple

from pydantic import ValidationError

from schemas.rule import RuleCreate


class PredefinedRule(RuleCreate):
    """A rule file: the RuleCreate fields plus the status it is seeded with.

    Unknown keys are rejected so that a typo (`window_second`) cannot silently
    fall back to a default value.
    """

    model_config = {"extra": "forbid"}

    status: Literal["active", "inactive"]


class RuleFileError(ValueError):
    """One or more rule files are missing or invalid."""


def summarize_validation_error(error: ValidationError) -> str:
    """Format a validation error as `location: message` pairs, without input values."""
    return "; ".join(
        f"{'.'.join(str(part) for part in item['loc']) or '<root>'}: {item['msg']}"
        for item in error.errors(include_input=False, include_url=False, include_context=False)
    )


def collect_rule_files(directory: Path) -> Tuple[List[PredefinedRule], List[str]]:
    """Read and validate every `*.json` file of a directory.

    Args:
        directory: Directory holding the rule files.

    Returns:
        The valid rules sorted by file name (deterministic order) and one
        message per problem found.
    """
    if not directory.is_dir():
        return [], [f"Rules directory not found: {directory}"]

    rules: List[PredefinedRule] = []
    problems: List[str] = []
    paths = sorted(directory.glob("*.json"))
    if not paths:
        problems.append(f"No rule file (*.json) in {directory}")

    seen_ids = set()
    for path in paths:
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError) as exc:
            problems.append(f"{path.name}: unreadable JSON ({exc})")
            continue
        try:
            rule = PredefinedRule.model_validate(raw)
        except ValidationError as exc:
            problems.append(f"{path.name}: {summarize_validation_error(exc)}")
            continue
        if rule.id != path.stem:
            problems.append(f"{path.name}: id '{rule.id}' must match the file name")
            continue
        if rule.id in seen_ids:
            problems.append(f"{path.name}: duplicate id '{rule.id}'")
            continue
        seen_ids.add(rule.id)
        rules.append(rule)

    return rules, problems


def load_rule_files(directory: Path) -> List[PredefinedRule]:
    """Load the rules of a directory, failing on the first invalid file set.

    Args:
        directory: Directory holding the rule files.

    Returns:
        Rules sorted by file name.

    Raises:
        RuleFileError: If the directory is missing, empty, or any file is invalid.
    """
    rules, problems = collect_rule_files(directory)
    if problems:
        raise RuleFileError("Invalid rule files: " + " | ".join(problems))
    return rules
