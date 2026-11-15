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


@pytest.mark.parametrize(
    ("short", "full"),
    [
        ("perceuse 500W", "Perceuse électrique 500W"),
        ("tuyau PVC", "Tuyau PVC Ø 32mm (barre 6m)"),
        ("câble", "Câble électrique 2.5mm² (rouleau 100m)"),
        ("pointes 2.5\"", "Pointes 2.5\" (boîte 500g)"),
        ("peinture", "Peinture satinée blanc 1L"),
        ("scie égoïne", "Scie égoïne 450mm"),
    ],
)
def test_should_match_by_token_when_one_name_is_contained_in_the_other(short, full):
    result = EntityNormalizer().match_detail(short, full)

    assert result.matches is True
    assert result.method == "token"
    assert 0.85 <= result.score < 1.0


@pytest.mark.parametrize(
    ("first", "second"),
    [
        ("ciment 50 kg", "Ciment-colle 25 kg"),
        ("ciment 50 kg", "Ciment-colle 50 kg"),
        ("ciment", "Ciment-colle 25 kg"),
        ("tuyau PVC 32mm", "Tuyau PPR 32mm"),
        ("tuyau PVC", "Raccord PVC coude 90° Ø 32"),
        ("marteau", "Perceuse électrique 500W"),
        ("kg", "Ciment 50 kg"),
        ("50", "Ciment 50 kg"),
    ],
)
def test_should_not_match_when_names_only_overlap(first, second):
    assert EntityNormalizer().match_detail(first, second).matches is False


def test_should_rank_a_closer_partial_name_higher_when_two_candidates_contain_the_name():
    normalizer = EntityNormalizer()

    near = normalizer.match_detail("tuyau PVC", "Tuyau PVC 32mm").score
    far = normalizer.match_detail("tuyau PVC", "Tuyau PVC Ø 32mm (barre 6m)").score

    assert near > far


@pytest.mark.parametrize(
    ("first", "second", "method"),
    [
        ("Ciment 50 kg", "ciment 50 kg", "exact"),
        ("cement 50 kg", "ciment 50 kg", "synonym"),
        ("perseuse 500W", "perceuse 500W", "fuzzy"),
        ("ciment 50 kg", "ciment 50 kg sac", "token"),
    ],
)
def test_should_report_the_method_when_names_match(first, second, method):
    assert EntityNormalizer().match_detail(first, second).method == method


@given(st.text(max_size=40), st.text(max_size=40))
def test_should_be_symmetric_when_comparing_any_two_names(first, second):
    normalizer = EntityNormalizer()

    assert normalizer.match_detail(first, second) == normalizer.match_detail(second, first)


NAME_WORDS = st.sampled_from(["tuyau", "pvc", "ciment", "32", "50", "mm", "kg", "barre"])


@given(st.lists(NAME_WORDS, min_size=1, max_size=5), st.lists(NAME_WORDS, min_size=1, max_size=5))
def test_should_be_symmetric_when_comparing_names_made_of_repeated_words(first, second):
    normalizer = EntityNormalizer()

    assert normalizer.match_detail(" ".join(first), " ".join(second)) == normalizer.match_detail(
        " ".join(second), " ".join(first)
    )


def test_should_give_the_same_answer_in_both_orders_when_a_number_is_repeated():
    normalizer = EntityNormalizer()

    assert normalizer.match("tuyau 32", "tuyau 32 32") == normalizer.match("tuyau 32 32", "tuyau 32")


@given(st.text(max_size=40), st.text(max_size=40))
def test_should_keep_score_between_0_and_1_when_comparing_any_two_names(first, second):
    result = EntityNormalizer().match_detail(first, second)

    assert 0.0 <= result.score <= 1.0
    assert (result.method is not None) is result.matches


@given(st.text(max_size=40))
def test_should_match_exactly_when_a_name_is_compared_with_itself(name):
    result = EntityNormalizer().match_detail(name, name)

    assert (result.matches, result.score, result.method) == (True, 1.0, "exact")


@given(st.text(max_size=40), st.text(max_size=40))
def test_should_give_the_same_result_when_names_are_normalized_first(first, second):
    normalizer = EntityNormalizer()

    assert normalizer.match_detail(first, second) == normalizer.match_detail(
        normalize_text(first), normalize_text(second)
    )
