"""
Website scraper for foundation and organization grant pages.

Scrapes specific websites like OCCF, SoCalGas, CA Grants Portal,
Sprouts Foundation, and Clean Power Alliance for grant listings.
Uses BeautifulSoup for static pages and can be extended with
Playwright for JavaScript-rendered content.
"""

import logging
import re
from datetime import date, datetime
from typing import Optional
from urllib.parse import urljoin

from bs4 import BeautifulSoup

from src.models.grant import Grant, GrantStatus, GrantType
from src.models.source import ScrapingConfig, WebsiteSource
from src.scrapers.base import BaseScraper, ScraperError

logger = logging.getLogger(__name__)

# Default website sources to scrape
DEFAULT_SITES = [
    WebsiteSource(
        name="Orange County Community Foundation",
        url="https://www.oc-cf.org/grants/",
        selectors={
            "grants_list": ".grant-opportunity, .funding-opportunity, article",
            "title": "h3, h2, .grant-title, .entry-title",
            "deadline": ".deadline, .due-date, .date",
            "amount": ".amount, .grant-amount",
            "link": "a",
        },
    ),
    WebsiteSource(
        name="SoCalGas Climate Champions",
        url="https://socalclimatechampionsgrant.com/",
        selectors={
            "grants_list": ".grant-info, .program-details, section",
            "title": "h2, h3, .program-title",
            "deadline": ".deadline, .date",
            "description": "p, .description",
        },
    ),
    WebsiteSource(
        name="CA Grants Portal",
        url="https://www.grants.ca.gov/grants/",
        params={
            "keyword": "environment climate community",
            "status": "open",
        },
        selectors={
            "grants_list": ".grant-listing, .grant-item, article",
            "title": ".grant-title, h3, h2",
            "deadline": ".grant-deadline, .deadline",
            "amount": ".grant-amount, .amount",
            "link": "a",
        },
    ),
    WebsiteSource(
        name="Sprouts Foundation",
        url="https://about.sprouts.com/donation-and-sponsorship-application/",
        selectors={
            "grants_list": ".grant-info, .program-section, article",
            "title": "h2, h3",
            "description": "p",
        },
    ),
    WebsiteSource(
        name="Clean Power Alliance",
        url="https://cleanpoweralliance.org/community-programs/",
        selectors={
            "grants_list": ".program-card, .grant-listing, article",
            "title": "h3, h2",
            "deadline": ".deadline, .date",
            "description": "p, .description",
            "link": "a",
        },
    ),
]


class WebsiteScraper(BaseScraper):
    """
    Scrapes specific websites for grant opportunity listings.

    Uses CSS selectors defined in configuration to extract grant
    information from HTML pages. Each website has custom selectors
    for its particular page structure.
    """

    def __init__(
        self,
        sites: Optional[list[WebsiteSource]] = None,
        config: Optional[ScrapingConfig] = None,
    ):
        """
        Initialize the website scraper.

        Args:
            sites: List of website sources to scrape.
                   Uses DEFAULT_SITES if not provided.
            config: General scraping configuration.
        """
        super().__init__(config)
        self.sites = sites or DEFAULT_SITES

    @property
    def source_name(self) -> str:
        return "Website Scraper"

    def scrape(self) -> list[Grant]:
        """
        Scrape all configured websites for grant listings.

        Returns:
            List of Grant objects discovered from websites
        """
        all_grants = []

        for site in self.sites:
            if not site.enabled:
                continue

            try:
                grants = self._scrape_site(site)
                all_grants.extend(grants)
                logger.info(
                    f"Site '{site.name}': {len(grants)} grants found"
                )
            except ScraperError as e:
                logger.warning(f"Failed to scrape '{site.name}': {e}")
            except Exception as e:
                logger.warning(
                    f"Unexpected error scraping '{site.name}': {e}"
                )

        return all_grants

    def _scrape_site(self, site: WebsiteSource) -> list[Grant]:
        """
        Scrape a single website for grant listings.

        Args:
            site: Website source configuration with URL and selectors

        Returns:
            List of grants extracted from this website
        """
        soup = self._get_soup(site.url, params=site.params or None)
        grants = []

        # Try to find grant listing containers
        selectors = site.selectors
        list_selector = selectors.get("grants_list", "article")

        # Try each selector (comma-separated)
        containers = []
        for selector in list_selector.split(","):
            selector = selector.strip()
            if selector:
                found = soup.select(selector)
                if found:
                    containers.extend(found)

        if not containers:
            # Fall back to extracting from the full page
            logger.debug(
                f"No containers found for '{site.name}', "
                f"trying full-page extraction"
            )
            grant = self._extract_single_grant(soup, site)
            if grant:
                grants.append(grant)
            return grants

        # Extract a grant from each container
        for container in containers:
            grant = self._extract_grant_from_container(container, site)
            if grant:
                grants.append(grant)

        return grants

    def _extract_grant_from_container(
        self, container: BeautifulSoup, site: WebsiteSource
    ) -> Optional[Grant]:
        """
        Extract a single grant from an HTML container element.

        Args:
            container: BeautifulSoup element containing grant info
            site: Website source configuration

        Returns:
            Grant object or None if extraction fails
        """
        selectors = site.selectors

        # Extract title
        title_selector = selectors.get("title", "h3, h2")
        title_elem = None
        for sel in title_selector.split(","):
            title_elem = container.select_one(sel.strip())
            if title_elem:
                break
        title = self.extract_text(title_elem)

        if not title or len(title) < 5:
            return None

        # Extract link
        link_selector = selectors.get("link", "a")
        link_elem = container.select_one(link_selector)
        url = self.extract_url(link_elem, site.url) if link_elem else site.url

        # Extract deadline
        deadline_text = ""
        deadline = None
        deadline_selector = selectors.get("deadline", ".deadline")
        for sel in deadline_selector.split(","):
            deadline_elem = container.select_one(sel.strip())
            if deadline_elem:
                deadline_text = self.extract_text(deadline_elem)
                deadline = self._parse_date(deadline_text)
                break

        # Extract amount
        amount_text = ""
        amount_min = 0.0
        amount_max = 0.0
        amount_selector = selectors.get("amount", ".amount")
        for sel in amount_selector.split(","):
            amount_elem = container.select_one(sel.strip())
            if amount_elem:
                amount_text = self.extract_text(amount_elem)
                amount_min, amount_max = self._parse_amount_values(
                    amount_text
                )
                break

        # Extract description
        description = ""
        desc_selector = selectors.get("description", "p")
        for sel in desc_selector.split(","):
            desc_elem = container.select_one(sel.strip())
            if desc_elem:
                description = self.extract_text(desc_elem)
                break

        # Determine status
        status = GrantStatus.UNKNOWN
        if deadline and deadline >= date.today():
            status = GrantStatus.OPEN
        elif deadline and deadline < date.today():
            status = GrantStatus.CLOSED

        return Grant(
            name=title[:200],
            source=f"website_{site.name.lower().replace(' ', '_')}",
            url=url,
            amount_min=amount_min,
            amount_max=amount_max,
            amount_text=amount_text,
            deadline=deadline,
            deadline_text=deadline_text,
            status=status,
            grant_type=self._infer_type(site.name, title),
            description=description[:500],
            focus_areas=[],
            geographic_scope=self._infer_geography(site.name),
            eligibility_notes="",
            how_to_apply=f"Visit {url}",
            funder=site.name,
        )

    def _extract_single_grant(
        self, soup: BeautifulSoup, site: WebsiteSource
    ) -> Optional[Grant]:
        """
        Extract grant info from a page that is itself about a single grant.

        Used as fallback when no listing containers are found.
        """
        title = self.extract_text(soup.find("h1"))
        if not title:
            title = self.extract_text(soup.find("title"))
        if not title:
            return None

        # Get page description
        description = ""
        meta_desc = soup.find("meta", attrs={"name": "description"})
        if meta_desc:
            description = meta_desc.get("content", "")
        if not description:
            first_p = soup.find("p")
            if first_p:
                description = self.extract_text(first_p)

        return Grant(
            name=title[:200],
            source=f"website_{site.name.lower().replace(' ', '_')}",
            url=site.url,
            description=description[:500],
            grant_type=self._infer_type(site.name, title),
            geographic_scope=self._infer_geography(site.name),
            funder=site.name,
            status=GrantStatus.UNKNOWN,
            how_to_apply=f"Visit {site.url}",
        )

    def _parse_date(self, text: str) -> Optional[date]:
        """Parse a date from text."""
        if not text:
            return None

        formats = [
            "%B %d, %Y",   # March 15, 2026
            "%b %d, %Y",   # Mar 15, 2026
            "%m/%d/%Y",    # 03/15/2026
            "%Y-%m-%d",    # 2026-03-15
            "%B %d %Y",    # March 15 2026
            "%b %d %Y",    # Mar 15 2026
        ]

        # Try to find a date pattern in the text
        date_match = re.search(
            r'(\w+\s+\d{1,2},?\s*\d{4}|\d{1,2}/\d{1,2}/\d{4}|\d{4}-\d{2}-\d{2})',
            text,
        )
        if date_match:
            date_str = date_match.group(1)
            for fmt in formats:
                try:
                    return datetime.strptime(date_str.strip(), fmt).date()
                except ValueError:
                    continue

        return None

    def _parse_amount_values(self, text: str) -> tuple[float, float]:
        """Parse min/max amounts from text."""
        if not text:
            return 0.0, 0.0

        amounts = re.findall(r'\$[\d,]+(?:\.\d{2})?', text)
        parsed = []
        for amt in amounts:
            try:
                parsed.append(float(amt.replace('$', '').replace(',', '')))
            except ValueError:
                continue

        if len(parsed) >= 2:
            return min(parsed), max(parsed)
        elif parsed:
            return parsed[0], parsed[0]

        return 0.0, 0.0

    def _infer_type(self, site_name: str, title: str) -> GrantType:
        """Infer grant type from the source website name."""
        name_lower = site_name.lower()

        if "community foundation" in name_lower:
            return GrantType.COMMUNITY_GRANT
        if "grants portal" in name_lower or "ca grants" in name_lower:
            return GrantType.STATE_GRANT
        if any(x in name_lower for x in ["socalgas", "edison", "power"]):
            return GrantType.CORPORATE_GRANT
        if "sprouts" in name_lower:
            return GrantType.CORPORATE_GRANT
        if "foundation" in name_lower:
            return GrantType.FOUNDATION_GRANT

        return GrantType.UNKNOWN

    def _infer_geography(self, site_name: str) -> str:
        """Infer geographic scope from the source website."""
        name_lower = site_name.lower()

        if "orange county" in name_lower or "occf" in name_lower:
            return "Orange County, CA"
        if "socalgas" in name_lower or "socal" in name_lower:
            return "Southern California"
        if "ca grants" in name_lower or "california" in name_lower:
            return "California"
        if "clean power" in name_lower:
            return "Southern California"

        return "National (U.S.)"
