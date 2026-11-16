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

Implémentation (`backend/mcp_servers/whatsapp_parser.py`, détail dans `backend/README.md`, « Parseur WhatsApp ») :
- Formats lus : `[JJ/MM/AAAA, HH:MM:SS] Auteur: texte` (Android), `[JJ/MM/AAAA HH:MM:SS] …` (iOS),
  `JJ/MM/AAAA HH:MM - Auteur: texte` (Android sans crochets), horloge 12 h `AM`/`PM` (`[M/J/AA, h:mm:ss AM] …`).
- Ordre jour/mois, décidé **par fichier** : un premier champ > 12 donne `dmy`, sinon un second champ > 12 donne
  `mdy`, sinon l'argument `default_date_order` du connecteur (`dmy` par défaut). Le choix est exposé
  (`date_order`, `date_order_source`) et journalisé quand c'est le défaut.
- Message sur plusieurs lignes : les lignes qui ne sont pas des en-têtes prolongent le message précédent
  (jointes par `\n`) ; ce ne sont pas des erreurs. `source_ref` et `id` portent la première ligne.
- Pièce jointe (`<Media omitted>`, `<Médias omis>`, `image omitted`, `<attached: …>`) : record gardé,
  `payload["attachment"] = true` (`false` sinon).
- Message système (sans auteur : chiffrement, arrivées) : ignoré et compté dans `system_skipped`, jamais dans
  `parse_errors`. Les autres lignes illisibles restent des erreurs (R4).

### R7: Mobile Money Connector
- CSV format
- Fields: transaction_id, phone, amount, status, timestamp

## Implementation (P1)

Les quatre connecteurs sont des classes Python (`backend/mcp_servers/*_connector.py`) qui
respectent R1 à R7. Ils sont appelés directement par l'API et exposés en serveurs MCP.

### Exposition MCP (implémentée)

- Un processus par source : `python backend/mcp_main.py --source excel|access|whatsapp|momo`.
  Kiro liste donc quatre serveurs (`chimeraflow-excel`, `chimeraflow-access`,
  `chimeraflow-whatsapp`, `chimeraflow-momo`).
- Transport : stdio uniquement. Le HTTP streamable n'est pas exposé (pas de port
  supplémentaire dans les fichiers compose).
- Outils (R1) : `fetch_records(limit: int = 100)` avec `1 <= limit <= 1000`, validé par le
  schéma de l'outil ; `health_check()`. Les deux sont déclarés en lecture seule.
  `fetch_records` renvoie `{source, count, parse_errors, records}` ; `records` contient des
  `UnifiedRecord` (R2). `parse_errors` compte les lignes ignorées pendant l'appel (R3).
- Ressource `chimeraflow://source/<source>` : métadonnées statiques de la source.
- Configuration : `DATA_DIR` (obligatoire) et, pour `access` seulement, `ACCESS_READER`
  (`mdbtools` ou `access-parser`). Aucune valeur par défaut : une variable manquante arrête
  le processus avec le code 2. Les serveurs n'importent pas `config.py` et n'ont donc besoin
  d'aucun réglage de l'API.
- Contraintes de `connectors.md` : 5 secondes par opération (lecture dans un thread
  de travail), 2 tentatives avec attente exponentielle, journaux JSON sur stderr
  (`connector`, `operation`, `records_count`, `errors_count`, `duration_ms`, sans contenu
  de record). stdout est réservé au protocole.
- Une erreur de lecture est renvoyée comme erreur d'outil sans chemin de fichier ; le détail
  reste dans les journaux. `health_check` renvoie `status: error` au lieu de lever.
- Enregistrement dans Kiro : `.kiro/settings/mcp.json` (modèle versionné dans
  `backend/mcp_servers/kiro-mcp.json`), uniquement des références à des chemins, aucun secret.
