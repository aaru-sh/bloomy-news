# Bloomy News Newsletter

---

## Subject Line Options

1. "Bloomy News: Your AI-powered news aggregator, now with 30-day retention"
2. "Self-hosted AI news that actually works"
3. "8 scrapers, 6 categories, 1 dashboard: Bloomy News v1.2.1"

---

## Body

### What is Bloomy News?

Bloomy News is a self-hosted news aggregator that pulls fresh articles from eight public sources twice a day, classifies them into six categories (LLM, Neural Nets, ML Research, AI Applications, Finance, Cybersecurity), and serves them up on a local dashboard and Telegram digest. No cloud. No accounts. No telemetry. Your data stays on your machine.

### What's New in v1.2.1

We shipped the two features that long-running installs have been asking for:

- **30-day retention** — the pipeline now prunes articles older than 30 days at the end of each run. Your database stops growing. A live DB with 1,794 articles shrank from 4.93 MB to 0.6 MB on the first cleanup. Total project storage is now bounded at ~14 MB flat, down from ~100 MB/year unbounded growth.
- **Dashboard autostart on Windows** — `python scripts/install_dashboard.py --install` writes a registry entry so the server starts at login. No admin rights, no Task Scheduler. On other platforms, double-click `BROWSE_DASHBOARD.bat`.
- **Type hints and a cleaner codebase** — `news_tool.py` went from a 982-line monolith to a 273-line orchestrator over 13 focused files. Both `news_tool.py` and `database.py` are fully annotated and mypy-clean.
- **131 tests pass**, up from 103 at v1.2.0. Coverage at 68%.

### 5 Features Worth Knowing

1. **Dual-mode classifier** — a fast keyword matcher that works offline with zero dependencies, or an optional embedding classifier (`sentence-transformers`) that uses semantic similarity for higher accuracy. The dispatcher picks automatically.
2. **Two-layer deduplication** — Jaccard title similarity catches near-duplicate news articles, and arXiv version tracking collapses v1/v2/v3 of the same paper into one entry.
3. **Zero-config to start** — the pipeline works with no API keys. You only need keys if you want NewsAPI, Finnhub finance, or Telegram digests.
4. **Local-only dashboard** — binds to `127.0.0.1:8080` with WCAG-AA contrast, dark/light theme, bookmarks, and full-text search. Not reachable from your LAN.
5. **Smart scheduler** — 12-hour loop with catch-up. If your laptop was off at midnight, the next run happens at startup, not at the next checkpoint.

### Get Started in 3 Steps

```bash
git clone https://github.com/aaru-sh/bloomy-news.git
cd bloomy-news
pip install -r requirements.txt && python scripts/smoke_test.py
```

If the smoke test prints `ALL CHECKS PASSED`, you're good. Then:

```bash
python news_tool.py && python dashboard/generate_data.py && python dashboard/serve.py
```

Open `http://127.0.0.1:8080` and you're reading.

### Under the Hood

- **SQLite primary store** with WAL mode, FTS5 full-text search, and atomic writes. Filesystem archive of compressed `.md.gz` files for historical articles.
- **8 scrapers**: arXiv (13 feeds), GitHub trending, NewsAPI, cybersecurity RSS (SecurityWeek, Krebs, BleepingComputer, cloud security blogs), Finnhub, Google News (14 queries with redirect resolution), and Markets.
- **Python 3.8+**, tested on 3.8 through 3.12. CI runs the full test suite + smoke test on every push. Type-checked with mypy.
- **MIT licensed.** One external dependency (`requests`) for the core pipeline. Everything else is stdlib.

### What's Next

- Discord / Slack digest (in addition to Telegram)
- WebSocket live updates on the dashboard
- Semantic dedup using sentence embeddings
- RSS aggregator mode with OPML import
- Configurable classifier training from user feedback

### Get Involved

We'd love contributions — code, docs, bug reports, or feature ideas. Start with [CONTRIBUTING.md](../CONTRIBUTING.md) or pick up a [good first issue](https://github.com/aaru-sh/bloomy-news/labels/good%20first%20issue). Questions? Open a thread in [GitHub Discussions](https://github.com/aaru-sh/bloomy-news/discussions).

### Links

- **GitHub**: https://github.com/aaru-sh/bloomy-news
- **Docs**: https://github.com/aaru-sh/bloomy-news/tree/main/docs
- **Release Notes**: https://github.com/aaru-sh/bloomy-news/releases/tag/v1.2.1
- **Changelog**: https://github.com/aaru-sh/bloomy-news/blob/main/CHANGELOG.md

---

*Bloomy News is MIT-licensed and runs entirely on your own machine. No accounts, no telemetry, no cloud.*
