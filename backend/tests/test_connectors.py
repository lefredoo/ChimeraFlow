"""
Contract tests for all MCP connectors
Validates compliance with connectors-spec.md (R1)
"""
import pytest
import shutil
from pathlib import Path
import sys

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from mcp_servers.base import UnifiedRecord
from mcp_servers.excel_connector import ExcelConnector
from mcp_servers.access_connector import AccessConnector
from mcp_servers.whatsapp_connector import WhatsAppConnector
from mcp_servers.momo_connector import MobileMoneyConnector


# Fixtures for test data paths
@pytest.fixture
def excel_path():
    """Path to synthetic Excel file"""
    return Path(__file__).parent.parent.parent / "data" / "tarifs_fournisseurs.xlsx"


@pytest.fixture
def access_path():
    """Path to synthetic Access database"""
    return Path(__file__).parent.parent.parent / "data" / "STOCK_ZOBO.mdb"


@pytest.fixture
def whatsapp_path():
    """Path to synthetic WhatsApp export"""
    return Path(__file__).parent.parent.parent / "data" / "commandes_clients.txt"


@pytest.fixture
def momo_path():
    """Path to synthetic Mobile Money CSV"""
    return Path(__file__).parent.parent.parent / "data" / "momo_transactions.csv"


class TestConnectorContract:
    """
    Test R1: All connectors must implement fetch_records() and health_check()
    """
    
    @pytest.mark.asyncio
    async def test_excel_connector_contract(self, excel_path):
        """Excel connector implements required methods"""
        connector = ExcelConnector(str(excel_path))
        
        # Test health_check returns correct structure
        health = await connector.health_check()
        assert "status" in health
        assert "source" in health
        assert health["source"] == "excel"
        assert health["status"] in ["ok", "degraded", "error"]
        
        # If file exists, should be able to fetch records
        if excel_path.exists():
            records = await connector.fetch_records(limit=10)
            assert isinstance(records, list)
            
            # All records must be UnifiedRecord
            for record in records:
                assert isinstance(record, UnifiedRecord)
                assert record.source == "excel"
                assert record.id.startswith("excel-")
                assert "entities" in record.to_dict()
                assert "payload" in record.to_dict()
    
    @pytest.mark.parametrize("reader", [
        "access-parser",
        pytest.param(
            "mdbtools",
            marks=pytest.mark.skipif(
                shutil.which("mdb-export") is None, reason="mdbtools (mdb-export) is not installed"
            ),
        ),
    ])
    @pytest.mark.asyncio
    async def test_access_connector_contract(self, access_path, reader):
        """Access connector implements required methods"""
        connector = AccessConnector(str(access_path), reader=reader)
        
        health = await connector.health_check()
        assert "status" in health
        assert "source" in health
        assert health["source"] == "access"
        assert health["status"] == "ok"
        
        if access_path.exists():
            records = await connector.fetch_records(limit=10)
            assert isinstance(records, list)
            
            for record in records:
                assert isinstance(record, UnifiedRecord)
                assert record.source == "access"
    
    @pytest.mark.asyncio
    async def test_whatsapp_connector_contract(self, whatsapp_path):
        """WhatsApp connector implements required methods"""
        connector = WhatsAppConnector(str(whatsapp_path))
        
        health = await connector.health_check()
        assert "status" in health
        assert "source" in health
        assert health["source"] == "whatsapp"
        
        if whatsapp_path.exists():
            records = await connector.fetch_records(limit=10)
            assert isinstance(records, list)
            
            for record in records:
                assert isinstance(record, UnifiedRecord)
                assert record.source == "whatsapp"
                assert record.id.startswith("wa-")
    
    @pytest.mark.asyncio
    async def test_momo_connector_contract(self, momo_path):
        """Mobile Money connector implements required methods"""
        connector = MobileMoneyConnector(str(momo_path))
        
        health = await connector.health_check()
        assert "status" in health
        assert "source" in health
        assert health["source"] == "momo"
        
        if momo_path.exists():
            records = await connector.fetch_records(limit=10)
            assert isinstance(records, list)
            
            for record in records:
                assert isinstance(record, UnifiedRecord)
                assert record.source == "momo"


class TestHealthCheckCaching:
    """
    Test R3 from connectors.md: health_check cached for 30 seconds
    """
    
    @pytest.mark.asyncio
    async def test_health_check_cache(self, whatsapp_path):
        """Health check returns cached result within 30 seconds"""
        import time
        
        connector = WhatsAppConnector(str(whatsapp_path))
        
        # First call
        health1 = await connector.health_check()
        time1 = time.time()
        
        # Immediate second call should be cached
        health2 = await connector.health_check()
        time2 = time.time()
        
        assert health1 == health2
        assert time2 - time1 < 0.1  # Should be instant (cached)


class TestErrorHandling:
    """
    Test R4 from connectors-spec.md: Parse errors should be logged and counted, not crash
    """
    
    @pytest.mark.asyncio
    async def test_missing_file_health_check(self):
        """Health check returns error for missing file"""
        connector = WhatsAppConnector("/nonexistent/path.txt")
        
        health = await connector.health_check()
        assert health["status"] == "error"
        assert "not found" in health["message"].lower() or "no such file" in health["message"].lower()
    
    @pytest.mark.asyncio
    async def test_parse_errors_counted(self, whatsapp_path):
        """Parse errors are counted without crashing"""
        if not whatsapp_path.exists():
            pytest.skip("WhatsApp test file not found")
        
        connector = WhatsAppConnector(str(whatsapp_path))
        
        # Should complete without exception
        records = await connector.fetch_records(limit=100)
        
        # Parse errors should be tracked
        assert hasattr(connector, 'parse_errors')
        assert len(records) > 0


class TestLimitEnforcement:
    """
    Test that connectors respect limit parameter (max 1000)
    """
    
    @pytest.mark.asyncio
    async def test_limit_respected(self, whatsapp_path):
        """Connector respects fetch limit"""
        if not whatsapp_path.exists():
            pytest.skip("WhatsApp test file not found")
        
        connector = WhatsAppConnector(str(whatsapp_path))
        
        # Request 5 records
        records = await connector.fetch_records(limit=5)
        assert len(records) <= 5
    
    @pytest.mark.asyncio
    async def test_max_limit_1000(self, whatsapp_path):
        """Connector enforces max limit of 1000"""
        if not whatsapp_path.exists():
            pytest.skip("WhatsApp test file not found")
        
        connector = WhatsAppConnector(str(whatsapp_path))
        
        # Request more than 1000
        records = await connector.fetch_records(limit=2000)
        assert len(records) <= 1000


class TestUnifiedSchema:
    """
    Test R2: All records conform to unified schema (AGENTS.md §19)
    """
    
    @pytest.mark.asyncio
    async def test_unified_record_structure(self, whatsapp_path):
        """All records have required fields"""
        if not whatsapp_path.exists():
            pytest.skip("WhatsApp test file not found")
        
        connector = WhatsAppConnector(str(whatsapp_path))
        records = await connector.fetch_records(limit=10)
        
        if len(records) > 0:
            record = records[0]
            record_dict = record.to_dict()
            
            # Required fields from unified schema
            assert "id" in record_dict
            assert "source" in record_dict
            assert "source_ref" in record_dict
            assert "timestamp" in record_dict
            assert "lang" in record_dict
            assert "entities" in record_dict
            assert "payload" in record_dict
            
            # Lang must be fr or en
            assert record_dict["lang"] in ["fr", "en"]
            
            # Entities must be list of dicts with type, raw, norm
            assert isinstance(record_dict["entities"], list)
            if len(record_dict["entities"]) > 0:
                entity = record_dict["entities"][0]
                assert "type" in entity
                assert "raw" in entity
                assert "norm" in entity
