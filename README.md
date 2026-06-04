# Bloomy News

A self-hosted news aggregation pipeline that scrapes 8 sources, classifies articles into 6 categories, deduplicates intelligently, and surfaces the result in a local dashboard and a Telegram digest — running unattended on a 12-hour cadence.

[![Python](https://img.shields.io/badge/python-3.11%2B-blue.svg)](https://www.python.org/)
[![License](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)
[![Status](https://img.shields.io/badge/status-active-success.svg)]()
[![Tests](https://img.shields.io/badge/tests-18%20passing-brightgreen.svg)](tests/)
[![Platform](https://img.shields.io/badge/platform-windows%20%7C%20linux-lightgrey.svg)]()

---

## Table of contents

- [Why this exists](#why-this-exists)
- [Features](#features)
- [Quick start](#quick-start)
- [Prerequisites](#prerequisites)
- [Installation](#installation)
- [Configuration](#configuration)
- [Usage](#usage)
- [How it works](#how-it-works)
- [Project structure](#project-structure)
- [Development](#development)
- [Deployment](#deployment)
- [Security](#security)
- [Troubleshooting](#troubleshooting)
- [Roadmap](#roadmap)
- [Contributing](#contributing)
- [Changelog](#changelog)
- [License](#license)

---

## Why this exists

Most "news aggregator" projects either pull from a single source, dump everything into one bucket, or require a hosted backend. **Bloomy News** is built for a single user running it on their own machine — no cloud, no accounts beyond the free-tier API keys, no LAN exposure. It pulls from academic preprints, security blogs, general tech news, and financial feeds, then routes each article to the right sub-channel in Telegram and the right filter in the dashboard.

The whole stack is one Python project, one local SQLite file, and one HTTP server bound to `127.0.0.1`. It runs itself twice a day via a Windows-scheduler-style loop, and catches up gracefully if the laptop was off at the scheduled time.

---

## Features

- **8 scrapers** — arXiv (13 RSS feeds), GitHub, NewsAPI, dedicated cybersecurity feeds (SecurityWeek, Krebs, Hacker News, BleepingComputer, AWS/GCP/Azure security blogs), Finnhub finance news, Google News (14 query feeds), and Markets.
- **6-category classifier** with arXiv category as a strong prior, multi-tag output, and a graceful "Uncategorized" fallback when no keyword matches.
- **Two-layer deduplication** — Jaccard title similarity (≥0.80) for general articles + arXiv version tracking (v1/v2/v3 of the same paper collapse to one entry).
- **SQLite primary store** with WAL mode, FTS5 full-text index, and atomic writes. Filesystem archive of compressed `.md.gz` files per category for historical articles.
- **3-page dashboard** at `http://127.0.0.1:8080` — landing (hero + category grid + recent), filters (calendar + search + multi-select dropdowns), bookmarks (starred articles, GitHub-starred style).
- **Dark / light theme** persisted in `localStorage`, WCAG-AA contrast ratios, full keyboard navigation, screen-reader landmarks.
- **Bookmarks with star buttons** on every article card and in the side panel, persisted server-side with input validation (ID pattern, 1KB body cap, 5K bookmark cap).
- **Telegram digest** — top 3 articles per category (18 max) to the main channel; inline buttons to open the source and save to bookmarks.
- **12-hour scheduler** with smart catch-up — if the laptop was off at 12:00, the next run happens at startup (after a 60s delay), not at the next checkpoint.
- **Zero external services** beyond the free-tier APIs and Telegram. No database server, no Redis, no Docker, no cloud function.

---

## Quick start

**Windows (one command):**

```bat
:: from the project root
LAUNCH_DAILY.bat
```

This runs a health check, starts the dashboard server on `http://127.0.0.1:8080`, executes the full news pipeline, and regenerates the dashboard data file.

**Linux / macOS (or step-by-step on Windows):**

```bash
# 1. install dependencies
pip install -r requirements.txt

# 2. create your secret file (optional - works without API keys too)
cp .env.example .env
# edit .env to add TELEGRAM_BOT_TOKEN, NEWS_API_KEY, FINNHUB_API_KEY

# 3. run the pipeline
python news_tool.py
python dashboard/generate_data.py

# 4. start the dashboard
python dashboard/serve.py
# -> open http://127.0.0.1:8080
```

The pipeline works with **zero API keys** — the optional keys (Telegram, NewsAPI, Finnhub) just unlock more scrapers.

---

## Prerequisites

- **Python 3.11+** (uses `tomllib` and modern type hints)
- **pip** for dependency installation
- **Windows 10/11** for the registry-based autostart scheduler. On Linux/macOS, the scheduler works as a foreground loop or can be wrapped with `cron` / `systemd` / `launchd`.
- **A Telegram bot token** (optional, but recommended) — create one via [@BotFather](https://t.me/BotFather).
- **NewsAPI key** (optional) — free tier at [newsapi.org](https://newsapi.org).
- **Finnhub key** (optional) — free tier at [finnhub.io](https://finnhub.io).
- **~50 MB disk** for the SQLite database and historical archives.

---

## Installation

### 1. Clone the repository

```bash
git clone https://github.com/<your-username>/Bloomy-news.git
cd Bloomy-news
```

### 2. Install Python dependencies

```bash
pip install -r requirements.txt
```

The dependency list is intentionally minimal — `requests`, `feedparser`, `python-dateutil`. Everything else is in the Python standard library.

### 3. Configure secrets (optional)

```bash
cp .env.example .env
```

Edit `.env` and fill in any of the three optional keys:

```bash
TELEGRAM_BOT_TOKEN=123456789:ABCdef-GHIjkl_MNOpqrSTUvwxYZ
NEWS_API_KEY=your_newsapi_key_here
FINNHUB_API_KEY=your_finnhub_key_here
```

If a key is missing, the corresponding scraper is skipped silently. The pipeline never crashes on missing config.

### 4. Configure Telegram channels (optional)

If you want the Telegram digest, edit `config/telegram.json` and set the channel IDs for your own bot and channels. The format is the standard Telegram chat ID (`-100...` for supergroups).

### 5. Run it

```bash
# one-shot: pipeline + dashboard
LAUNCH_DAILY.bat         # Windows
./launch_daily.sh        # create this for Linux/macOS — equivalent commands

# or manually:
python news_tool.py && python dashboard/generate_data.py
python dashboard/serve.py
```

Open `http://127.0.0.1:8080` in your browser.

---

## Configuration

All configuration is environment-driven. The order of precedence is:

1. Real environment variables (highest)
2. `.env` file in the project root
3. `config/*.json` files with `${VAR}` placeholder expansion
4. Built-in defaults (lowest)

### Environment variables

| Variable              | Required | Purpose                                                 |
| --------------------- | -------- | ------------------------------------------------------- |
| `TELEGRAM_BOT_TOKEN`  | No       | Bot token for the Telegram digest. Without it, no posting. |
| `NEWS_API_KEY`        | No       | NewsAPI key for the technology/science/business feeds.  |
| `FINNHUB_API_KEY`     | No       | Finnhub key for the market news feed.                   |

See `.env.example` for the template.

### Config files

| File                       | Purpose                                                      |
| -------------------------- | ------------------------------------------------------------ |
| `config/sources.json`      | API key placeholders + 13 arXiv feeds + 14 Google News feeds + security RSS + GitHub repo + Finnhub/NewsAPI endpoint templates |
| `config/categories.json`   | Classification keyword rules per category                   |
| `config/telegram.json`     | Bot token placeholder + main channel ID + 6 sub-channel IDs + channel usernames |

### Adding new feeds

RSS / API feeds are added by editing `config/sources.json`. No code changes are required for new arXiv categories or Google News queries. For new scraper *types* (e.g., a Reddit scraper), see [docs/SCRAPERS.md](docs/SCRAPERS.md).

---

## Usage

### Run the pipeline manually

```bash
python news_tool.py
```

Output looks like:

```
[1/8] arXiv (13 feeds)...
  -> 47 new articles
[2/8] GitHub...
  -> 3 new articles
[3/8] NewsAPI... (skipped - no API key)
[4/8] Cybersecurity...
  -> 12 new articles
[5/8] Finance...
  -> 8 new articles
[6/8] Tech...
  -> 0 new articles
[7/8] Google News (14 feeds)...
  -> 31 new articles
[8/8] Markets...
  -> 5 new articles
Classification: 106 articles, 8 Uncategorized

Pipeline complete. 106 articles added, 21 duplicates suppressed.
Telegram digest sent to 7 channels.
```

### Run the dashboard server

```bash
python dashboard/serve.py
```

Server output (one log line per error, otherwise silent):

```
Serving on http://127.0.0.1:8080
```

### Scheduler commands

```bash
python scripts/scheduler.py --install   # one-time: register HKCU\...\Run\BloomyScheduler
python scripts/scheduler.py --status    # show last-run state
python scripts/scheduler.py --run-now   # run pipeline once and exit
python scripts/scheduler.py              # foreground loop (Ctrl-C to stop)
python scripts/scheduler.py --uninstall # remove registry entry
```

### Dashboard API endpoints

All endpoints return JSON. All error responses use 4xx with a JSON body.

| Method | Path                       | Description                              |
| ------ | -------------------------- | ---------------------------------------- |
| GET    | `/api/articles`            | List articles, supports `?limit=N`       |
| GET    | `/api/bookmarks`           | List bookmarked article IDs              |
| POST   | `/api/bookmarks/toggle`    | Toggle bookmark for `{id: "..."}`        |
| GET    | `/api/stats`               | Per-category counts + total article count |

---

## How it works

### The pipeline, step by step

```
                 scripts/scheduler.py
                 (background loop, 12h cadence)
                            |
                            v
                  news_tool.py (pipeline)
                  ┌─────────┴─────────┐
                  v                   v
            8 scrapers         classify_article
            (parallel-ish,      (keyword match
             sequential)        with arXiv prior
                  │              + multi-tag)
                  └─────────┬─────────┘
                            v
                       database.py
                       (SQLite: articles, dedup_log,
                        FTS5, Jaccard title sim,
                        arXiv version dedup,
                        WAL mode, atomic writes)
                            │
                  ┌─────────┴─────────┐
                  v                   v
         dashboard/generate_data.py   scripts/telegram_bot.py
         (DB-primary, FS-fallback     (top 3 per category
          for historical)             to sub-channels)
                  │
                  v
         dashboard/data/dashboard_data.json
                  │
                  v
         dashboard/serve.py  ──>  http://127.0.0.1:8080
                  │
                  ├── index.html      (landing: hero + category cards + recent)
                  ├── filters.html    (calendar + search + multi-select dropdowns)
                  └── bookmarks.html  (starred articles, GitHub-starred style)
```

### Classification

`classify_article(title, summary, source=None, arxiv_category=None)` returns `(category, confidence, tags, subcategory)`.

The algorithm is keyword scoring with a strong prior:

1. If the source is arXiv, the arXiv subject category (`cs.CL`, `cs.LG`, `q-fin.ST`, etc.) is mapped to one of the 6 categories with high confidence (≥0.9) and used as the primary signal.
2. Otherwise, every word in the title and summary is scored against `CATEGORY_KEYWORDS` in `news_tool.py`. Each match is weighted by where it appears (title vs. body) and how specific the keyword is.
3. The top-scoring category wins. If no keyword matches above the threshold, the article is labeled `"Uncategorized"` (confidence 0.0) instead of being forced into a category.
4. All keywords that matched (across all categories) are returned as a tag list, capped at 5.

For the full keyword table and weighting details, see [docs/CLASSIFIER.md](docs/CLASSIFIER.md).

### Deduplication

Two layers, both in `database.py`:

1. **arXiv version dedup** — arXiv papers have versioned IDs (e.g., `2401.12345v2`). Versions are stripped at ingestion time, so the same paper posted 3 times with different versions is recorded once. Implemented in `_normalize_arxiv_id()`.
2. **Jaccard title similarity** — for every incoming article, the most recent 200 titles in the same category are compared via word-set Jaccard similarity. If any match exceeds 0.80, the article is rejected as a duplicate. Implemented in `is_duplicate_title()` and backed by `dedup_log` for performance.

For edge cases (substring matches, common words, punctuation), see [docs/DEDUP.md](docs/DEDUP.md).

### Scheduler state machine

The scheduler tracks two pieces of state in `.last_run` (atomic JSON write):

```json
{
  "last_run": "2026-06-04T12:00:01",
  "last_status": "ok"
}
```

On startup:

- No state file → run now (catch-up), then schedule
- State >12h old → run now (catch-up), then schedule
- State <12h old → wait for the next 12 AM / 12 PM checkpoint

The two checkpoint hours are `(0, 12)` — midnight and noon local time. This is configurable at the top of `scripts/scheduler.py`.

### Storage layout

Two-tier, write-both, read-DB-first:

- **SQLite** (`news.db`, WAL mode) — primary store. Holds `articles`, `dedup_log`, and an FTS5 virtual table for full-text search. `generate_data.py` reads from here.
- **Filesystem** (`<Category>/<YYYY-MM-DD>/<slug>.md.gz`) — historical archive. `generate_data.py` walks these only for articles missing from the DB (e.g., before a DB migration or for snapshots).

The `news.db` file is the source of truth at runtime. The `.md.gz` archives are a debuggable, gitignoreable history.

---

## Project structure

```
Bloomy-news/
├── LAUNCH_DAILY.bat            one-shot health+server+pipeline+regen (Windows)
├── news_tool.py                pipeline: 8 scrapers, classifier, dedup, telegram poster
├── database.py                 SQLite layer: articles, dedup_log, FTS5, Jaccard
├── secrets.py                  env + config loader with ${VAR} expansion
├── requirements.txt            requests, feedparser, python-dateutil
├── .env.example                template for the 3 optional API keys
├── .gitignore
├── LICENSE                     MIT
│
├── config/
│   ├── sources.json            API key placeholders + 13 arXiv feeds + 14 Google News feeds
│   ├── categories.json         classification keyword rules
│   └── telegram.json           bot placeholder + channel IDs
│
├── scripts/
│   ├── check_system.py         health check (Python version, deps, .env, news.db)
│   ├── scheduler.py            12h background loop with catch-up (registry autostart on Windows)
│   └── telegram_bot.py         daily digest poster (top 3 per category)
│
├── dashboard/
│   ├── index.html              landing: hero + category grid + recent 12
│   ├── filters.html            search + calendar + multi-select dropdowns
│   ├── bookmarks.html          starred articles
│   ├── style.css               shared styles (1628 lines, dark/light, WCAG-AA)
│   ├── app.js                  landing JS (star buttons, side panel, theme)
│   ├── app-filters.js          filter page JS (calendar, search, multi-tag chips)
│   ├── app-bookmarks.js        bookmarks page JS (un-star, side panel)
│   ├── serve.py                local HTTP server (127.0.0.1:8080, ThreadingHTTPServer)
│   ├── generate_data.py        DB-primary JSON builder with atomic write
│   ├── favicon.svg
│   └── data/                   runtime-generated (gitignored except .gitkeep)
│
├── tests/
│   └── test_fixes.py           18 unit tests
│
├── logs/                       runtime logs (gitignored)
│
├── LLM/                        historical article archive (gitignored)
├── Neural-Nets/
├── ML-Research/
├── AI-Applications/
├── Finance/
├── Cybersecurity/
│
├── docs/                       extended technical documentation
│   ├── ARCHITECTURE.md
│   ├── SCRAPERS.md
│   ├── CLASSIFIER.md
│   └── DEDUP.md
│
└── .github/                    GitHub templates
    ├── ISSUE_TEMPLATE/
    │   ├── bug_report.md
    │   └── feature_request.md
    └── PULL_REQUEST_TEMPLATE.md
```

---

## Development

### Running tests

```bash
python -m unittest tests.test_fixes -v
```

18 tests cover:

- `title_similarity` — Jaccard edge cases (identical, partial, normalized, empty)
- Classifier fallback — "Uncategorized" path, no false AI-Applications assignment
- ID validation — `^[a-zA-Z0-9_-]{1,64}$` pattern
- Secrets loader — env-overrides-config precedence, `${VAR}` expansion
- Bookmark API input limits — body cap, bookmark cap
- Scheduler state machine — catch-up at no-state / old-state / recent-state, next-checkpoint calc

### Adding a new scraper

See [docs/SCRAPERS.md](docs/SCRAPERS.md) for the full guide. Short version:

1. Add a `scrape_<name>()` function to `news_tool.py` that returns a list of article dicts with the same shape as the existing scrapers.
2. Add the call to the `run_pipeline()` orchestrator.
3. If the scraper needs an API key, add it to `config/sources.json` and `.env.example`.
4. Add a test if the parser is non-trivial.

### Adding a new category

1. Add a category to `CATEGORIES` in `news_tool.py` and a keyword block to `CATEGORY_KEYWORDS`.
2. Add the category to `config/categories.json` (if you keep keywords there too).
3. Add a `catColor`, `catIcon`, and `catLabel` to each of the three dashboard JS files.
4. Add a sub-channel ID to `config/telegram.json`.
5. Update the README's "Features" section.

### Code style

- **Python**: PEP 8 with 4-space indents, type hints on public functions, f-strings for formatting. No external linter configured — keep it simple.
- **JavaScript**: ES5-compatible syntax (no arrow functions, no `const`/`let`, no template literals) for maximum browser compatibility. `var` only. `escapeHtml()` for any user-controlled string before innerHTML.
- **HTML**: semantic tags first, ARIA only where semantics fail. All interactive elements get a focus-visible style.

---

## Deployment

### Background scheduling on Windows

```bash
python scripts/scheduler.py --install
```

This registers `HKCU\Software\Microsoft\Windows\CurrentVersion\Run\BloomyScheduler` with the value:

```
C:\Path\To\pythonw.exe "E:\Path\To\Bloomy-news\scripts\scheduler.py"
```

On every login, Windows starts the scheduler in the background (no console window, `pythonw.exe`). The scheduler then loops forever, running the pipeline at midnight and noon local time, with startup catch-up.

To remove: `python scripts/scheduler.py --uninstall`.

### Background scheduling on Linux / macOS

The scheduler works as a foreground loop. Wrap it with your platform's init system:

- **systemd** — create a user service that runs `python scripts/scheduler.py`
- **cron** — add `0 0,12 * * * cd /path/to/Bloomy-news && python news_tool.py && python dashboard/generate_data.py`
- **launchd** — create a `LaunchAgent` plist

The `scripts/scheduler.py --status` command works the same on all platforms.

### Telegram setup

1. Create a bot via [@BotFather](https://t.me/BotFather). Save the token to `.env` as `TELEGRAM_BOT_TOKEN`.
2. Create a channel, add the bot as an administrator with "post messages" permission.
3. Get the channel ID — send a message in the channel, then call `https://api.telegram.org/bot<token>/getUpdates` and read the `chat.id` from the response.
4. Put the channel ID (with the `-100` prefix) into `config/telegram.json` as `main_channel_id`.
5. Run `python news_tool.py` once. The digest should post within a few minutes.

---

## Security

- **Dashboard server binds `127.0.0.1`** only — not reachable from your LAN.
- **Bookmark API validates** the article ID against `^[a-zA-Z0-9_-]{1,64}$`, caps request bodies at 1 KB, and caps the bookmark list at 5,000 entries. All exceeded limits return `400` or `413`.
- **Atomic writes** for `bookmarks.json`, `dashboard_data.json`, `.last_run`, and the SQLite WAL mode guarantee no torn writes on crash.
- **Secrets are env-only.** Real values never appear in any tracked JSON or HTML file. `secrets.py` is the single reader; placeholder values like `${TELEGRAM_BOT_TOKEN}` are expanded at runtime.
- **CORS is restricted** to `http://localhost:8080`. All responses carry `X-Content-Type-Options: nosniff`, `X-Frame-Options: DENY`, `Referrer-Policy: no-referrer`, and `Cache-Control: no-store` for API endpoints.
- **HTML escaping** in the dashboard: all article text passes through `escapeHtml()` before `innerHTML` assignment. URL fields pass through `safeUrl()` which only allows `http://` and `https://`.
- **`.env` is gitignored.** A scan of every tracked file confirms no real tokens, API keys, or channel IDs (other than public Telegram channel IDs, which anyone can read by joining the channel).

If you find a security issue, please open a private advisory instead of a public issue.

---

## Troubleshooting

### "Skipped - no API key" everywhere

Your `.env` is missing or unreadable. Check:
- File exists at the project root (not in a subfolder).
- No trailing whitespace after the `=` sign.
- `python -c "from dotenv import dotenv_values; print(dotenv_values('.env'))"` returns your values.

### Dashboard says "Failed to load articles"

The `dashboard/data/dashboard_data.json` file is missing or stale. Run:

```bash
python dashboard/generate_data.py
```

If the file is corrupt, the server logs the JSON parse error to `logs/server.log`.

### Scheduler says "Pipeline failed" but logs look fine

Check `logs/pipeline_stdout.log` and `logs/scheduler.log`. The most common cause is a `config/sources.json` syntax error after a manual edit. Validate with `python -c "import json; json.load(open('config/sources.json'))"`.

### Telegram digest doesn't post

- Verify the bot token: `curl https://api.telegram.org/bot<token>/getMe`
- Verify the bot is an admin in the channel with "post messages" permission.
- Check the channel ID — it must be a supergroup ID starting with `-100`.
- Check `logs/pipeline_stdout.log` for the `Telegram` section.

### arXiv scraper returns 0 articles

arXiv occasionally rate-limits unauthenticated requests. The scraper already retries 3 times with exponential backoff. If you're consistently rate-limited, the request will show up in `logs/pipeline.log` as `HTTP 429`.

### Card borders look invisible on your monitor

The card border opacity (`rgba(255,255,255,0.4)`) is tuned for a typical laptop screen at 100% brightness. On high-brightness HDR displays it may look subtle. Edit the value in `dashboard/style.css` and reload.

---

## Roadmap

- [ ] Discord / Slack digest in addition to Telegram
- [ ] WebSocket-based live updates (replace the "refresh to see new" pattern)
- [ ] Per-user authentication for the dashboard (when run on a server instead of localhost)
- [ ] Embedding-based semantic dedup (in addition to Jaccard) for better cross-language detection
- [ ] RSS aggregator mode (read `OPML` of favorite feeds)
- [ ] A "training" mode for the classifier — accept user corrections to teach new keywords

---

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) for bug reports, feature requests, and pull request guidelines.

---

## Changelog

See [CHANGELOG.md](CHANGELOG.md) for the version history and what shipped in each release.

---

## License

[MIT](LICENSE) — see the license file for details.
