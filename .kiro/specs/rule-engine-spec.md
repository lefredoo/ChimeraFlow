# Rule Engine Specification

## Overview
Declarative JSON rules with NL→JSON conversion via LiteLLM

## Requirements

### R1: Rule DSL Schema
```json
{
  "id": "string",
  "version": 1,
  "natural_language": "string",
  "trigger": {"source": "string", "entity": "string"},
  "joins": [{
    "source": "string",
    "table": "string",
    "on": {"entity": "string", "field": "string"},
    "where": [{"field": "string", "op": "eq|ne|lt|lte|gt|gte|contains|in", "value": "any"}]
  }],
  "window_seconds": "int",
  "emit": {"severity": "info|warning|error", "template": "string"}
}
```

### R2: NL→JSON Conversion
- Use LiteLLM API
- Validate with Pydantic
- 2 retries on validation failure
- Budget cap enforced
- Fallback to predefined rules when budget exhausted

### R3: Interpreter
- Deterministic: same inputs → same outputs
- Allowed operators only (see R1)
- NO code execution
- Provenance tracking

### R4: Rate Limiting
- Per IP: 10 creations / 60s
- Global LLM budget: $5 (~3,300 FCFA)

### R5: Predefined Rules
Minimum 5 templates:
- Low stock alert
- Price change detection
- Customer order confirmation
- Payment reconciliation
- Anomaly detection

## Implementation (P2)

Status of the requirements above (details in `backend/README.md`):

- **R1 DSL**: implemented (`backend/schemas/rule.py`). Joins also take `sheet` (Excel) and `table` (Access).
- **R2 NL→JSON**: not implemented (LiteLLM and budget cap pending, see TECH_DEBT.md).
- **R3 Interpreter**: implemented (`backend/engine/interpreter.py`). The time window is symmetric around the trigger. With several candidates the best score wins, then the record at or before the trigger, then the closest in time. Entities match only when they contain the same numbers.
- **R4 Rate limiting**: not implemented.
- **R5 Predefined rules**: 5 rules seeded into the `rules` table at startup. `r_low_stock` and `r_high_value_order` are active. `r_payment_received`, `r_price_comparison` and `r_stock_replenish` are inactive until the DSL can express what they promise.
