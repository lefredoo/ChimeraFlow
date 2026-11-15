"""
Base connector interface for MCP servers
Implements contract defined in .kiro/specs/connectors-spec.md
"""
from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional
from datetime import datetime
from dataclasses import dataclass, asdict
import csv
import logging
import math
import subprocess
import zipfile

from openpyxl.utils.exceptions import InvalidFileException

logger = logging.getLogger(__name__)


def to_finite_float(value: Any) -> float:
    """Convert a cell or CSV text to a float that is a real number.

    `float()` accepts "nan" and "inf", which break comparisons and JSON output
    downstream; a connector counts them as parse errors instead.

    Args:
        value: Text or number to convert.

    Returns:
        The finite float.

    Raises:
        ValueError: If the value is not a number, or is NaN or infinite.
    """
    number = float(value)
    if not math.isfinite(number):
        raise ValueError(f"Not a finite number: {value!r}")
    return number

# Errors a connector may raise while reading its source: I/O, bad values, and the
# format errors of the readers (a truncated CSV, an .xlsx that is not a zip archive
# or has the wrong extension)
CONNECTOR_ERRORS = (
    OSError,
    ValueError,
    KeyError,
    RuntimeError,
    subprocess.SubprocessError,
    csv.Error,
    zipfile.BadZipFile,
    InvalidFileException,
)


@dataclass
class Entity:
    """Extracted entity from source data"""
    type: str  # product, person, amount, etc.
    raw: str   # Original text
    norm: str  # Normalized form


@dataclass
class UnifiedRecord:
    """
    Unified record schema (AGENTS.md §19)
    All connectors return data in this format
    """
    id: str
    source: str  # excel | access | whatsapp | momo
    source_ref: str  # File path + line/row reference
    timestamp: str  # ISO8601
    lang: str  # fr | en
    entities: List[Dict[str, str]]  # List of Entity dicts
    payload: Dict[str, Any]  # Source-specific data
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return asdict(self)


class BaseConnector(ABC):
    """
    Base class for all MCP connectors
    
    Contract (R1 from connectors-spec.md):
    - fetch_records(limit: int) -> List[UnifiedRecord]
    - health_check() -> dict
    """
    
    def __init__(self, source_name: str):
        self.source_name = source_name
        self.logger = logging.getLogger(f"connector.{source_name}")
        self._last_health_check: Optional[Dict[str, Any]] = None
        self._health_check_time: Optional[datetime] = None
        
    @abstractmethod
    async def fetch_records(self, limit: int = 100) -> List[UnifiedRecord]:
        """
        Fetch records from data source
        
        Args:
            limit: Maximum number of records to fetch (max 1000)
            
        Returns:
            List of unified records
            
        Raises:
            Should NOT raise on parse errors - log and skip bad records
        """
        pass
    
    async def health_check(self) -> Dict[str, Any]:
        """
        Check connector health
        
        Returns:
            {
                "status": "ok" | "degraded" | "error",
                "source": "source_name",
                "message": "optional message",
                "last_fetch": "ISO8601 timestamp or null"
            }
        """
        # Cache health check for 30 seconds (R3 from connectors.md)
        now = datetime.now()
        if self._last_health_check and self._health_check_time:
            age = (now - self._health_check_time).total_seconds()
            if age < 30:
                return self._last_health_check
        
        # Run actual health check
        try:
            health = await self._perform_health_check()
            self._last_health_check = health
            self._health_check_time = now
            return health
        except Exception as e:
            self.logger.error(f"Health check failed: {e}")
            return {
                "status": "error",
                "source": self.source_name,
                "message": str(e),
                "last_fetch": None
            }
    
    @abstractmethod
    async def _perform_health_check(self) -> Dict[str, Any]:
        """
        Actual health check implementation (must be overridden)
        """
        pass
    
    def normalize_text(self, text: str) -> str:
        """
        Normalize text for entity matching.

        Delegates to the single implementation in engine.normalizer.
        """
        # Imported here: engine.interpreter imports this module, so a
        # module-level import would create a cycle.
        from engine.normalizer import normalize_text

        return normalize_text(text)
