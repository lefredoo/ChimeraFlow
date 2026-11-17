"""
P6 (no fabrication) on the interpreter, over generated records AND generated rules.

For every emitted correlation:
- each provenance entry is an input record, in rule order (trigger, then one per join);
- the message is the template literal text plus values read from the cited input
  records (an independent oracle re-renders it), so no value is invented and a source
  text that looks like a placeholder is never expanded;
- every explanation value (entity, candidate name, condition `actual` and `expected`,
  gap) is read from, or recomputed from, the cited input records and the rule.
"""
import json
import math
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Tuple

from hypothesis import HealthCheck, find, given, settings, strategies as st

from engine.interpreter import RuleInterpreter
from engine.normalizer import EntityNormalizer
from mcp_servers.base import UnifiedRecord
from schemas.rule import PLACEHOLDER, Operator, RuleCreate
from schemas.sources import SOURCE_COLUMNS, TEMPLATE_FORBIDDEN_COLUMNS

ORIGIN = datetime(2026, 11, 3, 12, 0, 0)
SOURCES = ("whatsapp", "access", "excel", "momo")
PRODUCTS = [
    "ciment 50 kg", "Ciment50kg", "cement 50 kg", "ciment-colle 25 kg", "perceuse 500W",
    "Perceuse électrique 500W", "tuyau PVC", "Tuyau PVC Ø 32mm (barre 6m)", "marteau", "Marteau rivoir 500g",
]
# Texts that look like placeholders: a source value must never be expanded
PLACEHOLDER_LOOKALIKES = ["{product}", "{access.qty_stock}", "{excel.Prix_Unitaire}", "{momo.phone}", "{", "}{}"]
MAX_OFFSET = 1_500_000
ORDERING = (Operator.lt, Operator.lte, Operator.gt, Operator.gte)

product_names = st.sampled_from(PRODUCTS)
texts = st.one_of(product_names, product_names, st.text(max_size=20), st.sampled_from(PLACEHOLDER_LOOKALIKES))
numbers = st.one_of(
    st.integers(-10**6, 10**6),
    st.integers(),
    st.floats(allow_nan=False, allow_infinity=False),
)
payload_values = st.one_of(texts, numbers, st.booleans(), st.none())
# Columns that carry names: mostly product names, so that joins find candidates
NAME_COLUMNS = frozenset({"designation", "Produit", "reference", "text", "Fournisseur", "table"})
name_values = st.one_of(product_names, product_names, product_names, product_names, payload_values)
literals = st.one_of(texts, numbers, st.booleans())


def _record(source: str, index: int, offset: int, payload: dict, entities: list) -> UnifiedRecord:
    return UnifiedRecord(
        id=f"{source}-{index}",
        source=source,
        source_ref=f"{source}.file#{index}",
        timestamp=(ORIGIN + timedelta(seconds=offset)).isoformat(),
        lang="fr",
        entities=[{"type": kind, "raw": raw, "norm": raw.lower()} for kind, raw in entities],
        payload=payload,
    )


@st.composite
def records_of(draw, source: str) -> List[UnifiedRecord]:
    columns = sorted(SOURCE_COLUMNS[source])
    one = st.tuples(
        st.integers(-MAX_OFFSET, MAX_OFFSET),
        st.fixed_dictionaries({}, optional={c: name_values if c in NAME_COLUMNS else payload_values for c in columns}),
        st.lists(st.tuples(st.sampled_from(["product"] * 6 + ["person"]), texts), max_size=3),
    )
    return [_record(source, i, *parts) for i, parts in enumerate(draw(st.lists(one, max_size=4)))]


@st.composite
def conditions(draw, source: str, ref_sources: List[str]) -> dict:
    field = draw(st.sampled_from(sorted(SOURCE_COLUMNS[source])))
    kind = draw(st.sampled_from(["value", "in", "ref"] if ref_sources else ["value", "in"]))
    if kind == "value":
        return {"field": field, "op": draw(st.sampled_from([o.value for o in Operator if o != Operator.in_])),
                "value": draw(literals)}
    if kind == "in":
        return {"field": field, "op": "in", "value": draw(st.lists(st.one_of(literals, st.none()), max_size=5))}
    ref_source = draw(st.sampled_from(ref_sources))
    ref_field = draw(st.sampled_from(sorted(SOURCE_COLUMNS[ref_source])))
    op = draw(st.sampled_from([o for o in Operator if o != Operator.in_]))
    condition = {"field": field, "op": op.value, "ref": f"{ref_source}.{ref_field}"}
    if op in ORDERING and draw(st.booleans()):
        condition["tolerance_pct"] = draw(st.floats(0, 1000, allow_nan=False, allow_infinity=False))
    return condition


def some_conditions(source: str, ref_sources: List[str]):
    """Mostly no condition, so that enough rules find a record."""
    return st.one_of(st.just([]), st.just([]), st.lists(conditions(source, ref_sources), min_size=1, max_size=2))


@st.composite
def rules(draw) -> RuleCreate:
    trigger_source = draw(st.sampled_from(SOURCES))
    joined = draw(st.lists(st.sampled_from(SOURCES), min_size=1, max_size=4, unique=True))
    available = [trigger_source]
    joins = []
    for source in joined:
        join: Dict[str, Any] = {
            "source": source,
            "on": {
                "entity": draw(st.sampled_from(["product"] * 6 + ["person"])),
                "field": draw(st.sampled_from([*sorted(SOURCE_COLUMNS[source] & NAME_COLUMNS or SOURCE_COLUMNS[source]), "entities"])),
            },
            "where": draw(some_conditions(source, list(available))),
        }
        if source == "access":
            join["table"] = "Articles"
        if source == "excel":
            join["sheet"] = "Tarifs"
        joins.append(join)
        if source not in available:
            available.append(source)

    placeholders = ["{product}"] + [
        f"{{{source}.{column}}}"
        for source in available
        for column in sorted(SOURCE_COLUMNS[source] - TEMPLATE_FORBIDDEN_COLUMNS.get(source, frozenset()))
    ]
    literal_text = st.text(alphabet="abc XYZ:,-.0123456789€", max_size=8)
    template = "".join(draw(st.lists(st.one_of(literal_text, st.sampled_from(placeholders)), min_size=1, max_size=6)))
    return RuleCreate.model_validate({
        "id": "r_fabrication",
        "natural_language": "Rule generated by the no-fabrication property test.",
        "trigger": {
            "source": trigger_source,
            "entity": draw(st.sampled_from(["product"] * 6 + ["person"])),
            "where": draw(some_conditions(trigger_source, [])),
        },
        "joins": joins,
        "window_seconds": draw(st.integers(60, 2_592_000)),
        "emit": {"severity": "info", "template": template or "-"},
    })


@st.composite
def scenarios(draw) -> Tuple[RuleCreate, Dict[str, List[UnifiedRecord]]]:
    rule = draw(rules())
    return rule, {source: draw(records_of(source)) for source in SOURCES}


def _run(rule: RuleCreate, by_source: Dict[str, List[UnifiedRecord]]) -> List[dict]:
    every_record = [record for records in by_source.values() for record in records]
    return RuleInterpreter().execute(rule, every_record, by_source)


def _timestamp(record: UnifiedRecord) -> datetime:
    return datetime.fromisoformat(record.timestamp).replace(tzinfo=timezone.utc)


def _candidate_names(record: UnifiedRecord, join) -> List[str]:
    if join.on.field == "entities":
        return [e["raw"] for e in record.entities if e["type"] == join.on.entity and e["raw"]]
    value = record.payload.get(join.on.field)
    return [str(value)] if value else []


def _expected_message(template: str, product: str, payloads: Dict[str, dict]) -> str:
    """Re-render the template in one pass from the cited records only."""
    parts, position = [], 0
    for match in PLACEHOLDER.finditer(template):
        parts.append(template[position:match.start()])
        name, column = match.group(1), match.group(2)
        if column is None:
            parts.append(product)
        else:
            value = payloads[name].get(column)
            parts.append("" if value is None else str(value))
        position = match.end()
    parts.append(template[position:])
    return "".join(parts)


def _check_conditions(declared, outcomes, payload, context) -> None:
    assert len(outcomes) == len(declared)
    for condition, outcome in zip(declared, outcomes):
        assert outcome["passed"] is True
        assert (outcome["field"], outcome["op"]) == (condition.field, condition.op.value)
        assert outcome["actual"] == payload.get(condition.field)
        parts = condition.ref_parts()
        if parts is None:
            assert outcome["expected"] == condition.value
            assert "ref" not in outcome
            continue
        assert outcome["ref"] == condition.ref
        assert outcome["expected"] == context[parts[0]].get(parts[1])
        if "gap_pct" in outcome:
            assert math.isfinite(outcome["gap_pct"])
            assert outcome["gap_pct"] == round(
                abs(outcome["actual"] - outcome["expected"]) / abs(outcome["expected"]) * 100, 6
            )


def _check_correlation(rule: RuleCreate, by_source: Dict[str, List[UnifiedRecord]], correlation: dict) -> None:
    json.dumps(correlation, allow_nan=False)  # what is stored must be valid JSON: no NaN or infinity computed
    known = {(r.source, r.id): r for records in by_source.values() for r in records}
    normalizer = EntityNormalizer()

    # Provenance: the trigger, then one input record per join, in rule order
    provenance = correlation["provenance"]
    assert [p["source"] for p in provenance] == [rule.trigger.source, *(j.source for j in rule.joins)]
    cited = []
    for entry in provenance:
        record = known[(entry["source"], entry["record_id"])]
        assert entry["source_ref"] == record.source_ref
        cited.append(record)
    trigger_record, joined_records = cited[0], cited[1:]

    # Trigger explanation
    trigger = correlation["explanation"]["trigger"]
    assert (trigger["source"], trigger["record_id"], trigger["source_ref"]) == (
        trigger_record.source, trigger_record.id, trigger_record.source_ref,
    )
    trigger_names = [e["raw"] for e in trigger_record.entities if e["type"] == rule.trigger.entity]
    assert trigger["entity"]["raw"] in trigger_names
    assert trigger["entity"]["norm"] == normalizer.prepare(trigger["entity"]["raw"]).norm
    context = {trigger_record.source: trigger_record.payload}
    _check_conditions(rule.trigger.where, trigger["where"], trigger_record.payload, context)

    # Join explanations, each condition checked against the context known at that join
    joins = correlation["explanation"]["joins"]
    assert len(joins) == len(rule.joins)
    for join, record, explanation in zip(rule.joins, joined_records, joins):
        assert (explanation["source"], explanation["record_id"], explanation["source_ref"]) == (
            record.source, record.id, record.source_ref,
        )
        assert explanation["on"] == {"entity": join.on.entity, "field": join.on.field}
        assert explanation["candidate"]["raw"] in _candidate_names(record, join)
        assert explanation["candidate"]["norm"] == normalizer.prepare(explanation["candidate"]["raw"]).norm
        assert 0.0 <= explanation["score"] <= 1.0
        assert explanation["candidates"] >= 1
        _check_conditions(join.where, explanation["where"], record.payload, context)
        context[record.source] = record.payload

    # Message: template literal text plus values of the cited records only
    expected = _expected_message(rule.emit.template, trigger["entity"]["raw"], context)
    assert correlation["message"] == expected
    assert (correlation["rule_id"], correlation["severity"]) == (rule.id, rule.emit.severity)

    # Window: derived from the trigger timestamp and the rule only
    window = timedelta(seconds=rule.window_seconds)
    assert correlation["window_start"] == (_timestamp(trigger_record) - window).isoformat()
    assert correlation["window_end"] == (_timestamp(trigger_record) + window).isoformat()


@settings(suppress_health_check=[HealthCheck.too_slow, HealthCheck.data_too_large, HealthCheck.filter_too_much])
@given(scenario=scenarios())
def test_should_emit_only_values_read_from_the_input_records_when_a_correlation_is_found(scenario):
    rule, by_source = scenario

    for correlation in _run(rule, by_source):
        _check_correlation(rule, by_source, correlation)


# Integers beyond the float range exist in a payload (JSON has no size limit): a gap must stay defined or be refused
HUGE = 10**310
prices = st.one_of(st.integers(-1000, 100_000), st.integers(), st.integers(HUGE, HUGE * 10**10),
                   st.integers(-HUGE * 10**10, -HUGE), st.floats(allow_nan=False, allow_infinity=False),
                   st.booleans(), st.none(), texts)


@st.composite
def price_gap_scenarios(draw) -> Tuple[RuleCreate, Dict[str, List[UnifiedRecord]]]:
    """A price list compared with the purchase price through `ref` and `tolerance_pct` (numbers of any kind)."""
    product = draw(product_names)
    op = draw(st.sampled_from([o.value for o in ORDERING]))
    rule = RuleCreate.model_validate({
        "id": "r_price_gap",
        "natural_language": "Rule used by the price gap case of the no-fabrication property test.",
        "trigger": {"source": "whatsapp", "entity": "product"},
        "joins": [
            {"source": "access", "table": "Articles", "on": {"entity": "product", "field": "designation"},
             "where": [{"field": "qty_stock", "op": draw(st.sampled_from(["lt", "gte", "ne"])),
                        "value": draw(st.integers(-5, 50))}]},
            {"source": "excel", "sheet": "Tarifs", "on": {"entity": "product", "field": "Produit"},
             "where": [{"field": "Prix_Unitaire", "op": op, "ref": "access.prix_achat",
                        "tolerance_pct": draw(st.floats(0, 1000, allow_nan=False, allow_infinity=False))}]},
        ],
        "window_seconds": 2_592_000,
        "emit": {"severity": "warning",
                 "template": "{product}: stock {access.qty_stock}, achat {access.prix_achat}, prix {excel.Prix_Unitaire}"},
    })
    by_source = {
        "whatsapp": [_record("whatsapp", 0, 0, {"author": "A", "text": product}, [("product", product)])],
        "access": [_record("access", 0, -10, {"designation": product, "qty_stock": draw(prices),
                                                "prix_achat": draw(prices)}, [])],
        "excel": [_record("excel", 0, -20, {"Produit": product, "Prix_Unitaire": draw(prices)}, [])],
    }
    return rule, by_source


@settings(suppress_health_check=[HealthCheck.too_slow, HealthCheck.data_too_large])
@given(scenario=price_gap_scenarios())
def test_should_emit_only_values_read_from_the_input_records_when_comparing_prices_with_a_tolerance(scenario):
    rule, by_source = scenario

    for correlation in _run(rule, by_source):
        _check_correlation(rule, by_source, correlation)


def test_should_reach_tolerance_comparisons_when_exploring_price_gap_scenarios():
    """Guards against a vacuous property: a gap must be computed and pass in some scenario."""
    def has_gap(scenario) -> bool:
        return any(
            "gap_pct" in outcome
            for correlation in _correlations(scenario)
            for join in correlation["explanation"]["joins"]
            for outcome in join["where"]
        )

    find(price_gap_scenarios(), has_gap, settings=settings(max_examples=2000))


def _correlations(scenario) -> List[dict]:
    return _run(*scenario)


def test_should_generate_correlations_when_exploring_scenarios():
    """Guards against a vacuous property: the generators must reach correlations."""
    find(scenarios(), lambda scenario: len(_correlations(scenario)) >= 1, settings=settings(max_examples=2000))


def test_should_not_expand_a_placeholder_lookalike_when_a_source_value_contains_one():
    rule = RuleCreate.model_validate({
        "id": "r_lookalike",
        "natural_language": "Rule used to check that source text is not expanded.",
        "trigger": {"source": "whatsapp", "entity": "product"},
        "joins": [{"source": "excel", "sheet": "Tarifs", "on": {"entity": "product", "field": "Produit"}}],
        "window_seconds": 86400,
        "emit": {"severity": "info", "template": "{product} / {excel.Fournisseur}"},
    })
    message = _record("whatsapp", 0, 0, {"author": "A", "text": "x"}, [("product", "ciment 50 kg")])
    price = _record("excel", 0, 0, {"Produit": "ciment 50 kg", "Fournisseur": "{access.qty_stock}"}, [])
    by_source = {"whatsapp": [message], "excel": [price]}

    correlations = _run(rule, by_source)

    assert [c["message"] for c in correlations] == ["ciment 50 kg / {access.qty_stock}"]
    assert math.isfinite(correlations[0]["explanation"]["joins"][0]["score"])


def _price_gap_run(purchase_price, list_price) -> List[dict]:
    """Run the price gap rule on one message, one stock row and one price row."""
    rule = RuleCreate.model_validate({
        "id": "r_price_gap",
        "natural_language": "Rule used by the undefined gap regression tests.",
        "trigger": {"source": "whatsapp", "entity": "product"},
        "joins": [
            {"source": "access", "table": "Articles", "on": {"entity": "product", "field": "designation"}},
            {"source": "excel", "sheet": "Tarifs", "on": {"entity": "product", "field": "Produit"},
             "where": [{"field": "Prix_Unitaire", "op": "gt", "ref": "access.prix_achat", "tolerance_pct": 10}]},
        ],
        "window_seconds": 86400,
        "emit": {"severity": "warning", "template": "{product}: {excel.Prix_Unitaire}"},
    })
    by_source = {
        "whatsapp": [_record("whatsapp", 0, 0, {"author": "A", "text": "x"}, [("product", "ciment 50 kg")])],
        "access": [_record("access", 0, 0, {"designation": "ciment 50 kg", "prix_achat": purchase_price}, [])],
        "excel": [_record("excel", 0, 0, {"Produit": "ciment 50 kg", "Prix_Unitaire": list_price}, [])],
    }
    return _run(rule, by_source)


def test_should_not_abort_the_rule_when_a_price_is_an_integer_beyond_the_float_range():
    # Regression found by the property: int / int raised OverflowError and failed the whole execution
    assert _price_gap_run(1, 10**400) == []


def test_should_refuse_the_condition_when_the_gap_is_not_a_finite_number():
    # Regression found by the property: the gap was infinity, which cannot be stored as JSON
    assert _price_gap_run(1e-300, 1e308) == []
