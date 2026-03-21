"""
Integration tests for CSV data loaders and storage backends.
"""

import json
import os
import pytest
import tempfile

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.models.grant import Grant, GrantStatus, GrantType
from src.loaders.csv_loader import (
    parse_amount,
    parse_deadline,
    classify_grant_type,
    classify_status,
    load_all_grants_csv,
    load_mini_grants_csv,
    load_active_grants_csv,
    load_all_research_data,
)
from src.storage.local import LocalStorage


class TestParseAmount:
    """Tests for amount string parsing."""

    def test_range_format(self):
        lo, hi, text = parse_amount("$5,000 - $10,000")
        assert lo == 5000
        assert hi == 10000

    def test_up_to_format(self):
        lo, hi, text = parse_amount("Up to $30,000/yr (2 years)")
        assert hi == 30000
        assert "Up to" in text

    def test_single_amount(self):
        lo, hi, text = parse_amount("$500")
        assert lo == 500
        assert hi == 500

    def test_varies(self):
        lo, hi, text = parse_amount("Varies")
        assert lo == 0
        assert hi == 0
        assert "Varies" in text

    def test_empty_string(self):
        lo, hi, text = parse_amount("")
        assert lo == 0
        assert hi == 0

    def test_large_range(self):
        lo, hi, text = parse_amount("$75,000 - $115,000")
        assert lo == 75000
        assert hi == 115000

    def test_in_kind(self):
        lo, hi, text = parse_amount("In-kind (food/beverage)")
        assert lo == 0
        assert hi == 0


class TestParseDeadline:
    """Tests for deadline string parsing."""

    def test_standard_date(self):
        result = parse_deadline("Feb 18 2026")
        assert result is not None
        assert result.year == 2026
        assert result.month == 2
        assert result.day == 18

    def test_date_with_comma(self):
        result = parse_deadline("Mar 1, 2026")
        assert result is not None
        assert result.month == 3

    def test_rolling_returns_none(self):
        result = parse_deadline("Rolling")
        assert result is None

    def test_check_website_returns_none(self):
        result = parse_deadline("Check website")
        assert result is None

    def test_date_range(self):
        result = parse_deadline("Mar 10-31 2026")
        assert result is not None
        assert result.month == 3
        assert result.day == 31

    def test_month_year_only(self):
        result = parse_deadline("Apr 2026")
        assert result is not None
        assert result.month == 4
        assert result.year == 2026

    def test_empty_returns_none(self):
        result = parse_deadline("")
        assert result is None


class TestClassifiers:
    """Tests for type and status classifiers."""

    def test_federal_grant_type(self):
        result = classify_grant_type("Federal Grant")
        assert result == GrantType.FEDERAL_GRANT

    def test_mini_grant_type(self):
        result = classify_grant_type("Foundation Mini Grant")
        assert result == GrantType.MINI_GRANT

    def test_corporate_grant_type(self):
        result = classify_grant_type("Corporate Grant")
        assert result == GrantType.CORPORATE_GRANT

    def test_in_kind_type(self):
        result = classify_grant_type("Retail Donation")
        assert result == GrantType.IN_KIND

    def test_open_status(self):
        result = classify_status("APPLY NOW")
        assert result == GrantStatus.OPEN

    def test_monitor_status(self):
        result = classify_status("MONITOR")
        assert result == GrantStatus.MONITOR

    def test_rolling_status(self):
        result = classify_status("", "ROLLING")
        assert result == GrantStatus.ROLLING


class TestCSVLoaders:
    """Integration tests for loading actual research CSV files."""

    def test_load_all_grants(self):
        """Test loading the master grant list."""
        grants = load_all_grants_csv()
        assert len(grants) > 0
        assert all(isinstance(g, Grant) for g in grants)
        # Should have loaded the expected number
        assert len(grants) >= 30  # We know there are 41 rows

    def test_load_mini_grants(self):
        """Test loading the mini-grants list."""
        grants = load_mini_grants_csv()
        assert len(grants) > 0
        assert len(grants) >= 15  # We know there are 22 rows

    def test_load_active_grants(self):
        """Test loading the active grants list."""
        grants = load_active_grants_csv()
        assert len(grants) > 0

    def test_load_all_research_data(self):
        """Test loading and combining all CSV sources."""
        grants = load_all_research_data()
        assert len(grants) > 50  # Combined should be 80+

    def test_loaded_grants_have_names(self):
        """Test that loaded grants have non-empty names."""
        grants = load_all_grants_csv()
        for grant in grants:
            assert grant.name.strip() != ""

    def test_loaded_grants_have_urls(self):
        """Test that loaded grants have URLs."""
        grants = load_all_grants_csv()
        with_urls = [g for g in grants if g.url]
        assert len(with_urls) > len(grants) * 0.8  # >80% should have URLs


class TestLocalStorage:
    """Tests for the local JSON storage backend."""

    @pytest.fixture
    def temp_storage(self):
        """Create a temporary storage directory."""
        with tempfile.TemporaryDirectory() as tmpdir:
            yield LocalStorage(storage_dir=tmpdir)

    @pytest.fixture
    def sample_grants(self):
        """Create sample grants for storage testing."""
        return [
            Grant(
                name="Test Grant A",
                source="test",
                amount_max=5000,
                relevance_score=80,
            ),
            Grant(
                name="Test Grant B",
                source="test",
                amount_max=10000,
                relevance_score=60,
            ),
        ]

    def test_save_and_load(self, temp_storage, sample_grants):
        """Test saving and loading grants roundtrip."""
        temp_storage.save_grants(sample_grants, tag="test")
        loaded = temp_storage.load_latest()
        assert len(loaded) == 2
        assert loaded[0].name == "Test Grant A"
        assert loaded[1].name == "Test Grant B"

    def test_save_creates_latest(self, temp_storage, sample_grants):
        """Test that save creates latest.json."""
        temp_storage.save_grants(sample_grants)
        latest = temp_storage.storage_dir / "latest.json"
        assert latest.exists()

    def test_list_snapshots(self, temp_storage, sample_grants):
        """Test listing data snapshots."""
        temp_storage.save_grants(sample_grants, tag="v1")
        snapshots = temp_storage.list_snapshots()
        assert len(snapshots) >= 1

    def test_export_csv(self, temp_storage, sample_grants):
        """Test CSV export."""
        path = temp_storage.export_csv(sample_grants)
        assert os.path.exists(path)
        # Read and verify CSV content
        with open(path) as f:
            content = f.read()
        assert "Test Grant A" in content
        assert "Test Grant B" in content

    def test_load_nonexistent_returns_empty(self, temp_storage):
        """Test loading from nonexistent file returns empty list."""
        result = temp_storage.load_grants("/nonexistent/path.json")
        assert result == []

    def test_get_new_grants(self, temp_storage):
        """Test finding new grants vs. previous snapshot."""
        # Save initial batch
        initial = [Grant(name="Grant A", source="test")]
        temp_storage.save_grants(initial, tag="v1")

        # New batch with one additional grant
        updated = [
            Grant(name="Grant A", source="test"),
            Grant(name="Grant B", source="test"),
        ]
        new = temp_storage.get_new_grants(updated)
        # Grant B should be identified as new
        assert any(g.name == "Grant B" for g in new)
