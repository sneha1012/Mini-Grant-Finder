# Contributing to Mini-Grant Finder

Thank you for your interest in contributing to the Mini-Grant Finder! This project helps Delta Rising Foundation discover grant opportunities automatically.

## Getting Started

1. Fork the repository
2. Clone your fork: `git clone https://github.com/YOUR_USERNAME/Mini-Grant-Finder.git`
3. Install dependencies: `pip install -r requirements.txt`
4. Install dev tools: `pip install -e ".[dev]"`
5. Run the tests: `pytest`

## Development Workflow

1. Create a branch: `git checkout -b feature/your-feature`
2. Make your changes
3. Run tests: `pytest`
4. Run linter: `ruff check src/ dashboard/ tests/`
5. Commit with a clear message
6. Push and open a pull request

## Project Structure

- `src/scrapers/` — Grant data source scrapers
- `src/scoring/` — TF-IDF and keyword matching
- `src/pipeline/` — Data processing and deduplication
- `src/storage/` — Google Sheets and local JSON backends
- `dashboard/` — Streamlit web dashboard
- `tests/` — pytest test suite
- `config/` — YAML configuration files

## Adding a New Scraper

1. Create a new file in `src/scrapers/`
2. Extend `BaseScraper` from `src/scrapers/base.py`
3. Implement `scrape()` and `source_name`
4. Add the scraper to `src/main.py` find_grants()
5. Add configuration to `config/grant_sources.yaml`
6. Write tests in `tests/`

## Adding a New Data Source (RSS Feed)

1. Add the feed URL to `config/grant_sources.yaml` under `rss_feeds`
2. The RSS monitor will automatically pick it up on the next run

## Code Style

- Python 3.10+ type hints
- Docstrings on all public functions and classes
- Max line length: 88 characters (ruff default)
- Sort imports with `ruff check --select I`

## Important Notes

- This is a **$0 budget** project — no paid APIs
- All scrapers must fail gracefully (use `safe_scrape()`)
- Respect rate limits and robots.txt on source websites
- Never commit credentials or API keys
