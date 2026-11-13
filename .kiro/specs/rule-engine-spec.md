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
