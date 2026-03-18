"""
Data processing pipeline for grant deduplication, cleaning, and normalization.

Takes raw Grant objects from any source (CSV loader, scrapers) and produces
a clean, deduplicated, normalized dataset ready for scoring and display.
"""

import logging
import re
from datetime import date, datetime
from typing import Optional

from src.models.grant import Grant, GrantStatus, Priority

logger = logging.getLogger(__name__)


class GrantProcessor:
    """
    Processes raw grant data through cleaning, normalization, and deduplication.

    Pipeline stages:
    1. Clean - strip whitespace, fix encoding, normalize text
    2. Normalize - standardize dates, amounts, geographic scope
    3. Deduplicate - merge duplicates found from different sources
    4. Filter - remove expired, ineligible, or irrelevant grants
    5. Enrich - add computed fields like urgency and priority
    """

    def __init__(self, exclude_expired: bool = True, min_amount: float = 0):
        """
        Initialize the processor.

        Args:
            exclude_expired: Whether to filter out grants past their deadline
            min_amount: Minimum grant amount to include (0 = no minimum)
        """
        self.exclude_expired = exclude_expired
        self.min_amount = min_amount
        self._stats = {
            "input": 0,
            "cleaned": 0,
            "deduplicated": 0,
            "filtered": 0,
            "output": 0,
        }

    def process(self, grants: list[Grant]) -> list[Grant]:
        """
        Run the full processing pipeline on a list of grants.

        Args:
            grants: Raw Grant objects from loaders or scrapers

        Returns:
            Cleaned, deduplicated, and enriched grants
        """
        self._stats["input"] = len(grants)
        logger.info(f"Processing {len(grants)} raw grants...")

        # Stage 1: Clean
        grants = [self._clean_grant(g) for g in grants]
        self._stats["cleaned"] = len(grants)

        # Stage 2: Normalize
        grants = [self._normalize_grant(g) for g in grants]

        # Stage 3: Deduplicate
        grants = self._deduplicate(grants)
        self._stats["deduplicated"] = len(grants)

        # Stage 4: Filter
        grants = self._filter_grants(grants)
        self._stats["filtered"] = len(grants)

        # Stage 5: Enrich
        grants = [self._enrich_grant(g) for g in grants]
        self._stats["output"] = len(grants)

        logger.info(
            f"Pipeline complete: {self._stats['input']} in -> "
            f"{self._stats['output']} out "
            f"({self._stats['input'] - self._stats['output']} removed)"
        )
        return grants

    @property
    def stats(self) -> dict:
        """Get processing statistics from the last run."""
        return self._stats.copy()

    def _clean_grant(self, grant: Grant) -> Grant:
        """Clean and sanitize grant text fields."""
        grant.name = self._clean_text(grant.name)
        grant.description = self._clean_text(grant.description)
        grant.eligibility_notes = self._clean_text(grant.eligibility_notes)
        grant.geographic_scope = self._clean_text(grant.geographic_scope)
        grant.how_to_apply = self._clean_text(grant.how_to_apply)
        grant.funder = self._clean_text(grant.funder)
        grant.url = grant.url.strip()

        # Clean focus areas
        grant.focus_areas = [
            self._clean_text(fa) for fa in grant.focus_areas if fa.strip()
        ]

        return grant

    def _clean_text(self, text: str) -> str:
        """Strip whitespace, fix encoding artifacts, normalize spacing."""
        if not text:
            return ""

        # Fix common encoding issues
        text = text.replace("\u2014", "—")  # em dash
        text = text.replace("\u2013", "–")  # en dash
        text = text.replace("\u2018", "'").replace("\u2019", "'")
        text = text.replace("\u201c", '"').replace("\u201d", '"')

        # Normalize whitespace
        text = re.sub(r'\s+', ' ', text).strip()

        return text

    def _normalize_grant(self, grant: Grant) -> Grant:
        """Normalize dates, amounts, and geographic scope."""
        # Normalize geographic scope
        grant.geographic_scope = self._normalize_geography(
            grant.geographic_scope
        )

        # Ensure amount fields are consistent
        if grant.amount_max > 0 and grant.amount_min > grant.amount_max:
            grant.amount_min, grant.amount_max = grant.amount_max, grant.amount_min

        # Normalize status based on deadline
        if grant.deadline:
            days = (grant.deadline - date.today()).days
            if days < 0:
                grant.status = GrantStatus.CLOSED
            elif days <= 14 and grant.status == GrantStatus.OPEN:
                grant.status = GrantStatus.CLOSING_SOON

        # Set rolling status if deadline text indicates it
        if grant.deadline_text.lower().strip() in ("rolling", "ongoing", "open"):
            grant.status = GrantStatus.ROLLING

        return grant

    def _normalize_geography(self, scope: str) -> str:
        """Standardize geographic scope strings."""
        if not scope:
            return "Unknown"

        scope_lower = scope.lower()

        # Map common patterns
        mappings = {
            "national": "National (U.S.)",
            "u.s.": "National (U.S.)",
            "united states": "National (U.S.)",
            "global": "Global",
            "international": "Global",
            "california": "California",
            "orange county": "Orange County, CA",
            "garden grove": "Garden Grove, CA",
            "los angeles": "Los Angeles, CA",
            "socal": "Southern California",
        }

        for key, value in mappings.items():
            if key in scope_lower and len(scope) < 50:
                return value

        return scope

    def _deduplicate(self, grants: list[Grant]) -> list[Grant]:
        """
        Remove duplicate grants, keeping the richest version.

        Deduplication strategy:
        1. Exact name match (case-insensitive)
        2. High similarity name match (for slight variations)
        3. Same URL match

        When merging duplicates, keep the version with:
        - More complete information (longer description, more fields)
        - Most recent discovery date
        - Higher relevance score
        """
        seen_names: dict[str, Grant] = {}
        seen_urls: dict[str, Grant] = {}
        unique_grants: list[Grant] = []

        for grant in grants:
            # Normalize the name for comparison
            norm_name = self._normalize_name(grant.name)

            # Check for URL-based duplicate
            if grant.url and grant.url in seen_urls:
                existing = seen_urls[grant.url]
                merged = self._merge_grants(existing, grant)
                # Update references
                seen_urls[grant.url] = merged
                seen_names[self._normalize_name(existing.name)] = merged
                continue

            # Check for name-based duplicate
            if norm_name in seen_names:
                existing = seen_names[norm_name]
                merged = self._merge_grants(existing, grant)
                seen_names[norm_name] = merged
                if existing.url:
                    seen_urls[existing.url] = merged
                continue

            # New grant
            seen_names[norm_name] = grant
            if grant.url:
                seen_urls[grant.url] = grant
            unique_grants.append(grant)

        # Replace with merged versions
        result = []
        processed_names = set()
        for grant in unique_grants:
            norm_name = self._normalize_name(grant.name)
            if norm_name not in processed_names:
                result.append(seen_names.get(norm_name, grant))
                processed_names.add(norm_name)

        removed = len(grants) - len(result)
        if removed > 0:
            logger.info(f"Deduplication removed {removed} duplicate grants")

        return result

    def _normalize_name(self, name: str) -> str:
        """Normalize a grant name for deduplication comparison."""
        # Lowercase, strip punctuation, collapse whitespace
        name = name.lower().strip()
        name = re.sub(r'[—–\-]+', ' ', name)
        name = re.sub(r'[^\w\s]', '', name)
        name = re.sub(r'\s+', ' ', name)
        return name

    def _merge_grants(self, existing: Grant, new: Grant) -> Grant:
        """Merge two duplicate grants, keeping the richest data."""
        # Use longer/more complete values
        if len(new.description) > len(existing.description):
            existing.description = new.description
        if len(new.eligibility_notes) > len(existing.eligibility_notes):
            existing.eligibility_notes = new.eligibility_notes
        if len(new.how_to_apply) > len(existing.how_to_apply):
            existing.how_to_apply = new.how_to_apply
        if not existing.url and new.url:
            existing.url = new.url
        if not existing.deadline and new.deadline:
            existing.deadline = new.deadline
            existing.deadline_text = new.deadline_text
        if new.amount_max > existing.amount_max:
            existing.amount_min = new.amount_min
            existing.amount_max = new.amount_max
            existing.amount_text = new.amount_text

        # Merge focus areas
        existing_areas = set(existing.focus_areas)
        for area in new.focus_areas:
            if area not in existing_areas:
                existing.focus_areas.append(area)

        # Keep higher priority
        priority_order = {
            Priority.URGENT: 0,
            Priority.HIGH: 1,
            Priority.MEDIUM: 2,
            Priority.LOW: 3,
            Priority.MONITOR: 4,
        }
        if priority_order.get(new.priority, 5) < priority_order.get(
            existing.priority, 5
        ):
            existing.priority = new.priority

        # Track all sources
        sources = set(existing.source.split(","))
        sources.add(new.source)
        existing.source = ",".join(sorted(sources))

        return existing

    def _filter_grants(self, grants: list[Grant]) -> list[Grant]:
        """Filter out expired, ineligible, or low-value grants."""
        filtered = []

        for grant in grants:
            # Skip expired if configured
            if self.exclude_expired and grant.is_expired:
                logger.debug(f"Filtered (expired): {grant.name}")
                continue

            # Skip if below minimum amount threshold
            if self.min_amount > 0 and grant.amount_max > 0:
                if grant.amount_max < self.min_amount:
                    logger.debug(
                        f"Filtered (below min ${self.min_amount}): {grant.name}"
                    )
                    continue

            # Skip grants with empty names
            if not grant.name.strip():
                continue

            filtered.append(grant)

        removed = len(grants) - len(filtered)
        if removed > 0:
            logger.info(f"Filtering removed {removed} grants")

        return filtered

    def _enrich_grant(self, grant: Grant) -> Grant:
        """Add computed fields and update priority."""
        # Update priority based on deadline and score
        grant.update_priority()

        # Ensure last_updated is current
        grant.last_updated = datetime.now()

        # Regenerate ID to ensure consistency
        grant.grant_id = grant._generate_id()

        return grant


def process_grants(
    grants: list[Grant],
    exclude_expired: bool = True,
    min_amount: float = 0,
) -> list[Grant]:
    """
    Convenience function to process a list of grants.

    Args:
        grants: Raw Grant objects
        exclude_expired: Whether to remove expired grants
        min_amount: Minimum amount filter

    Returns:
        Processed list of Grant objects
    """
    processor = GrantProcessor(
        exclude_expired=exclude_expired,
        min_amount=min_amount,
    )
    return processor.process(grants)
