"""
Sources API - Expose MCP connectors via REST endpoints
"""
from fastapi import APIRouter, HTTPException, Query
from typing import List, Dict, Any
from pathlib import Path

from config import DATA_DIR
from mcp_servers.excel_connector import ExcelConnector
from mcp_servers.access_connector import AccessConnector
from mcp_servers.whatsapp_connector import WhatsAppConnector
from mcp_servers.momo_connector import MobileMoneyConnector

router = APIRouter(prefix="/api/v1/sources", tags=["sources"])

# Initialize connectors (singleton pattern)
_connectors: Dict[str, Any] = {}


def get_connectors() -> Dict[str, Any]:
    """Get or initialize all connectors"""
    global _connectors
    
    if not _connectors:
        data_path = Path(DATA_DIR)
        _connectors = {
            "excel": ExcelConnector(str(data_path / "tarifs_fournisseurs.xlsx")),
            "access": AccessConnector(str(data_path / "STOCK_ZOBO.mdb"), table_name="Articles"),
            "whatsapp": WhatsAppConnector(str(data_path / "commandes_clients.txt")),
            "momo": MobileMoneyConnector(str(data_path / "momo_transactions.csv")),
        }
    
    return _connectors


@router.get("")
async def list_sources():
    """
    List all available data sources with their health status
    """
    connectors = get_connectors()
    sources = []
    
    for name, connector in connectors.items():
        health = await connector.health_check()
        sources.append({
            "name": name,
            "status": health["status"],
            "message": health.get("message", ""),
            "last_fetch": health.get("last_fetch")
        })
    
    return {"sources": sources}


@router.get("/{source}/health")
async def source_health(source: str):
    """
    Get health status of a specific source
    """
    connectors = get_connectors()
    
    if source not in connectors:
        raise HTTPException(status_code=404, detail=f"Source '{source}' not found")
    
    connector = connectors[source]
    health = await connector.health_check()
    
    return health


@router.get("/{source}/records")
async def fetch_source_records(
    source: str,
    limit: int = Query(default=100, ge=1, le=1000, description="Max records to fetch")
):
    """
    Fetch records from a specific source
    
    Args:
        source: Source name (excel, access, whatsapp, momo)
        limit: Maximum number of records (1-1000)
    
    Returns:
        List of unified records
    """
    connectors = get_connectors()
    
    if source not in connectors:
        raise HTTPException(status_code=404, detail=f"Source '{source}' not found")
    
    connector = connectors[source]
    
    try:
        records = await connector.fetch_records(limit=limit)
        return {
            "source": source,
            "count": len(records),
            "records": [r.to_dict() for r in records]
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch records: {str(e)}")


@router.get("/all/records")
async def fetch_all_records(
    limit_per_source: int = Query(default=50, ge=1, le=500, description="Max records per source")
):
    """
    Fetch records from all sources
    
    Useful for dashboard overview
    """
    connectors = get_connectors()
    all_records = []
    errors = []
    
    for name, connector in connectors.items():
        try:
            records = await connector.fetch_records(limit=limit_per_source)
            all_records.extend([r.to_dict() for r in records])
        except Exception as e:
            errors.append({
                "source": name,
                "error": str(e)
            })
    
    return {
        "total_records": len(all_records),
        "records": all_records,
        "errors": errors if errors else None
    }
