# Architecture

This document is the deep technical reference for how Bloomsberg News works. For a quick overview, see the [README](../README.md#how-it-works).

## System overview

Bloomsberg News is a single-process, single-host pipeline. There is no message queue, no database server, no separate API tier. The components are:

```
┌──────────────────────────────────────────────────────────────────────┐
│                          Windows / Linux / macOS                       │
│                                                                       │
│  ┌──────────────────┐                                                 │
│  │ scripts/         │  long-running, 12h loop                        │
│  │ scheduler.py     │  reads .last_run, runs pipeline, sleeps         │
│  └────────┬─────────┘                                                 │
│           │ invokes                                                    │
│           v                                                            │
│  ┌──────────────────┐    ┌──────────────────┐                       │
│  │   news_tool.py   │───>│   database.py    │ <── reads/writes ───┐  │
│  │                  │    │   (SQLite, WAL)   │                     │  │
│  │ 8 scrapers       │    │   news.db         │                     │  │
│  │ 1 classifier     │    └────────┬──────────┘                     │  │
│  │ 1 dedup          │             │                                │  │
│  │ 1 telegram poster│             v                                │  │
│  └────────┬─────────┘    ┌──────────────────┐                      │  │
│           │              │ category folders │  historical archive  │  │
│           │              │ *.md.gz          │                      │  │
│           │              └──────────────────┘                      │  │
│           │                                                          │
│           v                                                          │
│  ┌──────────────────┐                                                │
│  │ dashboard/       │                                                │
│  │   generate_data  │ ──────────────────────────────────────────────┘
│  │   .py            │   reads DB-primary, FS-fallback
│  │                  │   writes dashboard_data.json (atomic)
│  │   serve.py       │   ThreadingHTTPServer on 127.0.0.1:8080
│  │                  │
│  │   *.html / *.js  │   served as static files + JSON API
│  └──────────────────┘
└──────────────────────────────────────────────────────────────────────┘
```

The scheduler is the only long-running process. Everything else is invoked on-demand.

---

## Component responsibilities

### `news_tool.py` — pipeline

A single file containing:

- 8 scraper functions (`scrape_arxiv`, `scrape_github`, `scrape_newsapi`, etc.) — each returns a `list[Article]`.
- `classify_article(title, summary, source, arxiv_category)` — the keyword classifier.
- `is_duplicate(article)` — checks both arXiv version dedup and Jaccard title dedup.
- `run_pipeline()` — orchestrator. Calls each scraper, runs the dedup check, inserts into the DB, writes filesystem archives, calls the Telegram poster.
- `post_to_telegram(categorized)` — sends the daily digest.

The `BASE` constant is the project root, computed as `Path(__file__).parent`. All file I/O is relative to `BASE`. No hardcoded `E:\` paths in any active code.

### `database.py` — SQLite layer

Owns the SQLite connection lifecycle, schema migrations, and all read/write helpers. Exposes:

- `init_db()` — creates the schema if it doesn't exist.
- `insert_article(article)` — atomic insert with dedup check.
- `is_duplicate_title(title, category, threshold=0.80)` — Jaccard check against the most recent 200 titles in the same category.
- `get_articles(limit, offset, category, source, query)` — for the dashboard.
- `get_stats()` — per-category counts and total.
- `toggle_bookmark(article_id)` — server-side bookmark store.

Connection mode is WAL (`PRAGMA journal_mode=WAL`) for concurrent reads + crash safety. The connection is opened once per process and reused.

### `secrets.py` — env + config loader

The single reader of `config/*.json` and `.env`. The order of precedence is documented in the README. Key functions:

- `get_telegram_token()` → `TELEGRAM_BOT_TOKEN` env, with `${TELEGRAM_BOT_TOKEN}` placeholder fallback in `config/telegram.json`.
- `get_newsapi_key()` → `NEWS_API_KEY` env, with `${NEWS_API_KEY}` placeholder fallback in `config/sources.json`.
- `get_finnhub_key()` → same pattern.

If an env var is not set and the config has a `${VAR}` placeholder, the function returns `""`. The scraper code treats empty keys as "skip this source" and never crashes.

### `dashboard/serve.py` — HTTP server

A subclass of `http.server.ThreadingHTTPServer` with:

- Bind to `127.0.0.1:8080` only.
- Security headers on every response.
- CORS restricted to `http://localhost:8080`.
- API endpoints validate input and return JSON.
- Static file serving for `*.html`, `*.js`, `*.css`, `*.svg`, `*.json`.
- 404 for unknown paths, 405 for wrong methods, 413 for oversized bodies, 500 only on actual exceptions.

The server logs one line per non-2xx response. Successful requests are silent to keep the log readable.

### `dashboard/generate_data.py` — JSON builder

Reads from `database.py` (DB-primary) and falls back to walking the `*/<YYYY-MM-DD>/*.md.gz` filesystem tree for any articles missing from the DB. Output is one atomic write of `dashboard_data.json`.

The atomic write pattern is:

1. Compute the new JSON content in memory.
2. Write to `dashboard_data.json.tmp`.
3. `os.replace(tmp, final)` — atomic on Windows and POSIX.

This guarantees the dashboard never reads a half-written file, even if the process is killed mid-write.

### `scripts/scheduler.py` — background loop

The 12-hour scheduler. State is one JSON file: `.last_run`. The state machine is:

```
                    ┌─────────────────────┐
                    │   start (any time)  │
                    └──────────┬──────────┘
                               │
                               v
                    ┌─────────────────────┐
                    │ read .last_run      │
                    │ (or treat as None   │
                    │  if missing)        │
                    └──────────┬──────────┘
                               │
              ┌────────────────┼────────────────┐
              │                │                │
              v                v                v
     ┌────────────┐   ┌────────────┐   ┌────────────┐
     │ no state   │   │ old state  │   │ recent     │
     │ or > 12h   │   │ (>12h)     │   │ (<12h)     │
     │            │   │            │   │            │
     │ run now,   │   │ run now,   │   │ wait for   │
     │ then loop  │   │ then loop  │   │ next 0h    │
     │            │   │            │   │ or 12h     │
     └────────────┘   └────────────┘   └────────────┘
              │                │                │
              └────────────────┴────────────────┘
                               │
                               v
                    ┌─────────────────────┐
                    │ sleep until next    │
                    │ checkpoint          │
                    │ (0:00 or 12:00)     │
                    └─────────────────────┘
```

The `next_checkpoint(now)` helper computes the next midnight or noon in local time. The `should_catch_up(last_run, now)` helper checks whether the last run is more than 12 hours old.

The startup delay is 60 seconds (`STARTUP_DELAY_SEC`) so the user has time to log in and the system has time to settle after boot.

### `scripts/telegram_bot.py` — digest poster

Reads the categorized articles from the most recent pipeline run, picks the top 3 by recency per category (18 max), formats a message with HTML markup, and calls the Telegram `sendMessage` API with inline keyboard buttons.

The inline buttons are:

- "Read" — opens the source URL
- "Save" — sends a callback query to the bot, which calls `toggle_bookmark()` on the server

The save callback requires the dashboard server to be running, since the bot uses an HTTP call to the local server, not a direct DB write. This keeps the bot stateless.

---

## Data model

### `articles` table

```sql
CREATE TABLE articles (
    id            TEXT PRIMARY KEY,         -- arxiv normalized ID or hash
    title         TEXT NOT NULL,
    summary       TEXT,
    url           TEXT NOT NULL,
    source        TEXT NOT NULL,             -- e.g. "arXiv cs.CL"
    category      TEXT NOT NULL,             -- 6 categories + "Uncategorized"
    subcategory   TEXT,
    confidence    REAL DEFAULT 0.0,
    tags          TEXT,                      -- JSON array
    published     TEXT,                      -- ISO 8601
    fetched_at    TEXT NOT NULL,             -- ISO 8601
    raw_json      TEXT                       -- full original payload
);
```

Primary key is the article ID. For arXiv, it's the normalized ID (version stripped). For other sources, it's a SHA-256 hash of `title + url`. Either way, the same article will not be inserted twice — `INSERT OR IGNORE` is used.

### `dedup_log` table

A side-channel for the Jaccard dedup check, to avoid loading all titles into Python on every check. Each row is a `(title_words_hash, category, article_id)` triple. The hash is SHA-256 of the sorted unique word set, normalized to lowercase and stripped of punctuation. On insert, we look up candidates by hash prefix; on match, we recompute Jaccard on the actual word sets.

This is faster than the naive approach (scan all titles in the category) because the hash filter reduces the candidate set by ~99% in practice.

### Bookmarks

Server-side, in `dashboard/data/bookmarks.json`:

```json
{
  "bookmarks": ["article_id_1", "article_id_2", ...]
}
```

Atomic write: `tmp + os.replace`. A `threading.Lock` in `serve.py` prevents concurrent writes from clobbering each other.

The 5,000-bookmark cap is enforced in `serve.py` before the write.

---

## Why these choices

### Why SQLite?

- **Crash safety** — WAL mode + `INSERT OR IGNORE` + atomic filesystem writes means the DB is always in a consistent state.
- **Performance** — the dedup check is the hot path; a single indexed lookup is faster than a Python loop over a JSON file.
- **Backup** — one file to copy. The filesystem archive is the human-readable backup.
- **No server** — `sqlite3` is in the Python stdlib. No install, no config, no `systemd` unit.

### Why a local HTTP server instead of `python -m http.server`?

- **Security headers** — easy to add to a custom subclass, impossible with the stdlib server.
- **CORS control** — same.
- **Request size limits** — needed to make the bookmark API safe.
- **Logging** — 4xx/5xx logs are useful for debugging the dashboard without spamming the console.

### Why a 12-hour scheduler instead of cron / Task Scheduler?

- **Catch-up** — if the laptop was off, the next run is at the next startup, not at the next scheduled time. Cron and Task Scheduler don't do this.
- **State** — `.last_run` makes the schedule observable and debuggable.
- **No platform lock-in** — the same `scheduler.py` runs on Windows, Linux, and macOS. The Windows-specific autostart is one `--install` flag, not a different tool.

### Why keyword classification instead of an LLM?

- **Cost** — zero. No API bills, no rate limits.
- **Latency** — microseconds per article, no network call.
- **Determinism** — same input always produces the same category. Useful for testing.
- **Transparency** — the keywords are in the source code. You can read them and disagree with them.
- **Limitation** — can't learn from context, can't handle novel terms, can misclassify ambiguous articles. The "Uncategorized" fallback is the acknowledgment of this.

The roadmap includes an embedding-based classifier as a future option for users who want better accuracy at the cost of latency and a small dependency.

---

## Failure modes and recovery

| Failure                                | Detection                    | Recovery                                      |
| -------------------------------------- | ---------------------------- | --------------------------------------------- |
| Scraper returns malformed HTML         | Parser exception, caught     | Article skipped, logged                        |
| Scraper returns 4xx/5xx                | `fetch_json` returns None    | Retried 3x with backoff, then skipped         |
| SQLite disk full                       | `sqlite3.OperationalError`   | Pipeline exits, alert in `pipeline.log`       |
| `.env` missing or malformed            | `secrets.py` returns empty   | Scrapers with required keys are skipped       |
| Telegram API rate limit                | `sendMessage` returns 429    | Retried with backoff in the same run          |
| Dashboard server not running           | Bot callback to `/api/...` fails | Bookmark save from Telegram fails silently |
| `news.db` corruption                    | `sqlite3.DatabaseError`      | Delete `news.db`, re-run pipeline, rebuilds   |
| `dashboard_data.json` corruption       | JSON parse error on startup  | `generate_data.py` rewrites it on next run    |
| Scheduler process killed               | Next OS boot, registry relaunches | Startup catch-up runs the pipeline         |

The `.last_run` file is the only piece of state that can be corrupted in a way that prevents the scheduler from making progress. If that happens, delete `.last_run` and the scheduler treats it as "no prior run, run now".

---

## Performance characteristics

Measured on a typical Windows laptop, no API key throttling:

- **Cold pipeline run**: 60-90 seconds (8 scrapers, ~100 articles fetched, classified, deduped, stored)
- **Warm pipeline run** (no new articles): 15-25 seconds (scrapers still hit the network, but every article fails the dedup check immediately)
- **Dashboard page load**: <100ms (data is in `dashboard_data.json`, served as a single static file)
- **Bookmark toggle**: <5ms (single JSON file write, atomic)
- **Memory**: 30-50 MB RSS for the scheduler; <20 MB for the dashboard server

The pipeline is intentionally I/O-bound, not CPU-bound. If you need to scale it, the parallelism opportunities are: parallelize the 8 scrapers (they're sequential today for predictable logging), and parallelize the `INSERT` statements within a single scraper's batch.

---

## See also

- [SCRAPERS.md](SCRAPERS.md) — how to add a new scraper
- [CLASSIFIER.md](CLASSIFIER.md) — classification algorithm details
- [DEDUP.md](DEDUP.md) — deduplication strategy details
- [README.md](../README.md#how-it-works) — high-level overview
