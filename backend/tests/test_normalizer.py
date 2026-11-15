"""
Tests for the entity normalizer (P2: normalization idempotence)
"""
import pytest
from hypothesis import given, strategies as st

from engine.normalizer import EntityNormalizer, normalize_text

# The same product written four ways in the demo scenario (Roadmap §2)
CIMENT_VARIANTS = ["ciment 50 kg", "Ciment50kg", "cimént 50kg", "ciment (50kg)"]


@pytest.mark.parametrize("variant", CIMENT_VARIANTS)
def test_should_normalize_to_same_key_when_variant_of_ciment_50_kg(variant):
    assert normalize_text(variant) == "ciment 50 kg"


@given(st.text(max_size=100))
def test_should_be_idempotent_when_normalizing_any_text(text):
    once = normalize_text(text)

    assert normalize_text(once) == once


@pytest.mark.parametrize("variant", CIMENT_VARIANTS)
def test_should_match_with_full_confidence_when_variant_of_ciment_50_kg(variant):
    matches, confidence = EntityNormalizer().match(variant, "Ciment 50 kg")

    assert matches is True
    assert confidence == 1.0


def test_should_not_match_when_products_differ():
    matches, _ = EntityNormalizer().match("Ciment 50 kg", "Perceuse électrique 500W")

    assert matches is False


@pytest.mark.parametrize("variant", CIMENT_VARIANTS)
def test_should_match_when_two_ciment_variants_are_compared(variant):
    matches, _ = EntityNormalizer().match(variant, "ciment (50kg)")

    assert matches is True


@pytest.mark.parametrize(
    ("first", "second"),
    [
        ("ciment 50 kg", "ciment 40 kg"),
        ("pointes 100mm", "pointes 10mm"),
        ("câble 2.5mm", "câble 25mm"),
        ("tuyau 1/2 pouce", "tuyau 12 pouce"),
        ("tuyau PVC", "tuyau PVC 32mm"),
    ],
)
def test_should_not_match_when_numbers_differ(first, second):
    matches, confidence = EntityNormalizer().match(first, second)

    assert matches is False
    assert confidence == 0.0


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("Câble 2.5mm", "cable 2-5 mm"),
        ("tuyau 1/2 pouce", "tuyau 1-2 pouce"),
        ("peinture 2,5 litres", "peinture 2-5 litres"),
    ],
)
def test_should_keep_decimal_and_fraction_as_one_token_when_normalizing(raw, expected):
    assert normalize_text(raw) == expected


@pytest.mark.parametrize("raw", ["Câble 2.5mm", "tuyau 1/2 pouce", "1.2.3", "1.,2"])
def test_should_be_idempotent_when_text_contains_decimals_or_fractions(raw):
    once = normalize_text(raw)

    assert normalize_text(once) == once
