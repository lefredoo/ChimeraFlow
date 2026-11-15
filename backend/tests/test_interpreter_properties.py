"""
Property-based tests of the interpreter (Hypothesis).

P1 provenance: every record a correlation cites is one of the inputs.
P4 determinism: the same inputs give the same correlations.
P5 window monotonicity: widening the window never removes a correlation.
"""
from datetime import datetime, timedelta

from hypothesis import given, strategies as st

from engine.interpreter import RuleInterpreter
from mcp_servers.base import UnifiedRecord
from schemas.rule import RuleCreate

ORIGIN = datetime(2026, 11, 3, 12, 0, 0)
PRODUCTS = [
    "ciment 50 kg", "Ciment50kg", "cement 50 kg", "ciment-colle 25 kg", "perceuse 500W",
    "Perceuse électrique 500W", "tuyau PVC", "Tuyau PVC Ø 32mm (barre 6m)", "marteau", "Marteau rivoir 500g",
]
MAX_WINDOW = 2_592_000
MAX_OFFSET = 1_500_000  # seconds from the trigger: reaches beyond the widest window


def _rule(window_seconds: int, where=None) -> RuleCreate:
    join = {
        "source": "excel",
        "sheet": "Tarifs",
        "on": {"entity": "product", "field": "Produit"},
        "where": where or [],
    }
    return RuleCreate.model_validate({
        "id": "r_property",
        "natural_language": "Rule used by the property tests of the interpreter.",
        "trigger": {"source": "whatsapp", "entity": "product"},
        "joins": [join],
        "window_seconds": window_seconds,
        "emit": {"severity": "info", "template": "{product} {excel.Prix_Unitaire}"},
    })


def _message(index: int, offset: int, products: list) -> UnifiedRecord:
    return UnifiedRecord(
        id=f"wa-{index}", source="whatsapp", source_ref=f"chat.txt#L{index}",
        timestamp=(ORIGIN + timedelta(seconds=offset)).isoformat(), lang="fr",
        entities=[{"type": "product", "raw": raw, "norm": raw.lower()} for raw in products],
        payload={"author": "Client A", "text": " ".join(products)},
    )


def _price(index: int, offset: int, name: str, price: int) -> UnifiedRecord:
    return UnifiedRecord(
        id=f"excel-{index}", source="excel", source_ref=f"tarifs.xlsx#row{index}",
        timestamp=(ORIGIN + timedelta(seconds=offset)).isoformat(), lang="fr",
        entities=[{"type": "product", "raw": name, "norm": name.lower()}],
        payload={"Produit": name, "Prix_Unitaire": price},
    )


messages = st.lists(
    st.tuples(st.integers(-MAX_OFFSET, MAX_OFFSET), st.lists(st.sampled_from(PRODUCTS), min_size=1, max_size=3)),
    max_size=6,
).map(lambda items: [_message(i, offset, products) for i, (offset, products) in enumerate(items)])

prices = st.lists(
    st.tuples(st.integers(-MAX_OFFSET, MAX_OFFSET), st.sampled_from(PRODUCTS), st.integers(0, 60000)),
    max_size=10,
).map(lambda items: [_price(i, offset, name, price) for i, (offset, name, price) in enumerate(items)])

windows = st.integers(60, MAX_WINDOW)


def _run(rule: RuleCreate, triggers, excel):
    return RuleInterpreter().execute(rule, triggers, {"whatsapp": triggers, "excel": excel})


def _triggered(correlations):
    """The (message, product) pairs that found a price: what a window must never lose."""
    return {
        (c["provenance"][0]["record_id"], c["explanation"]["trigger"]["entity"]["raw"]) for c in correlations
    }


@given(triggers=messages, excel=prices, first=windows, second=windows)
def test_should_keep_every_correlation_when_the_window_is_widened(triggers, excel, first, second):
    narrow, wide = sorted((first, second))

    narrow_found = _triggered(_run(_rule(narrow), triggers, excel))
    wide_found = _triggered(_run(_rule(wide), triggers, excel))

    assert narrow_found <= wide_found


@given(
    triggers=messages, excel=prices, first=windows, second=windows,
    threshold=st.integers(0, 60000),
)
def test_should_keep_every_correlation_when_the_window_is_widened_and_a_condition_filters_candidates(
    triggers, excel, first, second, threshold
):
    narrow, wide = sorted((first, second))
    where = [{"field": "Prix_Unitaire", "op": "gt", "value": threshold}]

    narrow_found = _triggered(_run(_rule(narrow, where), triggers, excel))
    wide_found = _triggered(_run(_rule(wide, where), triggers, excel))

    assert narrow_found <= wide_found


@given(triggers=messages, excel=prices, window=windows)
def test_should_cite_only_input_records_when_a_correlation_is_emitted(triggers, excel, window):
    known = {(record.source, record.id, record.source_ref) for record in [*triggers, *excel]}

    correlations = _run(_rule(window), triggers, excel)

    cited = {(p["source"], p["record_id"], p["source_ref"]) for c in correlations for p in c["provenance"]}
    assert cited <= known


@given(triggers=messages, excel=prices, window=windows)
def test_should_only_render_prices_found_in_the_sources_when_a_correlation_is_emitted(triggers, excel, window):
    source_prices = {str(record.payload["Prix_Unitaire"]) for record in excel}

    correlations = _run(_rule(window), triggers, excel)

    assert all(c["message"].rsplit(" ", 1)[-1] in source_prices for c in correlations)


@given(triggers=messages, excel=prices, window=windows)
def test_should_return_identical_correlations_when_the_same_inputs_are_run_twice(triggers, excel, window):
    rule = _rule(window)

    assert _run(rule, triggers, excel) == _run(rule, triggers, excel)
