# Mini-Grant Finder

[![Python 3.10+](https://img.shields.io/badge/python-3.10%2B-blue.svg)](https://www.python.org/downloads/)
[![Streamlit](https://img.shields.io/badge/Streamlit-1.29%2B-FF4B4B.svg)](https://streamlit.io)
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)
[![Daily Scrape](https://github.com/sneha1012/Mini-Grant-Finder/actions/workflows/daily_scrape.yml/badge.svg)](https://github.com/sneha1012/Mini-Grant-Finder/actions)

**Automated grant discovery dashboard for [Delta Rising Foundation](https://deltarising.org)** (EIN: 84-2889631, Garden Grove, CA).

Replaces manual Google searching with an automated pipeline that finds, scores, and displays grant opportunities relevant to our mission — at **$0 operating cost**.

---

## How It Works

```
   FIND                     PROCESS                  DISPLAY
   ────                     ───────                  ───────
   Grants.gov API     ──▶                     ──▶   Streamlit Dashboard
   RSS Feeds          ──▶   Clean & Dedup     ──▶     ├─ Metrics cards
   Website Scrapers   ──▶   TF-IDF Scoring    ──▶     ├─ Filterable table
   Keyword Search     ──▶   Program Matching  ──▶     ├─ Deadline alerts
   Research CSVs      ──▶   Priority Ranking  ──▶     └─ Detail view
                                │
                                ▼
                          JSON + Google Sheets
                          (data persistence)
```

**Four scrapers** discover grants from free sources. A **scikit-learn TF-IDF engine** scores each grant against Delta's mission and four programs. Results display on a **Streamlit dashboard** the team opens in a browser.

---

## Delta's Programs

| Program | Focus | Keywords |
|---------|-------|----------|
| **AI Climate Tools** | MRV software for carbon markets | climate AI, carbon verification, environmental data |
| **Resilience Nursery** | Native & drought-resistant plants | native plants, food security, pollinator habitat |
| **More Shade** | Urban shade & cooling structures | heat island, urban canopy, community cooling |
| **CBECN** | Indigenous community carbon projects | carbon credits, biodiversity, traditional knowledge |

---

## Quick Start

```bash
# Clone
git clone https://github.com/sneha1012/Mini-Grant-Finder.git
cd Mini-Grant-Finder

# Install
pip install -r requirements.txt

# Run the dashboard (loads 40+ researched grants automatically)
streamlit run dashboard/app.py

# Or run the full pipeline (scrapers + scoring)
python -m src.cli

# Run with specific options
python -m src.cli --no-scrape                    # Research data only
python -m src.cli --scrapers rss keyword         # Specific scrapers
python -m src.cli --min-score 50 --export csv    # Filter & export
```
