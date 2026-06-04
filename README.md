# Bloomy News

Your private news desk. Pulls AI, cybersecurity, finance, and tech
articles from 8 public sources, sorts them into 6 categories, and
shows them in a local dashboard and a Telegram digest — running
itself twice a day on your own machine.

[![Tests](https://github.com/aaru-sh/bloomy-news/actions/workflows/test.yml/badge.svg)](https://github.com/aaru-sh/bloomy-news/actions/workflows/test.yml)
[![License](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)
[![Version](https://img.shields.io/github/v/release/aaru-sh/bloomy-news?include_prereleases)](https://github.com/aaru-sh/bloomy-news/releases)
[![Python](https://img.shields.io/badge/python-3.8%20%7C%203.9%20%7C%203.10%20%7C%203.11%20%7C%203.12-blue.svg)](pyproject.toml)
[![Platform](https://img.shields.io/badge/platform-windows%20%7C%20linux%20%7C%20macos-lightgrey.svg)]()
[![Tests passing](https://img.shields.io/badge/tests-30%20unit%20%2B%2010%20smoke-brightgreen.svg)](tests/)

---

## What you get

- **8 scrapers** — arXiv (13 feeds), GitHub trending, NewsAPI, cybersecurity
  blogs, Finnhub, Google News, and market data
- **6 categories** — LLM, Neural Nets, ML Research, AI Applications,
  Finance, Cybersecurity
- **3-page dashboard** at <http://127.0.0.1:8080> — landing, filters,
  bookmarks. Dark / light theme, keyboard-navigable, screen-reader
  friendly.
- **Telegram digest** — top 3 articles per category, twice a day,
  with inline buttons
- **Smart dedup** — arXiv version tracking + Jaccard title similarity
  (≥0.80) so the same paper / story posted twice counts once
- **Runs itself** — 12-hour scheduler with catch-up if your laptop
  was asleep at the scheduled time
- **One external dep** — `requests`. Everything else is the Python
  standard library

**No cloud. No accounts. No telemetry.** Your data stays on your
machine, and the dashboard is only reachable on `127.0.0.1`.

---

## Quick start

You need **Python 3.8 or newer** and `git`. That's it.

### Install (Windows PowerShell)

```powershell
git clone https://github.com/aaru-sh/bloomy-news.git; Set-Location bloomy-news; pip install -r requirements.txt; python scripts/smoke_test.py
```

### Install (bash / zsh / WSL / macOS / Git Bash)

```bash
git clone https://github.com/aaru-sh/bloomy-news.git && cd bloomy-news && pip install -r requirements.txt && python scripts/smoke_test.py
```

If the smoke test prints `ALL CHECKS PASSED`, you're good.

### Run

**Windows PowerShell:**

```powershell
python news_tool.py; python dashboard/generate_data.py; python dashboard/serve.py
```

**bash / zsh / WSL / macOS / Git Bash:**

```bash
python news_tool.py && python dashboard/generate_data.py && python dashboard/serve.py
```

The server runs in the foreground. Open <http://127.0.0.1:8080> in
your browser. Press `Ctrl+C` to stop the server.

The first run creates `news.db` and the per-category archive
folders. Subsequent runs are idempotent — running the pipeline
twice in a row won't add duplicates.

---

## Optional: enable more scrapers

The pipeline works on **zero API keys**. To unlock the optional
scrapers, copy `.env.example` to `.env` and fill in the ones you
have. Missing keys are skipped silently.

| Key | Source        | Free tier        | Get it at                        |
| --- | ------------- | ---------------- | -------------------------------- |
| `NEWS_API_KEY`     | NewsAPI     | 100 req / day   | <https://newsapi.org>            |
| `FINNHUB_API_KEY`  | Finnhub     | 60 req / min    | <https://finnhub.io>             |
| `TELEGRAM_BOT_TOKEN` | Telegram  | free            | <https://t.me/BotFather>         |

For the full env var table, see [docs/CONFIGURATION.md](docs/CONFIGURATION.md).
For Telegram channel setup, see [docs/DEPLOYMENT.md#telegram-setup](docs/DEPLOYMENT.md#telegram-setup).

---

## Running it on a schedule

The included scheduler runs the pipeline at 12 AM and 12 PM local time
and catches up if your machine was off at the scheduled time.

**Foreground loop** (any platform, Ctrl+C to stop):

```bash
python scripts/scheduler.py
```

**Windows autostart** (registers a registry entry that runs on every
login):

```bash
python scripts/scheduler.py --install
```

**Linux / macOS autostart** — wrap the foreground loop with `systemd`,
`cron`, or `launchd`. Examples in
[docs/DEPLOYMENT.md](docs/DEPLOYMENT.md).

---

## What's in the box

```
bloomy-news/
├── news_tool.py          # pipeline entry point (8 scrapers + classifier + dedup)
├── database.py           # SQLite layer (articles, dedup, FTS5, atomic writes)
├── secrets.py            # env + config loader with ${VAR} expansion
├── dashboard/            # 3-page local UI + HTTP server (127.0.0.1:8080)
├── scripts/
│   ├── scheduler.py      # 12h background loop with catch-up
│   ├── telegram_bot.py   # daily digest poster
│   ├── smoke_test.py     # 10-check fresh-install verifier
│   └── check_system.py   # health check
├── tests/                # 30 unit tests
├── config/               # source URLs, category keywords, telegram channels
├── docs/                 # deep technical docs (see "Learn more" below)
├── .env.example          # template for the 3 optional API keys
├── pyproject.toml
└── requirements.txt
```

For the full file tree, see [docs/PROJECT_STRUCTURE.md](docs/PROJECT_STRUCTURE.md).

---

## Learn more

| If you want to…                                 | Read this                                          |
| ----------------------------------------------- | -------------------------------------------------- |
| Understand the architecture                     | [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md)       |
| Add a new scraper                               | [docs/SCRAPERS.md](docs/SCRAPERS.md)               |
| Tune the classifier                             | [docs/CLASSIFIER.md](docs/CLASSIFIER.md)           |
| Tweak the dedup logic                           | [docs/DEDUP.md](docs/DEDUP.md)                     |
| See every config option                         | [docs/CONFIGURATION.md](docs/CONFIGURATION.md)     |
| Deploy to a server or systemd                   | [docs/DEPLOYMENT.md](docs/DEPLOYMENT.md)           |
| See the full file tree                          | [docs/PROJECT_STRUCTURE.md](docs/PROJECT_STRUCTURE.md) |
| Contribute                                      | [CONTRIBUTING.md](CONTRIBUTING.md)                 |

---

## Troubleshooting

- **"Skipped - no API key" everywhere** — your `.env` is missing or
  malformed. Copy `.env.example` to `.env` and fill in the keys you
  have. The pipeline never crashes on missing keys.
- **Dashboard says "Failed to load articles"** — run
  `python dashboard/generate_data.py` to regenerate the data file.
- **Scheduler says "Pipeline failed"** — check `logs/pipeline_stdout.log`.
  Most often it's a JSON syntax error in `config/sources.json`.
- **Telegram digest doesn't post** — verify the bot token with
  `curl https://api.telegram.org/bot<token>/getMe`, and check the
  channel ID starts with `-100`.
- **arXiv returns 0 articles** — arXiv rate-limits unauthenticated
  requests occasionally. The scraper retries 3 times with backoff.
- **Something else looks off** — run `python scripts/smoke_test.py`
  first. It catches the common mistakes in 10 seconds.

---

## Security

The dashboard binds to `127.0.0.1` only. All file writes are atomic.
The bookmark API validates inputs (ID pattern, 1 KB body, 5K cap).
Secrets are env-only. The HTML output is escaped. See
[SECURITY.md](SECURITY.md) for the threat model and how to report
issues.

---

## Roadmap

- Discord / Slack digest in addition to Telegram
- Live dashboard updates (replace the "refresh to see new" pattern)
- Embedding-based semantic dedup (in addition to Jaccard)
- A "training" mode for the classifier

---

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md).

## License

[MIT](LICENSE) — see the license file for details.
