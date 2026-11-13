# Connector Conventions

## Error Handling

- **Parse errors**: Log + skip + continue. Increment error counter.
- **Connection errors**: Return in `health_check()`, don't crash main process.
- **Timeout**: 5 seconds max per fetch operation.
- **Retry**: 2 attempts with exponential backoff.

## Logging

Structured logs with:
- `connector`: source name
- `operation`: fetch_records | health_check
- `records_count`: number of records returned
- `errors_count`: number of parse errors
- `duration_ms`: operation duration

## Performance

- Fetch limit: default 100, max 1000
- Cache health_check for 30 seconds
- No blocking operations on main thread

## Normalization

Entity normalization strategy (hybrid):
1. Lowercase
2. Remove accents (unicodedata.normalize)
3. Collapse whitespace
4. Remove punctuation (except hyphens)
5. FR/EN synonym mapping (configurable dict)
6. Fuzzy match threshold: 0.85 (Levenshtein)

## Testing

Each connector MUST have:
- Unit tests (happy path)
- Parse error tests (malformed data)
- Property-based tests (round-trip, idempotence)
