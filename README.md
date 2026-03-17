# Delta Rising Foundation — Grant Finder Automation

## Project Overview

An automated grant discovery and dashboard system for **Delta Rising Foundation** (EIN: 84-2889631, Garden Grove, CA). The goal is to replace the current manual Google-search-based process with an automated pipeline that finds, filters, and categorizes mini-grants relevant to Delta's mission.

## Delta's Mission & Programs (for grant matching)

**Mission:** Accelerates science-based systemic solutions and evolves the art of sustainable culture.

**Vision:** An antiracist world of circular economies with minimized externalities and optimized carbon footprints where historically underrepresented groups have equal voices.

### Core Programs (grant matching categories)
| Program | Focus Area | Grant Keywords |
|---------|-----------|---------------|
| AI Climate Tools | Software for MRV of nature-based carbon markets | climate tech, carbon markets, MRV, AI/ML |
| Resilience Nursery | Native, drought-resistant, pollinator plants + education | native plants, urban greening, food security, pollinator habitat |
| More Shade for More People | Shade structures for urban resilience & health | urban resilience, heat island, community health, infrastructure |
| Community Biodiversity Energy Carbon Network | Indigenous peoples, smallholder farmers, local carbon projects | biodiversity, indigenous rights, carbon credits, agroforestry |

### Cross-cutting themes
- Antiracism / racial equity
- Environmental justice
- Circular economy
- Community empowerment
- Climate adaptation & resilience

## Folder Structure

```
grant-finder-automation/
├── README.md                  # This file
├── requirements.txt           # Python dependencies
├── config/
│   ├── grant_sources.yaml     # URLs and sources to scrape
│   ├── keywords.yaml          # Search terms per program area
│   └── delta_profile.yaml     # Organization profile for matching
├── scrapers/
│   ├── grants_gov.py          # Grants.gov scraper
│   ├── foundation_scraper.py  # Foundation/private grant scraper
│   └── rss_monitor.py         # RSS feed monitor for grant announcements
├── data/
│   ├── raw/                   # Raw scraped data
│   └── processed/             # Cleaned, filtered, categorized grants
├── dashboard/
│   └── app.py                 # Streamlit dashboard (internal, not public)
├── notebooks/
│   └── exploration.ipynb      # Research & prototyping notebooks
├── research/
│   ├── mini_grants_list.md    # Curated list of relevant mini-grants
│   ├── automation_approaches.md # Comparison of automation strategies
│   └── grant_sources.md       # Free grant databases & sources
└── docs/
    └── architecture.md        # System design & workflow docs
```

## Quick Start

```bash
pip install -r requirements.txt
# Run the dashboard
streamlit run dashboard/app.py
```

## Automation Approach (Budget-Friendly)

Since Delta is a nonprofit, we prioritize **free and open-source tools**:

1. **Web Scraping** — Python + BeautifulSoup/Selenium (free)
2. **Data Sources** — Grants.gov, Grantseeker.io, Candid, Philanthropy News Digest (all free tiers)
3. **NLP Matching** — Sentence-transformers or spaCy (free, local models)
4. **Dashboard** — Streamlit (free for internal use)
5. **Scheduling** — GitHub Actions free tier or cron jobs
6. **Notifications** — Email via SMTP or Google Sheets API (free)

See `research/automation_approaches.md` for the full comparison.
