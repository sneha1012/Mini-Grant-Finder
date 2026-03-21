"""
Unit tests for Grant and Source data models.
"""

import pytest
from datetime import date, datetime, timedelta

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.models.grant import Grant, GrantStatus, GrantType, Priority


class TestGrant:
    """Tests for the Grant dataclass."""

    def test_create_basic_grant(self):
        """Test creating a grant with minimal fields."""
        grant = Grant(name="Test Grant")
        assert grant.name == "Test Grant"
        assert grant.grant_id != ""
        assert grant.relevance_score == 0.0
        assert grant.status == GrantStatus.UNKNOWN

    def test_grant_id_generation(self):
        """Test that grant IDs are deterministic and unique."""
        g1 = Grant(name="Grant A", funder="Org A", source="test")
        g2 = Grant(name="Grant A", funder="Org A", source="test")
        g3 = Grant(name="Grant B", funder="Org B", source="test")

        assert g1.grant_id == g2.grant_id  # Same inputs = same ID
        assert g1.grant_id != g3.grant_id  # Different inputs = different ID

    def test_days_until_deadline_future(self):
        """Test deadline calculation for a future date."""
        future = date.today() + timedelta(days=10)
        grant = Grant(name="Test", deadline=future)
        assert grant.days_until_deadline == 10

    def test_days_until_deadline_past(self):
        """Test deadline calculation for a past date."""
        past = date.today() - timedelta(days=5)
        grant = Grant(name="Test", deadline=past)
        assert grant.days_until_deadline == -5

    def test_days_until_deadline_none(self):
        """Test deadline calculation when no deadline set."""
        grant = Grant(name="Test")
        assert grant.days_until_deadline is None

    def test_is_expired_future(self):
        """Test expired check for future deadline."""
        future = date.today() + timedelta(days=30)
        grant = Grant(name="Test", deadline=future)
        assert grant.is_expired is False

    def test_is_expired_past(self):
        """Test expired check for past deadline."""
        past = date.today() - timedelta(days=1)
        grant = Grant(name="Test", deadline=past)
        assert grant.is_expired is True

    def test_is_expired_no_deadline(self):
        """Test expired check when no deadline (should not be expired)."""
        grant = Grant(name="Test")
        assert grant.is_expired is False

    def test_urgency_label_this_week(self):
        """Test urgency label for imminent deadline."""
        soon = date.today() + timedelta(days=3)
        grant = Grant(name="Test", deadline=soon)
        assert grant.urgency_label == "This week"

    def test_urgency_label_upcoming(self):
        """Test urgency label for distant deadline."""
        far = date.today() + timedelta(days=90)
        grant = Grant(name="Test", deadline=far)
        assert grant.urgency_label == "Upcoming"

    def test_urgency_label_no_deadline(self):
        """Test urgency label when no deadline set."""
        grant = Grant(name="Test")
        assert grant.urgency_label == "No deadline"

    def test_amount_display_range(self):
        """Test amount display for a range."""
        grant = Grant(name="Test", amount_min=5000, amount_max=10000)
        assert "$5,000" in grant.amount_display
        assert "$10,000" in grant.amount_display

    def test_amount_display_max_only(self):
        """Test amount display for max-only."""
        grant = Grant(name="Test", amount_max=50000)
        assert "Up to $50,000" in grant.amount_display

    def test_amount_display_text_override(self):
        """Test amount display uses text when available."""
        grant = Grant(
            name="Test",
            amount_text="Up to $30,000/yr (2 years)",
            amount_max=30000,
        )
        assert grant.amount_display == "Up to $30,000/yr (2 years)"

    def test_amount_display_varies(self):
        """Test amount display defaults to Varies."""
        grant = Grant(name="Test")
        assert grant.amount_display == "Varies"

    def test_update_priority_urgent(self):
        """Test priority update for urgent grant."""
        deadline = date.today() + timedelta(days=7)
        grant = Grant(name="Test", deadline=deadline, relevance_score=80)
        grant.update_priority()
        assert grant.priority == Priority.URGENT

    def test_update_priority_high_score(self):
        """Test priority update for high-score grant."""
        deadline = date.today() + timedelta(days=60)
        grant = Grant(name="Test", deadline=deadline, relevance_score=75)
        grant.update_priority()
        assert grant.priority == Priority.HIGH

    def test_update_priority_monitor(self):
        """Test that monitor status overrides score-based priority."""
        grant = Grant(
            name="Test",
            status=GrantStatus.MONITOR,
            relevance_score=90,
        )
        grant.update_priority()
        assert grant.priority == Priority.MONITOR

    def test_to_dict_and_from_dict(self):
        """Test serialization roundtrip."""
        original = Grant(
            name="EPA Climate Grant",
            source="grants_gov",
            url="https://example.gov/grant",
            amount_min=5000,
            amount_max=50000,
            deadline=date(2026, 6, 15),
            status=GrantStatus.OPEN,
            grant_type=GrantType.FEDERAL_GRANT,
            relevance_score=72.5,
            matched_programs=["ai_climate_tools", "more_shade"],
            focus_areas=["climate", "environment"],
            priority=Priority.HIGH,
        )

        data = original.to_dict()
        restored = Grant.from_dict(data)

        assert restored.name == original.name
        assert restored.source == original.source
        assert restored.amount_min == original.amount_min
        assert restored.amount_max == original.amount_max
        assert restored.deadline == original.deadline
        assert restored.status == original.status
        assert restored.grant_type == original.grant_type
        assert restored.relevance_score == original.relevance_score
        assert restored.matched_programs == original.matched_programs
        assert restored.priority == original.priority

    def test_from_dict_handles_bad_enum(self):
        """Test from_dict gracefully handles invalid enum values."""
        data = {
            "name": "Test",
            "status": "invalid_status",
            "grant_type": "made_up_type",
            "priority": "bogus",
        }
        grant = Grant.from_dict(data)
        assert grant.status == GrantStatus.UNKNOWN
        assert grant.grant_type == GrantType.UNKNOWN
        assert grant.priority == Priority.MEDIUM


class TestGrantEnums:
    """Tests for grant-related enums."""

    def test_grant_status_values(self):
        assert GrantStatus.OPEN.value == "open"
        assert GrantStatus.ROLLING.value == "rolling"
        assert GrantStatus.CLOSED.value == "closed"

    def test_grant_type_values(self):
        assert GrantType.FEDERAL_GRANT.value == "federal_grant"
        assert GrantType.MINI_GRANT.value == "mini_grant"
        assert GrantType.IN_KIND.value == "in_kind"

    def test_priority_values(self):
        assert Priority.URGENT.value == "urgent"
        assert Priority.MONITOR.value == "monitor"
