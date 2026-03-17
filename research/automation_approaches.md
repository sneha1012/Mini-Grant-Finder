# Grant Search Automation — Approach Comparison

*Research for Delta Rising Foundation | February 2026*

Since Delta is a nonprofit, we need **free or near-free** solutions. Below are the viable approaches ranked by feasibility.

---

## TL;DR Recommendation

**Start with Approach 1 (Python scraping + local NLP) for the MVP.** It's completely free, gives full control, and can be extended later. Use Streamlit for the internal dashboard. Add RSS monitoring (Approach 3) for ongoing alerts. Consider Approach 5 (Google Sheets + Apps Script) as a lightweight alternative if the team prefers a spreadsheet-based workflow.

---

## Approach 1: Python Web Scraping + Local NLP (RECOMMENDED for MVP)

### Stack
- **Scraping:** BeautifulSoup + Requests (static sites) / Selenium or Playwright (dynamic JS sites)
- **NLP Matching:** sentence-transformers (free, runs locally) or spaCy
- **Storage:** SQLite or CSV/JSON files
- **Dashboard:** Streamlit (free, Python-native)
- **Scheduling:** cron job or GitHub Actions free tier (2,000 min/month)

### How it works
1. Scraper visits known grant listing pages (Grants.gov, foundation sites, etc.)
2. Extracts grant details: name, funder, amount, deadline, description, eligibility, URL
3. NLP model compares grant description against Delta's profile (mission, programs, keywords)
4. Scores relevance and categorizes by program area
5. Filters out expired grants (deadline < today)
6. Outputs to dashboard table with sorting/filtering

### Pros
- Completely free (no API keys, no subscriptions)
- Full control over what gets scraped and how
- NLP matching can be very accurate with good keyword/embedding setup
- Existing open-source project: [GrantAIScraper](https://github.com/zaina-saif/GrantAIScraper) as reference
- Streamlit dashboard is simple and internal-only

### Cons
- Requires Python development effort
- Scrapers need maintenance when websites change their HTML structure
- Must respect robots.txt and rate limits (ethical scraping)
- NLP models need some tuning for grant-specific language

### Cost: $0

---

## Approach 2: Grants.gov API + Apify Scrapers

### Stack
- **Federal grants:** Grants.gov has a public API (XML-based, no key needed for basic access)
- **Foundation grants:** Apify community actors (free tier: ~$5/month worth of compute)
- **Processing:** Python
- **Dashboard:** Streamlit

### How it works
1. Query Grants.gov API with Delta's keywords
2. Use Apify's pre-built Grants.gov scraper for broader searches
3. Process and filter results locally

### Pros
- Grants.gov API is free and official
- Apify has pre-built grant scrapers
- Less maintenance than DIY scrapers for supported sources

### Cons
- Grants.gov = federal grants only (misses foundation/private grants)
- Apify free tier is limited (~$5 credits/month)
- Apify actors are community-maintained (may break)

### Cost: $0–$5/month

---

## Approach 3: RSS Feeds + Email Monitoring

### Stack
- **RSS Reader:** feedparser (Python library)
- **Sources:** Philanthropy News Digest RSS, Grants.gov RSS, Foundation Center alerts
- **Notifications:** Email via free SMTP (Gmail/Outlook) or Slack webhook (free tier)

### How it works
1. Monitor RSS feeds from grant announcement sites
2. Parse new entries, run keyword matching
3. Push relevant grants to email/Slack/Google Sheet

### Pros
- Very lightweight and easy to set up
- No scraping = no HTML breakage issues
- Good for ongoing monitoring after initial discovery
- Can run as a simple cron job

### Cons
- Limited to sources that offer RSS feeds
- Not all grant sites have RSS
- Less comprehensive discovery than active scraping

### Cost: $0

---

## Approach 4: Free Grant Databases + Manual Workflow

### Stack
- **Sources:** Grantseeker.io, FindGrant.ai, Grantmakers.io, Grants.gov
- **Tracking:** Google Sheets (free)
- **Collaboration:** Google Sheets shared with development team

### How it works
1. Team members periodically search free databases
2. Copy relevant grants to shared Google Sheet
3. Columns: Grant Name, Funder, Amount, Deadline, Category, Status, Assigned To, Notes
4. Use conditional formatting for deadline alerts

### Pros
- Zero development effort
- Familiar tools (Google Sheets)
- Immediate team collaboration
- Good starting point while building automation

### Cons
- Still manual (defeats the project purpose long-term)
- Depends on human consistency
- No automatic matching/scoring

### Cost: $0

---

## Approach 5: Google Sheets + Apps Script Automation

### Stack
- **Backend:** Google Apps Script (JavaScript, free, runs in cloud)
- **Data:** Google Sheets as database + dashboard
- **Scraping:** UrlFetchApp (built into Apps Script)
- **Scheduling:** Time-driven triggers (built-in, free)
- **Notifications:** Gmail API (built into Apps Script)

### How it works
1. Apps Script fetches grant listing pages on a schedule
2. Parses HTML for grant details
3. Writes results to a Google Sheet
4. Highlights new grants, flags approaching deadlines
5. Sends email digest to development team

### Pros
- 100% free (Google account is all you need)
- No server or hosting needed
- Team already knows Google Sheets
- Built-in email notifications
- Easy to share internally (not public)

### Cons
- Apps Script has execution time limits (6 min/run for free accounts)
- JavaScript is less powerful than Python for NLP
- Limited to simple keyword matching (no embeddings)
- UrlFetchApp can't handle JS-rendered pages

### Cost: $0

---

## Approach 6: Using Free-Tier LLMs for Matching (Future Enhancement)

### Stack
- **LLM:** Ollama + Llama 3 or Mistral (free, runs locally) OR Google Gemini API free tier (15 req/min)
- **Purpose:** Read grant descriptions and assess fit with Delta's profile

### How it works
1. After scraping, send grant descriptions to a local LLM
2. Prompt: "Rate this grant's relevance to [Delta's profile] on 1-10 and explain why"
3. Use the score for ranking on the dashboard

### Pros
- Much smarter matching than keyword-based
- Can understand nuanced eligibility criteria
- Free if running locally (Ollama)
- Google Gemini free tier is generous

### Cons
- Requires decent hardware for local LLMs (8GB+ RAM)
- LLM responses need validation
- Adds complexity to the pipeline

### Cost: $0 (local) or free-tier API

---

## Comparison Matrix

| Approach | Cost | Dev Effort | Accuracy | Maintenance | Best For |
|----------|------|------------|----------|-------------|----------|
| 1. Python Scraping + NLP | $0 | High | High | Medium | MVP/Long-term |
| 2. Grants.gov API + Apify | $0–5/mo | Medium | Medium | Low | Federal grants |
| 3. RSS Monitoring | $0 | Low | Low | Low | Ongoing alerts |
| 4. Manual + Sheets | $0 | None | Varies | None | Immediate start |
| 5. Google Sheets + Apps Script | $0 | Medium | Medium | Medium | Lightweight teams |
| 6. Local LLM Matching | $0 | High | Very High | Medium | Future phase |

---

## Recommended Phased Approach

### Phase 1 — Now (Weeks 1–2)
- **Approach 4:** Set up the Google Sheet tracker immediately
- Start manually populating with grants from `mini_grants_list.md`
- Define the columns the development team needs

### Phase 2 — MVP (Weeks 3–6)
- **Approach 1:** Build Python scrapers for top 3–5 grant sources
- Add basic keyword matching
- Deploy Streamlit dashboard for internal use

### Phase 3 — Enhancement (Weeks 7–10)
- **Approach 3:** Add RSS feed monitoring for new grant alerts
- **Approach 6:** Integrate local LLM for smarter relevance scoring
- Add email notifications for the development team

### Phase 4 — Maturity (Ongoing)
- Expand scraper coverage to more sources
- Auto-assign grants to team members
- Track application status (applied, rejected, won, ineligible + reason)
- Historical analytics on win rates
