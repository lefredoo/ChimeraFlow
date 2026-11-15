"""
Pydantic schemas for Rule validation
Implements strict validation per AGENTS.md §20 (security: no code execution)
"""
import math
import re
from pydantic import BaseModel, Field, field_validator, model_validator
from typing import List, Dict, Any, Literal, Optional
from enum import Enum

from .sources import ENTITIES_FIELD, SOURCE_COLUMNS, TEMPLATE_FORBIDDEN_COLUMNS

# Bounds of the free-form parts of a rule (a draft written by a model can be arbitrarily large)
MAX_NAME_LENGTH = 100
MAX_VALUE_LENGTH = 200
MAX_LIST_ITEMS = 50
MAX_WHERE_ITEMS = 10
MAX_TEMPLATE_LENGTH = 500
MAX_TOLERANCE_PCT = 1000.0

# {product} or {source.field}; anything else between braces is left untouched
PLACEHOLDER = re.compile(r"\{([a-z]+)(?:\.([a-zA-Z_0-9]+))?\}")
# "<source>.<field>": the field of a record already matched by the rule
_REF_PATTERN = re.compile(r"^(whatsapp|momo|excel|access)\.([A-Za-z_][A-Za-z0-9_]{0,63})$")

SourceName = Literal["whatsapp", "momo", "excel", "access"]


# Allowed operators (whitelist - R5 from Roadmap)
class Operator(str, Enum):
    eq = "eq"
    ne = "ne"
    lt = "lt"
    lte = "lte"
    gt = "gt"
    gte = "gte"
    contains = "contains"
    in_ = "in"


# Operators that can compare a gap in percent with a tolerance
_ORDERING_OPERATORS = (Operator.lt, Operator.lte, Operator.gt, Operator.gte)


def _is_scalar(value: Any) -> bool:
    """True for a JSON scalar of bounded size (null, bool, number, short string)."""
    if value is None or isinstance(value, (bool, int)):
        return True
    if isinstance(value, float):
        return math.isfinite(value)
    return isinstance(value, str) and len(value) <= MAX_VALUE_LENGTH


class WhereCondition(BaseModel):
    """
    Condition on a record: `field <op> value`, or `field <op> ref`.

    Only whitelisted operators are allowed (security: R5). The right side is
    either a literal `value`, or `ref` = "<source>.<field>", the field of a
    record the rule already matched (the trigger or an earlier join). With
    `tolerance_pct`, the condition compares the relative gap between the two
    values, |field - ref| / |ref| in percent, with the tolerance:
    {"field": "Prix_Unitaire", "op": "gt", "ref": "access.prix_achat",
    "tolerance_pct": 10} holds when the prices differ by more than 10 %.
    """
    model_config = {"extra": "forbid"}

    field: str = Field(..., min_length=1, max_length=MAX_NAME_LENGTH)
    op: Operator
    value: Any = None  # String, int, float, list (absent when `ref` is used)
    ref: Optional[str] = Field(default=None, max_length=MAX_NAME_LENGTH)
    tolerance_pct: Optional[float] = Field(default=None, ge=0, le=MAX_TOLERANCE_PCT, allow_inf_nan=False)

    @field_validator("value")
    @classmethod
    def validate_value(cls, value: Any) -> Any:
        """A literal is a bounded scalar, or a bounded list of scalars."""
        if isinstance(value, list):
            if len(value) > MAX_LIST_ITEMS or not all(_is_scalar(item) for item in value):
                raise ValueError("value must be a scalar or a short list of scalars")
            return value
        if not _is_scalar(value):
            raise ValueError("value must be a scalar or a short list of scalars")
        return value

    @model_validator(mode="after")
    def validate_right_side(self) -> "WhereCondition":
        """Exactly one of `value` and `ref`; `tolerance_pct` only with `ref` and an ordering operator."""
        has_value = "value" in self.model_fields_set and self.value is not None
        if self.ref is None:
            if not has_value:
                raise ValueError("condition needs a 'value' or a 'ref'")
            if self.tolerance_pct is not None:
                raise ValueError("'tolerance_pct' needs a 'ref'")
            return self
        if has_value:
            raise ValueError("condition takes either 'value' or 'ref', not both")
        if not _REF_PATTERN.match(self.ref):
            raise ValueError("'ref' must look like <source>.<field>")
        if self.op == Operator.in_:
            raise ValueError("operator 'in' cannot be used with 'ref'")
        if self.tolerance_pct is not None and self.op not in _ORDERING_OPERATORS:
            raise ValueError("'tolerance_pct' needs one of the operators lt, lte, gt, gte")
        return self

    @model_validator(mode="after")
    def validate_in_list(self) -> "WhereCondition":
        """Operator `in` tests membership in a list."""
        if self.op == Operator.in_ and self.ref is None and not isinstance(self.value, list):
            raise ValueError("operator 'in' needs a list value")
        return self

    def ref_parts(self) -> Optional[tuple]:
        """(source, field) of `ref`, None when the condition has a literal value."""
        if self.ref is None:
            return None
        match = _REF_PATTERN.match(self.ref)
        return (match.group(1), match.group(2)) if match else None


class RuleTrigger(BaseModel):
    """
    Rule trigger definition
    Specifies which source and entity type activates this rule, and optional
    conditions the triggering record itself must satisfy (literal values only)
    """
    source: SourceName
    entity: str = Field(..., min_length=1, max_length=MAX_NAME_LENGTH)  # e.g. "product", "person", "amount"
    where: List[WhereCondition] = Field(default_factory=list, max_length=MAX_WHERE_ITEMS)


class JoinOn(BaseModel):
    """What a join matches on: an entity type and the column (or `entities`) compared with it."""
    model_config = {"extra": "forbid"}

    entity: str = Field(..., min_length=1, max_length=MAX_NAME_LENGTH)
    field: str = Field(..., min_length=1, max_length=MAX_NAME_LENGTH)


class RuleJoin(BaseModel):
    """
    Join definition for correlating data from another source
    """
    source: SourceName
    table: Optional[str] = Field(default=None, max_length=MAX_NAME_LENGTH)  # For Access (table name)
    sheet: Optional[str] = Field(default=None, max_length=MAX_NAME_LENGTH)  # For Excel (sheet name)
    on: JoinOn  # {entity: "product", field: "designation"}
    where: List[WhereCondition] = Field(default_factory=list, max_length=MAX_WHERE_ITEMS)

    @model_validator(mode="after")
    def validate_source_specific(self) -> "RuleJoin":
        """Validate that an Access join has a table and an Excel join has a sheet"""
        if self.source == "access" and not self.table:
            raise ValueError("Access join must specify 'table'")
        if self.source == "excel" and not self.sheet:
            raise ValueError("Excel join must specify 'sheet'")
        return self


class RuleEmit(BaseModel):
    """
    Emit definition: what to output when rule matches
    """
    severity: Literal["info", "warning", "error"]
    # e.g. "{product}: stock {access.qty}, prix {excel.prix} FCFA"
    template: str = Field(..., min_length=1, max_length=MAX_TEMPLATE_LENGTH)


def _check_column(source: str, column: str, where: str, allow_entities: bool = False) -> None:
    """Raise ValueError if a column is not exposed by a source."""
    if allow_entities and column == ENTITIES_FIELD:
        return
    if column not in SOURCE_COLUMNS[source]:
        raise ValueError(f"{where}: unknown column '{column}' for source '{source}'")


class RuleCreate(BaseModel):
    """
    Schema for creating a new rule
    Used for POST /rules endpoint
    """
    id: str = Field(..., min_length=1, max_length=100, pattern="^[a-z0-9_]+$")
    natural_language: str = Field(..., min_length=10, max_length=1000)
    trigger: RuleTrigger
    joins: List[RuleJoin] = Field(..., min_length=1, max_length=10)
    window_seconds: int = Field(default=604800, ge=60, le=2592000)  # 1 min to 30 days
    emit: RuleEmit

    @model_validator(mode="after")
    def validate_references(self) -> "RuleCreate":
        """Check columns, `ref` targets and template placeholders against the sources.

        - every column named by the rule is exposed by its source;
        - trigger conditions use literal values (nothing is matched yet);
        - each source is joined at most once;
        - a `ref` points to the trigger or to an earlier join;
        - a template placeholder names the product or a source of the rule, and
          never a column that identifies a person.
        """
        trigger_source = self.trigger.source
        for condition in self.trigger.where:
            _check_column(trigger_source, condition.field, "trigger.where")
            if condition.ref is not None:
                raise ValueError("trigger.where: 'ref' is not allowed on the trigger")

        available = {trigger_source}
        joined_sources = set()
        for index, join in enumerate(self.joins):
            where = f"joins[{index}]"
            # A `ref` and a template placeholder name a source, not a join: two joins on the
            # same source would make them ambiguous
            if join.source in joined_sources:
                raise ValueError(f"{where}: source '{join.source}' is already joined by an earlier join")
            joined_sources.add(join.source)
            _check_column(join.source, join.on.field, f"{where}.on", allow_entities=True)
            for condition in join.where:
                _check_column(join.source, condition.field, f"{where}.where")
                parts = condition.ref_parts()
                if parts is None:
                    continue
                ref_source, ref_field = parts
                if ref_source not in available:
                    raise ValueError(
                        f"{where}.where: 'ref' source '{ref_source}' is neither the trigger nor an earlier join"
                    )
                _check_column(ref_source, ref_field, f"{where}.where.ref")
            available.add(join.source)

        for match in PLACEHOLDER.finditer(self.emit.template):
            name, column = match.group(1), match.group(2)
            if column is None:
                if name != "product":
                    raise ValueError(f"emit.template: unknown placeholder '{{{name}}}'")
                continue
            if name not in available:
                raise ValueError(f"emit.template: source '{name}' is not used by the rule")
            _check_column(name, column, "emit.template")
            if column in TEMPLATE_FORBIDDEN_COLUMNS.get(name, frozenset()):
                raise ValueError(f"emit.template: column '{name}.{column}' identifies a person")
        return self

    model_config = {
        "json_schema_extra": {
            "example": {
                "id": "r_low_stock",
                "natural_language": "Quand un client demande un produit sur WhatsApp, montre son stock Access et son prix Excel, et alerte-moi si le stock est inférieur à 10.",
                "trigger": {
                    "source": "whatsapp",
                    "entity": "product"
                },
                "joins": [
                    {
                        "source": "access",
                        "table": "Articles",
                        "on": {"entity": "product", "field": "designation"},
                        "where": [{"field": "qty_stock", "op": "lt", "value": 10}]
                    },
                    {
                        "source": "excel",
                        "sheet": "Tarifs",
                        "on": {"entity": "product", "field": "Produit"}
                    }
                ],
                "window_seconds": 604800,
                "emit": {
                    "severity": "warning",
                    "template": "{product}: stock {access.qty_stock}, prix {excel.Prix_Unitaire} FCFA"
                }
            }
        }
    }


class RuleResponse(BaseModel):
    """
    Schema for rule returned by API
    """
    id: str
    version: int
    status: str
    natural_language: str
    trigger: RuleTrigger
    joins: List[RuleJoin]
    window_seconds: int
    emit: RuleEmit
    created_at: str
    updated_at: str
    
    model_config = {"from_attributes": True}


class CorrelationResponse(BaseModel):
    """
    Schema for correlation result
    """
    id: int
    rule_id: str
    detected_at: str
    severity: str
    message: str
    provenance: List[Dict[str, Any]]  # [{source, source_ref, record_id}]
    # Why the records match (see engine/interpreter.py); None for rows stored before it existed
    explanation: Optional[Dict[str, Any]] = None
    
    model_config = {"from_attributes": True}


class NaturalLanguageToRuleRequest(BaseModel):
    """
    Request to convert natural language to rule JSON
    """
    model_config = {"str_strip_whitespace": True}

    text: str = Field(..., min_length=20, max_length=1000)
    language: Literal["fr", "en"] = "fr"


class NaturalLanguageToRuleResponse(BaseModel):
    """
    Response from NL→JSON conversion: a draft rule, not stored.
    Failures are returned as errors (see api/errors.py), never in this body.
    """
    rule: RuleCreate
    retries: int = Field(default=0, ge=0)
