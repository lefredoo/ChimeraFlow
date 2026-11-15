"""
Tests that connectors expose source column names and entities that rules rely on
"""
import pytest

from mcp_servers.excel_connector import ExcelConnector
from mcp_servers.momo_connector import MobileMoneyConnector
from mcp_servers.whatsapp_connector import WhatsAppConnector

MOMO_CSV = (
    "transaction_id,timestamp,phone,customer_name,operator,amount,currency,status,reference,quantity\n"
    "MM1,2026-11-01 09:59:00,237650000000,Client D,Orange Money,14000,XAF,SUCCESS,Tuyau PVC 1/2 (6m),4\n"
    "MM2,not-a-date,237650000001,Client B,MTN MoMo,3000,XAF,SUCCESS,Cadenas Master Lock,1\n"
    "MM3,2026-11-02 08:48:00,237650000002,Client A,MTN MoMo,abc,XAF,PENDING,Peinture,2\n"
)


@pytest.mark.parametrize(
    "message, expected",
    [
        ("Bsr. Quel est le prix du ciment 50kg svp?", "ciment 50kg"),
        ("Il me faut du ciment 50 kg", "ciment 50 kg"),
        ("Ciment50kg disponible?", "Ciment50kg"),
        ("Avez-vous du cimént 50kg", "cimént 50kg"),
        ("Je prends du ciment (50kg)", "ciment (50kg)"),
    ],
)
def test_should_extract_product_with_quantity_when_message_mentions_ciment(message, expected):
    products = WhatsAppConnector("unused.txt")._extract_products(message)

    assert products == [expected]


def test_should_extract_nothing_when_message_has_no_product_keyword():
    assert WhatsAppConnector("unused.txt")._extract_products("Bonjour, merci beaucoup") == []


@pytest.mark.asyncio
async def test_should_keep_source_column_names_when_reading_excel(tmp_path):
    import pandas as pd

    path = tmp_path / "tarifs.xlsx"
    pd.DataFrame(
        {
            "Produit": ["Ciment 50 kg"],
            "Prix_Unitaire": [7500],
            "Fournisseur": ["Fournisseur A"],
            "Date_MAJ": [pd.Timestamp("2026-10-31")],
        }
    ).to_excel(path, sheet_name="Tarifs", index=False)

    records = await ExcelConnector(str(path)).fetch_records()

    assert records[0].timestamp == "2026-10-31T00:00:00"
    assert records[0].payload["Produit"] == "Ciment 50 kg"
    assert records[0].payload["Prix_Unitaire"] == 7500.0


@pytest.mark.asyncio
async def test_should_emit_product_entity_when_reading_momo_reference(tmp_path):
    path = tmp_path / "momo.csv"
    path.write_text(MOMO_CSV, encoding="utf-8")

    records = await MobileMoneyConnector(str(path)).fetch_records()

    assert [e["type"] for e in records[0].entities] == ["payment", "product"]
    assert records[0].entities[1]["raw"] == "Tuyau PVC 1/2 (6m)"
    assert records[0].payload["currency"] == "XAF"


@pytest.mark.asyncio
async def test_should_skip_and_count_errors_when_momo_rows_are_invalid(tmp_path):
    path = tmp_path / "momo.csv"
    path.write_text(MOMO_CSV, encoding="utf-8")
    connector = MobileMoneyConnector(str(path))

    records = await connector.fetch_records()

    assert len(records) == 1
    assert connector.parse_errors == 2
