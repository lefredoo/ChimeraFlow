"""
Pydantic schemas for Rule validation
Implements strict validation per AGENTS.md §20 (security: no code execution)
"""
from pydantic import BaseModel, Field, model_validator
from typing import List, Dict, Any, Literal, Optional
from enum import Enum


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


class RuleTrigger(BaseModel):
    """
    Rule trigger definition
    Specifies which source and entity type activates this rule
    """
    source: Literal["whatsapp", "momo", "excel", "access"]
    entity: str  # e.g. "product", "person", "amount"


class WhereCondition(BaseModel):
    """
    WHERE condition in a join
    Only allows whitelisted operators (security: R5)
    """
    field: str
    op: Operator
    value: Any  # String, int, float, list


class RuleJoin(BaseModel):
    """
    Join definition for correlating data from another source
    """
    source: Literal["whatsapp", "momo", "excel", "access"]
    table: Optional[str] = None  # For Access (table name)
    sheet: Optional[str] = None  # For Excel (sheet name)
    on: Dict[str, str]  # {entity: "product", field: "designation"}
    where: List[WhereCondition] = Field(default_factory=list)

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
    template: str  # e.g. "{product}: stock {access.qty}, prix {excel.prix} FCFA"


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
