"""
Predefined rules as data files: strict validation at load time, deterministic
order, no emoji in the shipped texts, validation CLI.
"""
import copy
import json
import os
import re
import subprocess
import sys
from pathlib import Path

import pytest

from engine.predefined_rules import RULES_DIR, get_predefined_rules
from engine.rule_files import RuleFileError, collect_rule_files, load_rule_files
from engine.validate_rules import main as validate_main

BACKEND_DIR = Path(__file__).resolve().parent.parent
EMOJI = re.compile("[\U0001F000-\U0001FFFF\u2600-\u27BF\uFE0F]")

VALID_FILE = {
    "id": "r_sample",
    "status": "active",
    "natural_language": "Alerte quand le stock Access est bas pour un produit demandé.",
    "trigger": {"source": "whatsapp", "entity": "product"},
    "joins": [
        {
            "source": "access",
            "table": "Articles",
            "on": {"entity": "product", "field": "designation"},
            "where": [{"field": "qty_stock", "op": "lt", "value": 10}],
        }
    ],
    "window_seconds": 604800,
    "emit": {"severity": "warning", "template": "{product}: stock {access.qty_stock}"},
}


def _write(directory: Path, name: str, content: dict) -> None:
    (directory / f"{name}.json").write_text(json.dumps(content), encoding="utf-8")


def _file_with(**overrides) -> dict:
    content = copy.deepcopy(VALID_FILE)
    content.update(overrides)
    return content


def test_should_load_rule_when_file_is_valid(tmp_path):
    _write(tmp_path, "r_sample", VALID_FILE)

    rules = load_rule_files(tmp_path)

    assert [(rule.id, rule.status) for rule in rules] == [("r_sample", "active")]


def test_should_sort_rules_by_file_name_when_loading(tmp_path):
    _write(tmp_path, "r_b", _file_with(id="r_b"))
    _write(tmp_path, "r_a", _file_with(id="r_a"))

    assert [rule.id for rule in load_rule_files(tmp_path)] == ["r_a", "r_b"]


def test_should_fail_when_directory_is_missing(tmp_path):
    with pytest.raises(RuleFileError, match="not found"):
        load_rule_files(tmp_path / "absent")


def test_should_fail_when_directory_has_no_rule_file(tmp_path):
    with pytest.raises(RuleFileError, match="No rule file"):
        load_rule_files(tmp_path)


def test_should_fail_when_file_is_not_json(tmp_path):
    (tmp_path / "r_broken.json").write_text("{not json", encoding="utf-8")

    with pytest.raises(RuleFileError, match=r"r_broken\.json: unreadable JSON"):
        load_rule_files(tmp_path)


def test_should_fail_when_rule_is_invalid(tmp_path):
    _write(tmp_path, "r_sample", _file_with(joins=[]))

    with pytest.raises(RuleFileError, match=r"r_sample\.json: joins"):
        load_rule_files(tmp_path)


def test_should_fail_when_status_is_missing(tmp_path):
    content = _file_with()
    del content["status"]
    _write(tmp_path, "r_sample", content)

    with pytest.raises(RuleFileError, match="status"):
        load_rule_files(tmp_path)


def test_should_fail_when_status_is_not_allowed(tmp_path):
    _write(tmp_path, "r_sample", _file_with(status="draft"))

    with pytest.raises(RuleFileError, match="status"):
        load_rule_files(tmp_path)


def test_should_fail_when_a_key_is_misspelled(tmp_path):
    _write(tmp_path, "r_sample", _file_with(window_second=60))

    with pytest.raises(RuleFileError, match="window_second"):
        load_rule_files(tmp_path)


def test_should_fail_when_id_differs_from_file_name(tmp_path):
    _write(tmp_path, "r_other", VALID_FILE)

    with pytest.raises(RuleFileError, match="must match the file name"):
        load_rule_files(tmp_path)


def test_should_report_every_invalid_file_when_collecting(tmp_path):
    _write(tmp_path, "r_ok", _file_with(id="r_ok"))
    _write(tmp_path, "r_bad1", _file_with(id="r_bad1", joins=[]))
    _write(tmp_path, "r_bad2", _file_with(id="r_bad2", window_seconds=1))

    rules, problems = collect_rule_files(tmp_path)

    assert [rule.id for rule in rules] == ["r_ok"]
    assert len(problems) == 2


def test_should_ship_five_valid_predefined_rules_when_loading_data_directory():
    rules = load_rule_files(RULES_DIR)

    assert [rule.id for rule in rules] == [
        "r_high_value_order",
        "r_low_stock",
        "r_payment_received",
        "r_price_comparison",
        "r_stock_replenish",
    ]


@pytest.mark.parametrize("rule", get_predefined_rules(), ids=lambda rule: rule.id)
def test_should_not_contain_emoji_when_rule_texts_are_shipped(rule):
    assert EMOJI.search(rule.natural_language + rule.emit.template) is None


def test_should_exit_zero_when_cli_validates_shipped_rules(capsys):
    assert validate_main([str(RULES_DIR)]) == 0
    assert "5 rule file(s) valid" in capsys.readouterr().out


def test_should_exit_one_and_name_the_file_when_cli_finds_an_invalid_rule(tmp_path, capsys):
    _write(tmp_path, "r_sample", _file_with(joins=[]))

    assert validate_main([str(tmp_path)]) == 1
    assert "r_sample.json" in capsys.readouterr().err


def test_should_exit_two_when_cli_gets_too_many_arguments(capsys):
    assert validate_main(["a", "b"]) == 2
    assert "Usage" in capsys.readouterr().err


def test_should_run_as_module_when_data_dir_is_set():
    result = subprocess.run(
        [sys.executable, "-m", "engine.validate_rules"],
        cwd=BACKEND_DIR, env={**os.environ}, capture_output=True, text=True,
    )

    assert result.returncode == 0
    assert "valid" in result.stdout
