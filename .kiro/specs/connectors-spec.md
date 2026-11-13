# Connectors Specification

## Overview
MCP servers for 4 data sources: Excel, Access, WhatsApp, Mobile Money

## Requirements

### R1: MCP Contract
Each connector SHALL implement:
- `fetch_records(limit: int) -> list[Record]`
- `health_check() -> dict`

### R2: Unified Record Schema
```json
{
  "id": "string",
  "source": "excel|access|whatsapp|momo",
  "source_ref": "string",
  "timestamp": "ISO8601",
  "lang": "fr|en",
  "entities": [{"type": "string", "raw": "string", "norm": "string"}],
  "payload": "object"
}
```

### R3: Error Handling
- Parse errors: skip line, increment counter, continue
- Connection errors: return error in health_check
- Never crash on malformed data

### R4: Excel Connector
- Handle merged cells
- Support imperfect formatting
- Extract: Produit, Prix_Unitaire, Fournisseur, Date_MAJ

### R5: Access Connector
- Read .mdb with mdbtools or access_parser
- Tables: Articles, Mouvements
- Extract: id, designation, unite, qty_stock

### R6: WhatsApp Connector
- Support Android and iOS export formats
- Parse multilingual dates (FR/EN)
- Handle multi-line messages
- Extract entities: product names

### R7: Mobile Money Connector
- CSV format
- Fields: transaction_id, phone, amount, status, timestamp

## Implementation (P1)
