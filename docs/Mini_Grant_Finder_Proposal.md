# Mini-Grant Finder Tool — Architecture Proposal

**Prepared by:** Sneha Maurya, Data Science
**Date:** February 16, 2026

---

## What This Is

A free internal tool that automatically finds mini-grant opportunities relevant to Delta Rising Foundation and displays them on a simple web dashboard. Grant writers open a URL, see the latest grants with deadlines, amounts, and apply links — and start applying.

No more manual Googling. The tool does the searching every day.

---

## The Problem Today

Our development team searches Google manually for mini-grants using keyword combinations ("donation request" + industry + location), then checks each result one by one. This is slow, inconsistent, and easy to miss deadlines. Different people find different things and there is no shared view.

---

## How the Tool Works

Four simple steps, running every day on autopilot:

**1. Find** — Python scripts automatically search grant databases, RSS feeds, foundation websites, and run the keyword search combinations the team currently does by hand.

**2. Score** — Each grant is compared against Delta's mission and programs using text-matching. Grants get a relevance score (0–100) and are tagged to the Delta program they fit best. Expired grants are filtered out.

**3. Display** — Results show up on a clean web dashboard. Grant writers see a table with: grant name, amount, deadline (color-coded), relevance score, and a clickable link to apply.

**4. Refresh** — Scripts re-run every morning automatically. Fresh data every day, no manual work.

---

## Architecture

```
   FIND                    PROCESS                 DISPLAY
   ----                    -------                 -------

   Grants.gov API    -->                     -->   Web Dashboard (URL)
   RSS Feeds         -->   Score relevance   -->     - Grant table
   Website Scrapers  -->   Filter expired    -->     - Filters & search
   Keyword Search    -->   Categorize        -->     - Deadline alerts
                           Deduplicate       -->     - Apply links
                                |
                                v
                          Google Sheets
                         (data storage)
```

---

## Data Sources

| Source | What It Covers | How |
|--------|---------------|-----|
| Grants.gov API | Federal grants (environment, community, climate) | Free XML API, no key needed |
| RSS Feeds | Grant announcements from Philanthropy News Digest, EPA, CA Grants Portal | feedparser library, very stable |
| Website Scrapers | Foundation sites — OCCF, SoCalGas, Sprouts, Garden Grove CF, Clean Power Alliance | Playwright / BeautifulSoup |
| Keyword Search | Automates the "Magic Keyword Algorithm" — "donation request" + industry + location | DuckDuckGo search library, free, no key |

---

## Tech Stack

Everything is free and open-source. No paid APIs, no hosting costs.

| Component | Tool | Cost |
|-----------|------|------|
| Scraping (dynamic sites) | Playwright | Free |
| Scraping (static sites) | BeautifulSoup | Free |
| Keyword search | duckduckgo-search | Free |
| Relevance scoring | scikit-learn TF-IDF | Free |
| Data storage | Google Sheets | Free |
| Dashboard | Streamlit | Free |
| Hosting | Streamlit Community Cloud | Free |
| Scheduling | GitHub Actions cron | Free |

**Total running cost: $0/month**

---

## What the Dashboard Looks Like

A single-page web app the team accesses through a URL:

- Top row: total grants found, how many are urgent, how many are new today
- Filters: by Delta program, deadline range, amount, grant type
- Table: grant name, amount, deadline (red/yellow/green), relevance score, apply link
- Click any row to see full details and eligibility

Non-tech users just open the link and browse. Nothing to install.

---

## Timeline

| Phase | When | What Gets Delivered |
|-------|------|-------------------|
| Phase 1 | Week 1 | Working dashboard with 40+ grants already researched, live on a URL |
| Phase 2 | Weeks 2–3 | Automated scraping from Grants.gov + RSS feeds. New grants appear daily |
| Phase 3 | Week 4 | Magic Keyword Algorithm running automatically on a weekly schedule |
| Phase 4 | Week 5 | Testing, stability, polish |

Phase 1 gives the team a usable tool right away. Each phase adds more automation on top.

---

## What We Already Have

- 40+ grants identified and verified (foundation grants, corporate sponsors, OC/LA local programs)
- Keyword configuration mapped to Delta's four programs
- Grant source database with 12 free sources prioritized
- Project folder structure set up

---

## Future Possibilities (When Budget Allows)

- AI-powered matching for smarter grant relevance
- Auto-fill assistance for common grant application fields
- Email or Slack alerts for new grants and approaching deadlines
- Application tracking (applied, won, rejected, ineligible) built into the dashboard

---

I put this doc together for our reference so we have a clear picture of the approach. Please review and let me know your thoughts — happy to dig deeper into any part of it.

---

*Sneha Maurya*
*Data Science, Delta Rising Foundation*
