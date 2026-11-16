"""
Columns the data sources expose to the rule DSL.

A rule can only name these columns (join keys, conditions, references and
template placeholders), which keeps a draft written by a language model from
inventing fields, and keeps personal data out of emitted messages.
"""
from typing import Dict, FrozenSet

# Payload columns of each connector (see backend/mcp_servers/*_connector.py)
SOURCE_COLUMNS: Dict[str, FrozenSet[str]] = {
    "whatsapp": frozenset({"author", "text"}),
    "momo": frozenset({
        "transaction_id", "timestamp", "phone", "customer_name", "operator",
        "amount", "currency", "status", "reference", "quantity",
    }),
    "excel": frozenset({"Produit", "Prix_Unitaire", "Fournisseur", "Date_MAJ", "row_index"}),
    "access": frozenset({
        "id", "designation", "unite", "qty_stock", "prix_achat", "date_modif", "table",
    }),
}

# Join key that matches against the entities of the joined record (typed
# entities extracted by the connector, such as the products of a message)
# instead of one payload column
ENTITIES_FIELD = "entities"

# Columns that identify a person: usable in conditions, never in an emitted message
TEMPLATE_FORBIDDEN_COLUMNS: Dict[str, FrozenSet[str]] = {
    "momo": frozenset({"phone", "customer_name"}),
}
