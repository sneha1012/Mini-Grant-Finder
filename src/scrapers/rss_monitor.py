"""
RSS feed monitor for grant announcements.

Monitors RSS feeds from Philanthropy News Digest, EPA, CA Grants Portal,
Federal Register, and Grants.gov for new grant opportunities relevant
to Delta Rising Foundation.
"""

import logging
import re
from datetime import date, datetime
from typing import Optional

import feedparser

from src.models.grant import Grant, GrantStatus, GrantType
from src.models.source import RSSSource, ScrapingConfig
from src.scrapers.base import BaseScraper, ScraperError

logger = logging.getLogger(__name__)

# Default RSS feeds to monitor
DEFAULT_FEEDS = [
    RSSSource(
        name="Philanthropy News Digest",
        url="https://philanthropynewsdigest.org/rfps/feed",
    ),
    RSSSource(
        name="EPA Grants",
        url="https://www.epa.gov/grants/epa-grants-rss-feed",
    ),
    RSSSource(
        name="CA Grants Portal",
        url="https://www.grants.ca.gov/grants/rss/",
    ),
    RSSSource(
        name="Grants.gov - Environment",
        url="https://www.grants.gov/rss/GG_OppModByCategory_ENV.xml",
    ),
    RSSSource(
        name="Federal Register - EPA",
        url="https://www.federalregister.gov/documents/search.rss?conditions%5Bagencies%5D%5B%5D=environmental-protection-agency&conditions%5Btype%5D%5B%5D=NOTICE",
    ),
]

# Keywords that suggest an RSS entry is about a grant/funding opportunity
GRANT_KEYWORDS = [
    "grant", "funding", "rfp", "request for proposal", "application",
    "award", "solicitation", "notice of funding", "nofo", "nofa",
    "mini-grant", "cooperative agreement", "financial assistance",
    "letter of intent", "loi", "sponsorship", "donation",
]

# Keywords relevant to Delta Rising Foundation's mission
RELEVANCE_KEYWORDS = [
    "environment", "climate", "sustainability", "carbon", "resilience",
    "native plant", "urban", "community", "biodiversity", "conservation",
    "environmental justice", "equity", "nonprofit", "garden",
    "forestry", "shade", "heat", "indigenous", "agroforestry",
    "pollution", "adaptation", "green", "renewable", "ecosystem",
]


class RSSMonitor(BaseScraper):
    """
    Monitors multiple RSS feeds for grant announcements.

    Fetches and parses RSS/Atom feeds, filters entries that look like
    grant opportunities, and extracts structured data into Grant objects.
    """

    def __init__(
        self,
        feeds: Optional[list[RSSSource]] = None,
        config: Optional[ScrapingConfig] = None,
    ):
        """
        Initialize the RSS monitor.

        Args:
            feeds: List of RSS feed sources to monitor.
                   Uses DEFAULT_FEEDS if not provided.
            config: General scraping configuration.
        """
        super().__init__(config)
        self.feeds = feeds or DEFAULT_FEEDS

    @property
    def source_name(self) -> str:
        return "RSS Feeds"

    def scrape(self) -> list[Grant]:
        """
        Fetch all configured RSS feeds and extract grant opportunities.

        Returns:
            List of Grant objects discovered from RSS feeds
        """
        all_grants = []

        for feed_source in self.feeds:
            if not feed_source.enabled:
                continue

            try:
                grants = self._process_feed(feed_source)
                all_grants.extend(grants)
                logger.info(
                    f"Feed '{feed_source.name}': {len(grants)} grants found"
                )
            except Exception as e:
                logger.warning(
                    f"Failed to process feed '{feed_source.name}': {e}"
                )

        return all_grants

    def _process_feed(self, feed_source: RSSSource) -> list[Grant]:
        """
        Fetch and process a single RSS feed.

        Args:
            feed_source: RSS feed configuration

        Returns:
            List of grants extracted from this feed
        """
        self._rate_limit()

        feed = feedparser.parse(
            feed_source.url,
            agent=self.config.user_agent,
        )

        if feed.bozo and not feed.entries:
            logger.warning(
                f"Feed parse error for '{feed_source.name}': "
                f"{feed.bozo_exception}"
            )
            return []

        grants = []
        for entry in feed.entries:
            # Check if entry looks like a grant opportunity
            if self._is_grant_opportunity(entry):
                grant = self._entry_to_grant(entry, feed_source)
                if grant:
                    grants.append(grant)

        return grants

    def _is_grant_opportunity(self, entry) -> bool:
        """
        Determine whether an RSS entry is about a grant/funding opportunity.

        Uses keyword matching on the title, summary, and tags to identify
        entries that are likely grant announcements vs. news articles.

        Args:
            entry: feedparser entry object

        Returns:
            True if this looks like a grant opportunity
        """
        # Build searchable text from the entry
        text_parts = [
            getattr(entry, "title", ""),
            getattr(entry, "summary", ""),
            getattr(entry, "description", ""),
        ]

        # Add tags/categories
        for tag in getattr(entry, "tags", []):
            text_parts.append(tag.get("term", ""))

        searchable = " ".join(text_parts).lower()

        # Check for grant-related keywords
        has_grant_keyword = any(kw in searchable for kw in GRANT_KEYWORDS)

        # Check for relevance to Delta's mission
        has_relevance = any(kw in searchable for kw in RELEVANCE_KEYWORDS)

        # Entry must contain at least one grant keyword AND one relevance keyword
        return has_grant_keyword and has_relevance

    def _entry_to_grant(
        self, entry, feed_source: RSSSource
    ) -> Optional[Grant]:
        """
        Convert an RSS entry to a Grant object.

        Extracts as much structured data as possible from the
        unstructured RSS entry content.

        Args:
            entry: feedparser entry object
            feed_source: Source feed configuration

        Returns:
            Grant object or None if the entry can't be parsed
        """
        title = getattr(entry, "title", "").strip()
        if not title:
            return None

        # Get the link
        url = getattr(entry, "link", "")
        if not url:
            links = getattr(entry, "links", [])
            if links:
                url = links[0].get("href", "")

        # Get description/summary
        summary = getattr(entry, "summary", "")
        if not summary:
            summary = getattr(entry, "description", "")
        # Strip HTML tags from summary
        summary = re.sub(r'<[^>]+>', '', summary).strip()
        summary = re.sub(r'\s+', ' ', summary)

        # Try to extract deadline from text
        deadline = self._extract_deadline(summary + " " + title)
        deadline_text = ""
        if deadline:
            deadline_text = deadline.strftime("%b %d, %Y")

        # Try to extract amount
        amount_min, amount_max, amount_text = self._extract_amount(
            summary + " " + title
        )

        # Parse publication date
        published = None
        if hasattr(entry, "published_parsed") and entry.published_parsed:
            try:
                published = datetime(*entry.published_parsed[:6])
            except (ValueError, TypeError):
                pass

        # Determine grant type based on feed source
        grant_type = self._infer_grant_type(title, summary, feed_source)

        # Extract focus areas from tags and content
        focus_areas = self._extract_focus_areas(entry, summary)

        # Determine geographic scope
        geo_scope = self._extract_geography(summary + " " + title)

        return Grant(
            name=title[:200],
            source=f"rss_{feed_source.name.lower().replace(' ', '_')}",
            url=url,
            amount_min=amount_min,
            amount_max=amount_max,
            amount_text=amount_text,
            deadline=deadline,
            deadline_text=deadline_text,
            status=GrantStatus.OPEN if deadline and deadline >= date.today()
            else GrantStatus.UNKNOWN,
            grant_type=grant_type,
            description=summary[:500],
            focus_areas=focus_areas,
            geographic_scope=geo_scope,
            eligibility_notes="",
            how_to_apply=f"See {url}" if url else "",
            funder=self._extract_funder(title),
            discovered_date=published or datetime.now(),
        )

    def _extract_deadline(self, text: str) -> Optional[date]:
        """Try to extract a deadline date from text content."""
        # Look for common deadline patterns
        patterns = [
            r'deadline[:\s]+(\w+ \d{1,2},?\s*\d{4})',
            r'due[:\s]+(\w+ \d{1,2},?\s*\d{4})',
            r'closes?[:\s]+(\w+ \d{1,2},?\s*\d{4})',
            r'by\s+(\w+ \d{1,2},?\s*\d{4})',
            r'(\w+ \d{1,2},?\s*\d{4})\s*deadline',
        ]

        for pattern in patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                date_str = match.group(1)
                for fmt in ["%B %d, %Y", "%B %d %Y", "%b %d, %Y", "%b %d %Y"]:
                    try:
                        return datetime.strptime(date_str.strip(), fmt).date()
                    except ValueError:
                        continue

        return None

    def _extract_amount(self, text: str) -> tuple[float, float, str]:
        """Try to extract grant amounts from text."""
        # Look for dollar amounts
        amounts = re.findall(r'\$[\d,]+(?:\.\d{2})?', text)
        if not amounts:
            return 0.0, 0.0, ""

        parsed = []
        for amt in amounts:
            try:
                parsed.append(float(amt.replace('$', '').replace(',', '')))
            except ValueError:
                continue

        if len(parsed) >= 2:
            return min(parsed), max(parsed), f"${min(parsed):,.0f} - ${max(parsed):,.0f}"
        elif parsed:
            # Check for "up to" pattern
            if "up to" in text.lower():
                return 0.0, parsed[0], f"Up to ${parsed[0]:,.0f}"
            return parsed[0], parsed[0], f"${parsed[0]:,.0f}"

        return 0.0, 0.0, ""

    def _infer_grant_type(
        self, title: str, summary: str, feed_source: RSSSource
    ) -> GrantType:
        """Infer the grant type from content and source."""
        text = f"{title} {summary}".lower()

        if "federal" in text or "epa" in feed_source.name.lower():
            return GrantType.FEDERAL_GRANT
        if "state" in text or "ca grants" in feed_source.name.lower():
            return GrantType.STATE_GRANT
        if "mini" in text:
            return GrantType.MINI_GRANT
        if "foundation" in text:
            return GrantType.FOUNDATION_GRANT
        if "corporate" in text or "sponsor" in text:
            return GrantType.CORPORATE_GRANT

        return GrantType.UNKNOWN

    def _extract_focus_areas(self, entry, summary: str) -> list[str]:
        """Extract focus area tags from entry metadata and content."""
        areas = []

        # From RSS tags
        for tag in getattr(entry, "tags", []):
            term = tag.get("term", "").strip()
            if term:
                areas.append(term)

        # From content keywords
        text = summary.lower()
        keyword_areas = {
            "climate": "Climate",
            "environment": "Environment",
            "conservation": "Conservation",
            "biodiversity": "Biodiversity",
            "community": "Community Development",
            "agriculture": "Agriculture",
            "urban": "Urban Development",
            "energy": "Energy",
            "water": "Water",
            "justice": "Environmental Justice",
        }

        for keyword, area in keyword_areas.items():
            if keyword in text and area not in areas:
                areas.append(area)

        return areas[:5]  # Limit to 5 areas

    def _extract_geography(self, text: str) -> str:
        """Try to extract geographic scope from text."""
        text_lower = text.lower()

        if "california" in text_lower or "ca " in text_lower:
            return "California"
        if "national" in text_lower or "u.s." in text_lower:
            return "National (U.S.)"
        if "orange county" in text_lower:
            return "Orange County, CA"
        if any(state in text_lower for state in [
            "nationwide", "federal", "all states"
        ]):
            return "National (U.S.)"

        return "National (U.S.)"  # Default assumption for RSS feeds

    def _extract_funder(self, title: str) -> str:
        """Try to extract the funding organization from the title."""
        # Look for patterns like "Organization: Grant Name" or "Organization —"
        separators = [":", "—", "-", "|", "–"]
        for sep in separators:
            if sep in title:
                parts = title.split(sep)
                if len(parts) >= 2 and len(parts[0].strip()) > 3:
                    return parts[0].strip()

        return ""
