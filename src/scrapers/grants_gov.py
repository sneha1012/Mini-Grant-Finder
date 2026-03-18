"""
Grants.gov scraper for federal grant opportunities.

Uses the Grants.gov free XML/REST API to search for grants relevant
to Delta Rising Foundation's programs (environment, climate, community
development, agriculture, science/technology).

No API key required — this is a free public API.
"""

import logging
from datetime import date, datetime
from typing import Optional
from xml.etree import ElementTree

from src.models.grant import Grant, GrantStatus, GrantType
from src.models.source import GrantsGovConfig, ScrapingConfig
from src.scrapers.base import BaseScraper, ScraperError

logger = logging.getLogger(__name__)

# Grants.gov category code mappings
CATEGORY_MAP = {
    "environment": "ENV",
    "natural_resources": "NR",
    "community_development": "CD",
    "agriculture": "AG",
    "science_technology": "ST",
    "education": "ED",
    "health": "HL",
}

# Grants.gov opportunity status codes
STATUS_MAP = {
    "posted": GrantStatus.OPEN,
    "forecasted": GrantStatus.UPCOMING,
    "closed": GrantStatus.CLOSED,
    "archived": GrantStatus.CLOSED,
}


class GrantsGovScraper(BaseScraper):
    """
    Scraper for the Grants.gov API.

    Uses the REST search endpoint to find relevant federal grants
    by category, agency, and keyword. Parses XML responses into
    Grant objects.

    The Grants.gov API is free and does not require authentication.
    Rate limiting is applied out of courtesy.
    """

    def __init__(
        self,
        config: Optional[GrantsGovConfig] = None,
        scraping_config: Optional[ScrapingConfig] = None,
    ):
        """
        Initialize the Grants.gov scraper.

        Args:
            config: Grants.gov-specific configuration
            scraping_config: General scraping settings
        """
        super().__init__(scraping_config)
        self.gg_config = config or GrantsGovConfig(
            categories=["environment", "natural_resources", "community_development"],
            agency_codes=["EPA", "USDA-NIFA", "DOI", "DOE"],
            max_results=100,
        )

    @property
    def source_name(self) -> str:
        return "Grants.gov"

    def scrape(self) -> list[Grant]:
        """
        Search Grants.gov for relevant grant opportunities.

        Searches by category and by keyword, then deduplicates results.

        Returns:
            List of Grant objects from Grants.gov
        """
        all_grants = []

        # Search by category
        for category in self.gg_config.categories:
            category_code = CATEGORY_MAP.get(category, category.upper())
            try:
                grants = self._search_by_category(category_code)
                all_grants.extend(grants)
                logger.info(
                    f"Category '{category}' ({category_code}): "
                    f"found {len(grants)} grants"
                )
            except ScraperError as e:
                logger.warning(f"Failed category search '{category}': {e}")

        # Search by keywords related to Delta's mission
        keywords = [
            "climate adaptation",
            "environmental justice",
            "carbon market",
            "urban forestry",
            "native plants",
            "community resilience",
            "biodiversity conservation",
        ]
        for keyword in keywords:
            try:
                grants = self._search_by_keyword(keyword)
                all_grants.extend(grants)
                logger.info(f"Keyword '{keyword}': found {len(grants)} grants")
            except ScraperError as e:
                logger.warning(f"Failed keyword search '{keyword}': {e}")

        # Deduplicate by opportunity ID
        seen_ids = set()
        unique = []
        for grant in all_grants:
            if grant.grant_id not in seen_ids:
                seen_ids.add(grant.grant_id)
                unique.append(grant)

        return unique

    def _search_by_category(self, category_code: str) -> list[Grant]:
        """Search Grants.gov by funding category code."""
        params = {
            "keyword": "",
            "oppNum": "",
            "cfda": "",
            "oppStatuses": "posted|forecasted",
            "fundingCategories": category_code,
            "agencies": "|".join(self.gg_config.agency_codes),
            "sortBy": "openDate|desc",
            "rows": min(self.gg_config.max_results, 25),
            "offset": 0,
        }
        return self._execute_search(params)

    def _search_by_keyword(self, keyword: str) -> list[Grant]:
        """Search Grants.gov by keyword."""
        params = {
            "keyword": keyword,
            "oppStatuses": "posted|forecasted",
            "agencies": "|".join(self.gg_config.agency_codes),
            "sortBy": "openDate|desc",
            "rows": min(self.gg_config.max_results, 15),
            "offset": 0,
        }
        return self._execute_search(params)

    def _execute_search(self, params: dict) -> list[Grant]:
        """
        Execute a search against the Grants.gov REST API.

        The API returns JSON with opportunity listings. Each listing
        contains basic metadata; full details require a separate call.
        """
        try:
            response = self._get(
                self.gg_config.search_url,
                params=params,
            )

            # The API can return JSON or XML depending on the endpoint
            content_type = response.headers.get("content-type", "")

            if "json" in content_type or "javascript" in content_type:
                return self._parse_json_response(response.json())
            elif "xml" in content_type:
                return self._parse_xml_response(response.text)
            else:
                # Try JSON first, fall back to XML
                try:
                    return self._parse_json_response(response.json())
                except Exception:
                    return self._parse_xml_response(response.text)

        except ScraperError:
            raise
        except Exception as e:
            raise ScraperError(f"Search failed: {e}")

    def _parse_json_response(self, data: dict) -> list[Grant]:
        """Parse JSON response from Grants.gov search API."""
        grants = []
        opportunities = data.get("oppHits", data.get("opportunities", []))

        if isinstance(opportunities, dict):
            opportunities = opportunities.get("oppHit", [])

        if not isinstance(opportunities, list):
            return grants

        for opp in opportunities:
            try:
                grant = self._opportunity_to_grant(opp)
                if grant:
                    grants.append(grant)
            except Exception as e:
                logger.debug(f"Failed to parse opportunity: {e}")

        return grants

    def _parse_xml_response(self, xml_text: str) -> list[Grant]:
        """Parse XML response from Grants.gov."""
        grants = []
        try:
            root = ElementTree.fromstring(xml_text)
        except ElementTree.ParseError as e:
            logger.warning(f"XML parse error: {e}")
            return grants

        # Handle various XML structures from Grants.gov
        for opp in root.iter():
            if opp.tag in ("OpportunitySynopsisDetail_1_0",
                           "OpportunityForecastDetail_1_0",
                           "opportunity"):
                try:
                    grant = self._xml_element_to_grant(opp)
                    if grant:
                        grants.append(grant)
                except Exception as e:
                    logger.debug(f"Failed to parse XML element: {e}")

        return grants

    def _opportunity_to_grant(self, opp: dict) -> Optional[Grant]:
        """Convert a Grants.gov opportunity dict to a Grant object."""
        title = opp.get("title", opp.get("oppTitle", ""))
        if not title:
            return None

        # Parse dates
        close_date = self._parse_gg_date(
            opp.get("closeDate", opp.get("closeDateStr", ""))
        )
        open_date = self._parse_gg_date(
            opp.get("openDate", opp.get("openDateStr", ""))
        )

        # Parse status
        status_str = opp.get("oppStatus", opp.get("status", "")).lower()
        status = STATUS_MAP.get(status_str, GrantStatus.UNKNOWN)

        # Parse amount
        award_floor = float(opp.get("awardFloor", 0) or 0)
        award_ceiling = float(opp.get("awardCeiling", 0) or 0)

        # Build amount text
        if award_ceiling > 0:
            if award_floor > 0:
                amount_text = f"${award_floor:,.0f} - ${award_ceiling:,.0f}"
            else:
                amount_text = f"Up to ${award_ceiling:,.0f}"
        else:
            amount_text = "Varies"

        # Get opportunity number and agency
        opp_number = opp.get("number", opp.get("oppNum", ""))
        agency = opp.get("agency", opp.get("agencyCode", ""))

        # Build description
        description = opp.get("synopsis", opp.get("description", ""))
        if not description:
            description = opp.get("oppTitle", title)

        grant = Grant(
            name=title,
            source="grants_gov",
            url=f"https://www.grants.gov/search-results-detail/{opp_number}"
            if opp_number
            else "https://www.grants.gov",
            amount_min=award_floor,
            amount_max=award_ceiling,
            amount_text=amount_text,
            deadline=close_date,
            deadline_text=opp.get("closeDate", opp.get("closeDateStr", "")),
            status=status,
            grant_type=GrantType.FEDERAL_GRANT,
            description=description[:500] if description else "",
            focus_areas=self._extract_categories(opp),
            geographic_scope="National (U.S.)",
            eligibility_notes=opp.get("eligibleApplicants", ""),
            how_to_apply="Apply at Grants.gov",
            funder=agency,
            grant_id=opp_number if opp_number else "",
        )

        return grant

    def _xml_element_to_grant(self, elem: ElementTree.Element) -> Optional[Grant]:
        """Convert an XML element to a Grant object."""
        title = self._xml_text(elem, "OpportunityTitle") or self._xml_text(
            elem, "title"
        )
        if not title:
            return None

        opp_number = self._xml_text(elem, "OpportunityNumber") or self._xml_text(
            elem, "number"
        )

        close_date = self._parse_gg_date(
            self._xml_text(elem, "CloseDate")
            or self._xml_text(elem, "closeDate")
        )

        award_floor = 0.0
        award_ceiling = 0.0
        try:
            award_ceiling = float(
                self._xml_text(elem, "AwardCeiling") or 0
            )
            award_floor = float(
                self._xml_text(elem, "AwardFloor") or 0
            )
        except (ValueError, TypeError):
            pass

        agency = self._xml_text(elem, "AgencyCode") or self._xml_text(
            elem, "agency"
        )

        description = self._xml_text(elem, "Description") or self._xml_text(
            elem, "synopsis"
        ) or ""

        return Grant(
            name=title,
            source="grants_gov",
            url=f"https://www.grants.gov/search-results-detail/{opp_number}"
            if opp_number
            else "https://www.grants.gov",
            amount_min=award_floor,
            amount_max=award_ceiling,
            amount_text=f"${award_floor:,.0f} - ${award_ceiling:,.0f}"
            if award_ceiling > 0
            else "Varies",
            deadline=close_date,
            status=GrantStatus.OPEN if close_date and close_date >= date.today()
            else GrantStatus.CLOSED,
            grant_type=GrantType.FEDERAL_GRANT,
            description=description[:500],
            geographic_scope="National (U.S.)",
            eligibility_notes=self._xml_text(elem, "EligibleApplicants") or "",
            how_to_apply="Apply at Grants.gov",
            funder=agency or "Federal",
            grant_id=opp_number or "",
        )

    @staticmethod
    def _xml_text(elem: ElementTree.Element, tag: str) -> Optional[str]:
        """Extract text from a child XML element."""
        child = elem.find(tag)
        if child is not None and child.text:
            return child.text.strip()
        return None

    @staticmethod
    def _parse_gg_date(date_str: str) -> Optional[date]:
        """Parse a Grants.gov date string into a date object."""
        if not date_str:
            return None

        formats = [
            "%m/%d/%Y",     # 03/15/2026
            "%Y-%m-%d",     # 2026-03-15
            "%m%d%Y",       # 03152026
            "%b %d, %Y",   # Mar 15, 2026
            "%B %d, %Y",   # March 15, 2026
        ]

        for fmt in formats:
            try:
                return datetime.strptime(date_str.strip(), fmt).date()
            except ValueError:
                continue

        return None

    @staticmethod
    def _extract_categories(opp: dict) -> list[str]:
        """Extract category/focus area tags from an opportunity."""
        categories = []
        cat_str = opp.get("cfdas", opp.get("fundingCategories", ""))
        if isinstance(cat_str, str):
            categories.extend(
                c.strip() for c in cat_str.split(";") if c.strip()
            )
        elif isinstance(cat_str, list):
            categories.extend(str(c) for c in cat_str)
        return categories
