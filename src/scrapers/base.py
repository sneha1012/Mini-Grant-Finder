"""
Base scraper class with common utilities for all grant scrapers.

Provides rate limiting, retry logic, error handling, request management,
and HTML parsing utilities shared across all scraper implementations.
"""

import logging
import time
from abc import ABC, abstractmethod
from typing import Optional

import requests
from bs4 import BeautifulSoup

from src.models.grant import Grant
from src.models.source import ScrapingConfig

logger = logging.getLogger(__name__)


class ScraperError(Exception):
    """Custom exception for scraper failures."""
    pass


class BaseScraper(ABC):
    """
    Abstract base class for all grant scrapers.

    Provides:
    - HTTP request management with retries and timeouts
    - Rate limiting to be polite to source websites
    - HTML parsing with BeautifulSoup
    - Consistent error handling and logging
    - Common text extraction utilities

    Subclasses must implement:
    - scrape() -> list[Grant]: The main scraping logic
    - source_name property: Name of this data source
    """

    def __init__(self, config: Optional[ScrapingConfig] = None):
        """
        Initialize the base scraper.

        Args:
            config: Scraping configuration (rate limits, user agent, etc.)
                    Uses defaults if not provided.
        """
        self.config = config or ScrapingConfig()
        self._session = requests.Session()
        self._session.headers.update({
            "User-Agent": self.config.user_agent,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.5",
        })
        self._last_request_time: float = 0.0
        self._request_count: int = 0

    @property
    @abstractmethod
    def source_name(self) -> str:
        """Name of this data source for logging and grant attribution."""
        pass

    @abstractmethod
    def scrape(self) -> list[Grant]:
        """
        Execute the scraping logic and return discovered grants.

        Returns:
            List of Grant objects found by this scraper
        """
        pass

    def safe_scrape(self) -> list[Grant]:
        """
        Run scrape() with error handling — never raises exceptions.

        Returns an empty list if scraping fails, so the pipeline
        continues even if individual sources are unavailable.
        """
        try:
            logger.info(f"Starting scrape: {self.source_name}")
            grants = self.scrape()
            logger.info(f"Completed {self.source_name}: found {len(grants)} grants")
            return grants
        except ScraperError as e:
            logger.warning(f"Scraper error ({self.source_name}): {e}")
            return []
        except requests.RequestException as e:
            logger.warning(f"Network error ({self.source_name}): {e}")
            return []
        except Exception as e:
            logger.error(f"Unexpected error ({self.source_name}): {e}", exc_info=True)
            return []

    def _get(self, url: str, params: Optional[dict] = None) -> requests.Response:
        """
        Make a rate-limited GET request with retries.

        Args:
            url: URL to request
            params: Optional query parameters

        Returns:
            Response object

        Raises:
            ScraperError: If all retries are exhausted
        """
        self._rate_limit()

        last_error = None
        for attempt in range(1, self.config.max_retries + 1):
            try:
                response = self._session.get(
                    url,
                    params=params,
                    timeout=self.config.timeout_seconds,
                )
                response.raise_for_status()
                self._request_count += 1
                return response
            except requests.RequestException as e:
                last_error = e
                if attempt < self.config.max_retries:
                    wait = attempt * 2  # Exponential-ish backoff
                    logger.debug(
                        f"Retry {attempt}/{self.config.max_retries} for {url} "
                        f"(waiting {wait}s): {e}"
                    )
                    time.sleep(wait)

        raise ScraperError(
            f"Failed after {self.config.max_retries} attempts for {url}: {last_error}"
        )

    def _get_soup(self, url: str, params: Optional[dict] = None) -> BeautifulSoup:
        """
        Fetch a URL and parse it with BeautifulSoup.

        Args:
            url: URL to fetch and parse
            params: Optional query parameters

        Returns:
            BeautifulSoup object for HTML parsing
        """
        response = self._get(url, params)
        return BeautifulSoup(response.content, "lxml")

    def _rate_limit(self) -> None:
        """Enforce rate limiting between requests."""
        if self._last_request_time > 0:
            elapsed = time.time() - self._last_request_time
            if elapsed < self.config.request_delay_seconds:
                sleep_time = self.config.request_delay_seconds - elapsed
                time.sleep(sleep_time)
        self._last_request_time = time.time()

    @staticmethod
    def extract_text(element, default: str = "") -> str:
        """
        Safely extract text from a BeautifulSoup element.

        Args:
            element: BeautifulSoup Tag or None
            default: Default value if element is None

        Returns:
            Cleaned text content
        """
        if element is None:
            return default
        text = element.get_text(strip=True)
        return text if text else default

    @staticmethod
    def extract_url(element, base_url: str = "") -> str:
        """
        Extract href URL from a BeautifulSoup link element.

        Args:
            element: BeautifulSoup Tag (expected to be an <a> tag)
            base_url: Base URL for resolving relative links

        Returns:
            Absolute URL string
        """
        if element is None:
            return ""
        href = element.get("href", "")
        if not href:
            return ""
        if href.startswith("http"):
            return href
        if href.startswith("/") and base_url:
            return base_url.rstrip("/") + href
        return href

    @staticmethod
    def clean_amount_text(text: str) -> str:
        """Clean and normalize amount text from HTML."""
        if not text:
            return ""
        # Remove extra whitespace
        import re
        text = re.sub(r'\s+', ' ', text).strip()
        return text

    def close(self) -> None:
        """Close the HTTP session."""
        self._session.close()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()
        return False

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}(source='{self.source_name}')"
