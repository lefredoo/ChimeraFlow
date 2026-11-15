"""
Connector error handling: format errors are connector errors, and the parse
error counter describes one fetch, not the life of the connector object.
"""
import csv
import zipfile

import pytest
from openpyxl.utils.exceptions import InvalidFileException

from mcp_servers.base import CONNECTOR_ERRORS
from mcp_servers.excel_connector import ExcelConnector
from mcp_servers.momo_connector import MobileMoneyConnector
from mcp_servers.whatsapp_connector import WhatsAppConnector


@pytest.mark.parametrize("error", [csv.Error, zipfile.BadZipFile, InvalidFileException])
def test_should_treat_a_reader_format_error_as_a_connector_error_when_listing_the_errors(error):
    assert issubclass(error, CONNECTOR_ERRORS)


async def test_should_report_the_errors_of_one_fetch_when_a_whatsapp_file_is_read_twice(tmp_path):
    export = tmp_path / "chat.txt"
    export.write_text("not a message line\n[01/11/2026, 09:24:00] Client A: perceuse 500W\n", encoding="utf-8")
    connector = WhatsAppConnector(str(export))

    await connector.fetch_records()
    await connector.fetch_records()

    assert connector.parse_errors == 1


async def test_should_report_the_errors_of_one_fetch_when_a_momo_file_is_read_twice(tmp_path):
    payments = tmp_path / "momo.csv"
    payments.write_text(
        "transaction_id,timestamp,phone,customer_name,operator,amount,currency,status,reference,quantity\n"
        ",2026-11-01 10:00:00,,,,100,XAF,SUCCESS,Ciment 50 kg,1\n",
        encoding="utf-8",
    )
    connector = MobileMoneyConnector(str(payments))

    await connector.fetch_records()
    await connector.fetch_records()

    assert connector.parse_errors == 1


async def test_should_raise_a_connector_error_when_the_xlsx_is_not_a_zip_archive(tmp_path):
    broken = tmp_path / "tarifs.xlsx"
    broken.write_bytes(b"this is not an excel file")

    with pytest.raises(CONNECTOR_ERRORS):
        await ExcelConnector(str(broken)).fetch_records()
