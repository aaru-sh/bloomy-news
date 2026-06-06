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
- `news_tool.py` split into `scrapers/` package + slim orchestrator (shipped in 1.4.0)
- Bookmark persistence: mirror JSON to articles table (shipped in 1.4.2)
- Test rewrite: `test_fresh_install.py` -> subprocess-based (shipped in 1.4.2)

---

## [1.4.2] - 2026-06-06

**Bookmark persistence in the SQLite database.** A sub-release
of the 1.4 line. The JSON bookmark store is now mirrored to a
new `bookmarked` column in the `articles` table, so the
bookmark state survives a clean rebuild of `dashboard_data.json`.
The blocker that prevented this — `TestFreshInstallFlow`'s
`sys.modules` pollution — is fixed in the same release: that
test now runs in a subprocess.

### Added
- **`bookmarked INTEGER NOT NULL DEFAULT 0`** column on
  `articles`, with a matching `idx_articles_bookmarked` index
  and an `ALTER TABLE` migration for existing DBs (added inside
  the same `try/except` pattern as the `is_read` and `title_words`
  backfills). The column is added to the `CREATE TABLE` schema
  for new DBs and to the post-create migration for pre-existing
  DBs that predate the column.
- **`database.set_bookmarked(article_id, value)`** — set the
  bookmark flag for a single article by integer id.
- **`database.is_bookmarked(article_id)`** — read the flag
  (unknown ids return False, matching the column default).
- **`database.set_bookmarked_by_hash_prefix(prefix, value)`** —
  mirror a JSON toggle to the DB by the 16-char hex prefix the
  dashboard uses as the article id. Returns True on match, False
  on no match. This is the entry point serve.py uses.
- **`database.get_bookmarked_article_ids()`** — list of integer
  ids currently bookmarked (handy for batch operations later).

### Changed
- **`dashboard/serve.py` mirrors every bookmark toggle to the
  articles table.** Best-effort: a DB failure is logged but the
  JSON response still returns 200 (the JSON is the source of
  truth for the user-facing view). Adds an `import database`
  at the top with the project root inserted into `sys.path`
  so the import works regardless of the current working
  directory.
- **`tests/test_fresh_install.py::TestFreshInstallFlow` now
  runs in a subprocess.** A small helper `_run_in_subprocess`
  takes a temp dir + a Python script, spawns a fresh interpreter
  with `sys.path[0]` and CWD pointing at the temp dir, and
  surfaces the script's stdout/stderr on failure. The
  `importlib`-based import dance is gone; the test no longer
  touches the real test process's `sys.modules`, which was
  blocking the bookmark-persistence work.
- **`tests/test_fresh_install.py::TestServerSmoke` mocks
  `serve.database`.** The new mirror in serve.py means
  `TestServerSmoke` would otherwise write to the real `news.db`
  on every toggle. The test now patches `serve.database` to a
  `MagicMock` in `setUp` and asserts the mock was called with
  the right args.
- **`tests/test_fresh_install.py` adds
  `test_bookmark_toggle_mirrors_to_db`** and updates
  `test_bookmark_id_rejected` to assert that the mirror is NOT
  called for a 400.

### Added (tests)
- **`tests/test_database_bookmark.py`** — 8 new tests covering
  the column creation, the ALTER TABLE migration, the
  round-trip of set/is, the hash-prefix lookup, the default
  value for new articles, and the unknown-id no-op.

### Verification
- 112 tests pass (1 skipped — the `TestRealWorldDistribution`
  smoke test that needs a populated `news.db`), up from 103
- mypy clean across `news_tool.py` and `database.py`
- Live DB migration verified: `ALTER TABLE articles ADD COLUMN
  bookmarked INTEGER NOT NULL DEFAULT 0` adds the column
  without error on the existing `news.db`
- `serve.database.set_bookmarked_by_hash_prefix` is invoked
  on every successful toggle and never on a 400

### Why a sub-version of 1.4 (not 1.5)
- The change is small and focused (one column, four helper
  functions, one mirror call, one test rewrite, one new test
  file). It does not justify a feature-level bump to 1.5.
- It is not purely a bug fix either — the column is new
  schema — but it is the same scope as 1.4.0 and 1.4.1
  (bookmark persistence has been deferred from 1.1.0 onward;
  the 1.4.2 release finally unblocks it without claiming a
  new feature number).

---

## [1.4.1] - 2026-06-06

**Launcher fixes, storage cleanup, logging fix, and GitHub
button.** A maintenance patch that ships the runtime issues
observed after the v1.4.0 build, the 100 MB → 15 MB storage
cleanup, and the GitHub link in the dashboard header. No
behavior changes to the pipeline, the classifier, the
digest, or the data layer. The `scrapers/` split from v1.4.0
is unchanged.

### Fixed

- **`LAUNCH_DAILY.bat` UTF-8 BOM removed.** The file was
  saved with a UTF-8 byte-order mark (`0xEF 0xBB 0xBF`)
  which `cmd.exe` does not strip from `.bat` files. The BOM
  was echoed as `∩╗┐` before `@echo off` and produced a
  spurious `'∩╗┐@echo off' is not recognized as an internal
  or external command, operable program or batch file`
  message at every run. The BOM also caused `@echo off` to
  be skipped, so every subsequent command was echoed to
  the terminal. Re-saved as UTF-8 **without** BOM via
  `UTF8Encoding($false)` in PowerShell.
- **Server-start polling loop in `LAUNCH_DAILY.bat`.** The
  original `timeout /t 2 /nobreak` then `netstat` check was
  too eager on slow first runs and printed a misleading
  `ERROR: Server failed to start` even when the server was
  binding successfully within the next second. Replaced with
  a 10-attempt polling loop (1 s between attempts) using
  `setlocal EnableDelayedExpansion` and `!ATTEMPT!` for the
  counter.
- **`serve.py` no-cache headers now cover HTML / JS / CSS.**
  `end_headers()` previously only added `Cache-Control:
  no-store, must-revalidate` for `/data/dashboard_data.json`
  and `/data/bookmarks.json`. The other static files
  (`index.html`, `app.js`, `app-filters.js`,
  `app-bookmarks.js`, `styles.css`) relied on
  `SimpleHTTPRequestHandler`'s default header set, which
  lets the browser cache them and force a hard refresh
  after every pipeline run. The check is now "every
  non-`/api/*` path gets no-cache". API endpoints keep
  their per-endpoint `Cache-Control` set by `_send_json`.
- **`LAUNCH_DAILY.bat` no longer "stuck" at the end.** The
  previous script ended with `goto :eof`, which returned to
  the parent `cmd.exe` and left the terminal window open
  with no further output. Now `pause >nul` runs before
  `goto :eof` (success path) and before `exit /b 1` (error
  path).
- **`serve.py` log redirect bug fixed.** The launcher's
  `start /B python ... > log 2>&1` was broken on Windows:
  cmd.exe's `>` redirect goes to `start`, not to the
  spawned python process, so `logs\server.log` was always
  0 bytes even when the server failed. `serve.py` now owns
  its own log file via Python's `logging` module and a
  `RotatingFileHandler` (1 MB max, 1 generation kept),
  written to `logs/server.log`. The launcher no longer
  redirects server output — just `start "" /B python -u
  dashboard\serve.py`.
- **Log rotation for `logs\pipeline_stdout.log`.** The
  pipeline run captures stdout/stderr to this log. A
  size-based rotation block at the top of
  `LAUNCH_DAILY.bat` rotates the log when it exceeds 1 MB
  (one generation kept as `.1`).

### Storage cleanup

- **`.mypy_cache/` removed** (94.57 MB → 0). The mypy
  incremental cache was 16 files of 4-8 MB each. v1.3.0
  added mypy to the dev toolchain and each `mypy
  news_tool.py database.py` run wrote one cache file;
  the cache grew to 94 MB over a single day of type-hint
  development. Already in `.gitignore` (line 11) so
  deletion is safe; regenerates on next mypy run.
- **`__pycache__/`, `.playwright-mcp/`,
  `dashboard-initial.png`, `logs\server_test*.log`
  removed** (~0.4 MB). All already in `.gitignore` or
  untracked.
- **`.gitignore` updated** to catch `dashboard-*.png` and
  `*-initial.png` patterns in the project root, so future
  debug screenshots don't sneak into the working tree.

After cleanup, the project is **15.75 MB** total (was
107 MB), and the git-tracked portion is unchanged.

### Added

- **GitHub repo button in the dashboard header.** Added
  to `index.html`, `filters.html`, and `bookmarks.html`
  between the existing nav links and the theme toggle.
  Styled with the existing `.nav-link` class for
  consistency, with the GitHub octocat SVG (14×14, current
  color), `target="_blank"`, `rel="noopener noreferrer"`,
  and `title="View source on GitHub"` for accessibility.
  Link target: <https://github.com/aaru-sh/bloomy-news>.

### What was deferred

- **Bookmark persistence** — still deferred to v1.5.0.
- **Test rewrite for `TestFreshInstallFlow`** — still
  required before bookmark persistence can land.
- **`dashboard_data.json` gzip compression** — the JSON
  is 4.58 MB (6726 articles). Compression would save ~3
  MB but requires `serve.py` to decompress on every
  `/api/articles` request, which adds startup and
  per-request CPU cost for a localhost dashboard that
  reads the file directly. Tracked for a future release.

### Verification

- 103 tests pass, 1 skipped (the real-world distribution
  smoke test that needs a populated `news.db`)
- Project storage: **15.75 MB** (was 107 MB before
  cleanup)
- BOMs verified gone on all touched files
  (`LAUNCH_DAILY.bat` first 3 bytes: `0x40 0x65 0x63`
  = `@ec`; `dashboard/serve.py` first 3 bytes: `0x23
  0x21 0x2F` = `#!/`; HTML files: `0x3C 0x21 0x44` =
  `<!D`)
- `server.log` now populates on server start (verified
  via `Start-Process python -u dashboard\serve.py`,
  logs `Dashboard server starting on http://127.0.0.1:8080`)

---

## [1.4.0] - 2026-06-05

**`news_tool.py` split into 13 focused files.** A maintenance-quality
release — no behavior changes, the pipeline scrapes, classifies,
stores, and digests exactly the same articles as v1.3.0. The only
change is module organization: every file in the project is now
under 280 lines, and adding a 9th source is a 30-line new file in
`scrapers/` instead of editing a 1000+ line monolith.

### Highlights
- **`scrapers/` package (11 files).** `_http.py` is the shared
  HTTP / `SOURCE_NAMES` / type-alias layer. `_rss.py` owns the
  feedparser + regex fallback path. `_keywords.py` owns the
  CATEGORY_KEYWORDS, SUBCATEGORY_KEYWORDS, and tokenization used
  by the keyword classifier. The 8 source scrapers (arxiv, github,
  newsapi, cybersec, tech, finance, google_news, markets) are
  each 18-72 lines and contain only the feed list and any
  source-specific logic (arXiv rate limit, GitHub HTML regex,
  Google News redirect resolver).
- **`classifier.py` (257 lines).** Owns the embedding state
  (`_embedding_model`, `_category_embeddings`, `_embedding_load_failed`),
  the `CATEGORY_EXAMPLES` centroid prompts, and the three
  classification functions (`_classify_embedding`,
  `_classify_keywords`, `classify_article`). The gate thresholds
  (KEYWORD_MINIMUM_ACCURACY=0.80, EMBEDDING=0.95, COMBINED=0.90)
  live here too.
- **`telegram.py` (163 lines).** Owns the digest formatter,
  the `urllib`-based `_send_telegram_message` (so tests can
  monkey-patch it without touching urllib), the category/emoji
  constants, and `post_to_telegram`. Reads the `config/telegram.json`
  config the same way as before.
- **`news_tool.py` (273 lines, down from 982).** Slim
  orchestrator: imports all 8 scrapers from `scrapers/`, calls
  `classifier.classify_article`, persists via
  `database.store_article`, and posts via
  `telegram.post_to_telegram`. Also owns the CLI entry point
  (`main()` + `evaluate_classifier_accuracy()` + the
  `python news_tool.py evaluate` flag). All public symbols are
  re-exported so existing callers and tests work unchanged
  via `from news_tool import scrape_arxiv, ...` and
  `news_tool.scrape_arxiv()`.

### Test updates
- 43 `patch.object(self.news_tool, "fetch_url", ...)` patches in
  `test_scraper_*.py` and `test_fixes.py` were updated to
  `patch("scrapers.<source>.fetch_url", ...)`. The original
  patches intercepted the call inside the same module;
  after the split, each scraper module has its own
  `fetch_url` binding, so the patch must target the
  namespace where the function is actually called. This is
  the standard "patch where it's used" Python pattern.
- `test_fixes.py` Telegram tests now patch
  `telegram._send_telegram_message` (the new home) and
  `telegram.logger` (the new logger).
- The `TestFreshInstallFlow` suite is **untouched** — it
  still passes 12/12. Bookmark persistence remains blocked
  on a separate test rewrite (subprocess-based) in v1.5.0.

### What was deferred
- **Bookmark persistence** — still deferred to v1.5.0.
  This release ships the file split that bookmark
  persistence was waiting on, but the test rewrite
  required to unblock the implementation is its own
  piece of work.

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
