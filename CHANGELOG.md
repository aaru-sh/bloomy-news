# Changelog

All notable changes to Bloomy News are documented in this file. The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Planned
- Discord / Slack digest support
- WebSocket live updates on the dashboard
- Semantic dedup using sentence embeddings (in addition to Jaccard)
- RSS aggregator mode with OPML import
- Configurable classifier training from user feedback
- Tighten keyword lists to bring the keyword-only classifier back above the 0.80 gate (currently 63.3% on the regression set, surfaced by the 1.1.2 gate split)
- `news_tool.py` split into `scrapers/` package + slim orchestrator (do at 9th source; was deferred from 1.3.0)
- Bookmark persistence: mirror JSON to articles table (deferred from 1.1.0, deferred again from 1.1.1, deferred again from 1.1.2, deferred again from 1.2.0, deferred again from 1.3.0)

---

## [1.3.0] - 2026-06-05

**Type hints on the entire public surface.** A maintenance-quality
release — no behavior changes, just static type information that
catches the "function changed its return shape" class of bugs
before they hit tests, and gives editors/IDEs something useful to
hover over.

### Highlights
- **mypy added to the dev toolchain.** `mypy>=1.10.0` in `requirements-dev.txt`, `mypy.ini` at the project root scoped to `news_tool.py, database.py, scripts/, dashboard/`. Runs locally with `python -m mypy news_tool.py database.py`; the only Python-version requirement is mypy's own runtime (3.10+), the code itself stays 3.8-compatible at runtime because we used `Optional` / `List` / `Dict` / `Tuple` from the `typing` module rather than the 3.10+ `X | None` syntax.
- **`news_tool.py` (982 lines, 27 functions) fully type-hinted.** Added `Article`, `ArticleList`, `CategoryMap`, `ClassifyResult` type aliases and a `from typing import ...` import block. Every public function now declares parameter and return types. The two `max(scores, key=...)` calls use a `lambda c: scores[c]` shim to satisfy mypy's strict `Callable` signature on `max`. The `_get_embedding_model` Optional `Connection` problem is gone (mypy 2.x requires the runtime type narrowing via `assert`).
- **`database.py` (651 lines, 24 functions) fully type-hinted.** Same `Article` / `ArticleList` aliases. Functions that took `conn=None` and called `if own_conn: conn = get_connection()` got an explicit `assert conn is not None` after the assignment so mypy knows `conn` is non-None inside the `try` block.
- **Type-narrowing fixes.** `_load_labeled_samples()` now raises a real `RuntimeError` when `importlib.util.spec_from_file_location()` returns `None` (e.g. `tests/test_classifier.py` missing at runtime) rather than crashing with a cryptic `AttributeError` on `spec.loader.exec_module`. The `get_articles` `params: List[Any]` annotation lets the FTS5/LIKE `extend(fts_ids)` work cleanly.

### Verification
- `python -m mypy news_tool.py database.py` → `Success: no issues found in 2 source files`
- `python -m unittest discover -s tests` → 103 tests pass, 1 skipped (real-world distribution smoke test, needs populated `news.db`)

### Not changed in this release
- `news_tool.py` split — still deferred. The type hints are the precondition: with `Article` / `ArticleList` / `CategoryMap` / `ClassifyResult` aliases in place, the split is now a mechanical `from news_tool_module import ...` rather than a search-and-replace.
- Bookmark persistence — still blocked on `TestFreshInstallFlow` sys.modules pollution.

### Future type work
- `scripts/` (scheduler, evaluate_classifier, telegram_bot) — currently excluded from mypy.ini scope to keep this release focused. Next pass.
- `dashboard/` (serve.py, generate_data.py) — same.

---

## [1.2.0] - 2026-06-05

**Scraper test coverage, feedparser swap, coverage in CI, and a
Dockerfile.** A feature release that hardens the repo against the
two most likely sources of silent breakage (feed shape changes and
RSS parser bugs) and packages the dashboard for non-Windows deployment.

### Highlights
- **Scraper correctness tests** (`f2c799e`, `34d30b2`, `c94df85`): 39 new tests across three files covering all 8 scrapers and `parse_rss()`. Mocks `news_tool.fetch_url` and `fetch_json` so no real HTTP. Tests assert feed list count (13 arxiv, 3 cybersec, 3 tech, 2 markets, 3 google_news, 3 newsapi, 3 github languages, 1 finnhub), per-article `source_key` tagging, `subcategory` on arxiv, and edge cases (CDATA, HTML entities, empty/malformed input, missing required fields, the dc:creator gap that feedparser now closes).
- **feedparser swap** (`85550bb`): `parse_rss()` now uses `feedparser.parse()` as the primary path. Handles RSS 2.0, RSS 1.0, Atom, all date formats, CDATA, HTML entities, `dc:creator`, and inline HTML in summaries. The legacy regex parser is preserved as `_parse_rss_regex()` and called via `logger.warning` if feedparser raises — we never want a single malformed feed to drop the whole scrape. `feedparser>=6.0.0` added to `requirements.txt`.
- **Coverage.py in CI** (`f362803`, `2e8f021`): `requirements-dev.txt` pins `coverage>=7.0`. `.coveragerc` disables the `no_source` warning that the fresh-install test's tempdir copies trigger and excludes trivial lines. The test workflow now runs `coverage run -m unittest discover -s tests` then `coverage report --fail-under=50`. Current measured coverage: **67%** (was 57% after the scraper tests, would be ~70% with both scraper + feedparser tests factored in). Threshold is intentionally conservative; raise as coverage grows.
- **Dockerfile** (`6dc4ebc`): `python:3.11-slim` base, non-root user (uid 1000), `HEALTHCHECK` on `http://127.0.0.1:8080/`, default `CMD` runs `dashboard/serve.py`. The dashboard binds localhost only (per repo convention); the `-p` flag must map `127.0.0.1:8080:8080` explicitly to keep it off the LAN. `.dockerignore` excludes `.git`, `news.db`, `dashboard/data/*.json`, `.env`, and IDE/OS files.

### Test surface
- `tests/test_scraper_arxiv.py` (163 lines, 11 tests): `TestArxivParseRss` (single item, multiple items, CDATA, HTML entities, summary truncation, missing-field rejection, `dc:creator` capture, Atom fallback), `TestScrapeArxivFeedList` (13 categories, subcategory tagging, empty-fetch handling), `TestScrapeArxivRateLimitRegression` (zero-rate-limit contract), `TestParseRssFallbackToRegex` (regex fallback when feedparser raises), `TestParseRssFeedparserPrimary` (feedparser is the primary path, not the fallback).
- `tests/test_scraper_json.py` (292 lines, 12 tests): `TestScrapeGithub` (3-repos-per-language, missing-description fallback, empty HTML, ISO published timestamp), `TestScrapeNewsapi` (missing-key short-circuit, 3-category parse, error-status rejection, falsy-response), `TestScrapeFinance` (Finnhub JSON parse with epoch->iso, no-key falls through to RSS, empty list, epoch=0 doesn't crash).
- `tests/test_scraper_rss.py` (353 lines, 16 tests): `TestScrapeCybersec` (3 feeds, failed-fetch, malformed), `TestScrapeTech` (3 feeds with source_keys, Atom `<entry>` fallback), `TestScrapeGoogleNews` (3 queries, redirect URL resolution, non-Google URLs skip the resolver), `TestScrapeMarkets` (2 feeds, failed-fetch), `TestParseRssEdgeCases` (Atom fallback, HTML entities, empty RSS, `SOURCE_NAMES` lookup), `TestResolveGoogleNewsRedirect` (non-Google passthrough, Google URL returns original on failure).

### Verification
- 103 tests, 1 skipped (real-world distribution, needs populated `news.db`)
- Coverage: 67% (target: 50%, threshold can be raised)
- `node --check` was not affected (no JS changes)
- `python -m coverage report --fail-under=50 --ignore-errors` exits 0

### Not changed in this release
- F (type hints) — deferred. Reviewer's "refactoring without types is a coin flip" concern is real but not blocking for solo work.
- G (news_tool.py split) — deferred. YAGNI for 8 scrapers; do at 9th source.
- E (NewsAPI/Finnhub rate-limit tracking) — deferred until actually throttled.
- Bookmark persistence — deferred again (sys.modules pollution in `TestFreshInstallFlow` still blocks the cleanest implementation).

---

## [1.1.2] - 2026-06-05

**Scrape surface, classifier visibility, and CI gate split.** A follow-up
patch to v1.1.1. The arXiv feed list now matches what the docs claim,
the Telegram digest is built from the in-memory categorized dict instead
of a fresh DB query, article embeddings are persisted to the database,
and the classifier CI gate is split into keyword / embedding / combined
sub-gates so a regression in any one path is named in the log.

### Highlights
- **arXiv: 13 feeds** (`4adfc0c`): the `scrape_arxiv` feed list is replaced with the 13 categories the docs and CHANGELOG already claimed (cs.AI, cs.LG, cs.CL, cs.CV, cs.NE, cs.RO, cs.IR, cs.MA, cs.HC, stat.ML, eess.SP, q-fin.ST, cs.CR). The README, `docs/SCRAPERS.md`, and `config/sources.json` now agree.
- **Telegram digest uses the categorized dict** (`97cb37f`): `post_to_telegram` is refactored into `_select_top_articles`, `_format_digest`, and `_send_telegram_message`. The digest is built from the in-memory `categorized` arg, not a re-query of today's articles from the DB. Falls back to the DB only when `categorized` is empty, with a `logger.warning`.
- **Article embeddings persisted** (`e24472b`): `store_article` now accepts `embedding: list[float] | None = None` and writes it to the existing `embedding` BLOB column. `load_article_embedding()` reads it back. The `classify_*` helpers return a 5-tuple `(category, confidence, tags, subcategory, embedding)` so the embedding survives the classify→store round trip without recomputation. Schema is unchanged.
- **Jaccard passes consistent string types** (`9ab4deb`): `title_similarity` gains a `pre_processed: bool = False` flag. `is_duplicate` passes `True` for stored `title_words` (the canonical pre-tokenized join), `False` for the raw `title` fallback. Eliminates the silent tokenization drift that produced different Jaccard scores for the same pair.
- **`migrate_from_files` logs exceptions** (`870b283`): the bare `except:` is replaced with `except Exception as e: logger.warning(...)`. `import logging` + module-level `logger` added. Tests cover `IOError` and `UnicodeDecodeError`.
- **`ARXIV_RATE_LIMIT` honored** (`61a496b`): `scrape_arxiv` reads `os.environ.get("ARXIV_RATE_LIMIT", "3.0")` and sleeps between feed fetches. Default of 3.0s matches arXiv's published guideline.
- **Classifier visibility** (`f227f0b`): `news_tool.EMBEDDING_AVAILABLE` is a module-level bool. `main()` prints `Classifier: embedding` or `Classifier: keyword (install sentence-transformers for better accuracy)` at pipeline start. `requirements.txt` gets a comment block; the README gets a one-line callout near the install instructions.
- **CI gate split** (`0b2b359`): `evaluate_classifier.py` now reports `keyword=...  embedding=...  combined=...` and exits 0 only if all three sub-gates pass: `KEYWORD_MINIMUM_ACCURACY=0.80`, `EMBEDDING_MINIMUM_ACCURACY=0.95`, `COMBINED_MINIMUM_ACCURACY=0.90` (the legacy `MINIMUM_ACCURACY` constant is kept as an alias). A new `TestRealWorldDistribution` smoke test runs `evaluate_classifier_accuracy` over the live `news.db` if it has more than 50 non-`Uncategorized` articles; skipped otherwise.
- **README "4 feeds" -> "13 feeds"**: three places in the README (feature list, install progress, repo tree) corrected to match the actual code and `docs/SCRAPERS.md`.

### Known behavior change
- The keyword-only classifier is currently at **63.3%** on the regression set, below the 0.80 keyword sub-gate. On a machine that does not install `sentence-transformers`, the gate now **fails correctly** (exit 1) where v1.1.1 would have shown 100% combined. The follow-up — tighten keyword lists — is tracked in `[Unreleased]`. Install `sentence-transformers` to get the full 100% combined path.

### Test surface
- `tests/test_fixes.py`: `TestTelegramCategorizedSource` (2 tests, categorized-dict source + DB-fallback path), `TestArxivRateLimit` (2 tests, env var read + default), `TestMigrateFromFilesLogs` (2 tests, IOError + UnicodeDecodeError), `TestJaccardPreprocessedVsRaw` (1 test), `TestEmbeddingStoredOnStoreArticle` (4 tests, store/load round-trip + None handling), `TestClassifierVisibility` (1 test, `EMBEDDING_AVAILABLE` module-level bool).
- `tests/test_classifier.py`: `TestGateThresholds` (5 tests, per-gate threshold constants), `TestRealWorldDistribution` (1 test, skipped without populated `news.db`), `test_classifier_return_shape` updated to assert 5-tuple length.

### Not changed in this release
- Bookmark persistence to the `articles` table remains deferred (now deferred three times). The `TestFreshInstallFlow` sys.modules pollution still blocks the cleanest implementation; needs the test rewritten to use a subprocess.
- Real-world classifier accuracy test (review item 11) is partially addressed by `TestRealWorldDistribution`; a true accuracy test requires labeled data — manual labeling or LLM-as-judge pipeline is out of scope for a patch release.

---

## [1.1.1] - 2026-06-05

**Bug fixes, classifier hardening, and dashboard modernization.** A follow-up
patch to v1.1.0. No new features; no breaking changes. The classifier is
less prone to substring false positives, the dashboard JavaScript is
fully ES6+, the database search and dedup paths use SQL pre-filtering
where they previously looped in Python, and several over-claims in the
docs were corrected.

### Highlights
- **Atomic bookmark writes** (`e2f272b`): `toggle_bookmark` in `database.py` now uses `tempfile.mkstemp` + `os.replace` and is guarded by `_BOOKMARKS_LOCK`. The dashboard server already had this since v1.1.0; the lower-level helper is now also crash-safe under concurrent requests.
- **FTS5 article search** (`e2f272b`): `get_articles(query=...)` now routes through the `articles_fts` MATCH expression. Behavior is unchanged for callers that don't pass a query; non-search calls still use the indexed columns. Falls back to `LIKE` only if the FTS5 query parses to nothing or the FTS5 table is unavailable.
- **SQL Jaccard pre-filter** (`e2f272b`): `is_duplicate` narrows candidates in SQL by shared significant words (length >= 4) before the Python Jaccard loop runs. Cuts the loop from O(200) to O(small) per call on a typical 5000-article database.
- **Word-boundary keyword classifier** (`44580bc`): `_classify_keywords` now tokenizes with `\b[\w'-]+\b` and matches by token-set membership. Sub-3-char keywords and pure stopwords are dropped. Multi-word keywords require all words to appear. Fixes the `social security -> Cybersecurity` and `runway model -> ML-Research` false positives.
- **Classifier accuracy metrics** (`44580bc`): new `evaluate_classifier_accuracy()` in `news_tool.py` returns `{correct, total, accuracy, by_category}` and prints a one-line CLI summary. `scripts/evaluate_classifier.py` wraps it and exits 0 only if accuracy >= `MINIMUM_ACCURACY` (0.90), suitable for CI gating.
- **Dashboard ES6+** (`c6cc52a`): `dashboard/app.js`, `app-filters.js`, and `app-bookmarks.js` are fully modernized — `const`/`let`, arrow callbacks, template literals, rest params. No bundler, no build step. The dashboard remains a static site served by `dashboard/serve.py`.
- **Docs audience split** (`0726c05`): the "Concepts for newcomers" block (RSS / SQL / API key explanations) is moved out of `README.md` and consolidated into `docs/NEWCOMERS.md`. The main README now assumes the reader knows what RSS, SQL, and JSON are, and links to the newcomers file in one line.
- **SECURITY.md atomicity claim** (`0726c05`): the over-claim is replaced with an accurate description that names both `dashboard/serve.py` and `database.py` as crash-safe under concurrent requests on the localhost deployment.
- **Scheduler `--verify`** (`eeacd73`): read-only diagnostic that confirms the registered Python path exists and is launchable, the repo path resolves, the database file is writable, the `.env` is present, and the autostart is registered. Prints one pass/fail line per check with a remediation hint. Exits non-zero on any failure. `--install` now runs `--verify` immediately after registering the task, so silent failures (moved venv, broken path encoding) are caught at install time, not at first scheduled run.

### Test surface
- `tests/test_fixes.py`: `test_bookmark_race` (concurrent toggles, no lost updates), `test_fts5_search` (FTS5 routing), `test_jaccard_prefilter` (SQL pre-filter coverage). Skipped via inline guards when the FTS5 table or `_BOOKMARKS_LOCK` symbol is missing.
- `tests/test_classifier.py`: `test_keyword_word_boundary` (no false positives on "social security" or "runway model" in disambiguating context), `test_evaluate_classifier_accuracy` (smoke test the evaluate API shape).
- `node --check` passes on all three dashboard JS files.

### Verification
- `python -m unittest discover -s tests -v` — OK, 1 CI-only skip.
- `python scripts/evaluate_classifier.py` — `Accuracy: 100.0% (30/30)  keyword=63.3%  embedding=100%` PASS.
- `python scripts/scheduler.py --verify` — all 6 checks pass on the dev box.
- Date-filter regression test (clicking 5 June on the calendar) still returns 88 articles, confirming the v1.1.0 hotfix is intact.

### Not in 1.1.1 (deferred)
- **Bookmark persistence to the articles table** — still deferred. The `TestFreshInstallFlow` test pollution issue from v1.1.0 was not addressed in this release; the auto-generated `dashboard_data.json` is still the only bookmark storage.
- **GitHub trending scraper** still uses regex against rendered HTML (out of scope per the "don't touch scrapers" constraint; a follow-up to use the GitHub REST API is planned).
- **RSS parser** still uses regex (out of scope per the "no new external dependencies" constraint; `feedparser` is not added).

### Migration
None. v1.1.0 -> v1.1.1 is a drop-in replacement. The classifier and bookmark changes are backward-compatible; the FTS5 search falls back to `LIKE` if FTS5 is unavailable, and the keyword classifier no longer returns categories that the substring matcher would have spuriously matched.

---

## [1.1.0] - 2026-06-05

**Code quality and classifier overhaul.** The pipeline is now faster, the classifier is meaningfully more accurate, and the docs match the code. No breaking changes to the public surface or the user experience.

### Highlights
- **Pipeline connection refactor** (`c4b1c33`): each pipeline run now uses a single SQLite connection for all article inserts (vs 3 connections per article). On a typical 200-500 article run this is ~600-1500 fewer round-trips, and the whole run commits as one transaction.
- **Classifier centroids** (`9df0ffb`): replaced single-description similarity with multi-example centroids (12 representative article titles per category). Accuracy on the labeled set jumped from 80% to 100% (30/30); `MINIMUM_ACCURACY` raised to 0.90.
- **Classifier robustness** (`332385e`, `ec39ed6`): when the sentence-transformers model can't load (HF rate-limit, OOM, network), the classifier now caches the failure and falls back to the keyword classifier for the rest of the process instead of crashing the pipeline.
- **Database cleanup** (`a062922`): NULL `title_words` rows from older pipelines are now backfilled on `init_db()`; orphaned `is_starred` column and `mark_starred()` function removed (dead code).
- **Google News redirects** (`349f04f`): Google News redirect URLs (`news.google.com/articles/...`) are now resolved to the underlying article URL via HEAD-then-GET with `<link rel="canonical">` fallback. Articles no longer appear in bookmarks / Telegram digests as "google.com/articles/..." placeholders.
- **Doc accuracy** (`11ea5e0`): README, `docs/CLASSIFIER.md`, `docs/SCRAPERS.md`, and `docs/PROJECT_STRUCTURE.md` now match the code (arXiv 4 feeds / Google News 3 queries, classifier trade-off documented).
- **Concurrency test** (`c0c48bb`): verifies 2 simultaneous pipeline runs don't double-insert; verifies 5 threads racing on the same URL only let one win.

### Fixed
- `_classify_embedding` no longer matches the literal "." against LLM at 0.15 confidence when the article is empty (it now short-circuits to `Uncategorized`).
- Classifier correctly returns LLM (not Neural-Nets) for "New transformer architecture for large language models" — centroid example added.
- Google News redirect URLs no longer appear as the bookmark / Telegram URL.

### Not in 1.1.0 (deferred)
- **Bookmark persistence fix** (mirror JSON to `articles.is_bookmarked`): the code change was implemented but the test suite breaks an unrelated `test_fresh_install.TestPathResolution` assertion via an `import database` side-effect in `dashboard/serve.py` that pollutes `sys.modules`. The "make clean wipes bookmarks" footgun is real but small; will revisit in 1.1.1 with a cleaner test isolation strategy.
- **CI model cache**: the classifier accuracy test still skips in CI (HF rate-limits the shared runner IP space). Local 100% accuracy is the gating signal; will revisit when GitHub-hosted runners get a more permissive HF tier.

---

## [1.0.0] - 2026-06-04

**Released.** Initial public release. The system has been in private use for several months; this release marks the first version packaged for distribution.

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

- All secrets in `.env` (gitignored); `config.py` loader expands `${VAR}` placeholders in `config/*.json`.
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
