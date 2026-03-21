"""
Pytest configuration and shared fixtures.

Provides common test fixtures used across all test modules,
including sample grants, mock data, and temporary directories.
"""

import sys
from datetime import date, timedelta
from pathlib import Path

import pytest

# Ensure project root is in path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.models.grant import Grant, GrantStatus, GrantType, Priority


@pytest.fixture
def climate_grant():
    """A grant related to climate/environment (should score high)."""
    return Grant(
        name="EPA Environmental Justice Community Change Grant",
        source="grants_gov",
        url="https://www.epa.gov/community-change",
        amount_min=50000,
        amount_max=500000,
        amount_text="$50,000 - $500,000",
        deadline=date.today() + timedelta(days=45),
        deadline_text="Rolling",
        status=GrantStatus.OPEN,
        grant_type=GrantType.FEDERAL_GRANT,
        description=(
            "Community-driven investments in climate adaptation, "
            "resilience, pollution reduction, and environmental justice "
            "for underserved communities"
        ),
        focus_areas=["climate", "environmental justice", "community"],
        geographic_scope="National (U.S.)",
        eligibility_notes="Partnership: 2 CBOs or CBO + tribal/gov",
        how_to_apply="Apply at Grants.gov",
        funder="EPA",
        relevance_score=0,
    )


@pytest.fixture
def nursery_grant():
    """A grant related to plants/gardens (should match Resilience Nursery)."""
    return Grant(
        name="Sprouts Healthy Communities Foundation",
        source="website",
        url="https://about.sprouts.com/donation",
        amount_min=5000,
        amount_max=10000,
        deadline=date.today() + timedelta(days=90),
        status=GrantStatus.OPEN,
        grant_type=GrantType.CORPORATE_GRANT,
        description="Nutrition education and school garden programs",
        focus_areas=["native plants", "community garden", "food security"],
        geographic_scope="Southern California",
        funder="Sprouts",
    )


@pytest.fixture
def expired_grant():
    """An expired grant for testing filters."""
    return Grant(
        name="Old Climate Grant 2025",
        source="csv",
        deadline=date.today() - timedelta(days=30),
        status=GrantStatus.CLOSED,
        grant_type=GrantType.FOUNDATION_GRANT,
        description="This grant has passed its deadline",
    )


@pytest.fixture
def rolling_grant():
    """A grant with a rolling deadline."""
    return Grant(
        name="Texas Grassroots Environmental Mini Grants",
        source="rss",
        url="https://www.txenvironment.org/mini-grants",
        amount_max=4000,
        status=GrantStatus.ROLLING,
        grant_type=GrantType.MINI_GRANT,
        description="Grassroots environmental organizing",
        focus_areas=["environment", "grassroots"],
        geographic_scope="Texas",
    )


@pytest.fixture
def sample_grant_list(climate_grant, nursery_grant, expired_grant, rolling_grant):
    """A list of diverse sample grants for testing."""
    return [climate_grant, nursery_grant, expired_grant, rolling_grant]


@pytest.fixture
def project_root():
    """Path to the project root directory."""
    return Path(__file__).parent.parent


@pytest.fixture
def config_dir(project_root):
    """Path to the config directory."""
    return project_root / "config"


@pytest.fixture
def research_dir(project_root):
    """Path to the research directory."""
    return project_root / "research"
