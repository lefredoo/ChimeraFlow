"""
Property-Based Testing with Hypothesis
Tests properties P1-P6 from Roadmap.md §7
"""
import asyncio
import tempfile
from dataclasses import replace
from datetime import datetime

import pytest
from hypothesis import given, strategies as st, settings
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).parent.parent))

from mcp_servers.base import BaseConnector
from mcp_servers.whatsapp_connector import WhatsAppConnector
from mcp_servers.whatsapp_parser import (
    EXPORT_FORMATS,
    ParsedMessage,
    export_messages,
    is_header_line,
    parse_export,
)


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
        
        # Some letters (e.g. U+2110) are uppercase but have no lowercase
        # mapping, so check that lowercasing the result changes nothing
        assert normalized == normalized.lower(), \
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
        
        # All variations must keep the product name and quantity
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


# --- P3: parse(export(messages)) == messages (Hypothesis) ---

# No control character, no line or paragraph separator (they would split a line), no
# invisible mark (the parser strips those before a header)
_PLAIN = st.characters(
    blacklist_categories=("Cc", "Cs", "Zl", "Zp"),
    blacklist_characters="\u200e\u200f\u202a\u202b\u202c\ufeff",
)
_PLACEHOLDERS = [
    "<Media omitted>",
    "<Médias omis>",
    "image omitted",
    "\u200e<attached: 00000012-PHOTO-2026-11-01-09-24-00.jpg>",
    "IMG-20261101-WA0001.jpg (file attached)",
]


_TEXT_LINE = st.text(_PLAIN, max_size=30).filter(lambda line: not is_header_line(line))
_WRITTEN_TEXT = (
    st.lists(_TEXT_LINE, min_size=1, max_size=3)
    .map("\n".join)
    .filter(lambda text: text != "" and text == text.strip())
)
_AUTHOR = st.text(_PLAIN, min_size=1, max_size=20).filter(lambda a: ":" not in a and a == a.strip())
_MOMENT = st.datetimes(
    min_value=datetime(2000, 1, 1),
    max_value=datetime(2099, 12, 31, 23, 59, 59),
).map(lambda moment: moment.replace(microsecond=0))
_MESSAGES = st.lists(
    st.builds(
        ParsedMessage,
        timestamp=_MOMENT,
        author=_AUTHOR,
        text=st.one_of(_WRITTEN_TEXT, st.sampled_from(_PLACEHOLDERS)),
    ),
    min_size=1,
    max_size=8,
)
_FORMATS_WITHOUT_SECONDS = ("android_nobracket_fr", "android_en")


def _fit(messages, export_format):
    """Drop the seconds that the format cannot write."""
    if export_format not in _FORMATS_WITHOUT_SECONDS:
        return messages
    return [replace(m, timestamp=m.timestamp.replace(second=0)) for m in messages]


def _default_order(export_format):
    return "mdy" if export_format in ("ios_en", "android_en") else "dmy"


class TestParserRoundTrip:
    """Property P3: parse(export(messages)) == messages across every export format"""

    @given(messages=_MESSAGES, export_format=st.sampled_from(EXPORT_FORMATS))
    @settings(max_examples=200)
    def test_should_parse_back_the_exported_messages_when_exporting_in_any_format(self, messages, export_format):
        messages = _fit(messages, export_format)

        result = parse_export(export_messages(messages, export_format).split("\n"), _default_order(export_format))

        assert result.messages == messages
        assert (result.parse_errors, result.system_skipped) == (0, 0)

    @given(messages=_MESSAGES, export_format=st.sampled_from(EXPORT_FORMATS))
    @settings(max_examples=100)
    def test_should_number_each_message_by_its_first_line_when_exporting_in_any_format(self, messages, export_format):
        messages = _fit(messages, export_format)
        first_lines = [1 + sum(m.text.count("\n") + 1 for m in messages[:i]) for i in range(len(messages))]

        result = parse_export(export_messages(messages, export_format).split("\n"), _default_order(export_format))

        assert [m.line_no for m in result.messages] == first_lines

    @given(messages=_MESSAGES, export_format=st.sampled_from(EXPORT_FORMATS))
    @settings(max_examples=40)
    def test_should_return_the_exported_messages_when_the_connector_reads_the_file(self, messages, export_format):
        messages = _fit(messages, export_format)

        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "chat.txt"
            path.write_text(export_messages(messages, export_format), encoding="utf-8", newline="\n")
            connector = WhatsAppConnector(str(path), default_date_order=_default_order(export_format))
            records = asyncio.run(connector.fetch_records(limit=1000))

        assert [(r.timestamp, r.payload["author"], r.payload["text"], r.payload["attachment"]) for r in records] == [
            (m.timestamp.isoformat(), m.author, m.text, m.attachment) for m in messages
        ]
