# Release notes — paste into the GitHub Release UI

Copy everything below the line into the "Describe this release" box on
https://github.com/aaru-sh/bloomy-news/releases/new?tag=v1.1.0

---

## Bloomy News v1.1.0 — Code quality and classifier overhaul

This is a polish release. No breaking changes; the user experience is
identical, the code is meaningfully better.

### What's inside

- **Pipeline connection refactor** — each pipeline run now uses a single
  SQLite connection for all article inserts (previously 3 connections
  per article). On a 200-500 article run, this is ~600-1500 fewer
  round-trips and the whole run commits as one transaction.
- **Classifier centroids** — replaced single-description similarity with
  multi-example centroids (12 representative article titles per
  category). Accuracy on the labeled set jumped from 80% to 100% (30/30);
  `MINIMUM_ACCURACY` raised to 0.90.
- **Classifier robustness** — when the sentence-transformers model can't
  load (HF rate-limit, OOM, network), the classifier caches the failure
  and falls back to the keyword classifier instead of crashing.
- **Database cleanup** — NULL `title_words` rows are now backfilled on
  `init_db()`; orphaned `is_starred` column and `mark_starred()` function
  removed.
- **Google News redirects** — `news.google.com/articles/...` URLs are
  now resolved to the underlying article URL via HEAD-then-GET with
  `<link rel="canonical">` fallback. No more redirect placeholders in
  bookmarks or Telegram digests.
- **Doc accuracy** — README, `docs/CLASSIFIER.md`, `docs/SCRAPERS.md`,
  and `docs/PROJECT_STRUCTURE.md` now match the code.
- **Concurrency test** — verifies 2 simultaneous pipeline runs don't
  double-insert and 5 threads racing on the same URL only let one win.

### Upgrade notes

- Drop-in. No config changes, no migrations required (the `is_bookmarked`
  column migration is forward-only and runs automatically on
  `init_db()`).
- 38 unit tests + 8 smoke checks; classifier accuracy is verified to
  30/30 = 100% on the labeled set.

### Install / upgrade

```bash
git pull
pip install -e .
python -m unittest discover tests/
```

### Full v1.0.0 release notes (preserved below for reference)

---

## Bloomy News v1.0.0 — First public release

The system has been in private use for several months; this release marks
the first version packaged for distribution.

### What's inside

- **8 scrapers** — arXiv (4 subject feeds), GitHub trending, NewsAPI, dedicated
  cybersecurity feeds, Finnhub, Google News, and market data
- **6-category classifier** with arXiv subject prior and a graceful
  "Uncategorized" fallback
- **Two-layer deduplication** — Jaccard title similarity (≥0.80) plus arXiv
  version tracking
- **3-page dashboard** with dark/light theme, WCAG-AA contrast, full
  keyboard nav, and screen-reader landmarks
- **Bookmarks** with server-side persistence, input validation, and star
  buttons on every article card
- **Telegram digest** — top 3 articles per category to the main channel plus
  6 sub-channels with inline buttons
- **12-hour scheduler** with smart catch-up, registry autostart on Windows,
  foreground loop on Linux/macOS
- **Local-only** — dashboard binds 127.0.0.1, secrets are env-driven, no
  cloud, no third-party data sink beyond Telegram and the free-tier APIs

### Quick start

```bash
git clone https://github.com/aaru-sh/bloomy-news
cd bloomy-news
pip install -r requirements.txt          # or: pip install -e .
python scripts/smoke_test.py             # verify your machine
python news_tool.py                      # run the pipeline
python dashboard/generate_data.py        # regenerate the dashboard data
python dashboard/serve.py                # start the server on :8080
```

Then open <http://127.0.0.1:8080>.

### Verification

- ✅ 30 unit tests pass (`python -m unittest discover -s tests`)
- ✅ 10-check smoke test passes (`python scripts/smoke_test.py`)
- ✅ CI runs on Python 3.8 – 3.12 (`.github/workflows/test.yml`)
- ✅ No secrets in tracked files (`.env` is gitignored; `config/*.json` use
  `${VAR}` placeholders)

### Security

- All secrets in `.env` (gitignored); `config.py` loader expands `${VAR}`
  placeholders in `config/*.json`
- Bookmark API validates ID pattern (`^[a-zA-Z0-9_-]{1,64}$`), caps request
  body at 1 KB, caps bookmark list at 5,000
- All file writes are atomic (temp + `os.replace`)
- HTTP responses carry `X-Content-Type-Options: nosniff`, `X-Frame-Options: DENY`,
  `Referrer-Policy: no-referrer`
- CORS restricted to `http://localhost:8080`
- HTML output goes through `escapeHtml()` and `safeUrl()` to prevent XSS
- SQLite uses WAL mode for crash safety

### Known limitations

- arXiv is the only source providing structured category metadata; other
  sources rely on keyword scoring only
- The keyword classifier is hand-tuned and does not learn from user feedback
- The dashboard is single-user (no auth, by design — see SECURITY.md)
- Telegram digest is sent to all categories in a single batch; no per-user
  subscription control

### What's in the project

| Area            | What's there                                        |
| --------------- | --------------------------------------------------- |
| License         | MIT                                                 |
| Python          | 3.8 – 3.12                                          |
| Runtime deps    | `requests` (only)                                   |
| Test runner     | stdlib `unittest`                                   |
| CI              | GitHub Actions (`.github/workflows/test.yml`)       |
| Dep updates     | Dependabot, weekly, scoped                          |
| Contributing    | `CONTRIBUTING.md` + Conventional Commits            |
| Code of conduct | Contributor Covenant 2.1                            |
| Security policy | `SECURITY.md` + GitHub Security Advisories          |
| Citation        | `CITATION.cff` (auto-BibTeX on GitHub)              |
| Docs            | `README.md` + `docs/{ARCHITECTURE,SCRAPERS,CLASSIFIER,DEDUP}.md` |
| Changelog       | `CHANGELOG.md` (Keep-a-Changelog 1.1.0)             |

### Thanks

To the maintainers of arXiv, GitHub, BleepingComputer, TheHackersNews,
KrebsOnSecurity, Yahoo Finance, Investing.com, TechCrunch, The Verge,
Ars Technica, CNBC, MarketWatch, Google News, NewsAPI, and Finnhub for
the public data sources that make this possible.
