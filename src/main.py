"""
Main orchestrator for the Mini-Grant Finder pipeline.

Ties together the full Find -> Score -> Store workflow:
1. FIND:  Load existing research data + run scrapers
2. SCORE: TF-IDF relevance scoring + program matching
3. STORE: Save to Google Sheets + local JSON

Can be run as a daily cron job via GitHub Actions or manually
from the command line.
"""

import logging
import sys
from datetime import datetime
from pathlib import Path
from typing import Optional

# Add project root to path
PROJECT_ROOT = Path(__file__).parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.loaders.csv_loader import load_all_research_data
from src.models.grant import Grant
from src.models.source import SourceRegistry
from src.pipeline.processor import GrantProcessor
from src.scoring.program_matcher import ProgramMatcher
from src.scoring.relevance import RelevanceScorer
from src.scrapers.grants_gov import GrantsGovScraper
from src.scrapers.keyword_search import KeywordSearcher
from src.scrapers.rss_monitor import RSSMonitor
from src.scrapers.website_scraper import WebsiteScraper
from src.storage.local import LocalStorage
from src.storage.sheets import SheetsStorage

logger = logging.getLogger(__name__)

CONFIG_DIR = PROJECT_ROOT / "config"


def setup_logging(level: str = "INFO") -> None:
    """Configure logging for the pipeline."""
    log_level = getattr(logging, level.upper(), logging.INFO)
    logging.basicConfig(
        level=log_level,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
        handlers=[
            logging.StreamHandler(sys.stdout),
        ],
    )


def find_grants(
    use_scrapers: bool = True,
    use_research: bool = True,
    scrapers: Optional[list[str]] = None,
) -> list[Grant]:
    """
    Stage 1: FIND grants from all configured sources.

    Args:
        use_scrapers: Whether to run live scrapers
        use_research: Whether to load existing research CSV data
        scrapers: List of specific scrapers to run. None = all.
                  Options: 'grants_gov', 'rss', 'keyword', 'website'

    Returns:
        List of raw Grant objects from all sources
    """
    all_grants = []

    # Load existing research data
    if use_research:
        logger.info("Loading existing research data...")
        research_grants = load_all_research_data()
        all_grants.extend(research_grants)
        logger.info(f"Loaded {len(research_grants)} grants from research CSVs")

    # Run scrapers
    if use_scrapers:
        scraper_list = scrapers or ["grants_gov", "rss", "keyword", "website"]

        # Load source registry from config
        sources_config = str(CONFIG_DIR / "grant_sources.yaml")
        try:
            registry = SourceRegistry.from_yaml(sources_config)
        except Exception as e:
            logger.warning(f"Could not load source config: {e}")
            registry = None

        if "grants_gov" in scraper_list:
            logger.info("Running Grants.gov scraper...")
            config = registry.grants_gov if registry else None
            scraper = GrantsGovScraper(config=config)
            grants = scraper.safe_scrape()
            all_grants.extend(grants)
            logger.info(f"Grants.gov: {len(grants)} grants")

        if "rss" in scraper_list:
            logger.info("Running RSS feed monitor...")
            feeds = registry.rss_feeds if registry else None
            scraper = RSSMonitor(feeds=feeds)
            grants = scraper.safe_scrape()
            all_grants.extend(grants)
            logger.info(f"RSS feeds: {len(grants)} grants")

        if "keyword" in scraper_list:
            logger.info("Running keyword search...")
            config = registry.keyword_search if registry else None
            scraper = KeywordSearcher(config=config)
            grants = scraper.safe_scrape()
            all_grants.extend(grants)
            logger.info(f"Keyword search: {len(grants)} grants")

        if "website" in scraper_list:
            logger.info("Running website scraper...")
            sites = registry.websites if registry else None
            scraper = WebsiteScraper(sites=sites)
            grants = scraper.safe_scrape()
            all_grants.extend(grants)
            logger.info(f"Website scraper: {len(grants)} grants")

    logger.info(f"FIND stage complete: {len(all_grants)} total raw grants")
    return all_grants


def score_grants(grants: list[Grant]) -> list[Grant]:
    """
    Stage 2: SCORE grants for relevance and match to programs.

    Runs TF-IDF relevance scoring and keyword-based program matching
    on the processed grant data.

    Args:
        grants: Processed grant objects

    Returns:
        Scored and sorted grants
    """
    logger.info(f"Scoring {len(grants)} grants...")

    # TF-IDF relevance scoring
    try:
        scorer = RelevanceScorer()
        grants = scorer.score_grants(grants)
        logger.info("TF-IDF relevance scoring complete")
    except Exception as e:
        logger.error(f"Relevance scoring failed: {e}")

    # Keyword-based program matching
    try:
        matcher = ProgramMatcher()
        grants = matcher.match_grants(grants)
        logger.info("Program matching complete")
    except Exception as e:
        logger.error(f"Program matching failed: {e}")

    # Log scoring summary
    if grants:
        scores = [g.relevance_score for g in grants]
        logger.info(
            f"SCORE stage complete: "
            f"min={min(scores):.0f}, max={max(scores):.0f}, "
            f"avg={sum(scores)/len(scores):.0f}, "
            f"matched={sum(1 for g in grants if g.matched_programs)}"
        )

    return grants


def store_grants(grants: list[Grant], tag: str = "") -> dict:
    """
    Stage 3: STORE scored grants to all configured backends.

    Saves to local JSON (always) and Google Sheets (if configured).

    Args:
        grants: Scored grant objects to store
        tag: Optional tag for the snapshot filename

    Returns:
        Dict with storage results
    """
    results = {}

    # Always save locally
    local = LocalStorage()
    filepath = local.save_grants(grants, tag=tag)
    results["local"] = {"success": True, "path": filepath}
    logger.info(f"Saved to local: {filepath}")

    # Try Google Sheets
    sheets = SheetsStorage()
    if sheets.is_available:
        success = sheets.save_grants(grants)
        results["sheets"] = {"success": success}
        if success:
            logger.info("Saved to Google Sheets")
    else:
        results["sheets"] = {"success": False, "reason": "not_configured"}
        logger.info("Google Sheets not configured, skipping")

    return results


def run_pipeline(
    use_scrapers: bool = True,
    use_research: bool = True,
    scrapers: Optional[list[str]] = None,
    exclude_expired: bool = True,
    min_amount: float = 0,
    tag: str = "",
    log_level: str = "INFO",
) -> dict:
    """
    Run the full Find -> Process -> Score -> Store pipeline.

    This is the main entry point for the Mini-Grant Finder.

    Args:
        use_scrapers: Whether to run live scrapers
        use_research: Whether to load existing research data
        scrapers: Specific scrapers to run (None = all)
        exclude_expired: Whether to filter expired grants
        min_amount: Minimum grant amount to include
        tag: Optional tag for the output filename
        log_level: Logging level (DEBUG, INFO, WARNING, ERROR)

    Returns:
        Dict with pipeline results and statistics
    """
    setup_logging(log_level)
    start_time = datetime.now()

    logger.info("=" * 60)
    logger.info("Mini-Grant Finder Pipeline")
    logger.info(f"Delta Rising Foundation — {start_time.strftime('%Y-%m-%d %H:%M')}")
    logger.info("=" * 60)

    # Stage 1: FIND
    logger.info("\n--- Stage 1: FIND ---")
    raw_grants = find_grants(
        use_scrapers=use_scrapers,
        use_research=use_research,
        scrapers=scrapers,
    )

    # Process: Clean, normalize, deduplicate
    logger.info("\n--- Processing ---")
    processor = GrantProcessor(
        exclude_expired=exclude_expired,
        min_amount=min_amount,
    )
    processed_grants = processor.process(raw_grants)

    # Stage 2: SCORE
    logger.info("\n--- Stage 2: SCORE ---")
    scored_grants = score_grants(processed_grants)

    # Stage 3: STORE
    logger.info("\n--- Stage 3: STORE ---")
    storage_results = store_grants(scored_grants, tag=tag)

    # Summary
    elapsed = (datetime.now() - start_time).total_seconds()

    results = {
        "timestamp": start_time.isoformat(),
        "elapsed_seconds": elapsed,
        "raw_count": len(raw_grants),
        "processed_count": len(processed_grants),
        "scored_count": len(scored_grants),
        "processing_stats": processor.stats,
        "storage": storage_results,
        "top_grants": [
            {
                "name": g.name,
                "score": g.relevance_score,
                "programs": g.matched_programs,
                "deadline": str(g.deadline) if g.deadline else "N/A",
                "amount": g.amount_display,
            }
            for g in scored_grants[:10]
        ],
    }

    logger.info("\n" + "=" * 60)
    logger.info("Pipeline complete!")
    logger.info(f"  Raw grants found:  {len(raw_grants)}")
    logger.info(f"  After processing:  {len(processed_grants)}")
    logger.info(f"  Scored & stored:   {len(scored_grants)}")
    logger.info(f"  Time elapsed:      {elapsed:.1f}s")
    logger.info("=" * 60)

    return results


if __name__ == "__main__":
    # Quick run with research data only (no live scraping)
    results = run_pipeline(
        use_scrapers=False,
        use_research=True,
        tag="manual",
    )
