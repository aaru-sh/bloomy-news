# Good First Issues

Welcome, new contributor! These issues are designed to be approachable for first-timers. Each is self-contained and requires no deep domain knowledge. Look for the `good first issue` label to filter.

---

## Documentation

### 1. Add docstrings to undocumented functions in `scrapers/_http.py`

The HTTP helper module contains several utility functions that lack docstrings. Add clear, concise docstrings (Google or NumPy style) to every public function in `scrapers/_http.py`. Reference the function's signature and return type where applicable.

- **Files:** `scrapers/_http.py`
- **Approach:** Read each function, understand its purpose from usage in sibling scrapers, and write a one-line summary plus a `Returns:` section.
- **Estimate:** 1 hour
- **Labels:** `good first issue`, `documentation`

---

### 2. Fix a typo or grammar issue in the README

Review `README.md` for typos, grammatical errors, broken links, or inconsistent formatting. Pick one issue and open a focused PR.

- **Files:** `README.md`
- **Approach:** Read the README end-to-end, identify a concrete error, and fix it with a minimal diff.
- **Estimate:** 1 hour
- **Labels:** `good first issue`, `documentation`

---

### 3. Update outdated documentation in `docs/`

Several docs pages may reference old CLI flags, removed features, or outdated installation steps. Review files in `docs/` against the current codebase and correct anything stale.

- **Files:** `docs/*.md`
- **Approach:** Grep for the term or flag in the codebase. If it no longer exists, update the doc to reflect current behavior.
- **Estimate:** 2 hours
- **Labels:** `good first issue`, `documentation`

---

## Tests

### 4. Write tests for edge cases in `database.cleanup_old_articles()`

`database.py` has a `cleanup_old_articles()` function that deletes articles older than a threshold. Write unit tests covering: zero articles to delete, boundary date conditions, and calling it with an empty database.

- **Files:** `tests/test_database.py`
- **Approach:** Use the existing test fixtures to set up a temporary SQLite database. Insert articles with known timestamps, call cleanup, and assert the correct rows remain.
- **Estimate:** 2 hours
- **Labels:** `good first issue`, `test`

---

### 5. Add a test for the `classify_article` edge case with empty input

The `classifier.py` module's `classify_article` function should handle empty strings or None gracefully. Add a test that verifies the function returns a sensible default (e.g., `"uncategorized"`) when given empty input.

- **Files:** `tests/test_classifier.py`
- **Approach:** Write a parametrized test with `""`, `None`, whitespace-only strings. Assert the return value is the expected fallback category.
- **Estimate:** 2 hours
- **Labels:** `good first issue`, `test`

---

### 6. Add a test for `dashboard/serve.py` HTTP 404 response

The HTTP server likely returns a 404 for unknown paths. Add an integration test that hits a non-existent route and asserts a 404 status code.

- **Files:** `tests/test_dashboard.py`
- **Approach:** Spin up the server on a test port using `threading` or `subprocess`, send a request with `urllib.request` to `/nonexistent-path`, and verify the response code.
- **Estimate:** 3 hours
- **Labels:** `good first issue`, `test`

---

## Bug Fixes

### 7. Fix inconsistent error handling in `scrapers/` modules

Some scrapers silently swallow exceptions while others raise `ValueError`. Pick one scraper module and unify its error handling to use a consistent pattern (log + re-raise or log + return empty list).

- **Files:** `scrapers/*.py`
- **Approach:** Audit a single scraper's `except` blocks. Standardize to `logging.warning(...)` followed by a re-raise or an explicit return, matching the pattern used in `scrapers/_http.py`.
- **Estimate:** 3 hours
- **Labels:** `good first issue`, `bug`

---

### 8. Fix a missing `None` check in the CLI argument parser

`news_tool.py` may not handle the case where a user passes no arguments and no default config exists. Add a guard that prints a usage message instead of crashing with a traceback.

- **Files:** `news_tool.py`
- **Approach:** Wrap the argument parsing block in a try/except or add an `if len(sys.argv) < 2` check with a `parser.print_help()` call.
- **Estimate:** 2 hours
- **Labels:** `good first issue`, `bug`

---

## Enhancements

### 9. Add a new category keyword to the classifier

The ML classifier in `classifier.py` categorizes articles by keywords. Add one new category (e.g., `"science"` or `"finance"`) with a small seed list of keywords. Update any relevant configuration or test.

- **Files:** `classifier.py`, `tests/test_classifier.py`
- **Approach:** Add the category string to the keyword dictionary, write a test asserting articles containing the new keywords are classified correctly.
- **Estimate:** 2 hours
- **Labels:** `good first issue`, `enhancement`

---

### 10. Improve error messages in the CLI

Several CLI operations in `news_tool.py` produce bare `sys.exit(1)` calls with no message. Replace these with descriptive messages that explain what went wrong and what the user should do.

- **Files:** `news_tool.py`
- **Approach:** Search for `sys.exit(1)` and `sys.exit(2)`. Before each, add a `print(...)` or `sys.stderr.write(...)` with a human-readable explanation.
- **Estimate:** 2 hours
- **Labels:** `good first issue`, `enhancement`

---

### 11. Add a missing type hint to a specific function in `database.py`

Several functions in `database.py` are missing return type annotations. Pick one function and add the correct type hints for all parameters and the return value.

- **Files:** `database.py`
- **Approach:** Run `mypy database.py` to identify missing hints. Add the annotation based on what the function actually returns.
- **Estimate:** 1 hour
- **Labels:** `good first issue`, `enhancement`

---

### 12. Add a progress indicator to the batch scrape command

When scraping multiple sources, `news_tool.py` provides no visual feedback. Add a simple print statement that shows which source is being scraped (e.g., `[3/8] Scraping example.com...`).

- **Files:** `news_tool.py`
- **Approach:** Find the loop that iterates over sources. Add `print(f"[{i+1}/{total}] Scraping {name}...")` at the start of each iteration.
- **Estimate:** 1 hour
- **Labels:** `good first issue`, `enhancement`

---

### 13. Add a `--verbose` flag to the CLI for debug output

The CLI currently has no verbosity control. Add a `--verbose` flag that enables `logging.DEBUG` so users can see detailed scraper and database activity.

- **Files:** `news_tool.py`
- **Approach:** Add a `--verbose` argument via `argparse`. In the handler, call `logging.basicConfig(level=logging.DEBUG)` when the flag is set.
- **Estimate:** 2 hours
- **Labels:** `good first issue`, `enhancement`

---

### 14. Standardize return types across scraper modules

Some scrapers return a list of dicts, others return a list of named tuples. Pick two scrapers and align their return types to a single schema (a TypedDict or dataclass).

- **Files:** `scrapers/*.py`
- **Approach:** Define a `TypedDict` with fields like `title`, `url`, `date`, `source`. Update one scraper to return `list[ArticleDict]` and add a type alias for reuse.
- **Estimate:** 4 hours
- **Labels:** `good first issue`, `enhancement`

---

### 15. Add a simple health check endpoint to the dashboard server

`dashboard/serve.py` serves static content but has no health check. Add a `/health` endpoint that returns `200 OK` with a JSON body containing `{"status": "ok"}`.

- **Files:** `dashboard/serve.py`
- **Approach:** Add a route handler for `/health`. Return a `json.dumps({"status": "ok"})` response with `Content-Type: application/json`.
- **Estimate:** 1 hour
- **Labels:** `good first issue`, `enhancement`
