"""
Data source models for the Mini-Grant Finder.

Defines configuration models for the various grant data sources
(APIs, RSS feeds, websites, keyword searches) used by the scrapers.
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Optional

import yaml


class SourceType(Enum):
    """Type of grant data source."""
    API = "api"
    RSS = "rss"
    HTML = "html"
    KEYWORD_SEARCH = "keyword_search"


@dataclass
class ScrapingConfig:
    """Global scraping configuration settings."""
    user_agent: str = "DeltaRisingGrantFinder/1.0 (nonprofit research)"
    request_delay_seconds: int = 2
    max_retries: int = 3
    timeout_seconds: int = 30
    respect_robots_txt: bool = True


@dataclass
class RSSSource:
    """Configuration for an RSS feed source."""
    name: str
    url: str
    schedule: str = "daily"
    enabled: bool = True

    def __repr__(self) -> str:
        return f"RSSSource(name='{self.name}', url='{self.url}')"


@dataclass
class WebsiteSource:
    """Configuration for a website scraping source."""
    name: str
    url: str
    selectors: dict = field(default_factory=dict)
    params: dict = field(default_factory=dict)
    schedule: str = "weekly"
    enabled: bool = True
    requires_javascript: bool = False

    def __repr__(self) -> str:
        return f"WebsiteSource(name='{self.name}', url='{self.url}')"


@dataclass
class KeywordSearchConfig:
    """Configuration for keyword-based search."""
    engine: str = "duckduckgo"
    max_results_per_query: int = 15
    cooldown_seconds: int = 3
    query_templates: list[str] = field(default_factory=list)
    schedule: str = "weekly"

    def __repr__(self) -> str:
        return f"KeywordSearchConfig(engine='{self.engine}', templates={len(self.query_templates)})"


@dataclass
class GrantsGovConfig:
    """Configuration for the Grants.gov API source."""
    name: str = "Grants.gov"
    base_url: str = "https://www.grants.gov"
    xml_feed: str = "https://www.grants.gov/xml/XMLExtract.zip"
    search_url: str = "https://www.grants.gov/grantsws/rest/opportunities/search/"
    categories: list[str] = field(default_factory=list)
    eligible_types: list[str] = field(default_factory=list)
    agency_codes: list[str] = field(default_factory=list)
    max_results: int = 100
    schedule: str = "daily"

    def __repr__(self) -> str:
        return f"GrantsGovConfig(categories={len(self.categories)}, agencies={len(self.agency_codes)})"


@dataclass
class SourceRegistry:
    """
    Registry holding all configured grant data sources.

    Loads from config/grant_sources.yaml and provides access to
    all source configurations used by the scrapers.
    """
    grants_gov: Optional[GrantsGovConfig] = None
    rss_feeds: list[RSSSource] = field(default_factory=list)
    websites: list[WebsiteSource] = field(default_factory=list)
    keyword_search: Optional[KeywordSearchConfig] = None
    scraping_config: ScrapingConfig = field(default_factory=ScrapingConfig)

    @classmethod
    def from_yaml(cls, filepath: str) -> "SourceRegistry":
        """Load source registry from a YAML configuration file."""
        with open(filepath, "r") as f:
            config = yaml.safe_load(f)

        registry = cls()

        # Parse Grants.gov config
        if "grants_gov" in config:
            gg = config["grants_gov"]
            registry.grants_gov = GrantsGovConfig(
                name=gg.get("name", "Grants.gov"),
                base_url=gg.get("base_url", ""),
                xml_feed=gg.get("xml_feed", ""),
                search_url=gg.get("search_url", ""),
                categories=gg.get("categories", []),
                eligible_types=gg.get("eligible_types", []),
                agency_codes=gg.get("agency_codes", []),
                max_results=gg.get("max_results", 100),
                schedule=gg.get("schedule", "daily"),
            )

        # Parse RSS feeds
        if "rss_feeds" in config:
            for feed in config["rss_feeds"]:
                registry.rss_feeds.append(
                    RSSSource(
                        name=feed.get("name", ""),
                        url=feed.get("url", ""),
                        schedule=feed.get("schedule", "daily"),
                    )
                )

        # Parse website scrapers
        if "website_scrapers" in config:
            for site in config["website_scrapers"]:
                registry.websites.append(
                    WebsiteSource(
                        name=site.get("name", ""),
                        url=site.get("url", ""),
                        selectors=site.get("selectors", {}),
                        params=site.get("params", {}),
                        schedule=site.get("schedule", "weekly"),
                    )
                )

        # Parse keyword search config
        if "keyword_search" in config:
            ks = config["keyword_search"]
            registry.keyword_search = KeywordSearchConfig(
                engine=ks.get("engine", "duckduckgo"),
                max_results_per_query=ks.get("max_results_per_query", 15),
                cooldown_seconds=ks.get("cooldown_seconds", 3),
                query_templates=ks.get("query_templates", []),
                schedule=ks.get("schedule", "weekly"),
            )

        # Parse global scraping config
        if "scraping_config" in config:
            sc = config["scraping_config"]
            registry.scraping_config = ScrapingConfig(
                user_agent=sc.get("user_agent", ""),
                request_delay_seconds=sc.get("request_delay_seconds", 2),
                max_retries=sc.get("max_retries", 3),
                timeout_seconds=sc.get("timeout_seconds", 30),
                respect_robots_txt=sc.get("respect_robots_txt", True),
            )

        return registry

    @property
    def all_source_names(self) -> list[str]:
        """Get names of all configured sources."""
        names = []
        if self.grants_gov:
            names.append(self.grants_gov.name)
        names.extend(feed.name for feed in self.rss_feeds)
        names.extend(site.name for site in self.websites)
        if self.keyword_search:
            names.append(f"Keyword Search ({self.keyword_search.engine})")
        return names

    def __repr__(self) -> str:
        return (
            f"SourceRegistry("
            f"grants_gov={'yes' if self.grants_gov else 'no'}, "
            f"rss={len(self.rss_feeds)}, "
            f"websites={len(self.websites)}, "
            f"keyword_search={'yes' if self.keyword_search else 'no'})"
        )
