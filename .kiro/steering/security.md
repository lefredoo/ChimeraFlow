# Security Guidelines

## Absolute Rules

1. **NO code execution**: NEVER execute generated code from LLM. Rules are JSON only.
2. **Sanitize all inputs**: XSS prevention on all source-originated text before display.
3. **No secrets in code**: Use environment variables exclusively (requireEnv pattern).
4. **Rate limiting**: Enforce per-IP limits on rule creation.
5. **Budget caps**: LLM usage must respect hard budget limit.
6. **Input validation**: Validate all user inputs server-side with Pydantic.

## Data Handling

- All demo data is 100% synthetic
- No real phone numbers, messages, or business data
- Source files are read-only in production (Docker volume)

## API Security

- CORS whitelist only
- No authentication bypass
- Rate limit on all mutation endpoints
- Structured logging (no PII in logs)

## Prompt Injection Prevention

Source text (WhatsApp, Excel cells) is untrusted. When passing to LLM:
- Clearly separate instructions from data
- Use structured prompts
- Validate LLM output against strict schema
- Never trust LLM for security decisions
