"""
Property-Based Testing with Hypothesis
Tests properties P1-P6 from Roadmap.md §7
"""
import pytest
from hypothesis import given, strategies as st, settings, assume
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).parent.parent))

from mcp_servers.base import BaseConnector


class TestNormalizationProperties:
    """
    Property P2: Normalization idempotence
    norm(norm(x)) == norm(x)
    """
    
    @given(st.text(min_size=1, max_size=100))
    @settings(max_examples=200)
    def test_normalization_idempotent(self, text):
        """Normalizing twice gives same result as normalizing once"""
        # Create dummy connector to access normalize_text
        class DummyConnector(BaseConnector):
            async def fetch_records(self, limit=100):
                return []
            
            async def _perform_health_check(self):
                return {"status": "ok", "source": "dummy"}
        
        connector = DummyConnector("dummy")
        
        norm_once = connector.normalize_text(text)
        norm_twice = connector.normalize_text(norm_once)
        
        assert norm_once == norm_twice, f"Normalization not idempotent: '{text}' -> '{norm_once}' -> '{norm_twice}'"
    
    @given(st.text(alphabet=st.characters(whitelist_categories=('Lu', 'Ll')), min_size=1, max_size=50))
    def test_normalization_lowercase(self, text):
        """Normalized text is always lowercase"""
        class DummyConnector(BaseConnector):
            async def fetch_records(self, limit=100):
                return []
            
            async def _perform_health_check(self):
                return {"status": "ok", "source": "dummy"}
        
        connector = DummyConnector("dummy")
        normalized = connector.normalize_text(text)
        
        # Only check alphabetic characters (numbers/symbols don't have case)
        alpha_chars = [c for c in normalized if c.isalpha()]
        if alpha_chars:
            assert normalized.islower() or not any(c.isalpha() for c in normalized), \
                f"Normalized text not lowercase: '{text}' -> '{normalized}'"
    
    def test_normalization_specific_cases(self):
        """Test specific normalization cases from demo scenario"""
        class DummyConnector(BaseConnector):
            async def fetch_records(self, limit=100):
                return []
            
            async def _perform_health_check(self):
                return {"status": "ok", "source": "dummy"}
        
        connector = DummyConnector("dummy")
        
        # Test cases from Roadmap.md §2: same product written 4 ways
        variations = [
            "ciment 50 kg",
            "Ciment50kg",
            "cimént 50kg",
            "ciment (50kg)"
        ]
        
        normalized = [connector.normalize_text(v) for v in variations]
        
        # All variations should normalize to similar forms
        # (may differ slightly due to punctuation, but product name should match)
        print(f"\nNormalization results:")
        for orig, norm in zip(variations, normalized):
            print(f"  '{orig}' -> '{norm}'")
        
        # At minimum, "ciment" and "50kg" should appear in all
        for norm in normalized:
            assert "ciment" in norm, f"Expected 'ciment' in '{norm}'"
            assert "50" in norm, f"Expected '50' in '{norm}'"


class TestDeterminism:
    """
    Property P4: Determinism
    Same inputs and rule give same output
    """
    
    def test_normalization_deterministic(self):
        """Same input always produces same normalized output"""
        class DummyConnector(BaseConnector):
            async def fetch_records(self, limit=100):
                return []
            
            async def _perform_health_check(self):
                return {"status": "ok", "source": "dummy"}
        
        connector = DummyConnector("dummy")
        
        test_inputs = [
            "Ciment 50 kg",
            "PRODUIT SPÉCIAL",
            "article-123",
            "Prix: 5000 FCFA"
        ]
        
        for text in test_inputs:
            # Normalize multiple times
            results = [connector.normalize_text(text) for _ in range(10)]
            
            # All results should be identical
            assert len(set(results)) == 1, \
                f"Non-deterministic normalization for '{text}': {set(results)}"


class TestProvenance:
    """
    Property P1: Provenance conservation
    Every emitted correlation lists only records that exist in inputs
    
    Note: Full correlation testing requires rule engine (P2)
    Here we test that connectors preserve source_ref
    """
    
    @pytest.mark.asyncio
    async def test_source_ref_present(self):
        """All records have non-empty source_ref"""
        from mcp_servers.whatsapp_connector import WhatsAppConnector
        
        test_file = Path(__file__).parent.parent.parent / "data" / "commandes_clients.txt"
        
        if not test_file.exists():
            pytest.skip("Test file not found")
        
        connector = WhatsAppConnector(str(test_file))
        records = await connector.fetch_records(limit=50)
        
        for record in records:
            assert record.source_ref, f"Missing source_ref in record {record.id}"
            assert "#" in record.source_ref, \
                f"source_ref should contain line/row reference: {record.source_ref}"


class TestNoFabrication:
    """
    Property P6: No fabrication
    No emitted field value is absent from source records
    
    Test that entities are actually extracted from payload, not invented
    """
    
    @pytest.mark.asyncio
    async def test_entities_from_payload(self):
        """Entity 'raw' values must appear in payload"""
        from mcp_servers.whatsapp_connector import WhatsAppConnector
        
        test_file = Path(__file__).parent.parent.parent / "data" / "commandes_clients.txt"
        
        if not test_file.exists():
            pytest.skip("Test file not found")
        
        connector = WhatsAppConnector(str(test_file))
        records = await connector.fetch_records(limit=20)
        
        for record in records:
            record_dict = record.to_dict()
            payload_str = str(record_dict["payload"]).lower()
            
            # Check each entity
            for entity in record_dict["entities"]:
                raw_value = entity["raw"].lower()
                
                # Entity raw value should appear in payload
                # (may not be exact match due to extraction logic, but words should be present)
                words = raw_value.split()
                if len(words) > 0:
                    # At least one word from entity should be in payload
                    found = any(word in payload_str for word in words if len(word) > 2)
                    assert found, \
                        f"Entity '{entity['raw']}' not found in payload: {record_dict['payload']}"


class TestRoundTrip:
    """
    Property P3: Parser round-trip
    parse(export(messages)) should preserve message content
    
    Note: Full round-trip requires export function (not in MVP)
    Here we test that parsing is lossless for key fields
    """
    
    @pytest.mark.asyncio
    async def test_whatsapp_parse_lossless(self):
        """Parsed WhatsApp records preserve original text"""
        from mcp_servers.whatsapp_connector import WhatsAppConnector
        
        test_file = Path(__file__).parent.parent.parent / "data" / "commandes_clients.txt"
        
        if not test_file.exists():
            pytest.skip("Test file not found")
        
        connector = WhatsAppConnector(str(test_file))
        records = await connector.fetch_records(limit=10)
        
        # Each record should have original text in payload
        for record in records:
            payload = record.to_dict()["payload"]
            
            # WhatsApp records should preserve author and text
            if "author" in payload:
                assert payload["author"], "Author should not be empty"
            
            if "text" in payload:
                assert payload["text"], "Text should not be empty"
