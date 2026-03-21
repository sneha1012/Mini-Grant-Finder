"""
Unit tests for the data processing pipeline.
"""

import pytest
from datetime import date, timedelta

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.models.grant import Grant, GrantStatus, GrantType, Priority
from src.pipeline.processor import GrantProcessor


class TestGrantProcessor:
    """Tests for the GrantProcessor pipeline."""

    @pytest.fixture
    def processor(self):
        """Create a processor with default settings."""
        return GrantProcessor(exclude_expired=True)

    @pytest.fixture
    def sample_grants(self):
        """Create a sample list of grants for testing."""
        return [
            Grant(
                name="EPA Climate Grant",
                source="grants_gov",
                url="https://grants.gov/epa-climate",
                amount_max=50000,
                deadline=date.today() + timedelta(days=30),
                status=GrantStatus.OPEN,
                description="Climate adaptation funding",
            ),
            Grant(
                name="Community Garden Mini Grant",
                source="rss",
                amount_max=5000,
                deadline=date.today() + timedelta(days=60),
                status=GrantStatus.OPEN,
                description="Native plants and gardens",
            ),
            Grant(
                name="Expired Old Grant",
                source="csv",
                deadline=date.today() - timedelta(days=10),
                status=GrantStatus.CLOSED,
                description="This one is past due",
            ),
        ]

    def test_process_filters_expired(self, processor, sample_grants):
        """Test that expired grants are filtered out."""
        result = processor.process(sample_grants)
        names = [g.name for g in result]
        assert "Expired Old Grant" not in names
        assert "EPA Climate Grant" in names

    def test_process_keeps_active(self, processor, sample_grants):
        """Test that active grants are kept."""
        result = processor.process(sample_grants)
        assert len(result) >= 2

    def test_process_includes_expired_when_configured(self, sample_grants):
        """Test including expired grants when configured."""
        processor = GrantProcessor(exclude_expired=False)
        result = processor.process(sample_grants)
        names = [g.name for g in result]
        assert "Expired Old Grant" in names

    def test_deduplication_by_name(self, processor):
        """Test deduplication of grants with same name."""
        grants = [
            Grant(name="EPA Climate Grant", source="csv", description="Short"),
            Grant(
                name="EPA Climate Grant",
                source="rss",
                description="Longer description with more detail",
                amount_max=50000,
            ),
        ]
        result = processor.process(grants)
        assert len(result) == 1
        # Should keep the richer version
        assert result[0].amount_max == 50000
        assert "Longer" in result[0].description

    def test_deduplication_by_url(self, processor):
        """Test deduplication of grants with same URL."""
        grants = [
            Grant(
                name="Grant Version A",
                url="https://example.com/grant/123",
                source="csv",
            ),
            Grant(
                name="Grant Version B",
                url="https://example.com/grant/123",
                source="rss",
            ),
        ]
        result = processor.process(grants)
        assert len(result) == 1

    def test_dedup_merges_focus_areas(self, processor):
        """Test that deduplication merges focus areas."""
        grants = [
            Grant(
                name="Test Grant",
                focus_areas=["climate", "environment"],
                source="csv",
            ),
            Grant(
                name="Test Grant",
                focus_areas=["justice", "community"],
                source="rss",
            ),
        ]
        result = processor.process(grants)
        assert len(result) == 1
        # Should have merged focus areas
        assert len(result[0].focus_areas) >= 3

    def test_clean_whitespace(self, processor):
        """Test that extra whitespace is cleaned."""
        grants = [
            Grant(
                name="  Grant with   extra   spaces  ",
                description="  Description   too  ",
            ),
        ]
        result = processor.process(grants)
        assert result[0].name == "Grant with extra spaces"
        assert "  " not in result[0].description

    def test_normalize_geography(self, processor):
        """Test geographic scope normalization."""
        grants = [
            Grant(name="Test A", geographic_scope="national"),
            Grant(name="Test B", geographic_scope="orange county"),
            Grant(name="Test C", geographic_scope="california"),
        ]
        result = processor.process(grants)

        scopes = {g.name: g.geographic_scope for g in result}
        assert "U.S." in scopes.get("Test A", "")
        assert "CA" in scopes.get("Test B", "")

    def test_status_update_closing_soon(self, processor):
        """Test status auto-update for approaching deadline."""
        grants = [
            Grant(
                name="Almost Due Grant",
                deadline=date.today() + timedelta(days=5),
                status=GrantStatus.OPEN,
            ),
        ]
        result = processor.process(grants)
        assert result[0].status == GrantStatus.CLOSING_SOON

    def test_min_amount_filter(self):
        """Test minimum amount filter."""
        processor = GrantProcessor(min_amount=1000)
        grants = [
            Grant(name="Big Grant", amount_max=50000),
            Grant(name="Small Grant", amount_max=500),
            Grant(name="No Amount Grant", amount_max=0),
        ]
        result = processor.process(grants)
        names = [g.name for g in result]
        assert "Big Grant" in names
        assert "Small Grant" not in names
        # No amount = include (don't filter unknown amounts)
        assert "No Amount Grant" in names

    def test_empty_name_filtered(self, processor):
        """Test that grants with empty names are filtered."""
        grants = [
            Grant(name=""),
            Grant(name="   "),
            Grant(name="Valid Grant"),
        ]
        result = processor.process(grants)
        assert len(result) == 1
        assert result[0].name == "Valid Grant"

    def test_processing_stats(self, processor, sample_grants):
        """Test that processing stats are tracked."""
        processor.process(sample_grants)
        stats = processor.stats
        assert stats["input"] == 3
        assert stats["output"] > 0
        assert stats["output"] <= stats["input"]

    def test_enrichment_updates_priority(self, processor):
        """Test that enrichment stage updates grant priority."""
        grants = [
            Grant(
                name="Urgent Grant",
                deadline=date.today() + timedelta(days=5),
                relevance_score=80,
                status=GrantStatus.OPEN,
            ),
        ]
        result = processor.process(grants)
        assert result[0].priority == Priority.URGENT

    def test_rolling_status_preserved(self, processor):
        """Test that rolling deadlines are handled correctly."""
        grants = [
            Grant(
                name="Rolling Grant",
                deadline_text="Rolling",
                status=GrantStatus.OPEN,
            ),
        ]
        result = processor.process(grants)
        assert result[0].status == GrantStatus.ROLLING
