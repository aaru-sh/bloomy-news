# Release notes — paste into the GitHub Release UI

Copy everything below the line into the "Describe this release" box on
https://github.com/aaru-sh/bloomy-news/releases/new?tag=v1.4.2

---

## Bloomy News v1.4.2 — Bookmark persistence in SQLite

A sub-release of the 1.4 line. The JSON bookmark store is now
mirrored to a new `bookmarked` column in the `articles` table,
so the bookmark state survives a clean rebuild of
`dashboard_data.json`. The blocker that prevented this from
shipping — `TestFreshInstallFlow`'s `sys.modules` pollution —
is fixed in the same release.

### What's in this release

- **`bookmarked` column on the `articles` table.**
  `INTEGER NOT NULL DEFAULT 0` with a matching
  `idx_articles_bookmarked` index. Added to the
  `CREATE TABLE` schema for new DBs and via
  `ALTER TABLE ... ADD COLUMN` for existing DBs (inside a
  `try/except` so re-runs are safe).
- **Four new database helpers.**
  `set_bookmarked(article_id, value)`,
  `is_bookmarked(article_id)`,
  `set_bookmarked_by_hash_prefix(prefix, value)` (the
  dashboard's article id is the first 16 hex chars of the
  SHA-256 of `url + title`), and
  `get_bookmarked_article_ids()`.
- **serve.py mirrors every toggle to the DB.** Best-effort:
  a DB failure is logged but the user-facing JSON response
  still returns 200, because the JSON is the source of truth
  for what the user sees.
- **`TestFreshInstallFlow` runs in a subprocess.** A small
  `_run_in_subprocess` helper takes a temp dir + a Python
  script, spawns a fresh interpreter, and surfaces the
  script's stdout/stderr on failure. The `importlib`-
  based import dance is gone; the test no longer touches
  the real test process's `sys.modules`. This was the
  blocker that kept bookmark persistence deferred from
  1.1.0 onward.
- **`TestServerSmoke` mocks `serve.database`.** The new
  mirror would otherwise write to the real `news.db` on
  every toggle during tests; the mock prevents that and
  lets the new `test_bookmark_toggle_mirrors_to_db` test
  assert the call args.
- **8 new tests in `test_database_bookmark.py`.** Cover
  the column creation, the ALTER TABLE migration, the
  round-trip of set/is, the hash-prefix lookup, the
  default value for new articles, and the unknown-id
  no-op.

### Verification

- **112 tests pass**, 1 skipped (the
  `TestRealWorldDistribution` smoke test that needs a
  populated `news.db`); up from 103 in v1.4.1
- mypy clean across `news_tool.py` and `database.py`
- Live DB migration verified: the `ALTER TABLE` adds the
  `bookmarked` column to the existing `news.db` without
  error; `PRAGMA table_info(articles)` confirms the new
  column and its `NOT NULL DEFAULT 0` constraint
- `serve.database.set_bookmarked_by_hash_prefix` is invoked
  on every successful toggle and never on a 400 (asserted
  in `test_bookmark_id_rejected`)

### Why a sub-version of 1.4 (not 1.5)

- The change is small and focused (one column, four
  helpers, one mirror call, one test rewrite, one new
  test file). It does not justify a feature-level bump.
- It is not purely a bug fix either — the column is new
  schema — but the scope matches 1.4.0 and 1.4.1.
- Bookmark persistence has been deferred from v1.1.0
  onward; this release finally unblocks it without
  claiming a new feature number.

### Upgrading

No JSON changes (the bookmark file format is unchanged).
No new dependencies. `git pull` and re-run
`LAUNCH_DAILY.bat`:

1. `init_db()` will ALTER TABLE to add the `bookmarked`
   column to any pre-existing `news.db`.
2. From the next bookmark toggle, the DB column tracks
   the JSON. The JSON is still the source of truth for
   the user-facing view; the DB column is a second copy
   that survives `dashboard_data.json` rebuilds.
3. New articles default to `bookmarked = 0` and stay
   that way until you click the star.

---

## Bloomy News v1.4.1 — Launcher fixes, storage cleanup, logging fix, and GitHub button

A maintenance patch. **No behavior changes** to the
pipeline, the classifier, the digest, or the data layer.
The `scrapers/` split from v1.4.0 is unchanged. This
release ships the runtime issues observed after the v1.4.0
build, the 100 MB → 15 MB storage cleanup, the `serve.py`
log redirect fix, log rotation, and a GitHub link in the
dashboard header.

### What's in this release

- **Four launcher / dashboard fixes** — `LAUNCH_DAILY.bat`
  BOM removed, server-start polling loop (10×1s), no-cache
  headers now cover HTML / JS / CSS, and `pause` at the end
  so the window doesn't appear "stuck".
- **`serve.py` log redirect fix** — the `start /B python
  ... > log 2>&1` redirect was broken on Windows: the
  redirect went to `start`, not to the spawned python, so
  `logs\server.log` was always 0 bytes even when the server
  failed. `serve.py` now owns its own log file via
  Python's `logging` + `RotatingFileHandler` (1 MB max,
  1 generation kept).
- **Log rotation** for `logs\pipeline_stdout.log` (1 MB
  → `.1`, one generation kept) at the top of
  `LAUNCH_DAILY.bat`.
- **Storage cleanup** — `.mypy_cache/` (94.57 MB),
  `__pycache__/`, `.playwright-mcp/`,
  `dashboard-initial.png`, `logs\server_test*.log` removed.
  Project is now **15.75 MB** total (was 107 MB).
- **GitHub repo button** in the dashboard header on all
  three pages, linking to
  <https://github.com/aaru-sh/bloomy-news>.
- **`.gitignore` update** to catch `dashboard-*.png` and
  `*-initial.png` patterns.

### Why the project grew from 11 MB to 107 MB

v1.3.0 (one day before this release) added mypy to the dev
toolchain. During v1.3.0's type-hint development, each
`mypy news_tool.py database.py` run wrote a 4-8 MB cache
file to `.mypy_cache/3.10/`. Over 15+ runs in one day,
that grew to **94.57 MB** of type-check cache. The
`.mypy_cache/` is in `.gitignore` (line 11) so it's not
tracked, but it persists on disk. This release deletes it
once; it will regrow over time and may need periodic
cleanup until we add a scheduled cleanup task.

### Verification

- 103 tests pass, 1 skipped (the `TestRealWorldDistribution`
  smoke test that needs a populated `news.db`)
- Project storage: **15.75 MB** (was 107 MB before
  cleanup)
- BOMs verified gone on all touched files
- `server.log` now populates on server start
  (verified: `2026-06-06 14:26:25,907 [INFO]
  bloomy_news.dashboard: Dashboard server starting on
  http://127.0.0.1:8080`)

### Upgrading

No schema changes. No config changes. `git pull` and re-run
`LAUNCH_DAILY.bat` — the next launch will:

1. Show the system check output **without** the leading
   `∩╗┐@echo off is not recognized` line.
2. Wait up to 10 s for the dashboard server to bind (instead
   of 2 s).
3. Allow the dashboard to refetch HTML / JS / CSS on the
   next page load (no hard refresh needed).
4. Show "Press any key to close this window..." at the end
   (the window will not close silently while you're reading
   the output).
5. Write a populated `logs\server.log` (visible as soon as
   the server starts).
6. Show the new GitHub icon link in the dashboard header,
   between the existing nav links and the theme toggle.

---

## Bloomy News v1.4.0 — `news_tool.py` split into 13 focused files

A maintenance-quality release. **No behavior changes** — the
pipeline scrapes, classifies, stores, and digests exactly the
same articles as v1.3.0. The only change is module organization:
every file in the project is now under 280 lines, and adding a
9th source is a 30-line new file in `scrapers/` instead of
editing a 1000+ line monolith.

### What changed

- **`scrapers/` package (11 files).**
  - `scrapers/_http.py` (66 lines) — `fetch_url`, `fetch_json`,
    `SOURCE_NAMES`, and the `Article` / `ArticleList` type
    aliases. The lowest layer of the scraper stack.
  - `scrapers/_rss.py` (140 lines) — `parse_rss` with the
    feedparser primary path and `_parse_rss_regex` fallback
    (the legacy parser is kept so a feedparser crash on a
    malformed feed doesn't drop the whole scrape).
  - `scrapers/_keywords.py` (135 lines) — `CATEGORY_KEYWORDS`,
    `SUBCATEGORY_KEYWORDS`, the `STOPWORDS` set, and the
    tokenization helpers (`_tokenize`, `_keyword_tokens`,
    `_filter_keywords`) used by the keyword classifier.
  - `scrapers/arxiv.py` (40 lines) — 13 arXiv feeds with the
    `ARXIV_RATE_LIMIT` env var (3.0s default).
  - `scrapers/github.py` (47 lines) — 3 language trending
    pages parsed via HTML regex.
  - `scrapers/newsapi.py` (30 lines) — NewsAPI
    `top-headlines` for `technology` / `science` / `business`.
  - `scrapers/cybersec.py` (19 lines) — 3 security RSS feeds.
  - `scrapers/tech.py` (19 lines) — TechCrunch / The Verge /
    Ars Technica.
  - `scrapers/finance.py` (40 lines) — Finnhub JSON +
    Yahoo Finance / Investing.com RSS.
  - `scrapers/google_news.py` (72 lines) — 3 queries + the
    `resolve_google_news_redirect` URL un-redirector.
  - `scrapers/markets.py` (18 lines) — CNBC + MarketWatch.
- **`classifier.py` (257 lines).** Owns the embedding state
  (`_embedding_model`, `_category_embeddings`,
  `_embedding_load_failed`), the `CATEGORY_EXAMPLES` centroid
  prompts, and the three classification functions. The gate
  thresholds (`KEYWORD_MINIMUM_ACCURACY=0.80`,
  `EMBEDDING=0.95`, `COMBINED=0.90`) live here.
- **`telegram.py` (163 lines).** Owns the digest formatter,
  the `urllib`-based `_send_telegram_message` (so tests
  can monkey-patch it without touching urllib), the
  category/emoji constants, and `post_to_telegram`. Reads
  `config/telegram.json` the same way as before.
- **`news_tool.py` (273 lines, down from 982).** Slim
  orchestrator: imports all 8 scrapers from `scrapers/`,
  calls `classifier.classify_article`, persists via
  `database.store_article`, and posts via
  `telegram.post_to_telegram`. Also owns the CLI entry
  point (`main()` + `evaluate_classifier_accuracy()` +
  the `python news_tool.py evaluate` flag).
- **Re-export pattern in `news_tool.py`.** All public symbols
  are re-exported so existing callers and tests work
  unchanged via `from news_tool import scrape_arxiv, ...`
  and `news_tool.scrape_arxiv()`.

### Test updates

- 43 `patch.object(self.news_tool, "fetch_url", ...)` patches
  in `test_scraper_*.py` and `test_fixes.py` were updated to
  `patch("scrapers.<source>.fetch_url", ...)`. The original
  patches intercepted the call inside the same module; after
  the split, each scraper module has its own `fetch_url`
  binding, so the patch must target the namespace where the
  function is actually called. This is the standard
  "patch where it's used" Python pattern.
- `test_fixes.py` Telegram tests now patch
  `telegram._send_telegram_message` (the new home) and
  `telegram.logger` (the new logger).
- `TestFreshInstallFlow` is **untouched** — it still passes
  12/12. Bookmark persistence remains blocked on a separate
  test rewrite (subprocess-based) in v1.5.0.

### Verification

- 103 tests pass, 1 skipped (the `TestRealWorldDistribution`
  test that needs a populated `news.db`)
- 68% coverage (same as v1.3.0)
- mypy clean across 16 source files
  (`news_tool.py`, `database.py`, `classifier.py`,
  `telegram.py`, `scrapers/`)

### What was deferred

- **Bookmark persistence** — still deferred to v1.5.0.
  This release ships the file split that bookmark
  persistence was waiting on, but the test rewrite
  required to unblock the implementation is its own
  piece of work.

---

## Bloomy News v1.3.0 — Type hints on the public surface

A maintenance-quality release. **No behavior changes** — every
article, scrape, classifier decision, and Telegram message works
exactly as it did in v1.2.0. The only change is static type
information on the public surface of `news_tool.py` and `database.py`.

### What changed

- **mypy in the dev toolchain.** `mypy>=1.10.0` in
  `requirements-dev.txt`, `mypy.ini` at the project root. Scoped to
  the two main modules for now (scripts/ and dashboard/ are next).
  Run locally with `python -m mypy news_tool.py database.py`.
- **`news_tool.py` (982 lines, 27 functions) fully type-hinted.**
  Added `Article`, `ArticleList`, `CategoryMap`, `ClassifyResult`
  type aliases so the dict-of-strings-the-shape-of-an-article is
  named once. Every public function declares parameter and return
  types; the rest of the codebase imports the aliases.
- **`database.py` (651 lines, 24 functions) fully type-hinted.**
  Same `Article` / `ArticleList` aliases. The "open fresh
  connection if none provided" pattern in five functions got an
  `assert conn is not None` after the assignment so mypy can follow
  the type narrowing.
- **One real bug fix folded in.** `_load_labeled_samples()` now
  raises a clear `RuntimeError` when
  `importlib.util.spec_from_file_location()` returns `None`, instead
  of crashing with a cryptic `AttributeError` on a possibly-None
  spec.

### What was deferred

- **`news_tool.py` split** — still deferred. The type hints are
  the precondition: with `Article` / `ArticleList` / `CategoryMap`
  / `ClassifyResult` aliases in place, the split is now a
  mechanical move rather than a rewrite.
- **Bookmark persistence** — still blocked on
  `TestFreshInstallFlow` sys.modules pollution.
- **`scripts/` and `dashboard/` type hints** — out of scope for
  this release, scoped follow-up.

### Upgrading

No schema changes. No config changes. `git pull`, then
`pip install -r requirements-dev.txt` if you want to run mypy
locally.

---

## Bloomy News v1.2.0 — Scraper test coverage, feedparser, coverage in CI, and a Dockerfile

A feature release that hardens the repo against the two most likely
sources of silent breakage (feed shape changes and RSS parser bugs)
and packages the dashboard for non-Windows deployment.

### What changed

- **39 new scraper tests** covering all 8 scrapers (`scrape_arxiv`,
  `scrape_github`, `scrape_newsapi`, `scrape_cybersec`, `scrape_finance`,
  `scrape_tech`, `scrape_google_news`, `scrape_markets`) and
  `parse_rss()`. Mocks `fetch_url`/`fetch_json` so no real HTTP. The
  test suite is now **103 tests** (was 61) and any day a feed's HTML
  shape changes, you'll know immediately.
- **feedparser swap** — `parse_rss()` now uses `feedparser.parse()` as
  the primary path. Handles RSS 2.0, RSS 1.0, Atom, all date formats,
  CDATA, HTML entities, `dc:creator`, and inline HTML in summaries.
  The legacy regex parser is preserved as `_parse_rss_regex()` and
  called via `logger.warning` if feedparser raises — we never want a
  single malformed feed to drop the whole scrape. Fixes the
  documented `<dc:creator>` limitation; real arXiv author names now
  flow through.
- **Coverage.py in CI** — `requirements-dev.txt` pins `coverage>=7.0`,
  the test workflow now runs `coverage run -m unittest discover -s
  tests` then `coverage report --fail-under=50`. Current measured
  coverage: **67%**. Threshold is intentionally conservative; raise
  it as coverage grows.
- **Dockerfile** — `python:3.11-slim` base, non-root user (uid 1000),
  `HEALTHCHECK` on `http://127.0.0.1:8080/`, default `CMD` runs
  `dashboard/serve.py`. Build with `docker build -t bloomy-news .`,
  run with `docker run --rm -p 127.0.0.1:8080:8080 bloomy-news`. The
  service binds localhost only (per repo convention); the `-p` flag
  must map `127.0.0.1:8080:8080` to keep it off the LAN.

### What was deferred

- **Type hints** on the public surface of `news_tool.py` and
  `database.py` — reviewer's concern is real but not blocking for
  solo work.
- **`news_tool.py` split** into a `scrapers/` package + slim
  orchestrator — do at the 9th source, not before.
- **NewsAPI/Finnhub rate-limit tracking** — defer until actually
  throttled.
- **Bookmark persistence to the articles table** — still blocked
  by `TestFreshInstallFlow` sys.modules pollution; needs the test
  rewritten to use a subprocess.

### Upgrading

No schema changes. No config changes. `git pull`, then either
`pip install -r requirements.txt` to pick up `feedparser`, or just
rebuild the Docker image.

---

## Bloomy News v1.1.2 — Scrape surface, classifier visibility, and CI gate split

A follow-up patch to v1.1.1. The arXiv feed list now matches what the
docs claim, the Telegram digest is built from the in-memory categorized
dict instead of a fresh DB query, article embeddings are persisted to
the database, and the classifier CI gate is split into keyword /
embedding / combined sub-gates so a regression in any one path is named
in the log.

### What changed

- **arXiv: 13 feeds** (the list the docs already promised, not the 4
  that were actually wired up)
- **Telegram digest uses the in-memory categorized dict** — no more
  surprising yourself with stale DB rows in a fresh run
- **Article embeddings persisted** to the existing `embedding` BLOB
  column (schema unchanged); the classify → store round trip preserves
  the 384-dim vector
- **Jaccard comparison** passes consistent string types (stored
  `title_words` for the fast path, raw `title` for the fallback), so the
  same article pair always scores the same
- **`migrate_from_files`** logs exceptions instead of swallowing them
- **`ARXIV_RATE_LIMIT` honored** — defaults to 3.0s, matching arXiv's
  published guideline
- **Classifier visibility** — `main()` prints which mode is running;
  README and `requirements.txt` get a one-line callout about the
  optional `sentence-transformers` install
- **CI gate split** — `evaluate_classifier.py` reports
  `keyword=... embedding=... combined=...` and exits 0 only if all
  three sub-gates pass. The keyword-only regression drops to 63.3% on
  the test set, so on a machine without `sentence-transformers` the
  gate now fails loudly instead of hiding the gap behind a 100%
  combined number

### Heads-up

The keyword-only path is currently 63.3% on the regression set. With
`pip install -r requirements.txt` and no extras, the gate will now
**exit 1** where v1.1.1 would have shown 100% combined. Install
`sentence-transformers` to get the full path back, or wait for the
keyword-list tightening in the next release.

### Upgrading

No schema changes. No config changes. `git pull` and re-run
`scheduler.py --install --verify` if you want the install-time self-check
(from v1.1.1).

---

## Bloomy News v1.1.1 — Bug fixes, classifier hardening, dashboard modernization

This is a follow-up patch to v1.1.0. No new features; no breaking
changes. The classifier is less prone to substring false positives, the
dashboard JavaScript is fully ES6+, the database search and dedup paths
use SQL pre-filtering where they previously looped in Python, and a
few over-claims in the docs were corrected.

### What's inside

- **Atomic bookmark writes** — `toggle_bookmark` in `database.py` now uses
  `tempfile.mkstemp` + `os.replace` and is guarded by `_BOOKMARKS_LOCK`.
  The dashboard server already had this since v1.1.0; the lower-level
  helper is now also crash-safe under concurrent requests.
- **FTS5 article search** — `get_articles(query=...)` now routes through
  the `articles_fts` MATCH expression. Behavior is unchanged for callers
  that don't pass a query. Falls back to `LIKE` only if FTS5 is
  unavailable or the query parses to nothing.
- **SQL Jaccard pre-filter** — `is_duplicate` narrows candidates in SQL
  by shared significant words (length >= 4) before the Python Jaccard
  loop runs. Cuts the loop from O(200) to O(small) per call on a typical
  5000-article database.
- **Word-boundary keyword classifier** — `_classify_keywords` now
  tokenizes with `\b[\w'-]+\b` and matches by token-set membership. Sub-3-char
  keywords and pure stopwords are dropped. Multi-word keywords require
  all words to appear. Fixes the `social security -> Cybersecurity` and
  `runway model -> ML-Research` false positives that plain substring
  matching produced.
- **Classifier accuracy metrics** — new `evaluate_classifier_accuracy()`
  in `news_tool.py` returns `{correct, total, accuracy, by_category}` and
  prints a one-line CLI summary. `scripts/evaluate_classifier.py` wraps
  it and exits 0 only if accuracy >= `MINIMUM_ACCURACY` (0.90).
  On the current labeled set: **100.0% (30/30)** overall;
  `keyword=63.3%` `embedding=100%`.
- **Dashboard ES6+** — `dashboard/app.js`, `app-filters.js`, and
  `app-bookmarks.js` are fully modernized: `const`/`let`, arrow
  callbacks, template literals, rest params. No bundler, no build step.
  The dashboard remains a static site served by `dashboard/serve.py`.
- **Docs audience split** — the "Concepts for newcomers" block
  (RSS / SQL / API key explanations) is moved out of `README.md` and
  consolidated into `docs/NEWCOMERS.md`. The main README now assumes
  the reader knows what RSS, SQL, and JSON are.
- **SECURITY.md atomicity claim** — the over-claim is replaced with an
  accurate description that names both `dashboard/serve.py` and
  `database.py` as crash-safe under concurrent requests.
- **Scheduler `--verify`** — read-only diagnostic that confirms the
  registered Python path exists and is launchable, the repo path
  resolves, the database file is writable, the `.env` is present, and
  the autostart is registered. Prints one pass/fail line per check
  with a remediation hint. `--install` now runs `--verify` immediately
  after registering the task, so silent failures (moved venv, broken
  path encoding) are caught at install time.

### What's still known / deferred

- **Bookmark persistence to the articles table** — still deferred from
  v1.1.0. The `TestFreshInstallFlow` test pollution issue was not
  addressed in this release; `dashboard_data.json` remains the only
  bookmark storage. The atomic + locked writes in v1.1.1 keep the
  existing storage safe.
- **GitHub trending scraper** still uses regex against rendered HTML
  (out of scope this release; a follow-up to use the GitHub REST API
  is planned).
- **RSS parser** still uses regex (out of scope per the "no new
  external dependencies" rule; `feedparser` is not added).

### Migration

None. v1.1.0 -> v1.1.1 is a drop-in replacement. The classifier and
bookmark changes are backward-compatible; the FTS5 search falls back to
`LIKE` if FTS5 is unavailable, and the keyword classifier no longer
returns categories that the substring matcher would have spuriously
matched.

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
