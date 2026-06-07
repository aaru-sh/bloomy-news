# Testing

Bloomy News uses Python's built-in `unittest` framework. The test suite covers the core pipeline (scraping, classification, storage, deduplication), the dashboard server, the Telegram digest, the scheduler, and the fresh-install flow.

## Test Architecture

### File Organization

Tests live in `tests/` and mirror the source modules they exercise:

| Test file | What it covers |
|---|---|
| `test_fixes.py` | Core regression tests — title similarity, classifier fallback, ID validation, secrets loader, scheduler, concurrent inserts, bookmark race conditions, FTS5 search, embedding persistence, Jaccard prefilter, arXiv rate limiting, Telegram digest source |
| `test_database_extended.py` | Database edge cases — empty titles, duplicate detection, pagination, FTS5, Jaccard with empty strings, concurrent bookmarks |
| `test_database_bookmark.py` | The `bookmarked` column (v1.4.2) — schema migration, `set_bookmarked`/`is_bookmarked` round-trip, hash-prefix lookup |
| `test_classifier.py` | Classifier accuracy against a labeled set of 30 samples; gate thresholds; real-DB distribution smoke test |
| `test_classifier_extended.py` | Classifier edge cases — empty inputs, embedding vs. keyword paths, confidence ranges, return shape |
| `test_fresh_install.py` | End-to-end fresh-install flow via subprocess isolation; path resolution; server smoke tests |
| `test_retention.py` | `cleanup_old_articles()` — age threshold, RFC 2822 dates, `created_at` fallback, dedup_log pruning |
| `test_install_dashboard.py` | Windows registry autostart installer — `--install`, `--uninstall`, `--verify`, idempotency |
| `test_scraper_arxiv.py` | arXiv RSS parser and `scrape_arxiv()` — feed list, subcategory tagging, CDATA, HTML entities, rate limiting, feedparser fallback |
| `test_scraper_rss.py` | RSS-based scrapers — `scrape_cybersec()`, `scrape_tech()`, `scrape_google_news()`, `scrape_markets()`; Atom `<entry>` fallback; redirect resolution |
| `test_scraper_json.py` | JSON/HTML scrapers — `scrape_github()`, `scrape_newsapi()`, `scrape_finance()` (Finnhub + RSS) |
| `test_telegram.py` | Telegram module — digest formatting, emoji mapping, article limiting, send success/failure |
| `test_integration.py` | Full pipeline integration — scrape → classify → store → digest; dashboard endpoints; scheduler logic |

### Subprocess Isolation (`test_fresh_install.py`)

The `TestFreshInstallFlow` class runs each test case in a **fresh Python subprocess**. This is necessary because:

1. The project's modules (`database`, `news_tool`, `serve`, etc.) set `DB_PATH` and other paths at import time based on `__file__`.
2. Importing these modules into the test process binds them to the project root's `news.db`. A subsequent `database.DB_PATH = tmp_path` only changes the module-level variable in the test process — not in any already-cached `sys.modules` copies.
3. Previous approaches (copying source files and using `importlib`) polluted `sys.modules` for the rest of the test suite, causing flaky failures in `TestServerSmoke` and other classes.

The `_run_in_subprocess()` helper constructs a Python snippet, prepends `sys.path` and `os.chdir` setup, and runs it via `subprocess.run()` with a 30-second timeout. The parent test process's `sys.modules` stays clean.

```python
def _run_in_subprocess(root: Path, script: str) -> str:
    full = (
        f"import sys, os; sys.path.insert(0, r'{root.as_posix()}'); "
        f"os.chdir(r'{root.as_posix()}')\n" + script
    )
    result = subprocess.run(
        [sys.executable, "-c", full],
        capture_output=True, text=True, timeout=30,
    )
    if result.returncode != 0:
        raise AssertionError(
            f"subprocess failed (exit {result.returncode}):\n"
            f"STDOUT:\n{result.stdout}\nSTDERR:\n{result.stderr}"
        )
    return result.stdout + result.stderr
```

### Mocking Strategy

The project uses `unittest.mock.patch` and `unittest.mock.patch.object` extensively. Mocks target specific module attributes rather than entire modules:

- **Scraper HTTP calls**: Each scraper test patches `fetch_url` or `fetch_json` at the scraper module level (e.g., `scrapers.arxiv.fetch_url`, `scrapers.github.fetch_url`), not at the definition site.
- **Telegram sends**: `telegram._send_telegram_message` is patched to capture outbound messages without sending them.
- **Environment variables**: `patch.dict(os.environ, {...})` is used for API keys (`NEWS_API_KEY`, `FINNHUB_API_KEY`, `TELEGRAM_BOT_TOKEN`, `ARXIV_RATE_LIMIT`).
- **Database path**: Tests that need a clean DB swap `database.DB_PATH` to a `tempfile.TemporaryDirectory` in `setUp` and restore it in `tearDown`.
- **Windows registry**: `test_install_dashboard.py` snapshots registry values before each test and restores them after, so tests are idempotent and don't corrupt the developer's autostart settings.
- **`time.sleep`**: Rate-limit tests patch `news_tool.time.sleep` to verify the correct sleep duration without actually waiting.
- **Feedparser**: Fallback tests patch `feedparser.parse` to raise, verifying the regex fallback path.

## Running Tests

### Run All Tests

```bash
python -m unittest discover -s tests
```

### Run a Specific Module

```bash
python -m unittest tests.test_fixes
python -m unittest tests.test_scraper_arxiv
python -m unittest tests.test_database_extended
```

### Run a Specific Test Class

```bash
python -m unittest tests.test_fixes.TestTitleSimilarity
python -m unittest tests.test_fresh_install.TestFreshInstallFlow
```

### Run a Specific Test Method

```bash
python -m unittest tests.test_fixes.TestConcurrentPipelineInserts.test_concurrent_inserts_dedupe_by_url
```

### Run with Coverage

```bash
python -m coverage run -m unittest discover -s tests
python -m coverage report --show-missing
```

The coverage configuration in `.coveragerc` enforces a **68% minimum** (`fail_under = 68`), omits `tests/`, `scripts/`, `docs/`, and `__pycache__/`, and disables the `no_source` warning (fresh-install tests copy source files to temp directories).

### Verbose Output

Add `-v` for per-test pass/fail output:

```bash
python -m unittest discover -s tests -v
```

## Writing Tests

### Naming Conventions

- **Test files**: `test_<module>.py`
- **Test classes**: `Test<Feature>(unittest.TestCase)`
- **Test methods**: `test_<behavior>` — use descriptive names that state the expected behavior, not just the input

```python
class TestCleanupOldArticles(unittest.TestCase):
    def test_deletes_articles_older_than_threshold(self):
        ...
    def test_keeps_articles_within_threshold(self):
        ...
    def test_empty_published_uses_created_at(self):
        ...
```

### setUp / tearDown Pattern

Most database tests follow this pattern — swap `DB_PATH` to a temp directory, restore in `tearDown`:

```python
def setUp(self):
    import database
    self._database = database
    self._tmpdir = Path(tempfile.mkdtemp())
    self._tmp_db = self._tmpdir / "news.db"
    self._original_db_path = database.DB_PATH
    database.DB_PATH = self._tmp_db
    database.init_db()

def tearDown(self):
    self._database.DB_PATH = self._original_db_path
    import shutil
    shutil.rmtree(self._tmpdir, ignore_errors=True)
```

`test_database_extended.py` extracts this into a `_DBTestCase` base class to avoid repetition:

```python
class _DBTestCase(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.tmp_path = Path(self.tmp.name)
        self.original_db_path = database.DB_PATH
        database.DB_PATH = self.tmp_path / "news.db"

    def tearDown(self):
        database.DB_PATH = self.original_db_path
        self.tmp.cleanup()
```

### Parameterized Tests with `self.subTest()`

Use `subTest` when testing multiple inputs against the same assertion:

```python
def test_accuracy_above_threshold(self):
    for title, summary, expected in LABELED_SAMPLES:
        with self.subTest(title=title):
            cat, conf, tags, subcat, emb = classify_article({"title": title, "summary": summary})
            self.assertEqual(cat, expected)
```

### Mocking External Dependencies

Mock HTTP at the scraper module level, not at `requests.get`:

```python
# Correct — mock at the call site
with patch("scrapers.arxiv.fetch_url", return_value=empty_rss):
    articles = self.news_tool.scrape_arxiv()

# Also correct — mock at the call site for a different scraper
with patch("scrapers.github.fetch_url", return_value=GH_HTML):
    articles = self.news_tool.scrape_github()
```

Mock environment variables:

```python
with patch.dict(os.environ, {"NEWS_API_KEY": "test_key_12345"}):
    articles = self.news_tool.scrape_newsapi()
```

### Testing with Temp Directories

Always use `tempfile.TemporaryDirectory` and clean up in `tearDown`. On Windows, use `ignore_cleanup_errors=True` to avoid `PermissionError` on locked files:

```python
self.tmp = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
```

### Testing Database Operations

Each test gets a fresh DB by swapping `database.DB_PATH`. Call `database.init_db()` after the swap to create the schema. Restore the original path in `tearDown`:

```python
def setUp(self):
    self._database = database
    self._tmpdir = Path(tempfile.mkdtemp())
    self._tmp_db = self._tmpdir / "news.db"
    self._original_db_path = database.DB_PATH
    database.DB_PATH = self._tmp_db
    database.init_db()

def tearDown(self):
    self._database.DB_PATH = self._original_db_path
    import shutil
    shutil.rmtree(self._tmpdir, ignore_errors=True)
```

### Conditionally Skipping Tests

Skip tests when optional dependencies are unavailable or when the environment doesn't support the feature:

```python
def setUp(self):
    try:
        import requests
        self._requests_available = True
    except ImportError:
        self._requests_available = False

def test_three_feeds(self):
    if not self._requests_available:
        self.skipTest("requests not available")
    ...
```

Skip Windows-only tests:

```python
@unittest.skipUnless(os.name == "nt", "Windows-only (uses HKCU registry)")
class TestInstallDashboard(unittest.TestCase):
    ...
```

Skip in CI when model download is rate-limited:

```python
def setUp(self):
    if os.environ.get("CI") == "true":
        self.skipTest("Classifier accuracy test skipped in CI: requires downloading model")
```

## Test Patterns

### Subprocess Isolation

`test_fresh_install.py` copies source files into a temp directory, then runs assertions in a subprocess so the parent process's `sys.modules` stays clean. This prevents cross-test contamination when modules bind paths at import time.

### Mock HTTP

All scraper tests mock `fetch_url` and `fetch_json` at the scraper module level (e.g., `scrapers.arxiv.fetch_url`). This avoids real network calls and makes tests deterministic. The mock targets the function where it's called, not where it's defined.

### Temp Directories

Tests that need filesystem access use `tempfile.TemporaryDirectory`. The DB path swap pattern (`database.DB_PATH = tmp_path`) ensures each test starts with an empty database and doesn't touch the developer's real `news.db`.

### Registry Mocking (Windows)

`test_install_dashboard.py` snapshots the Windows registry values before each test and restores them after. This makes registry-writing tests safe to run on developer machines without corrupting the autostart configuration.

### Live DB Smoke Tests

Some tests (`TestCleanupOnLiveDB`, `TestRealWorldDistribution`) run against the real `news.db` when it exists. They skip automatically on fresh clones or CI environments where the database isn't populated.

### Concurrent Access Tests

`TestConcurrentPipelineInserts` and `TestBookmarkRace` use multiple threads to verify that SQLite's UNIQUE INDEX and the `_BOOKMARKS_LOCK` prevent duplicate inserts and lost updates under concurrent access.

### Feedparser Fallback

`TestParseRssFallbackToRegex` patches `feedparser.parse` to raise, then verifies that `parse_rss()` falls back to the legacy regex parser and still produces correct articles.

## CI Integration

The GitHub Actions workflow (`.github/workflows/test.yml`) runs on every push and PR to `main`:

1. **Matrix**: Python 3.8, 3.9, 3.10, 3.11, 3.12 on `ubuntu-latest`
2. **Dependencies**: `requirements.txt` + `requirements-dev.txt`
3. **HuggingFace cache**: Caches the `all-MiniLM-L6-v2` model (~80MB) to avoid re-downloading on every run
4. **Unit tests with coverage**: `python -m coverage run -m unittest discover -s tests -v`
5. **Coverage gate**: `python -m coverage report --fail-under=68 --show-missing`
6. **Coverage XML**: Generated on Python 3.12 and uploaded as an artifact (14-day retention)
7. **Fresh-install smoke test**: `python scripts/smoke_test.py`
8. **Pylint**: `pylint news_tool.py database.py classifier.py telegram.py`
9. **mypy**: Configured in `mypy.ini` — checks `news_tool.py`, `database.py`, `scripts/`, `dashboard/` with Python 3.10 target

## Common Pitfalls

### Don't Import `news_tool` in Subprocess Tests

`test_fresh_install.py` runs in a subprocess precisely because importing `news_tool` (and `database`) at the module level binds paths. Tests that need to modify `sys.modules` or test fresh-install behavior must run in a separate interpreter.

### Use `ignore_cleanup_errors=True` on Windows

`tempfile.TemporaryDirectory()` can raise `PermissionError` on Windows when SQLite or other processes hold file handles. Use:

```python
self.tmp = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
```

### Mock at the Call Site, Not the Definition Site

Patch where the function is used, not where it's defined:

```python
# Correct
with patch("scrapers.arxiv.fetch_url", ...):

# Wrong — patches the definition, may miss rebinding
with patch("news_tool.fetch_url", ...):
```

### Clean Up Test Databases in tearDown

Always restore `database.DB_PATH` and remove temp directories in `tearDown`. Failing to do so leaks state into subsequent tests.

### `test_classifier.py` Skips in CI

The classifier accuracy test downloads the `all-MiniLM-L6-v2` model, which is rate-limited in CI. The test skips when `CI=true` and validates accuracy locally before each release.

### `test_install_dashboard.py` Is Windows-Only

Registry tests are decorated with `@unittest.skipUnless(os.name == "nt", ...)`. They won't run on Linux/macOS CI runners.
