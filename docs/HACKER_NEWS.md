# Hacker News "Show HN" Post — Bloomy News

## Title (under 80 chars)

```
Show HN: Bloomy News – self-hosted AI news aggregator with 8 scrapers
```

---

## Post Body

Paste the following as the HN post body. HN prefers technical depth, concrete numbers, and no marketing language. Aim for ~300 words.

---

I built Bloomy News because I was spending 30+ minutes every morning manually visiting arXiv, GitHub trending, SecurityWeek, and a handful of finance blogs. RSS readers gave me volume without filtering. Cloud aggregators wanted my data. So I wrote a Python script that does the job locally.

**What it does:** Bloomy News scrapes 8 public sources twice a day, classifies articles into 6 categories (LLM, Neural Nets, ML Research, AI Applications, Finance, Cybersecurity), deduplicates, and shows the result in a 3-page local dashboard or a Telegram digest. Runs on `127.0.0.1` only — no cloud, no accounts, no telemetry.

**How it works:**

The pipeline is a single Python process. Eight scrapers run sequentially: arXiv (13 RSS feeds covering cs.AI, cs.LG, cs.CL, cs.CV, cs.NE, cs.RO, cs.IR, cs.MA, cs.HC, stat.ML, eess.SP, q-fin.ST, cs.CR), GitHub trending, NewsAPI, cybersecurity feeds (SecurityWeek, Krebs, BleepingComputer, Hacker News, cloud provider security blogs), Finnhub, Google News (3 query feeds with redirect resolution), and Markets. New articles are classified using one of two modes: a keyword matcher (zero external deps, deterministic) or an embedding classifier (`all-MiniLM-L6-v2` via sentence-transformers, ~80 MB model, higher accuracy on ambiguous titles). The classifier uses arXiv subject categories as a strong prior when present. Deduplication is two-layer: arXiv version tracking (v1/v2/v3 collapse to one entry) plus Jaccard title similarity at ≥0.80 over the most recent 200 titles per category.

**Technical details:**

- Python 3.8+, one required dependency (`requests`). Everything else is stdlib.
- 131 passing tests, 68% coverage, CI on Python 3.8–3.12.
- SQLite with WAL mode, FTS5 full-text search, atomic writes.
- Dashboard is vanilla HTML/CSS/JS — no framework, no build step, dark/light theme, WCAG-AA contrast.
- Scheduler has smart catch-up: if the laptop was off at noon, it runs at next startup.
- Config is env-driven with `${VAR}` placeholder expansion in JSON files. `.env` is gitignored.

**Getting started:**

```bash
git clone https://github.com/aaru-sh/bloomy-news.git
cd bloomy-news
pip install -r requirements.txt
python scripts/smoke_test.py  # verifies install in 10 seconds
python news_tool.py            # runs the pipeline
python dashboard/generate_data.py && python dashboard/serve.py
# open http://127.0.0.1:8080
```

Zero API keys required to start — arXiv, GitHub, and cybersecurity scrapers work out of the box. Add NewsAPI/Finnhub/Telegram keys later if you want more sources or the digest.

**What's next:** Discord/Slack digest, WebSocket live updates, semantic dedup with embeddings, and a plugin system for custom scrapers.

MIT license. Feedback welcome: https://github.com/aaru-sh/bloomy-news

---

## HN-Specific Tips

- **Post timing:** Tuesday or Wednesday, 9-11 AM ET gets the most traction
- **Engage quickly:** Reply to comments in the first 2 hours. HN rewards active makers.
- **Be honest about limitations:** If someone points out a flaw, acknowledge it and explain your reasoning. HN respects this.
- **Don't defend aggressively:** If the project isn't for someone, say "fair enough" and move on.
- **Technical depth wins:** When answering questions, include code snippets, architecture details, or benchmark numbers.
- **Follow-up comment idea:** If the post gains traction, post a follow-up comment with a GIF or screenshot of the dashboard in action.

## Cross-Posting Strategy

1. **Hacker News** — Post "Show HN" first (technical audience, honest feedback)
2. **Product Hunt** — Launch 2-3 hours before or after HN (see `PRODUCT_HUNT.md`)
3. **Twitter/X** — Share the GitHub link with a one-line description
4. **Reddit** — r/selfhosted, r/Python, r/artificial (check each sub's rules first)
