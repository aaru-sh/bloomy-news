# Product Hunt Launch Materials — Bloomy News

## Tagline (60 chars max)

```
Self-hosted AI news aggregator with 8 scrapers and 6-category classification
```

## Description (260 chars max)

```
Bloomy News scrapes 8 sources, classifies articles into 6 AI categories, and sends a daily Telegram digest. Runs on localhost, no cloud, no tracking. Python, MIT, open source.
```

---

## Topics

1. **Open Source**
2. **Artificial Intelligence**
3. **Python**
4. **Developer Tools**
5. **Self-Hosted**

---

## First Comment (Maker Comment)

Post this as the first comment immediately after the product goes live. This is where you tell the story behind the project.

---

I built Bloomy News because I was drowning in news tabs.

Every morning I'd open arXiv, GitHub trending, SecurityWeek, Hacker News, a few finance blogs — and by the time I'd scrolled through everything, the important stuff was buried. I tried Feedly, I tried RSS readers, I tried custom Python scripts. Nothing stuck because everything wanted my data in the cloud, or required a subscription, or classified articles badly.

So I built the tool I actually wanted.

**What it does:** Bloomy News runs on localhost. It pulls fresh articles from 8 sources (arXiv with 13 RSS feeds, GitHub trending, cybersecurity feeds, Google News, Finance, Markets, NewsAPI) twice a day, classifies them into 6 categories (LLM, Neural Nets, ML Research, AI Applications, Finance, Cybersecurity) using either keyword matching or an optional sentence-transformers embedding model, deduplicates everything, and shows the result in a 3-page dashboard or a Telegram digest.

**Key technical decisions:**
- **SQLite, not Postgres.** One file, zero setup, WAL mode for concurrency. The whole thing is a Python script, not a server.
- **Dual-mode classifier.** Keyword mode works with zero deps. Embedding mode (all-MiniLM-L6-v2) gives better accuracy but costs ~1 GB. Users choose their trade-off.
- **Two-layer dedup.** Jaccard title similarity (≥0.80) plus arXiv version tracking. Same paper appearing 3 times with v1/v2/v3 collapses to one entry.
- **127.0.0.1 only.** The dashboard server binds localhost. No LAN exposure, no auth needed.

**What's next:** Discord/Slack digest, WebSocket live updates, semantic dedup with embeddings, and a plugin system for custom scrapers.

If this sounds useful, star the repo on GitHub — it helps more people find it: https://github.com/aaru-sh/bloomy-news

---

## Maker Comment Template (Personal Story Version)

Use this version if you want a more personal, less technical tone:

---

I spent two years maintaining a bookmarks folder called "Daily News" with 40+ tabs I never finished reading. RSS readers didn't solve it — they gave me volume without filtering. Cloud aggregators gave me filtering but wanted my reading habits as payment.

I wanted something different: a news desk that runs on my machine, knows what I care about (AI, security, finance), and hands me 15-20 curated articles twice a day — not 200.

Bloomy News is that tool. It scrapes 8 sources, classifies everything with a dual-mode AI classifier (keyword matching for zero-deps, sentence-transformers for accuracy), deduplicates aggressively, and delivers the result to a local dashboard or Telegram.

No cloud. No tracking. No accounts. Just a Python script and a SQLite file.

It's open source under MIT. If you've ever wanted a private, self-hosted news aggregator for AI/tech/finance — give it a try: https://github.com/aaru-sh/bloomy-news

---

## Visual Assets Needed

Before launch, prepare these screenshots for the Product Hunt gallery:

1. **Dashboard landing page** — dark mode, showing category cards and recent articles
2. **Filters page** — search, calendar picker, multi-select dropdowns
3. **Terminal output** — the pipeline running with scraper progress
4. **Architecture diagram** — the pipeline flow from scrapers → classifier → DB → dashboard/Telegram

---

## Launch Day Checklist

- [ ] Schedule the post for **Tuesday or Wednesday, 12:01 AM PT** (peak traffic)
- [ ] Prepare the first comment (copy from above)
- [ ] Have 3-4 screenshots ready for the gallery
- [ ] Set the GitHub repo URL as the website link
- [ ] Tag topics: Open Source, Artificial Intelligence, Python, Developer Tools, Self-Hosted
- [ ] Post on Hacker News "Show HN" (see `HACKER_NEWS.md`) 2-3 hours before or after PH launch
- [ ] Share on Twitter/X with the GitHub link
- [ ] Respond to every comment in the first 2 hours (algorithm boost)
