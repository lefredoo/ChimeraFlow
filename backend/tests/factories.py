"""
Builders for in-memory unified records shared by the rule engine tests.
"""
from mcp_servers.base import UnifiedRecord

DEFAULT_PRODUCT = "Ciment 50 kg"


def make_whatsapp_record(timestamp: str = "2026-11-02T11:08:00", raw: str = "ciment 50kg") -> UnifiedRecord:
    """WhatsApp message asking about a product."""
    return UnifiedRecord(
        id="wa-5",
        source="whatsapp",
        source_ref="commandes_clients.txt#L5",
        timestamp=timestamp,
        lang="fr",
        entities=[{"type": "product", "raw": raw, "norm": raw}],
        payload={"author": "Client A", "text": f"Bsr. Quel est le prix du {raw} svp?"},
    )


def make_access_record(qty_stock, date_modif: str = "2026-11-01T00:00:00") -> UnifiedRecord:
    """Access stock row for the default product."""
    return UnifiedRecord(
        id="access-16",
        source="access",
        source_ref="STOCK_ZOBO.mdb#Articles#16",
        timestamp=date_modif,
        lang="fr",
        entities=[{"type": "product", "raw": DEFAULT_PRODUCT, "norm": "ciment 50 kg"}],
        payload={"id": "16", "designation": DEFAULT_PRODUCT, "qty_stock": qty_stock, "date_modif": date_modif},
    )


def make_excel_record(
    price: int,
    date_maj: str = "2026-10-31T00:00:00",
    produit: str = DEFAULT_PRODUCT,
    row: int = 17,
) -> UnifiedRecord:
    """Excel price list row."""
    return UnifiedRecord(
        id=f"excel-{row}",
        source="excel",
        source_ref=f"tarifs_fournisseurs.xlsx#row{row}",
        timestamp=date_maj,
        lang="fr",
        entities=[{"type": "product", "raw": produit, "norm": produit.lower()}],
        payload={"Produit": produit, "Prix_Unitaire": price, "Date_MAJ": date_maj},
    )
