# Changelog

All notable changes to Bloomsberg News are documented in this file. The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Planned
- Discord / Slack digest support
- WebSocket live updates on the dashboard
- Semantic dedup using sentence embeddings (in addition to Jaccard)
- RSS aggregator mode with OPML import
- Configurable classifier training from user feedback

---

## [1.0.0] - 2026-06-04

Initial public release. The system has been in private use for several months; this release marks the first version packaged for distribution.

### Highlights

- 8 scrapers covering arXiv (13 feeds), GitHub, NewsAPI, dedicated cybersecurity feeds, Finnhub finance, Google News (14 queries), and Markets.
- 6-category classifier with arXiv category as a strong prior and a graceful "Uncategorized" fallback.
- Two-layer deduplication: Jaccard title similarity (≥0.80) plus arXiv version tracking.
- 3-page dashboard with dark/light theme, WCAG-AA contrast, full keyboard nav, and screen-reader landmarks.
- Bookmarks with server-side persistence, input validation, and star buttons on every article card.
- Telegram digest: top 3 articles per category to the main channel + 6 sub-channels with inline buttons.
- 12-hour scheduler with smart catch-up, registry autostart on Windows, foreground loop on Linux/macOS.
- Local-only deployment: dashboard binds `127.0.0.1`, secrets are env-driven, no cloud, no third-party data sink beyond Telegram and the free-tier APIs.

### Security

- All secrets in `.env` (gitignored); `secrets.py` loader expands `${VAR}` placeholders in `config/*.json`.
- Bookmark API validates ID pattern (`^[a-zA-Z0-9_-]{1,64}$`), caps request body at 1 KB, caps bookmark list at 5,000.
- All file writes (bookmarks, dashboard data, scheduler state) are atomic (temp + `os.replace`).
- HTTP responses carry `X-Content-Type-Options: nosniff`, `X-Frame-Options: DENY`, `Referrer-Policy: no-referrer`, `Cache-Control: no-store` for API endpoints.
- CORS restricted to `http://localhost:8080`.
- HTML output goes through `escapeHtml()` and `safeUrl()` to prevent XSS via article content.
- SQLite uses WAL mode for crash safety.

### Testing

- 18 unit tests covering title similarity, classifier fallback, ID validation, secrets loader, bookmark API input limits, and scheduler state-machine transitions. Run with `python -m unittest tests.test_fixes -v`.

### Known limitations

- arXiv is the only source providing structured category metadata; other sources rely on keyword scoring only.
- The keyword classifier is hand-tuned and does not learn from user feedback. Adding new keywords is a code change in `news_tool.py`.
- The dashboard is single-user. There is no authentication — the server is bound to localhost by design.
- Telegram digest is sent to all categories in a single batch; there is no per-user subscription control.

---

## [0.x] - Pre-release development (2026-01 to 2026-05)

Pre-1.0 development history, condensed:

### Added
- Initial pipeline skeleton with 4 scrapers (arXiv, GitHub, NewsAPI, Security RSS)
- SQLite-backed dedup log
- First dashboard (single-page) with category grid
- Telegram bot with category sub-channels

### Changed
- Migrated from filesystem-only storage to SQLite + filesystem hybrid
- Reworked classifier to use arXiv subject category as a prior signal
- Replaced inline-deduplication with Jaccard similarity scoring
- Refactored dashboard from one page to three (landing, filters, bookmarks)
- Switched secrets storage from JSON files to `.env` with placeholder expansion
- Replaced `python -m http.server` with a custom `ThreadingHTTPServer` subclass for security headers and 4xx/5xx logging
- Replaced 0.5-confidence "AI-Applications" fallback with "Uncategorized" (no category is better than a wrong one)

### Fixed
- Hardcoded `0.0.0.0` binding → `127.0.0.1`
- Hardcoded API keys in tracked config files → env placeholders
- Bookmark API ID truncation on IDs >64 chars → pattern rejection
- Race condition in concurrent bookmark writes → atomic temp + rename + lock
- `formatDateShort` timezone bug for date-only ISO strings → local-parse instead of UTC
- Classifier 0.50 confidence defaulting to "AI-Applications" → "Uncategorized"
- GitHub scraper dropping per-repo descriptions → dict-based parser
- Hardcoded `path` in `news_tool.py` → relative to `BASE` directory
- Atomic write for `dashboard_data.json` (was using non-atomic `open + write`)
- Pipeline crash on `requests.exceptions.SSLError` from a single scraper → per-scraper try/except
- HTML entity double-escaping in summaries → single decode with unescape
- Memory leak in 1-hour scheduler loop → 12h cadence with explicit checkpoints
- Pipeline logging everything to stdout → split between `pipeline.log` and `pipeline_stdout.log`

### Removed
- Fictional "6 worker" architecture from README
- Dead `run_all.ps1` script referenced in README
- Dead `prompts/worker*.md` files
- Dead `scripts/classify.py` and `DAILY_CHECKLIST.md`
- Leftover `index/` directory of older-pipeline artifacts
- Hardcoded GitHub link in dashboard footer (replaced with "Local" indicator)
- Fictional "production" tier of storage stats from README
