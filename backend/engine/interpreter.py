"""
Rule Interpreter
Executes rules against unified records with proper operator whitelist
"""
from dataclasses import dataclass
from typing import List, Dict, Any, Optional, Tuple
from datetime import datetime, timedelta, timezone
import logging
import re

from schemas.rule import PLACEHOLDER, RuleCreate, Operator, WhereCondition
from schemas.sources import ENTITIES_FIELD
from mcp_servers.base import UnifiedRecord
from .normalizer import EntityNormalizer, MatchResult


logger = logging.getLogger(__name__)

# Gaps are compared rounded, so that float noise (10.000000000000002 %) never decides a rule
_GAP_DECIMALS = 6


def _parse_timestamp(value: str) -> datetime:
    """Parse an ISO 8601 timestamp into a timezone-aware datetime.

    Source timestamps are naive (no offset); they are interpreted as UTC so
    that comparisons never mix naive and aware datetimes.

    Args:
        value: ISO 8601 timestamp, optionally ending with "Z".

    Returns:
        Timezone-aware datetime.

    Raises:
        ValueError: If the value is not a valid ISO 8601 timestamp.
    """
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed


def render_template(template: str, values: Dict[str, Any]) -> str:
    """Render an emit template in a single pass.

    Placeholders are replaced in one scan of the template, so text coming from
    a source (a product name, a payload field) is never scanned again: a value
    containing "{momo.phone}" stays literal. A placeholder without a value
    renders as an empty string rather than as something that looks like data.

    Args:
        template: Template such as "{product}: stock {access.qty_stock}".
        values: Template values: "product" (str) and one payload dict per source.

    Returns:
        Rendered message.
    """
    def replace(match: "re.Match[str]") -> str:
        name, field = match.group(1), match.group(2)
        value = values.get(name)
        if field is None:
            return str(value) if isinstance(value, (str, int, float)) else ""
        if not isinstance(value, dict):
            return ""
        field_value = value.get(field)
        return "" if field_value is None else str(field_value)

    return PLACEHOLDER.sub(replace, template)


@dataclass(frozen=True)
class JoinMatch:
    """The record a join picked, and why it was picked."""

    record: UnifiedRecord
    candidate_raw: str  # the text compared with the trigger entity
    result: MatchResult
    where: List[Dict[str, Any]]  # outcome of each condition, in rule order
    candidates: int  # in-window records whose name matched and whose conditions held


class RuleInterpreter:
    """
    Interprets and executes correlation rules
    
    Security: Only whitelisted operators allowed (R5 from Roadmap)
    Determinism: Same inputs → same outputs (P4)
    """
    
    def __init__(self):
        self.normalizer = EntityNormalizer(fuzzy_threshold=0.85)
    
    def execute(
        self,
        rule: RuleCreate,
        trigger_records: List[UnifiedRecord],
        all_records: Dict[str, List[UnifiedRecord]]
    ) -> List[Dict[str, Any]]:
        """
        Execute a rule against records
        
        Args:
            rule: Rule definition
            trigger_records: Records that match the trigger
            all_records: All available records by source {source: [records]}
            
        Returns:
            List of correlations (each with provenance and explanation), in
            trigger record order, then entity order within a record
        """
        correlations = []
        
        # Filter trigger records by source
        trigger_source = rule.trigger.source
        filtered_triggers = [
            r for r in trigger_records
            if r.source == trigger_source
        ]
        
        logger.info(f"Executing rule {rule.id} on {len(filtered_triggers)} trigger records")
        
        # For each trigger record, attempt to correlate every entity it carries
        for trigger_record in filtered_triggers:
            correlations.extend(self._correlate_record(rule, trigger_record, all_records))
        
        return correlations
    
    def _correlate_record(
        self,
        rule: RuleCreate,
        trigger_record: UnifiedRecord,
        all_records: Dict[str, List[UnifiedRecord]]
    ) -> List[Dict[str, Any]]:
        """
        Correlate a single trigger record with other sources

        A record that satisfies the trigger conditions yields one correlation
        per distinct entity of the rule's entity type (a message asking for two
        products correlates both).

        Returns:
            Correlations found, possibly empty
        """
        passed, trigger_conditions = self._check_where_conditions(
            trigger_record.payload, rule.trigger.where, {}
        )
        if not passed:
            return []

        correlations = []
        for entity in self._extract_entities(trigger_record, rule.trigger.entity):
            correlation = self._correlate_entity(
                rule, trigger_record, entity, trigger_conditions, all_records
            )
            if correlation:
                correlations.append(correlation)
        return correlations

    def _correlate_entity(
        self,
        rule: RuleCreate,
        trigger_record: UnifiedRecord,
        trigger_entity: Dict[str, str],
        trigger_conditions: List[Dict[str, Any]],
        all_records: Dict[str, List[UnifiedRecord]]
    ) -> Optional[Dict[str, Any]]:
        """
        Attempt to correlate one entity of a trigger record with the joined sources

        Returns:
            Correlation dict or None if a join found no record
        """
        # Apply time window: joined records must fall within window_seconds
        # before or after the trigger (reference data such as prices usually
        # predates the message that triggers the rule)
        trigger_time = _parse_timestamp(trigger_record.timestamp)
        window_start = trigger_time - timedelta(seconds=rule.window_seconds)
        window_end = trigger_time + timedelta(seconds=rule.window_seconds)
        
        # Provenance: start with trigger record
        provenance = [{
            "source": trigger_record.source,
            "source_ref": trigger_record.source_ref,
            "record_id": trigger_record.id
        }]
        
        # Template values and condition references: the trigger record first,
        # then each joined record (a join may refer to the ones before it)
        template_values: Dict[str, Any] = {
            "product": trigger_entity["raw"],  # Use raw for display
            trigger_record.source: trigger_record.payload,
        }
        context: Dict[str, Dict[str, Any]] = {trigger_record.source: trigger_record.payload}

        trigger_explanation = {
            "source": trigger_record.source,
            "record_id": trigger_record.id,
            "source_ref": trigger_record.source_ref,
            "entity": {
                "raw": trigger_entity["raw"],
                "norm": self.normalizer.prepare(trigger_entity["raw"]).norm,
            },
            "where": trigger_conditions,
        }
        join_explanations = []

        for join in rule.joins:
            match = self._find_join_match(
                trigger_entity,
                all_records.get(join.source, []),
                join,
                trigger_time,
                window_start,
                window_end,
                context,
            )
            if match is None:
                logger.debug(f"No {join.source} record for {trigger_record.id} / {trigger_entity['raw']}")
                return None

            record = match.record
            provenance.append({
                "source": record.source,
                "source_ref": record.source_ref,
                "record_id": record.id
            })
            template_values[join.source] = record.payload
            context[join.source] = record.payload
            join_explanations.append({
                "source": record.source,
                "record_id": record.id,
                "source_ref": record.source_ref,
                "on": {"entity": join.on.entity, "field": join.on.field},
                "candidate": {
                    "raw": match.candidate_raw,
                    "norm": self.normalizer.prepare(match.candidate_raw).norm,
                },
                "score": round(match.result.score, 4),
                "method": match.result.method,
                "candidates": match.candidates,
                "where": match.where,
            })

        # No detected_at here: engine output depends on its inputs only (P4);
        # the API layer stamps the detection time.
        return {
            "rule_id": rule.id,
            "severity": rule.emit.severity,
            "message": render_template(rule.emit.template, template_values),
            "provenance": provenance,
            "explanation": {"trigger": trigger_explanation, "joins": join_explanations},
            "window_start": window_start.isoformat(),
            "window_end": window_end.isoformat()
        }
    
    def _extract_entities(self, record: UnifiedRecord, entity_type: str) -> List[Dict[str, str]]:
        """Entities of a type carried by a record, in order, without duplicates.

        Two mentions that normalize to the same product ("ciment 50 kg" and
        "Ciment50kg" in one message) are one entity: the first one is kept.
        """
        entities: List[Dict[str, str]] = []
        seen = set()
        for entity in record.entities:
            if entity["type"] != entity_type or not entity["raw"]:
                continue
            key = self.normalizer.prepare(entity["raw"]).canonical
            if key in seen:
                continue
            seen.add(key)
            entities.append(entity)
        return entities
    
    def _candidate_names(self, record: UnifiedRecord, join: Any) -> List[str]:
        """Texts of a joined record that are compared with the trigger entity."""
        if join.on.field == ENTITIES_FIELD:
            return [
                entity["raw"] for entity in record.entities
                if entity["type"] == join.on.entity and entity["raw"]
            ]
        value = record.payload.get(join.on.field)
        return [str(value)] if value else []

    def _find_join_match(
        self,
        trigger_entity: Dict[str, str],
        source_records: List[UnifiedRecord],
        join: Any,
        trigger_time: datetime,
        window_start: datetime,
        window_end: datetime,
        context: Dict[str, Dict[str, Any]],
    ) -> Optional[JoinMatch]:
        """
        Find the best matching record in a join source

        Every in-window record that matches the entity and satisfies the WHERE
        conditions is a candidate. The winner is chosen deterministically:
        1. highest similarity score
        2. on a tie, a record at or before the trigger wins over one after it
        3. then the closest in time to the trigger (the most recent one when
           before it, so the latest price wins among duplicates)
        4. then source order

        Args:
            trigger_entity: Entity from trigger record
            source_records: Records from join source
            join: Join definition
            trigger_time: Timestamp of the trigger record
            window_start: Time window start
            window_end: Time window end
            context: Payloads of the trigger and earlier joins, by source (targets of `ref`)

        Returns:
            The winning JoinMatch, or None
        """
        best_key: Optional[Tuple[float, int, float, int]] = None
        best: Optional[JoinMatch] = None
        candidates = 0

        for index, record in enumerate(source_records):
            # Check time window
            record_time = _parse_timestamp(record.timestamp)
            if not (window_start <= record_time <= window_end):
                continue

            # Best name of the record that matches the trigger entity
            name_match: Optional[Tuple[str, MatchResult]] = None
            for name in self._candidate_names(record, join):
                result = self.normalizer.match_detail(trigger_entity["raw"], name)
                if result.matches and (name_match is None or result.score > name_match[1].score):
                    name_match = (name, result)
            if name_match is None:
                continue

            passed, conditions = self._check_where_conditions(record.payload, join.where, context)
            if not passed:
                continue
            candidates += 1

            offset_seconds = (record_time - trigger_time).total_seconds()
            key = (
                -round(name_match[1].score, 6),
                0 if offset_seconds <= 0 else 1,
                abs(offset_seconds),
                index,
            )
            if best_key is None or key < best_key:
                best_key = key
                best = JoinMatch(
                    record=record,
                    candidate_raw=name_match[0],
                    result=name_match[1],
                    where=conditions,
                    candidates=0,
                )

        if best is None:
            return None
        logger.debug(f"Join match for {trigger_entity['raw']}: {best.record.id} (score {best.result.score:.2f})")
        return JoinMatch(best.record, best.candidate_raw, best.result, best.where, candidates)

    def _check_where_conditions(
        self,
        payload: Dict[str, Any],
        conditions: List[WhereCondition],
        context: Dict[str, Dict[str, Any]],
    ) -> Tuple[bool, List[Dict[str, Any]]]:
        """
        Check if payload satisfies WHERE conditions

        Security: Only whitelisted operators (Operator enum).
        A comparison between incompatible types (e.g. "abc" < 10) is a
        non-match for this record and never aborts the rule.

        Returns:
            (all conditions hold, one outcome per condition checked). The
            outcomes stop at the first failing condition.
        """
        outcomes: List[Dict[str, Any]] = []
        for condition in conditions:
            outcome = self._evaluate_condition(condition, payload, context)
            outcomes.append(outcome)
            if not outcome["passed"]:
                return False, outcomes
        return True, outcomes

    def _evaluate_condition(
        self,
        condition: WhereCondition,
        payload: Dict[str, Any],
        context: Dict[str, Dict[str, Any]],
    ) -> Dict[str, Any]:
        """Evaluate one condition and report the values it was decided on.

        Returns:
            {field, op, expected, actual, passed} plus `ref`, `tolerance_pct`
            and `gap_pct` when the condition uses them. `expected` is the
            literal value, or the value found through `ref`.
        """
        actual = payload.get(condition.field)
        outcome: Dict[str, Any] = {"field": condition.field, "op": condition.op.value}

        expected: Any = condition.value
        parts = condition.ref_parts()
        if parts is not None:
            ref_source, ref_field = parts
            expected = context.get(ref_source, {}).get(ref_field)
            outcome["ref"] = condition.ref
        if condition.tolerance_pct is not None:
            outcome["tolerance_pct"] = condition.tolerance_pct
        outcome["expected"] = expected
        outcome["actual"] = actual
        outcome["passed"] = False

        if actual is None or expected is None:
            return outcome

        try:
            if condition.tolerance_pct is None:
                outcome["passed"] = self._apply_operator(condition.op, actual, expected)
                return outcome

            gap = self._gap_pct(actual, expected)
            if gap is None:
                return outcome
            outcome["gap_pct"] = gap
            outcome["passed"] = self._apply_operator(condition.op, gap, condition.tolerance_pct)
        except TypeError:
            logger.warning(
                f"Incompatible types for condition {condition.field} {condition.op.value}: "
                f"{type(actual).__name__} vs {type(expected).__name__}"
            )
        return outcome

    @staticmethod
    def _gap_pct(actual: Any, reference: Any) -> Optional[float]:
        """Relative gap |actual - reference| / |reference| in percent.

        Returns:
            The gap, or None when either side is not a number or the
            reference is zero (the gap is undefined, so the condition fails).
        """
        for value in (actual, reference):
            if isinstance(value, bool) or not isinstance(value, (int, float)):
                return None
        if reference == 0:
            return None
        return round(abs(actual - reference) / abs(reference) * 100, _GAP_DECIMALS)

    def _apply_operator(self, op: Operator, actual: Any, expected: Any) -> bool:
        """Apply one whitelisted operator.

        Args:
            op: Operator from the whitelist.
            actual: Value found in the source payload.
            expected: Value declared in the rule.

        Returns:
            True if the condition holds.

        Raises:
            TypeError: If the operands cannot be compared.
        """
        if op == Operator.eq:
            return actual == expected
        if op == Operator.ne:
            return actual != expected
        if op == Operator.lt:
            return actual < expected
        if op == Operator.lte:
            return actual <= expected
        if op == Operator.gt:
            return actual > expected
        if op == Operator.gte:
            return actual >= expected
        if op == Operator.contains:
            return str(expected) in str(actual)
        if op == Operator.in_:
            return actual in expected

        logger.warning(f"Unknown operator: {op}")
        return False
