"""
Dashboard data loading and caching layer.

Handles loading grant data from JSON snapshots or research CSVs,
with Streamlit caching to avoid reloading on every interaction.
Also computes summary metrics for the dashboard.
"""

import logging
import sys
from datetime import date, datetime
from pathlib import Path
from typing import Optional

import streamlit as st

# Add project root to path
PROJECT_ROOT = Path(__file__).parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.models.grant import Grant

logger = logging.getLogger(__name__)


@st.cache_data(ttl=300)  # Cache for 5 minutes
def load_dashboard_data() -> list[Grant]:
    """
    Load grant data for the dashboard with caching.

    Tries loading sources in this order:
    1. Latest JSON snapshot from data/processed/
    2. Research CSV files (with processing)
    3. Empty list if nothing available

    Returns:
        List of Grant objects, sorted by relevance score
    """
    # Try JSON snapshot first
    grants = _load_from_json()
    if grants:
        logger.info(f"Loaded {len(grants)} grants from JSON snapshot")
        return grants

    # Fall back to research CSVs
    grants = _load_from_research()
    if grants:
        logger.info(f"Loaded {len(grants)} grants from research CSVs")
        return grants

    logger.warning("No grant data available")
    return []


def _load_from_json() -> list[Grant]:
    """Try to load from the latest JSON snapshot."""
    try:
        from src.storage.local import LocalStorage

        storage = LocalStorage()
        grants = storage.load_latest()
        return sorted(grants, key=lambda g: g.relevance_score, reverse=True)
    except Exception as e:
        logger.debug(f"Could not load JSON snapshot: {e}")
        return []


def _load_from_research() -> list[Grant]:
    """Load and process research CSV data."""
    try:
        from src.loaders.csv_loader import load_all_research_data
        from src.pipeline.processor import process_grants

        raw_grants = load_all_research_data()
        if not raw_grants:
            return []

        processed = process_grants(raw_grants)

        # Try scoring if possible
        try:
            from src.scoring.relevance import RelevanceScorer
            from src.scoring.program_matcher import ProgramMatcher

            scorer = RelevanceScorer()
            processed = scorer.score_grants(processed)

            matcher = ProgramMatcher()
            processed = matcher.match_grants(processed)
        except Exception as e:
            logger.debug(f"Scoring not available: {e}")

        return processed
    except Exception as e:
        logger.debug(f"Could not load research data: {e}")
        return []


def get_summary_metrics(grants: list[Grant]) -> dict:
    """
    Compute summary metrics for the dashboard header.

    Args:
        grants: List of all grants

    Returns:
        Dict with: total_grants, urgent_count, high_relevance,
                   new_today, total_funding, avg_score
    """
    today = date.today()

    total = len(grants)

    # Urgent: deadline within 14 days
    urgent = sum(
        1 for g in grants
        if g.deadline and 0 <= (g.deadline - today).days <= 14
    )

    # High relevance: score >= 60
    high_rel = sum(1 for g in grants if g.relevance_score >= 60)

    # New today (discovered today)
    new_today = sum(
        1 for g in grants
        if g.discovered_date
        and g.discovered_date.date() == today
    )

    # Total funding (sum of max amounts)
    total_funding = sum(g.amount_max for g in grants if g.amount_max > 0)

    # Average score
    scores = [g.relevance_score for g in grants if g.relevance_score > 0]
    avg_score = sum(scores) / len(scores) if scores else 0

    return {
        "total_grants": total,
        "urgent_count": urgent,
        "high_relevance": high_rel,
        "new_today": new_today,
        "total_funding": total_funding,
        "avg_score": round(avg_score, 1),
    }


def get_program_distribution(grants: list[Grant]) -> dict[str, int]:
    """
    Count grants per program for charts.

    Args:
        grants: List of grants

    Returns:
        Dict mapping program names to grant counts
    """
    distribution = {}
    for grant in grants:
        for program in grant.matched_programs:
            distribution[program] = distribution.get(program, 0) + 1

    return dict(sorted(distribution.items(), key=lambda x: x[1], reverse=True))


def get_type_distribution(grants: list[Grant]) -> dict[str, int]:
    """
    Count grants per type for charts.

    Args:
        grants: List of grants

    Returns:
        Dict mapping grant types to counts
    """
    distribution = {}
    for grant in grants:
        type_name = grant.grant_type.value.replace("_", " ").title()
        distribution[type_name] = distribution.get(type_name, 0) + 1

    return dict(sorted(distribution.items(), key=lambda x: x[1], reverse=True))


def get_deadline_timeline(grants: list[Grant], days_ahead: int = 90) -> list[dict]:
    """
    Get grants with deadlines in the next N days for timeline display.

    Args:
        grants: List of grants
        days_ahead: Number of days to look ahead

    Returns:
        List of dicts with grant info sorted by deadline
    """
    today = date.today()
    timeline = []

    for grant in grants:
        if grant.deadline and 0 <= (grant.deadline - today).days <= days_ahead:
            timeline.append({
                "name": grant.name,
                "deadline": grant.deadline,
                "days_left": (grant.deadline - today).days,
                "amount": grant.amount_display,
                "score": grant.relevance_score,
                "url": grant.url,
            })

    timeline.sort(key=lambda x: x["deadline"])
    return timeline
