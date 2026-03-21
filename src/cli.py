"""
Command-line interface for the Mini-Grant Finder.

Provides argparse-based CLI for running the grant discovery pipeline
manually, with options to select specific scrapers, set filters,
and export results.

Usage:
    python -m src.cli                        # Run full pipeline
    python -m src.cli --scrapers rss         # Only RSS feeds
    python -m src.cli --no-scrape            # Research data only
    python -m src.cli --export csv           # Export to CSV
    python -m src.cli --min-score 50         # Only high-relevance
"""

import argparse
import sys
from pathlib import Path

# Add project root to path
PROJECT_ROOT = Path(__file__).parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


def create_parser() -> argparse.ArgumentParser:
    """Build the argument parser."""
    parser = argparse.ArgumentParser(
        prog="mini-grant-finder",
        description=(
            "Mini-Grant Finder — Automated grant discovery for "
            "Delta Rising Foundation"
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python -m src.cli                          Run full pipeline (research + scrapers)
  python -m src.cli --no-scrape              Load research data only (no live scraping)
  python -m src.cli --scrapers rss keyword   Run only RSS and keyword scrapers
  python -m src.cli --min-score 40           Show only grants scoring 40+
  python -m src.cli --export csv             Export results to CSV
  python -m src.cli --list-sources           Show configured data sources
  python -m src.cli --stats                  Show pipeline statistics
        """,
    )

    # Pipeline mode
    mode_group = parser.add_argument_group("Pipeline options")
    mode_group.add_argument(
        "--no-scrape",
        action="store_true",
        help="Skip live scrapers, use research data only",
    )
    mode_group.add_argument(
        "--no-research",
        action="store_true",
        help="Skip research CSV data, use scrapers only",
    )
    mode_group.add_argument(
        "--scrapers",
        nargs="+",
        choices=["grants_gov", "rss", "keyword", "website"],
        help="Specific scrapers to run (default: all)",
    )

    # Filtering
    filter_group = parser.add_argument_group("Filtering")
    filter_group.add_argument(
        "--min-score",
        type=float,
        default=0,
        help="Minimum relevance score to include (0-100)",
    )
    filter_group.add_argument(
        "--min-amount",
        type=float,
        default=0,
        help="Minimum grant amount in USD",
    )
    filter_group.add_argument(
        "--include-expired",
        action="store_true",
        help="Include grants past their deadline",
    )
    filter_group.add_argument(
        "--program",
        choices=[
            "ai_climate_tools",
            "resilience_nursery",
            "more_shade",
            "cbecn",
        ],
        help="Filter by Delta program",
    )

    # Output
    output_group = parser.add_argument_group("Output")
    output_group.add_argument(
        "--export",
        choices=["csv", "json"],
        help="Export results to file format",
    )
    output_group.add_argument(
        "--output",
        type=str,
        help="Output file path (default: auto-generated in data/processed/)",
    )
    output_group.add_argument(
        "--top",
        type=int,
        default=0,
        help="Show only top N grants by relevance",
    )
    output_group.add_argument(
        "--tag",
        type=str,
        default="",
        help="Tag for the output filename (e.g., 'weekly', 'manual')",
    )

    # Info commands
    info_group = parser.add_argument_group("Information")
    info_group.add_argument(
        "--list-sources",
        action="store_true",
        help="List all configured data sources and exit",
    )
    info_group.add_argument(
        "--stats",
        action="store_true",
        help="Show statistics from the last pipeline run",
    )
    info_group.add_argument(
        "--snapshots",
        action="store_true",
        help="List available data snapshots",
    )

    # Verbosity
    parser.add_argument(
        "-v", "--verbose",
        action="store_true",
        help="Enable verbose (DEBUG) logging",
    )
    parser.add_argument(
        "-q", "--quiet",
        action="store_true",
        help="Suppress non-error output",
    )

    return parser


def cmd_list_sources():
    """List all configured data sources."""
    from src.models.source import SourceRegistry

    config_path = str(PROJECT_ROOT / "config" / "grant_sources.yaml")
    try:
        registry = SourceRegistry.from_yaml(config_path)
    except Exception as e:
        print(f"Error loading sources config: {e}")
        return

    print("\nConfigured Data Sources")
    print("=" * 50)

    if registry.grants_gov:
        print(f"\n  Grants.gov API")
        print(f"    Categories: {', '.join(registry.grants_gov.categories)}")
        print(f"    Agencies: {', '.join(registry.grants_gov.agency_codes)}")
        print(f"    Schedule: {registry.grants_gov.schedule}")

    if registry.rss_feeds:
        print(f"\n  RSS Feeds ({len(registry.rss_feeds)} configured)")
        for feed in registry.rss_feeds:
            print(f"    - {feed.name}")
            print(f"      {feed.url}")

    if registry.websites:
        print(f"\n  Website Scrapers ({len(registry.websites)} configured)")
        for site in registry.websites:
            print(f"    - {site.name}")
            print(f"      {site.url}")

    if registry.keyword_search:
        ks = registry.keyword_search
        print(f"\n  Keyword Search ({ks.engine})")
        print(f"    Templates: {len(ks.query_templates)}")
        print(f"    Max results per query: {ks.max_results_per_query}")

    print()


def cmd_snapshots():
    """List available data snapshots."""
    from src.storage.local import LocalStorage

    storage = LocalStorage()
    snapshots = storage.list_snapshots()

    if not snapshots:
        print("No data snapshots found.")
        return

    print("\nData Snapshots")
    print("=" * 50)
    for snap in snapshots:
        size_kb = snap["size_bytes"] / 1024
        print(
            f"  {snap['filename']:<35} "
            f"{snap['grant_count']:>4} grants  "
            f"{size_kb:>6.1f} KB"
        )
    print()


def cmd_run_pipeline(args):
    """Run the main pipeline with CLI arguments."""
    from src.main import run_pipeline

    log_level = "DEBUG" if args.verbose else ("ERROR" if args.quiet else "INFO")

    results = run_pipeline(
        use_scrapers=not args.no_scrape,
        use_research=not args.no_research,
        scrapers=args.scrapers,
        exclude_expired=not args.include_expired,
        min_amount=args.min_amount,
        tag=args.tag or "cli",
        log_level=log_level,
    )

    # Post-pipeline: apply additional filters
    scored_count = results.get("scored_count", 0)

    if args.min_score > 0 or args.program or args.top or args.export:
        from src.storage.local import LocalStorage

        storage = LocalStorage()
        grants = storage.load_latest()

        # Filter by minimum score
        if args.min_score > 0:
            grants = [g for g in grants if g.relevance_score >= args.min_score]

        # Filter by program
        if args.program:
            grants = [g for g in grants if args.program in g.matched_programs]

        # Limit to top N
        if args.top > 0:
            grants = grants[:args.top]

        # Export
        if args.export == "csv":
            filepath = args.output or None
            path = storage.export_csv(grants, filepath)
            print(f"\nExported {len(grants)} grants to: {path}")

        elif args.export == "json":
            filepath = args.output or None
            if filepath:
                path = storage.save_grants(grants, tag="export")
            print(f"\nExported {len(grants)} grants to JSON")

        # Print summary table
        if not args.quiet:
            print(f"\n{'='*70}")
            print(f"{'Name':<40} {'Score':>6} {'Deadline':<12} {'Amount':<15}")
            print(f"{'-'*40} {'-'*6} {'-'*12} {'-'*15}")
            for g in grants[:20]:
                deadline = (
                    g.deadline.strftime("%b %d %Y") if g.deadline
                    else g.deadline_text[:12]
                )
                print(
                    f"{g.name[:39]:<40} "
                    f"{g.relevance_score:>5.0f}  "
                    f"{deadline:<12} "
                    f"{g.amount_display:<15}"
                )
            if len(grants) > 20:
                print(f"  ... and {len(grants) - 20} more")
            print(f"{'='*70}")


def main():
    """CLI entry point."""
    parser = create_parser()
    args = parser.parse_args()

    if args.list_sources:
        cmd_list_sources()
        return

    if args.snapshots:
        cmd_snapshots()
        return

    cmd_run_pipeline(args)


if __name__ == "__main__":
    main()
