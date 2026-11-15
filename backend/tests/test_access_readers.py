"""
Access readers: mdbtools and access-parser must produce the same records.
"""
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

from mcp_servers.access_connector import AccessConnector, _cell_to_text

BACKEND_DIR = Path(__file__).resolve().parent.parent
ACCESS_PATH = BACKEND_DIR.parent / "data" / "STOCK_ZOBO.mdb"
HAS_MDBTOOLS = shutil.which("mdb-export") is not None


class TestAccessReaderSelection:
    def test_should_raise_when_reader_is_unknown(self):
        with pytest.raises(ValueError, match="Unknown Access reader"):
            AccessConnector(str(ACCESS_PATH), reader="jackcess")

    def test_should_use_configured_reader_when_none_is_given(self):
        assert AccessConnector(str(ACCESS_PATH)).reader == os.environ["ACCESS_READER"]

    @pytest.mark.parametrize("env, expected", [
        ({"ACCESS_READER": "jackcess"}, "must be one of"),
        ({"ACCESS_READER": None}, "ACCESS_READER"),
    ])
    def test_should_fail_fast_when_access_reader_setting_is_invalid(self, env, expected):
        child_env = {**os.environ}
        for name, value in env.items():
            if value is None:
                child_env.pop(name, None)
            else:
                child_env[name] = value
        result = subprocess.run(
            [sys.executable, "-c", "import config"],
            cwd=BACKEND_DIR, env=child_env, capture_output=True, text=True,
        )
        assert result.returncode != 0
        assert expected in result.stderr


class TestAccessCellConversion:
    def test_should_scale_currency_when_column_is_money(self):
        assert _cell_to_text(15000000, is_currency=True) == "1500.0000"

    def test_should_keep_integer_when_column_is_not_money(self):
        assert _cell_to_text(45, is_currency=False) == "45"

    def test_should_return_empty_text_when_value_is_null(self):
        assert _cell_to_text(None, is_currency=False) == ""


@pytest.mark.skipif(not HAS_MDBTOOLS, reason="mdbtools (mdb-export) is not installed")
class TestAccessReadersAgree:
    @pytest.mark.asyncio
    async def test_should_produce_identical_records_when_reading_stock_database(self):
        via_mdbtools = await AccessConnector(str(ACCESS_PATH), reader="mdbtools").fetch_records(limit=1000)
        via_parser = await AccessConnector(str(ACCESS_PATH), reader="access-parser").fetch_records(limit=1000)

        assert len(via_parser) == 24
        assert [r.to_dict() for r in via_parser] == [r.to_dict() for r in via_mdbtools]

    @pytest.mark.asyncio
    async def test_should_list_same_tables_when_checking_health(self):
        via_mdbtools = await AccessConnector(str(ACCESS_PATH), reader="mdbtools").health_check()
        via_parser = await AccessConnector(str(ACCESS_PATH), reader="access-parser").health_check()

        assert via_parser["tables"] == via_mdbtools["tables"]


class TestAccessParserReader:
    @pytest.mark.asyncio
    async def test_should_read_all_articles_when_using_access_parser(self):
        records = await AccessConnector(str(ACCESS_PATH), reader="access-parser").fetch_records(limit=1000)

        assert len(records) == 24
        assert records[0].payload["designation"] == "Pointes 2.5 pouces"
        assert records[0].payload["prix_achat"] == 1500.0
        assert records[0].timestamp == "2026-11-01T00:00:00"

    @pytest.mark.asyncio
    async def test_should_raise_when_table_does_not_exist(self):
        connector = AccessConnector(str(ACCESS_PATH), table_name="Missing", reader="access-parser")

        with pytest.raises(RuntimeError):
            await connector.fetch_records()
