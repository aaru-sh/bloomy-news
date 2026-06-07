# Social Media Content — Bloomy News

Prepared content for promoting Bloomy News across Twitter/X, LinkedIn, and Reddit.

**GitHub:** https://github.com/aaru-sh/bloomy-news

---

## Twitter/X Posts (5 variations)

### 1. Technical Angle
```
I built a self-hosted AI news aggregator that scrapes 8 sources, classifies articles into 6 categories via keyword + embedding, and sends a daily Telegram digest. No cloud, no tracking, just Python 3.8+ and SQLite. Check it out 👇
https://github.com/aaru-sh/bloomy-news
#opensource #AI
```

### 2. Problem-Solution Angle
```
Tired of algorithmic news feeds deciding what you read? Bloomy News is a self-hosted aggregator that gives YOU control. AI-classified, locally stored, privacy-first. Runs on 127.0.0.1 only.
https://github.com/aaru-sh/bloomy-news
#privacy #selfhosted
```

### 3. Feature-Highlight Angle
```
The best feature of my news aggregator? 30-day retention. The SQLite database stays at 8MB forever. No bloat, no cleanup cron, no managed DB. Just a file on disk and WAL mode.
https://github.com/aaru-sh/bloomy-news
#efficiency #sqlite
```

### 4. Community/Milestone Angle
```
Just hit 131 tests and 68% coverage on Bloomy News. The classifier got a dual-mode upgrade: keyword + all-MiniLM-L6-v2 embedding. Tests run on Python 3.8–3.12 in CI. Open source, MIT, contributions welcome.
https://github.com/aaru-sh/bloomy-news
#python #testing
```

### 5. Show HN Style
```
Show HN: Bloomy News – a self-hosted AI news aggregator with 8 scrapers, a 6-category classifier, and a 3-page dashboard. No cloud, no Docker, no Node.js. Just Python, SQLite, and a localhost HTTP server.
https://github.com/aaru-sh/bloomy-news
#showhn
```

---

## LinkedIn Post

**I built an AI news aggregator that runs entirely on my laptop — and here's what I learned.**

I follow AI, machine learning, cybersecurity, and finance — and I was drowning in tabs. RSS readers felt dated, algorithmic feeds felt manipulative, and most "AI-powered" news tools require a cloud account I don't trust.

So I built Bloomy News: a self-hosted news desk that pulls fresh articles from 8 public sources twice a day, classifies them into 6 categories, removes duplicates, and delivers a clean local dashboard plus a Telegram digest.

**How it works under the hood:**

- 8 scrapers (arXiv, GitHub trending, NewsAPI, cybersecurity feeds, Finnhub, Google News, Markets) run sequentially with retry logic and backoff.
- A dual-mode classifier picks articles into LLM, Neural Nets, ML Research, AI Applications, Finance, and Cybersecurity. The default keyword classifier is fast and offline; an optional embedding mode uses all-MiniLM-L6-v2 for better accuracy on ambiguous titles.
- Two-layer deduplication: arXiv version tracking (v1/v2/v3 collapse to one entry) plus Jaccard title similarity at 0.80 threshold.
- SQLite with WAL mode, FTS5 full-text index, and atomic writes for crash safety.
- A 3-page dashboard at 127.0.0.1:8080 — landing, filters, and bookmarks — with dark/light theme and keyboard navigation.

**The numbers:** 131 tests passing, 68% coverage, Python 3.8–3.12 CI matrix. Zero cloud services, zero telemetry, zero Docker dependency. The database stays under 8MB with automatic 30-day retention.

It's MIT licensed and fully open source. If you're interested in privacy-first news aggregation, self-hosting, or just want to see how the classifier and dedup work, take a look:

https://github.com/aaru-sh/bloomy-news

I'm looking for contributors — especially for the embedding classifier tuning, the Telegram bot UX, and the roadmap items (Discord digest, WebSocket live updates, OPML import).

---

## Reddit Posts

### r/selfhosted

**Title:** Bloomy News – self-hosted AI news aggregator with 8 scrapers, 6-category classifier, and Telegram digest

**Body:**

I've been building a self-hosted news aggregator called Bloomy News for the past few months, and it's at a point where I think others in this community might find it useful.

**The problem I was solving:** I follow AI, ML, cybersecurity, and finance. Every "AI-powered" news tool I tried required a cloud account, sent telemetry home, or had an algorithm that decided what I should see. I wanted something local-first that I control.

**What it does:**
- Pulls articles from 8 sources: arXiv (13 RSS feeds across cs.AI, cs.LG, cs.CL, cs.CV, cs.NE, cs.RO, cs.IR, cs.MA, cs.HC, stat.ML, eess.SP, q-fin.ST, cs.CR), GitHub trending, NewsAPI, dedicated cybersecurity feeds (SecurityWeek, Krebs, BleepingComputer, cloud provider security blogs), Finnhub, Google News, and Markets
- Classifies articles into 6 categories (LLM, Neural Nets, ML Research, AI Applications, Finance, Cybersecurity) using a keyword classifier with an optional embedding mode via sentence-transformers
- Deduplicates using Jaccard title similarity (≥0.80) and arXiv version tracking
- Runs a 3-page dashboard at 127.0.0.1:8080 with landing, filters (calendar, search, multi-select dropdowns), and bookmarks
- Sends a daily Telegram digest with top 3 articles per category and inline buttons
- Retains articles for 30 days automatically — the SQLite database stays tiny

**Why I think this community would care:**
- No cloud, no accounts, no telemetry. Dashboard binds to localhost only.
- Runs on anything with Python 3.8+. No Docker, no Node.js, no database server. Just `pip install -r requirements.txt` and go.
- The 12-hour scheduler with startup catch-up means if your laptop was off at midnight, it runs the pipeline on boot — not at the next cron slot.
- Windows autostart via registry entry, Linux/macOS via systemd/cron/launchd.
- MIT licensed, 131 tests, 68% coverage, CI on Python 3.8–3.12.

**What's on the roadmap:** Discord/Slack digest, WebSocket live updates, per-user auth for running on a server, OPML import, and a feedback-trained classifier.

**GitHub:** https://github.com/aaru-sh/bloomy-news

Happy to answer questions, hear feedback, or help anyone get it running. Contributions welcome — especially around classifier tuning and the Telegram bot UX.

---

### r/Python

**Title:** Bloomy News – a Python news aggregator with keyword + embedding classifier, two-layer dedup, and SQLite

**Body:**

I want to share a Python project I've been building: Bloomy News, a self-hosted news aggregator for AI, ML, cybersecurity, and finance news.

It's a single-process Python application — no framework, no async, no web server stack. Just `requests` and the standard library, with an optional `sentence-transformers` dependency for the embedding classifier.

**Architecture highlights:**

- **8 scraper functions** in `news_tool.py` — each returns a `list[Article]` dict. arXiv uses 13 RSS feeds parsed with `urllib` and `xml.etree.ElementTree`. GitHub trending is scraped from HTML. NewsAPI, Finnhub, and Google News hit JSON APIs. All scrapers have retry logic with exponential backoff.

- **Dual-mode classifier** (`classify_article()`) — the default keyword mode scores title + summary tokens against a weighted keyword table per category. The optional embedding mode encodes text with `all-MiniLM-L6-v2` and compares cosine similarity against per-category centroids. The arXiv subject category is used as a strong prior when present.

- **Two-layer deduplication** — arXiv version IDs are normalized at ingestion (v1/v2/v3 → one entry). General articles go through Jaccard title similarity against the most recent 200 titles in the same category, backed by a `dedup_log` table with hash-based candidate filtering for performance.

- **SQLite with WAL mode** — FTS5 for full-text search, `INSERT OR IGNORE` for idempotency, atomic filesystem writes for bookmarks and dashboard data. The schema is simple: `articles`, `dedup_log`, and an FTS virtual table.

- **Dashboard** — three static HTML pages served by a `ThreadingHTTPServer` subclass on 127.0.0.1:8080. Security headers on every response, CORS restricted to localhost, input validation on the bookmark API (ID regex, 1KB body cap, 5K bookmark cap). The JSON data file is built with an atomic write pattern (tmp + `os.replace`).

- **12-hour scheduler** — tracks state in `.last_run` (atomic JSON). On startup, if the last run is >12h old, it catches up immediately. Windows autostart via `HKCU\...\Run` registry key with `pythonw.exe`.

**Testing:** 131 tests across `tests/test_fixes.py`, `tests/test_fresh_install.py`, and extended test files. Tests cover classifier fallback paths, Jaccard edge cases, ID validation, secrets loader precedence, bookmark API limits, scheduler state machine, and fresh-install verification (no hardcoded paths). CI runs on Python 3.8–3.12 via GitHub Actions.

**What I learned building it:**
- SQLite WAL mode is excellent for this use case — concurrent reads during writes, crash safety, zero config.
- Keyword classifiers are surprisingly good when you tune the weights. The "Uncategorized" fallback is better than forcing a bad classification.
- `os.replace()` for atomic writes is cross-platform and eliminates half-written file bugs.
- The dual-mode classifier taught me when to reach for embeddings vs. when keywords are enough. Keyword mode is deterministic, fast, and transparent. Embedding mode handles ambiguous titles better but costs 1GB disk and 500MB RAM at load.

**GitHub:** https://github.com/aaru-sh/bloomy-news

MIT licensed. I'm looking for contributions — especially around classifier tuning, dedup edge cases, and the Telegram bot. If you have questions about the architecture or want to add a scraper, happy to discuss.
