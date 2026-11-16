"""
Schemas of the normalization sandbox (POST /api/v1/normalize).
"""
from typing import Annotated, List, Optional

from pydantic import BaseModel, Field, StringConstraints

MAX_TEXT_LENGTH = 200
MAX_COMPARISONS = 20


class NormalizeRequest(BaseModel):
    """A product name to normalize, and names to compare it with."""

    text: str = Field(..., min_length=1, max_length=MAX_TEXT_LENGTH)
    compare_with: List[Annotated[str, StringConstraints(max_length=MAX_TEXT_LENGTH)]] = Field(
        default_factory=list,
        max_length=MAX_COMPARISONS,
        description="Names to score against `text` (at most 20)",
    )


class NormalizedForms(BaseModel):
    """How a name is reduced before matching."""

    text: str
    norm: str  # lowercase, no accents, no punctuation: the key shown in the UI
    canonical: str  # `norm` with FR/EN synonyms replaced (what is compared)
    tokens: List[str]
    numbers: List[str]  # numeric tokens: names with different numbers never match


class NormalizeComparison(NormalizedForms):
    """A compared name and how it scores against the request text."""

    score: float
    matched: bool
    method: Optional[str] = None  # exact | synonym | fuzzy | token, None when not matched


class NormalizeResponse(NormalizedForms):
    comparisons: List[NormalizeComparison]
