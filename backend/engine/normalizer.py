"""
Entity normalizer with hybrid strategy
Follows Roadmap §2 and P2 decision: rules + fuzzy + synonyms
"""
import unicodedata
import re
from typing import Dict, List, Optional, Tuple
from difflib import SequenceMatcher

_PUNCTUATION = re.compile(r"[^\w\s-]")
# Decimal point or fraction bar between two digits ("2.5", "1/2"): kept as a hyphen
# so the number stays one token ("2-5") instead of fusing into "25"
_NUMBER_SEPARATOR = re.compile(r"(?<=\d)[.,/](?=\d)")
_NUMBER_TOKEN = re.compile(r"\d+(?:-\d+)*")
# Boundary between a letter and a digit, in either direction ("50kg" -> "50 kg")
_LETTER_DIGIT_BOUNDARY = re.compile(r"(?<=[^\W\d_])(?=\d)|(?<=\d)(?=[^\W\d_])")


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


class EntityNormalizer:
    """
    Hybrid entity normalization:
    1. Strict rules (lowercase, accents, whitespace, punctuation)
    2. Fuzzy matching (Levenshtein distance)
    3. FR/EN synonym mapping
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
        "50kg": ["50 kg", "50-kg"],
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

    def fuzzy_match(self, text1: str, text2: str) -> float:
        """
        Compute fuzzy similarity between two texts
        
        Args:
            text1: First text (normalized)
            text2: Second text (normalized)
            
        Returns:
            Similarity score (0.0 to 1.0)
        """
        return SequenceMatcher(None, text1, text2).ratio()
    
    def match(self, entity1: str, entity2: str) -> Tuple[bool, float]:
        """
        Determine if two entities match using hybrid strategy
        
        Args:
            entity1: First entity (raw)
            entity2: Second entity (raw)
            
        Returns:
            (matches: bool, confidence: float)
        """
        # Normalize both
        norm1 = self.normalize(entity1)
        norm2 = self.normalize(entity2)
        
        # Apply synonyms
        syn1 = self.apply_synonyms(norm1)
        syn2 = self.apply_synonyms(norm2)
        
        # Exact match after synonym mapping
        if syn1 == syn2:
            return (True, 1.0)

        # Products that differ by a number are different products
        # ("ciment 50 kg" vs "ciment 40 kg" would otherwise score 0.92)
        if self.numeric_tokens(syn1) != self.numeric_tokens(syn2):
            return (False, 0.0)
        
        # Fuzzy match
        similarity = self.fuzzy_match(syn1, syn2)
        matches = similarity >= self.fuzzy_threshold
        
        return (matches, similarity)
    
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
            if confidence > best_confidence:
                best_confidence = confidence
                best_match = candidate
        
        # Only return if above threshold
        if best_confidence >= self.fuzzy_threshold:
            return (best_match, best_confidence)
        
        return (None, 0.0)
