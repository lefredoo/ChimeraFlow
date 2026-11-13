"""
Rule Interpreter
Executes rules against unified records with proper operator whitelist
"""
from typing import List, Dict, Any, Optional, Tuple
from datetime import datetime, timedelta, timezone
import logging
import re

from schemas.rule import RuleCreate, Operator
from mcp_servers.base import UnifiedRecord
from .normalizer import EntityNormalizer


logger = logging.getLogger(__name__)

# {product} or {source.field}; anything else between braces is left untouched
_PLACEHOLDER = re.compile(r"\{([a-z]+)(?:\.([a-zA-Z_0-9]+))?\}")


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

    return _PLACEHOLDER.sub(replace, template)


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
            List of correlations (each with provenance)
        """
        correlations = []
        
        # Filter trigger records by source
        trigger_source = rule.trigger.source
        filtered_triggers = [
            r for r in trigger_records
            if r.source == trigger_source
        ]
        
        logger.info(f"Executing rule {rule.id} on {len(filtered_triggers)} trigger records")
        
        # For each trigger record, attempt to correlate
        for trigger_record in filtered_triggers:
            correlation = self._correlate_record(rule, trigger_record, all_records)
            if correlation:
                correlations.append(correlation)
        
        return correlations
    
    def _correlate_record(
        self,
        rule: RuleCreate,
        trigger_record: UnifiedRecord,
        all_records: Dict[str, List[UnifiedRecord]]
    ) -> Optional[Dict[str, Any]]:
        """
        Attempt to correlate a single trigger record with other sources
        
        Returns:
            Correlation dict or None if no match
        """
        # Extract trigger entity
        trigger_entity = self._extract_entity(trigger_record, rule.trigger.entity)
        if not trigger_entity:
            return None
        
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
        
        # Template values: start with trigger entity
        template_values: Dict[str, Any] = {
            "product": trigger_entity["raw"]  # Use raw for display
        }
        
        # Attempt each join
        join_results = {}
        for join in rule.joins:
            source_records = all_records.get(join.source, [])
            
            # Find matching record
            match = self._find_join_match(
                trigger_entity,
                source_records,
                join,
                trigger_time,
                window_start,
                window_end
            )
            
            if match:
                # Add to provenance
                provenance.append({
                    "source": match.source,
                    "source_ref": match.source_ref,
                    "record_id": match.id
                })
                
                # Add payload to template values
                join_results[join.source] = match.payload
                template_values[join.source] = match.payload
        
        # Check if all required joins matched
        if len(join_results) < len(rule.joins):
            logger.debug(f"Incomplete joins for {trigger_record.id}: {len(join_results)}/{len(rule.joins)}")
            return None
        
        # Render message template
        message = render_template(rule.emit.template, template_values)

        # No detected_at here: engine output depends on its inputs only (P4);
        # the API layer stamps the detection time.
        return {
            "rule_id": rule.id,
            "severity": rule.emit.severity,
            "message": message,
            "provenance": provenance,
            "window_start": window_start.isoformat(),
            "window_end": window_end.isoformat()
        }
    
    def _extract_entity(self, record: UnifiedRecord, entity_type: str) -> Optional[Dict[str, str]]:
        """Extract entity of given type from record"""
        record_dict = record.to_dict()
        for entity in record_dict.get("entities", []):
            if entity["type"] == entity_type:
                return entity
        return None
    
    def _find_join_match(
        self,
        trigger_entity: Dict[str, str],
        source_records: List[UnifiedRecord],
        join: Any,
        trigger_time: datetime,
        window_start: datetime,
        window_end: datetime
    ) -> Optional[UnifiedRecord]:
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

        Returns:
            Best matching UnifiedRecord or None
        """
        field_name = join.on.get("field")
        best_key: Optional[Tuple[float, int, float, int]] = None
        best_record: Optional[UnifiedRecord] = None

        for index, record in enumerate(source_records):
            # Check time window
            record_time = _parse_timestamp(record.timestamp)
            if not (window_start <= record_time <= window_end):
                continue

            # Extract field value from payload
            field_value = record.payload.get(field_name)
            if not field_value:
                continue

            # Check entity match
            matches, confidence = self.normalizer.match(
                trigger_entity["raw"],
                str(field_value)
            )
            if not matches or not self._check_where_conditions(record.payload, join.where):
                continue

            offset_seconds = (record_time - trigger_time).total_seconds()
            key = (
                -round(confidence, 6),
                0 if offset_seconds <= 0 else 1,
                abs(offset_seconds),
                index,
            )
            if best_key is None or key < best_key:
                best_key = key
                best_record = record

        if best_record is not None:
            logger.debug(f"Join match for {trigger_entity['raw']}: {best_record.id} (score {-best_key[0]:.2f})")

        return best_record

    def _check_where_conditions(self, payload: Dict[str, Any], conditions: List[Any]) -> bool:
        """
        Check if payload satisfies WHERE conditions

        Security: Only whitelisted operators (Operator enum).
        A comparison between incompatible types (e.g. "abc" < 10) is a
        non-match for this record and never aborts the rule.
        """
        for condition in conditions:
            actual = payload.get(condition.field)
            if actual is None:
                return False

            try:
                satisfied = self._apply_operator(condition.op, actual, condition.value)
            except TypeError:
                logger.warning(
                    f"Incompatible types for condition {condition.field} {condition.op.value}: "
                    f"{type(actual).__name__} vs {type(condition.value).__name__}"
                )
                return False

            if not satisfied:
                return False

        return True

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
