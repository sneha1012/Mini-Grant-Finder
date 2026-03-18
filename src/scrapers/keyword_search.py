"""
DuckDuckGo keyword searcher for grant discovery.

Automates the "Magic Keyword Algorithm" — the same search patterns
the team uses manually but running automatically. Uses the free
duckduckgo-search library (no API key needed).

Query patterns based on the team's proven manual approach:
  "donation request" + industry + location
  "{keyword}" + "grant" + "nonprofit" + year
"""

import logging
import re
import time
from datetime import datetime
from typing import Optional

from src.models.grant import Grant, GrantStatus, GrantType
from src.models.source import KeywordSearchConfig, ScrapingConfig
from src.scrapers.base import BaseScraper

logger = logging.getLogger(__name__)

# Default query templates based on the team's manual keyword strategy
DEFAULT_TEMPLATES = [
    '"{keyword}" "request for proposals" nonprofit grant 2026',
    '"{keyword}" mini grant community nonprofit application',
    '"donation request" "{keyword}" California nonprofit',
    '"{keyword}" foundation grant small nonprofit environment',
    '"{keyword}" grant opportunity 501c3 climate',
]

# Keywords organized by Delta Rising Foundation program
PROGRAM_KEYWORDS = {
    "ai_climate_tools": [
        "carbon market verification",
        "climate technology nonprofit",
        "MRV environmental data",
        "carbon credit monitoring",
    ],
    "resilience_nursery": [
        "native plant nursery grant",
        "community garden funding",
        "urban agriculture nonprofit",
        "pollinator habitat grant",
        "food forest community",
    ],
    "more_shade": [
        "urban shade structure grant",
        "heat island mitigation funding",
        "urban forestry nonprofit grant",
        "community cooling center",
        "tree canopy grant",
    ],
    "cbecn": [
        "indigenous carbon credit",
        "community biodiversity grant",
        "smallholder farmer carbon",
        "traditional ecological knowledge funding",
    ],
    "cross_cutting": [
        "environmental justice mini grant",
        "racial equity environment grant",
        "community resilience nonprofit California",
        "climate adaptation small grant",
        "grassroots environmental organizing",
    ],
}

# URL patterns that typically indicate a grant/funding page
GRANT_URL_PATTERNS = [
    r"grant", r"fund", r"rfp", r"application", r"apply",
    r"solicitation", r"opportunity", r"award", r"sponsor",
    r"donation", r"giving", r"philanthropy", r"foundation",
]

# Domains to skip (not grant sources)
SKIP_DOMAINS = [
    "youtube.com", "facebook.com", "twitter.com", "instagram.com",
    "linkedin.com", "reddit.com", "wikipedia.org", "amazon.com",
    "pinterest.com", "tiktok.com",
]


class KeywordSearcher(BaseScraper):
    """
    Searches DuckDuckGo for grant opportunities using keyword patterns.

    Implements the "Magic Keyword Algorithm" that Delta's team uses
    manually, automating the process of discovering grants through
    strategic search queries.
    """

    def __init__(
        self,
        config: Optional[KeywordSearchConfig] = None,
        scraping_config: Optional[ScrapingConfig] = None,
    ):
        """
        Initialize the keyword searcher.

        Args:
            config: Keyword search configuration
            scraping_config: General scraping settings
        """
        super().__init__(scraping_config)
        self.search_config = config or KeywordSearchConfig(
            query_templates=DEFAULT_TEMPLATES,
            max_results_per_query=15,
            cooldown_seconds=3,
        )

    @property
    def source_name(self) -> str:
        return "DuckDuckGo Keyword Search"

    def scrape(self) -> list[Grant]:
        """
        Run keyword searches across all program areas.

        Returns:
            List of Grant objects discovered via keyword search
        """
        all_grants = []
        seen_urls = set()

        for program, keywords in PROGRAM_KEYWORDS.items():
            for keyword in keywords:
                try:
                    grants = self._search_keyword(keyword, program)
                    for grant in grants:
                        if grant.url not in seen_urls:
                            seen_urls.add(grant.url)
                            all_grants.append(grant)
                except Exception as e:
                    logger.warning(f"Search failed for '{keyword}': {e}")

                # Respect rate limits
                time.sleep(self.search_config.cooldown_seconds)

        logger.info(f"Keyword search found {len(all_grants)} unique results")
        return all_grants

    def _search_keyword(self, keyword: str, program: str) -> list[Grant]:
        """
        Search DuckDuckGo for a single keyword and extract grant results.

        Args:
            keyword: The search keyword/phrase
            program: Delta program this keyword belongs to

        Returns:
            List of grants found for this keyword
        """
        grants = []

        try:
            from duckduckgo_search import DDGS
        except ImportError:
            logger.error(
                "duckduckgo-search not installed. "
                "Run: pip install duckduckgo-search"
            )
            return grants

        try:
            with DDGS() as ddgs:
                results = list(ddgs.text(
                    keyword,
                    max_results=self.search_config.max_results_per_query,
                ))
        except Exception as e:
            logger.warning(f"DuckDuckGo search error for '{keyword}': {e}")
            return grants

        for result in results:
            url = result.get("href", result.get("link", ""))
            title = result.get("title", "")
            body = result.get("body", result.get("snippet", ""))

            # Skip irrelevant domains
            if self._should_skip_url(url):
                continue

            # Check if the result looks like a grant opportunity
            if not self._looks_like_grant(title, body, url):
                continue

            grant = self._result_to_grant(
                title=title,
                url=url,
                snippet=body,
                keyword=keyword,
                program=program,
            )
            if grant:
                grants.append(grant)

        return grants

    def _should_skip_url(self, url: str) -> bool:
        """Check if a URL should be skipped (social media, etc.)."""
        if not url:
            return True
        url_lower = url.lower()
        return any(domain in url_lower for domain in SKIP_DOMAINS)

    def _looks_like_grant(self, title: str, body: str, url: str) -> bool:
        """
        Determine if a search result looks like a grant opportunity.

        Uses a combination of URL patterns and content keywords
        to identify likely grant pages.
        """
        combined = f"{title} {body} {url}".lower()

        # Must match at least one grant-related pattern
        has_grant_signal = any(
            re.search(pattern, combined) for pattern in GRANT_URL_PATTERNS
        )

        return has_grant_signal

    def _result_to_grant(
        self,
        title: str,
        url: str,
        snippet: str,
        keyword: str,
        program: str,
    ) -> Optional[Grant]:
        """
        Convert a search result to a Grant object.

        Args:
            title: Search result title
            url: Search result URL
            snippet: Search result description/snippet
            keyword: The keyword that found this result
            program: Delta program area for this keyword

        Returns:
            Grant object or None
        """
        if not title or not url:
            return None

        # Clean title
        title = re.sub(r'\s+', ' ', title).strip()
        if len(title) > 200:
            title = title[:197] + "..."

        # Try to extract amount from snippet
        amount_min, amount_max, amount_text = self._extract_amount(snippet)

        # Try to infer grant type
        grant_type = self._infer_type(title, snippet, url)

        # Build description
        description = snippet.strip()
        if keyword not in description.lower():
            description = f"Found via: {keyword}. {description}"

        return Grant(
            name=title,
            source="keyword_search",
            url=url,
            amount_min=amount_min,
            amount_max=amount_max,
            amount_text=amount_text,
            deadline=None,
            deadline_text="Check website",
            status=GrantStatus.UNKNOWN,
            grant_type=grant_type,
            description=description[:500],
            focus_areas=[keyword],
            geographic_scope="",
            eligibility_notes="Verify eligibility on source website",
            how_to_apply=f"Visit {url}",
            funder=self._extract_domain_name(url),
            matched_programs=[program] if program != "cross_cutting" else [],
        )

    def _extract_amount(self, text: str) -> tuple[float, float, str]:
        """Extract dollar amounts from text."""
        if not text:
            return 0.0, 0.0, ""

        amounts = re.findall(r'\$[\d,]+(?:\.\d{2})?', text)
        parsed = []
        for amt in amounts:
            try:
                val = float(amt.replace('$', '').replace(',', ''))
                if val < 10_000_000:  # Skip unreasonably large numbers
                    parsed.append(val)
            except ValueError:
                continue

        if len(parsed) >= 2:
            lo, hi = min(parsed), max(parsed)
            return lo, hi, f"${lo:,.0f} - ${hi:,.0f}"
        elif parsed:
            return parsed[0], parsed[0], f"${parsed[0]:,.0f}"

        return 0.0, 0.0, ""

    def _infer_type(self, title: str, snippet: str, url: str) -> GrantType:
        """Infer grant type from content."""
        combined = f"{title} {snippet} {url}".lower()

        if "gov" in url.lower() or "federal" in combined:
            return GrantType.FEDERAL_GRANT
        if ".ca.gov" in url.lower() or "state" in combined:
            return GrantType.STATE_GRANT
        if "mini" in combined:
            return GrantType.MINI_GRANT
        if "foundation" in combined:
            return GrantType.FOUNDATION_GRANT
        if "corporate" in combined or "sponsor" in combined:
            return GrantType.CORPORATE_GRANT

        return GrantType.UNKNOWN

    @staticmethod
    def _extract_domain_name(url: str) -> str:
        """Extract a clean domain name from a URL."""
        try:
            from urllib.parse import urlparse
            parsed = urlparse(url)
            domain = parsed.netloc
            # Remove www. prefix
            if domain.startswith("www."):
                domain = domain[4:]
            # Get just the organization name
            parts = domain.split(".")
            if len(parts) >= 2:
                return parts[-2].title()
            return domain
        except Exception:
            return ""
