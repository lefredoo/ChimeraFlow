"""
Entity normalizer with hybrid strategy
Follows Roadmap §2 and P2 decision: rules + fuzzy + synonyms + token containment
"""
import unicodedata
import re
from collections import Counter
from dataclasses import dataclass
from typing import Dict, FrozenSet, List, Optional, Tuple
from rapidfuzz import fuzz
from rapidfuzz.distance import Levenshtein

_PUNCTUATION = re.compile(r"[^\w\s-]")
# Decimal point or fraction bar between two digits ("2.5", "1/2"): kept as a hyphen
# so the number stays one token ("2-5") instead of fusing into "25"
_NUMBER_SEPARATOR = re.compile(r"(?<=\d)[.,/](?=\d)")
_NUMBER_TOKEN = re.compile(r"\d+(?:-\d+)*")
# Boundary between a letter and a digit, in either direction ("50kg" -> "50 kg")
_LETTER_DIGIT_BOUNDARY = re.compile(r"(?<=[^\W\d_])(?=\d)|(?<=\d)(?=[^\W\d_])")

# Match methods, from the most to the least certain
METHOD_EXACT = "exact"
METHOD_SYNONYM = "synonym"
METHOD_FUZZY = "fuzzy"
METHOD_TOKEN = "token"

# Partial (token containment) scores live in [TOKEN_BASE_SCORE, TOKEN_MAX_SCORE]:
# above the fuzzy threshold, always below an exact match (1.0)
TOKEN_BASE_SCORE = 0.85
TOKEN_MAX_SCORE = 0.99
# Smallest length of a word that can anchor a partial match ("pvc" yes, "kg" no)
_MIN_ANCHOR_LENGTH = 3
# Typos are tolerated only inside words of this length or more ("pvc" vs "ppr" are two
# products, "perceuse" vs "perseuse" is one typo), and only up to this word similarity
_MIN_TYPO_WORD_LENGTH = 5
_MIN_TYPO_WORD_SIMILARITY = 0.75
# Bound of the per-instance preparation cache (a run sees a few hundred names)
_MAX_CACHED_TEXTS = 8192


def normalize_text(text: str) -> str:
    """Normalize text for entity matching (single source of truth).

    Strategy from .kiro/steering/connectors.md. Whitespace is collapsed last
    so the result is idempotent: normalize_text(normalize_text(x)) equals
    normalize_text(x) (property P2).

    1. Lowercase
    2. Remove accents
    3. Keep decimals and fractions as one token ("2.5" -> "2-5")
    4. Remove punctuation (except hyphens)
    5. Split letters from digits ("Ciment50kg" -> "ciment 50 kg")
    6. Collapse whitespace

    Args:
        text: Raw text.

    Returns:
        Normalized text.
    """
    text = text.lower()
    text = unicodedata.normalize("NFD", text)
    text = "".join(c for c in text if unicodedata.category(c) != "Mn")
    text = _NUMBER_SEPARATOR.sub("-", text)
    text = _PUNCTUATION.sub("", text)
    text = _LETTER_DIGIT_BOUNDARY.sub(" ", text)
    return " ".join(text.split())


@dataclass(frozen=True)
class PreparedText:
    """A raw name reduced to the forms the matcher compares."""

    norm: str  # normalize_text(raw)
    canonical: str  # norm with synonyms replaced by their canonical word
    tokens: Tuple[str, ...]  # words of `canonical`, in order
    numbers: Tuple[str, ...]  # numeric tokens of `canonical`, sorted


@dataclass(frozen=True)
class MatchResult:
    """Outcome of comparing two names.

    `method` is None when the names do not match; `score` is 0.0 when the
    numbers made the comparison pointless, otherwise the similarity found.
    """

    matches: bool
    score: float
    method: Optional[str]


class EntityNormalizer:
    """
    Hybrid entity normalization:
    1. Strict rules (lowercase, accents, whitespace, punctuation)
    2. FR/EN synonym mapping
    3. Fuzzy matching (Levenshtein distance) for typos
    4. Token containment for partial names ("tuyau pvc" in "tuyau pvc 32mm barre 6m")
    """
    
    # Synonym dictionary (FR/EN)
    SYNONYMS = {
        # Construction materials
        "ciment": ["cement", "cimént"],
        "cement": ["ciment"],
        
        # Hardware
        "pointe": ["pointes", "clou", "clous", "nail", "nails"],
        "vis": ["screw", "screws"],
        "tuyau": ["pipe", "tube"],
        
        # Measurements (normalize variations)
        "kg": ["kilo", "kilogramme", "kilogram"],
        "litre": ["l", "liter"],
        
        # Products
        "peinture": ["paint", "painting"],
        "marteau": ["hammer"],
        "perceuse": ["drill"],
    }
    
    def __init__(self, fuzzy_threshold: float = 0.85):
        """
        Args:
            fuzzy_threshold: Minimum similarity for fuzzy match (0.0 to 1.0)
        """
        self.fuzzy_threshold = fuzzy_threshold
        
        # Flatten synonyms for quick lookup
        self.synonym_map = self._build_synonym_map()
        self._prepared: Dict[str, PreparedText] = {}
    
    def _build_synonym_map(self) -> Dict[str, str]:
        """Build flat synonym map: variant → canonical"""
        mapping = {}
        for canonical, variants in self.SYNONYMS.items():
            mapping[canonical] = canonical
            for variant in variants:
                mapping[variant.lower()] = canonical
        return mapping
    
    def normalize(self, text: str) -> str:
        """
        Full normalization pipeline
        
        Args:
            text: Raw text to normalize
            
        Returns:
            Normalized text
        """
        return normalize_text(text)
    
    def apply_synonyms(self, text: str) -> str:
        """
        Apply synonym mapping to normalized text
        
        Args:
            text: Normalized text
            
        Returns:
            Text with synonyms replaced by canonical forms
        """
        words = text.split()
        canonical_words = []
        
        for word in words:
            # Check if word has a canonical form
            canonical = self.synonym_map.get(word, word)
            canonical_words.append(canonical)
        
        return ' '.join(canonical_words)
    
    @staticmethod
    def numeric_tokens(text: str) -> List[str]:
        """
        Numbers found in a normalized text, as a sorted multiset

        Args:
            text: Normalized text

        Returns:
            Sorted list of numeric tokens ("50", "2-5"), repeated numbers kept
        """
        return sorted(_NUMBER_TOKEN.findall(text))

    def prepare(self, raw: str) -> PreparedText:
        """Reduce a raw name to the forms the matcher compares (cached).

        Args:
            raw: Raw name as written in a source.

        Returns:
            Normalized text, canonical text, tokens and numbers.
        """
        cached = self._prepared.get(raw)
        if cached is not None:
            return cached
        norm = self.normalize(raw)
        canonical = self.apply_synonyms(norm)
        prepared = PreparedText(
            norm=norm,
            canonical=canonical,
            tokens=tuple(canonical.split()),
            numbers=tuple(self.numeric_tokens(canonical)),
        )
        if len(self._prepared) >= _MAX_CACHED_TEXTS:
            self._prepared.clear()
        self._prepared[raw] = prepared
        return prepared

    def fuzzy_match(self, text1: str, text2: str) -> float:
        """
        Compute fuzzy similarity between two texts
        
        Args:
            text1: First text (normalized)
            text2: Second text (normalized)
            
        Returns:
            Similarity score (0.0 to 1.0)
        """
        return Levenshtein.normalized_similarity(text1, text2)

    def _is_typo_variant(self, first: PreparedText, second: PreparedText) -> bool:
        """True if two names differ only by typos inside their longer words.

        Whole-string similarity alone accepts "tuyau pvc 32 mm" for
        "tuyau ppr 32 mm" (0.87): the names must have the same number of
        words, and each pair of words must be equal or be two close spellings
        of a word long enough to hold a typo.
        """
        if len(first.tokens) != len(second.tokens):
            return False
        for word1, word2 in zip(first.tokens, second.tokens):
            if word1 == word2:
                continue
            if min(len(word1), len(word2)) < _MIN_TYPO_WORD_LENGTH:
                return False
            if self.fuzzy_match(word1, word2) < _MIN_TYPO_WORD_SIMILARITY:
                return False
        return True

    @staticmethod
    def _has_anchor(tokens: FrozenSet[str]) -> bool:
        """True if a token set holds a real word (not only numbers and units)."""
        return any(
            len(token) >= _MIN_ANCHOR_LENGTH and not token[0].isdigit() for token in tokens
        )

    def _containment_score(self, first: PreparedText, second: PreparedText) -> Optional[float]:
        """Score of a partial match, or None when one name does not contain the other.

        The shorter name must be fully contained in the longer one, word for
        word (set containment: a word like "ciment-colle" is not "ciment"),
        must hold at least one real word, and its numbers must be among the
        numbers of the longer name. This is the subset case of rapidfuzz's
        token-set ratio, without its leniency on names that merely overlap
        ("tuyau pvc 32mm" vs "tuyau ppr 32mm" would score 0.9 there).

        Returns:
            A score in [TOKEN_BASE_SCORE, TOKEN_MAX_SCORE]: the more of the
            longer name the shorter one covers, the higher it is.
        """
        small, large = (
            (first, second)
            if len(set(first.tokens)) <= len(set(second.tokens))
            else (second, first)
        )
        small_set, large_set = frozenset(small.tokens), frozenset(large.tokens)
        if not small_set <= large_set or not self._has_anchor(small_set):
            return None
        if Counter(small.numbers) - Counter(large.numbers):
            return None
        coverage = fuzz.ratio(" ".join(sorted(small_set)), " ".join(sorted(large_set))) / 100.0
        return TOKEN_BASE_SCORE + (TOKEN_MAX_SCORE - TOKEN_BASE_SCORE) * coverage

    def match_detail(self, entity1: str, entity2: str) -> MatchResult:
        """
        Compare two entities and say how they matched

        Order of the checks:
        1. Same text once synonyms are applied: "exact" (same normalized
           text) or "synonym" (they differ only by synonyms), score 1.0.
        2. Same numbers on both sides: Levenshtein similarity at or above the
           threshold, with typos only inside long words, is "fuzzy"; otherwise a name contained in the
           other is "token".
        3. Different numbers: the products differ ("ciment 50 kg" vs
           "ciment 40 kg" would otherwise score 0.92), unless one side has
           fewer numbers that all appear on the other side and its words are
           contained in the other ("tuyau PVC" in "Tuyau PVC 32mm (barre 6m)"):
           a name without numbers matches a numbered one only that way.

        Args:
            entity1: First entity (raw)
            entity2: Second entity (raw)

        Returns:
            MatchResult(matches, score, method)
        """
        first, second = self.prepare(entity1), self.prepare(entity2)

        if first.canonical == second.canonical:
            method = METHOD_EXACT if first.norm == second.norm else METHOD_SYNONYM
            return MatchResult(True, 1.0, method)

        if first.numbers == second.numbers:
            similarity = self.fuzzy_match(first.canonical, second.canonical)
            if similarity >= self.fuzzy_threshold and self._is_typo_variant(first, second):
                return MatchResult(True, similarity, METHOD_FUZZY)
            partial = self._containment_score(first, second)
            if partial is not None:
                return MatchResult(True, partial, METHOD_TOKEN)
            return MatchResult(False, similarity, None)

        partial = self._containment_score(first, second)
        if partial is not None:
            return MatchResult(True, partial, METHOD_TOKEN)
        return MatchResult(False, 0.0, None)

    def match(self, entity1: str, entity2: str) -> Tuple[bool, float]:
        """
        Determine if two entities match using hybrid strategy
        
        Args:
            entity1: First entity (raw)
            entity2: Second entity (raw)
            
        Returns:
            (matches: bool, confidence: float)
        """
        result = self.match_detail(entity1, entity2)
        return (result.matches, result.score)
    
    def find_best_match(self, entity: str, candidates: List[str]) -> Tuple[Optional[str], float]:
        """
        Find best matching candidate for an entity
        
        Args:
            entity: Entity to match
            candidates: List of candidate entities
            
        Returns:
            (best_match: str, confidence: float) or (None, 0.0) if no match
        """
        best_match = None
        best_confidence = 0.0
        
        for candidate in candidates:
            matches, confidence = self.match(entity, candidate)
            if matches and confidence > best_confidence:
                best_confidence = confidence
                best_match = candidate
        
        return (best_match, best_confidence) if best_match is not None else (None, 0.0)
