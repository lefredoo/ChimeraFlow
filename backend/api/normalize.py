"""
Normalization sandbox: POST /api/v1/normalize

Shows how a product name is reduced (normalized key, tokens, numbers) and how
it scores against other names, with the same matcher the rule engine uses.
Stateless and bounded (1 text of 200 characters, 20 comparisons), and behind
the Bearer token like every /api/v1 router: it has no per-IP limit, so the page
can score as the user types.
"""
from fastapi import APIRouter

from engine.normalizer import EntityNormalizer
from schemas.normalize import (
    NormalizeComparison,
    NormalizeRequest,
    NormalizeResponse,
)

router = APIRouter(prefix="/api/v1/normalize", tags=["normalize"])

# Same threshold as the rule interpreter
_normalizer = EntityNormalizer(fuzzy_threshold=0.85)


def _forms(text: str) -> dict:
    prepared = _normalizer.prepare(text)
    return {
        "text": text,
        "norm": prepared.norm,
        "canonical": prepared.canonical,
        "tokens": list(prepared.tokens),
        "numbers": list(prepared.numbers),
    }


@router.post("", response_model=NormalizeResponse)
def normalize(payload: NormalizeRequest) -> NormalizeResponse:
    """Normalize a name and score it against up to 20 other names."""
    comparisons = []
    for other in payload.compare_with:
        result = _normalizer.match_detail(payload.text, other)
        comparisons.append(NormalizeComparison(
            **_forms(other),
            score=round(result.score, 4),
            matched=result.matches,
            method=result.method,
        ))
    return NormalizeResponse(**_forms(payload.text), comparisons=comparisons)

