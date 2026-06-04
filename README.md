# Bloomsberg News

Local news aggregation system that scrapes 8 sources, classifies into 6 categories, stores in SQLite, publishes to a local dashboard and a Telegram digest, and runs automatically twice daily.

## Quick start

```bat
LAUNCH_DAILY.bat
```

Does a health check, starts the local dashboard server on `http://127.0.0.1:8080`, runs the news pipeline, and regenerates the dashboard data file.

For manual / scheduled runs:

```bash
python news_tool.py
python dashboard/generate_data.py
```

## Automation

Twice-daily scheduler (12:00 AM and 12:00 PM local) with smart catch-up if the laptop was off.

```bash
python scripts/scheduler.py --install   # one-time setup: registers HKCU\...\Run\BloomsbergScheduler
python scripts/scheduler.py --status    # show last-run state
python scripts/scheduler.py --run-now   # run pipeline once and exit
python scripts/scheduler.py --uninstall
```

State is persisted in `.last_run`. The scheduler reads the timestamp on startup and only runs if the last successful run was more than 12 hours ago (with a 60s startup delay).

## Architecture

```
                 scripts/scheduler.py
                 (background loop, 12h cadence)
                            |
                            v
                  news_tool.py (pipeline)
                  ┌─────────┴─────────┐
                  v                   v
            8 scrapers         classify_article
            (arXiv, GitHub,     (keyword match,
            NewsAPI, Cyber,     returns category
            Finance, Tech,      + confidence +
            Google News,        subcategory)
            Markets)
                  │                   │
                  └─────────┬─────────┘
                            v
                       database.py
                       (SQLite: articles, dedup_log,
                        FTS5, Jaccard title sim,
                        arXiv version dedup,
                        WAL mode)
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
                  ├── filters.html    (calendar + search + category/source/date)
                  └── bookmarks.html  (starred articles, GitHub-starred style)
```

The dashboard binds to `127.0.0.1` only — not accessible from the LAN.

## Scrapers

All defined in `news_tool.py`:

| Scraper       | Source                                              | Output                |
| ------------- | --------------------------------------------------- | --------------------- |
| arXiv         | 13 arXiv RSS feeds (cs.CL, cs.AI, cs.LG, etc.)      | LLM, Neural-Nets, ML-Research, Cybersecurity, Finance |
| GitHub        | VoltAgent/awesome-ai-agent-papers                   | LLM, AI-Applications, Cybersecurity |
| NewsAPI       | NewsAPI (top headlines)                             | All categories        |
| Cybersecurity | SecurityWeek, Krebs, The Hacker News, BleepingComputer | Cybersecurity       |
| Finance       | Finnhub market news                                 | Finance               |
| Tech          | RSS feeds                                           | LLM, AI-Applications, ML-Research |
| Google News   | 14 query feeds (LLM, agents, ML, cyber, market, fed, quant, etc.) | All categories      |
| Markets       | Additional finance feeds                            | Finance               |

API keys and feed URLs live in `config/sources.json`. Secrets are loaded via `secrets.py` with `${VAR}` expansion from `.env`.

## Categories

Defined in `config/categories.json` and `news_tool.py:CATEGORY_KEYWORDS`. Six primary plus one fallback:

- LLM
- Neural-Nets
- ML-Research
- AI-Applications
- Finance
- Cybersecurity
- Uncategorized (fallback when no keyword matches above the threshold)

Each article gets a category, confidence score, tags, and a subcategory.

## Storage

Two-tier:

- **SQLite** (`news.db`, WAL mode) — primary store, FTS5 full-text search, Jaccard-similarity title dedup, arXiv version dedup (treats v1/v2/v3 of same paper as one)
- **Filesystem** (`LLM/`, `Neural-Nets/`, `ML-Research/`, `AI-Applications/`, `Finance/`, `Cybersecurity/` at project root) — historical articles as compressed `.md.gz`. `generate_data.py` reads DB first, falls back to filesystem only for older entries.

`news_tool.py` writes to both. `generate_data.py` reads from DB-primary.

## Dashboard

`http://127.0.0.1:8080/index.html` after `LAUNCH_DAILY.bat`.

- Three pages: `index.html` (landing), `filters.html` (calendar + search + dropdowns), `bookmarks.html` (starred)
- Dark/light theme toggle (persisted in `localStorage`)
- Bookmarks: server-side JSON file at `dashboard/data/bookmarks.json` with `POST /api/bookmarks/toggle`
- Search and filter all client-side over the generated JSON

## Telegram

`scripts/telegram_bot.py` posts a daily digest:

- Top 3 articles per category (18 max) to the main channel
- Inline buttons to the source URL and a "save to bookmarks" callback
- One run per day, after the pipeline completes

Bot token and channel IDs are in `config/telegram.json` (substitute `${TELEGRAM_BOT_TOKEN}` from `.env`).

## Configuration

`.env` (real values, gitignored):

```
TELEGRAM_BOT_TOKEN=...
NEWSAPI_KEY=...
FINNHUB_KEY=...
```

`.env.example` — template.

`config/sources.json` — API keys, RSS feed URLs.

`config/categories.json` — classification keyword rules.

`config/telegram.json` — bot username, main channel, per-category sub-channel IDs.

`secrets.py` is the central loader: reads `.env` first, falls back to `config/*.json` with `${VAR}` placeholder expansion.

## Tests

```bash
python -m unittest tests.test_fixes -v
```

18 tests covering `title_similarity`, classifier fallback, ID validation, secrets loader, bookmark API input limits, and scheduler state-machine.

## Directory layout

```
E:\AI\Projects\News\
├── LAUNCH_DAILY.bat            one-shot health+server+pipeline+regen
├── news_tool.py                pipeline (scrapers, classifier, dedup, telegram)
├── database.py                 SQLite layer (articles, dedup_log, FTS5, Jaccard)
├── secrets.py                  env+config loader
├── news.db                     SQLite database
├── requirements.txt
├── .env / .env.example
├── .gitignore
├── .last_run                   scheduler state (timestamp + last status)
│
├── config/
│   ├── sources.json            API keys + RSS feeds
│   ├── categories.json         classification rules
│   └── telegram.json           bot + channel IDs
│
├── scripts/
│   ├── check_system.py         health check
│   ├── scheduler.py            12h background loop with catch-up
│   └── telegram_bot.py         daily digest poster
│
├── dashboard/
│   ├── index.html              landing
│   ├── filters.html            search + calendar + dropdowns
│   ├── bookmarks.html          starred articles
│   ├── style.css
│   ├── app.js / app-filters.js / app-bookmarks.js
│   ├── serve.py                local HTTP server (127.0.0.1:8080)
│   ├── generate_data.py        DB-primary JSON builder
│   ├── favicon.svg
│   └── data/
│       ├── dashboard_data.json
│       └── bookmarks.json
│
├── tests/
│   └── test_fixes.py           18 unit tests
│
├── logs/
│   ├── pipeline.log
│   ├── pipeline_stdout.log
│   ├── scheduler.log
│   └── server.log
│
├── LLM/                        historical article archive (compressed)
├── Neural-Nets/
├── ML-Research/
├── AI-Applications/
├── Finance/
├── Cybersecurity/
│
└── index/                      leftover artifacts from older pipeline,
                                not referenced by current code
```

## Security notes

- Dashboard server binds `127.0.0.1` only — not reachable from the LAN
- Bookmark API validates ID pattern (`[a-zA-Z0-9_-]{1,64}`), caps body at 1KB and bookmark count at 5000
- All HTTP responses include `X-Content-Type-Options`, `X-Frame-Options`, `Referrer-Policy`, `Cache-Control`
- CORS restricted to `http://localhost:8080`
- `secrets.py` is the only place that reads `config/*.json`; raw values never reach HTML/JS
- `.env` is gitignored; `.env.example` has placeholders only
