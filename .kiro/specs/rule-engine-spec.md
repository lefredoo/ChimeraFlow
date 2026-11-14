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
- **R2 NL→JSON**: implemented (`POST /api/v1/rules/from-text`, `backend/engine/nl_to_rule.py`). LiteLLM proxy (`LITELLM_API_KEY`, `LITELLM_BASE_URL`, `LITELLM_MODEL`, `LITELLM_BUDGET_USD`; the feature is disabled unless all four are set). The user text reaches the model only as a JSON string in a delimited data section, never in the instructions. The answer is validated with `RuleCreate` (id and `natural_language` are set by the server), with 2 retries that feed back the validation errors. The result is a draft that is not stored. The global budget cap is tracked in Redis (cost from `litellm.completion_cost`, else a token estimate); once spent, or when the counter is unreadable, the endpoint refuses and returns the predefined rules as `fallback_rules`. The same fallback comes with the feature-disabled, provider-error and conversion-failed errors.
- **R3 Interpreter**: implemented (`backend/engine/interpreter.py`). The time window is symmetric around the trigger. With several candidates the best score wins, then the record at or before the trigger, then the closest in time. Entities match only when they contain the same numbers.
- **R4 Rate limiting**: implemented (`backend/api/rate_limit.py`, slowapi with Redis storage) on `POST /rules`, `DELETE /rules/{id}`, `POST /correlations/execute` and `POST /rules/from-text`. The limit is `RATE_LIMIT_PER_IP` per `RATE_LIMIT_WINDOW_SECONDS` (both required, so the "10 per 60 s" of R4 is configuration, not code); the NL endpoint has its own, stricter limit (`RATE_LIMIT_NL_PER_IP`). The client key is the TCP peer, or the `X-Forwarded-For` address when the peer is in `TRUSTED_PROXIES`. The 429 carries `Retry-After`. The global LLM budget is `LITELLM_BUDGET_USD`.
- **R5 Predefined rules**: 5 rules, one JSON file each in `data/rules/` (RuleCreate fields plus `status`), validated at startup and seeded into the `rules` table. `r_low_stock` and `r_high_value_order` are active. `r_payment_received`, `r_price_comparison` and `r_stock_replenish` are inactive until the DSL can express what they promise. `python -m engine.validate_rules` checks the files.
- **API errors**: every error has `{"detail": {"code", "message"}}` with a stable code (see `backend/README.md`); the frontend maps codes to its i18n texts.
