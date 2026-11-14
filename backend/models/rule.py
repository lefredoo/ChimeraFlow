"""
Rule and Correlation models
Implements schema from AGENTS.md §20
"""
from sqlalchemy import Column, Integer, String, DateTime, JSON, Text, Enum, ForeignKey
from sqlalchemy.orm import relationship
from datetime import datetime, timezone
import enum

from .base import Base


def _utc_now() -> datetime:
    """Current time as a timezone-aware UTC datetime (column default)."""
    return datetime.now(timezone.utc)


class RuleStatus(enum.Enum):
    """Rule status enum"""
    active = "active"
    inactive = "inactive"
    draft = "draft"


class CorrelationSeverity(enum.Enum):
    """Correlation severity levels"""
    info = "info"
    warning = "warning"
    error = "error"


class Rule(Base):
    """
    Correlation rule
    
    Schema follows AGENTS.md §20:
    {
        "id": "r_low_stock",
        "version": 1,
        "natural_language": "...",
        "trigger": {"source": "whatsapp", "entity": "product"},
        "joins": [...],
        "window_seconds": 604800,
        "emit": {...}
    }
    """
    __tablename__ = "rules"
    
    # Primary fields
    id = Column(String(100), primary_key=True)
    version = Column(Integer, nullable=False, default=1)
    status = Column(Enum(RuleStatus), nullable=False, default=RuleStatus.active)
    
    # Natural language description
    natural_language = Column(Text, nullable=False)
    
    # Rule definition (JSON)
    trigger = Column(JSON, nullable=False)  # {source, entity}
    joins = Column(JSON, nullable=False)    # [{source, table, on, where}]
    window_seconds = Column(Integer, nullable=False, default=604800)  # 7 days
    emit = Column(JSON, nullable=False)     # {severity, template}
    
    # Metadata
    created_at = Column(DateTime(timezone=True), nullable=False, default=_utc_now)
    updated_at = Column(DateTime(timezone=True), nullable=False, default=_utc_now, onupdate=_utc_now)
    
    # Relationships
    executions = relationship("RuleExecution", back_populates="rule", cascade="all, delete-orphan")
    correlations = relationship("Correlation", back_populates="rule", cascade="all, delete-orphan")


class RuleExecution(Base):
    """
    Track rule execution history
    """
    __tablename__ = "rule_executions"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    rule_id = Column(String(100), ForeignKey("rules.id", ondelete="CASCADE"), nullable=False)
    
    # Execution metadata
    executed_at = Column(DateTime(timezone=True), nullable=False, default=_utc_now)
    duration_ms = Column(Integer, nullable=False)  # Execution time
    
    # Results
    correlations_found = Column(Integer, nullable=False, default=0)
    records_scanned = Column(Integer, nullable=False, default=0)
    
    # Error tracking
    error = Column(Text, nullable=True)
    
    # Relationship
    rule = relationship("Rule", back_populates="executions")


class Correlation(Base):
    """
    Correlation result emitted by a rule
    
    Stores provenance for P1 (all contributing records)
    """
    __tablename__ = "correlations"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    rule_id = Column(String(100), ForeignKey("rules.id", ondelete="CASCADE"), nullable=False)
    
    # When this correlation was found
    detected_at = Column(DateTime(timezone=True), nullable=False, default=_utc_now)
    
    # Severity and message
    severity = Column(Enum(CorrelationSeverity), nullable=False)
    message = Column(Text, nullable=False)
    
    # Provenance (P1 property: all contributing records)
    # [{source, source_ref, record_id}]
    provenance = Column(JSON, nullable=False)
    
    # Optional: time window bounds
    window_start = Column(DateTime(timezone=True), nullable=True)
    window_end = Column(DateTime(timezone=True), nullable=True)

    # Relationship
    rule = relationship("Rule", back_populates="correlations")
