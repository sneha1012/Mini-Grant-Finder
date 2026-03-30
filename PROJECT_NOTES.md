# Grant Finder — Project Notes

## Live App

**URL:** https://delta-grant-finder.streamlit.app

Deployed on Streamlit Community Cloud (free). Auto-redeploys on every push to `main`.
If no one visits for a few days, it goes to sleep and wakes up automatically (~30s) on the next visit.

---

## How It Works

### Pipeline Overview (Find → Score → Store)

The pipeline runs in three stages:

1. **FIND** — Collects grants from multiple sources:
   - Grants.gov API scraper
   - RSS feed monitor (foundation/government feeds)
   - DuckDuckGo keyword search (free, no API key)
   - Direct website scraper for specific funder sites
   - Pre-loaded research CSV data

2. **SCORE** — Ranks every grant by relevance to Delta Rising:
   - Uses **TF-IDF + cosine similarity** (runs locally, no API costs)
   - Compares each grant's text against Delta's mission statement and 4 program descriptions
   - Weighted: 60% mission alignment + 40% best program match
   - Also does keyword-based program matching (AI Climate Tools, Resilience Nursery, More Shade, CBECN)
   - Assigns priority (Urgent/High/Medium/Low) based on score + deadline proximity

3. **STORE** — Saves results:
   - Local JSON files in `output/` (always)
   - `output/latest.json` is what the dashboard reads
   - Google Sheets (optional, if credentials configured)

### Dashboard Features

- **Filters:** Program, Deadline, Priority, Grant Type, Relevance Score slider, Text search
- **Search:** Matches against grant name, funder, description, and focus areas
- **Tabs:** Dashboard (table + charts), Deadline Alerts, Grant Details
- **Charts:** Grants by program, grants by type, upcoming deadlines

### Config Files

- `config/delta_profile.yaml` — Delta Rising's mission, programs, and org info
- `config/keywords.yaml` — Search keywords per program + cross-cutting terms + filter criteria
- `config/grant_sources.yaml` — RSS feeds, websites, and scraper settings

---

## How to Update Grant Results

### Option 1: Full pipeline (scrapes live sources)

```bash
python -m src.cli run
```

This runs all scrapers, scores results, and saves to `output/latest.json`. The dashboard will pick up the new data automatically.

### Option 2: Research data only (no live scraping)

```bash
python -m src.main
```

Loads from existing CSV research data, scores, and saves. Faster, no network calls.

### Option 3: Specific scrapers only

```bash
python -m src.cli run --scrapers grants_gov rss
```

Available scrapers: `grants_gov`, `rss`, `keyword`, `website`

### After updating

Push to GitHub and the live app auto-updates:

```bash
git add output/latest.json
git commit -m "Update grant data"
git push
```

---

## Potential Improvements

### 1. Better Scoring Differentiation
Most grants currently cluster in the 40-60 "MED" priority range with no program match. Tuning the keywords in `config/keywords.yaml` to be more specific would help differentiate high-relevance grants from noise.

### 2. Fuzzy Search
The dashboard search currently does exact substring matching — "climate" works, but "climate change adaptation" won't match "climate adaptation for change." Adding fuzzy or partial token matching would improve search quality.

### 3. Saved/Favorited Grants
Let users bookmark grants they're interested in so they can come back to them later without re-filtering.

### 4. Email Digest
Weekly automated email with new high-scoring grants so Sarah doesn't have to check the dashboard manually.

### 5. Automated Pipeline Refresh
Currently the pipeline must be run manually to get fresh data. A GitHub Action on a weekly cron schedule could automate this so the dashboard always has fresh results.

### 6. Google Sheets Integration
Credentials aren't configured yet. Once set up, scored grants would auto-sync to a shared Google Sheet for the team to collaborate on.
