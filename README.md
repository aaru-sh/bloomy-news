# Bloomy News

A self-hosted news desk for people who follow AI, machine learning, cybersecurity, and finance. Bloomy News runs on your own machine, pulls fresh articles from eight public sources twice a day, sorts them into six categories, removes duplicates, and shows the result in a local dashboard and a Telegram digest — no cloud, no account, no telemetry.

If you are new to the AI field, the rest of this README is written so that you can understand every line. If you have built news aggregators before, skip the **Concepts** section and head straight to [Quick start](#quick-start).

[![Tests](https://github.com/aaru-sh/bloomy-news/actions/workflows/test.yml/badge.svg)](https://github.com/aaru-sh/bloomy-news/actions/workflows/test.yml)
[![License](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)
[![Version](https://img.shields.io/github/v/release/aaru-sh/bloomy-news?include_prereleases)](https://github.com/aaru-sh/bloomy-news/releases)
[![Python](https://img.shields.io/badge/python-3.8%20%7C%203.9%20%7C%203.10%20%7C%203.11%20%7C%203.12-blue.svg)](pyproject.toml)
[![Platform](https://img.shields.io/badge/platform-windows%20%7C%20linux%20%7C%20macos-lightgrey.svg)]()
[![Tests passing](https://img.shields.io/badge/tests-30%20unit%20%2B%2010%20smoke-brightgreen.svg)](tests/)

---

## What this project does, in plain English

A **news aggregator** is a program that reads articles from many different websites and combines them in one place. The "many different websites" part is interesting because every website publishes news differently. Some expose a feed (a small, structured file that says "here are my latest 20 articles"). Some offer an **API** (an official door for programs to ask for the latest articles). Some have neither, and you have to parse the HTML yourself. Bloomy News does all three.

Bloomy News runs **eight scrapers** (one per source type) and writes the result into a single **SQLite database** file. After the articles are in the database, three things happen:

1. A **classifier** looks at each article's title and summary and decides which of six **categories** it belongs to (LLM, Neural Nets, ML Research, AI Applications, Finance, Cybersecurity). The classifier is a hand-written keyword matcher — no LLM, no neural network, no GPU, no API cost. It is fast, deterministic, and runs offline.
2. A **deduplicator** removes articles that are essentially the same. The same press release often appears on five different sites, and arXiv papers get re-posted as the authors update them; both cases are caught.
3. Two **publishers** make the data visible: a local HTTP **dashboard** at `http://127.0.0.1:8080` (only reachable from your own machine), and a **Telegram digest** that posts the top three articles per category to a channel of your choice.

A **scheduler** repeats the whole process every 12 hours — at 12:00 and 24:00 local time. If your machine was asleep at 12:00, the scheduler runs the pipeline as soon as you start it again (with a 60-second delay so it doesn't fight with the boot process), and then resumes the 12-hour cadence.

The whole project is **one folder, one Python interpreter, and three optional API keys**. No Docker, no Postgres, no Redis, no cloud function, no telemetry.

---

## Quick start

You need **Python 3.8 or newer** and `git`. The pipeline works with zero API keys; you only need them if you want to enable NewsAPI, Finnhub, or the Telegram digest.

### Install

**Windows PowerShell:**

```powershell
git clone https://github.com/aaru-sh/bloomy-news.git; Set-Location bloomy-news; pip install -r requirements.txt; python scripts/smoke_test.py
```

**bash / zsh / WSL / macOS / Git Bash:**

```bash
git clone https://github.com/aaru-sh/bloomy-news.git && cd bloomy-news && pip install -r requirements.txt && python scripts/smoke_test.py
```

If the smoke test prints `ALL CHECKS PASSED`, your install is good. If it prints `[FAIL]`, read the line under it — it tells you what is wrong and how to fix it.

### Run

**Windows PowerShell:**

```powershell
python news_tool.py; python dashboard/generate_data.py; python dashboard/serve.py
```

**bash / zsh / WSL / macOS / Git Bash:**

```bash
python news_tool.py && python dashboard/generate_data.py && python dashboard/serve.py
```

Open <http://127.0.0.1:8080> in your browser. Press `Ctrl+C` to stop the server.

The first run creates `news.db` (the SQLite database) and six per-category archive folders. Subsequent runs are **idempotent** — running the pipeline twice in a row does not add duplicate articles.

### Run on a schedule

**Windows (auto-start at login):**

```bash
python scripts/scheduler.py --install
```

**Linux / macOS (foreground loop, or wrap with `cron` / `systemd` / `launchd`):**

```bash
python scripts/scheduler.py
```

Details for every platform are in [Deployment](#deployment--windows-linux-macos-and-telegram-setup).

---

## Concepts for newcomers

This section explains every technical term used in the rest of the README. If you are already familiar with RSS, APIs, classifiers, and SQL, you can skip to [What's in the box](#whats-in-the-box).

### The AI / ML landscape

If you are entering the AI field, you will see these terms thrown around. They are not synonyms:

- **Artificial Intelligence (AI)** is the broadest term: any system that does something that would normally need human thinking. This includes rule-based systems, search algorithms, optimization solvers, and machine learning.
- **Machine Learning (ML)** is a subset of AI where the system learns rules from data, rather than being explicitly programmed. The classic example is a spam filter: instead of writing "if the subject contains 'free', classify as spam", you give the system 10,000 labeled emails and let it find the patterns.
- **Deep Learning** is a subset of ML that uses **neural networks** with many layers. Deep learning is what powers most of the recent AI breakthroughs — image recognition, speech synthesis, large language models. "Deep" refers to the number of layers, not to philosophical depth.
- **Neural Networks (Neural Nets)** are the architecture behind deep learning. They are loosely inspired by how biological neurons connect, but the analogy is loose — modern neural nets are just chains of matrix multiplications with non-linear activation functions in between.
- **Large Language Models (LLMs)** are a specific application of deep learning: very large neural networks trained on huge text corpora to predict the next word in a sequence. GPT, Claude, Llama, and Mistral are all LLMs. They are a subset of deep learning, which is a subset of ML, which is a subset of AI.
- **ML Research** is the academic study of new machine learning methods. Papers on arXiv under `cs.LG` (machine learning) and `stat.ML` (statistics for ML) are categorized here.
- **AI Applications** is what people build with the above. A medical imaging tool, a coding assistant, a recommendation engine, a fraud detector — these are all AI applications.

Bloomy News tracks all four layers because someone entering the field needs to see research papers (`ML Research` and `Neural Nets`) and the new models they produce (`LLM`) and the products built on top of them (`AI Applications`).

### Data sources

- **arXiv** ([arxiv.org](https://arxiv.org)) is a free, open-access archive of research papers. Researchers post their papers here **before** peer review, so you see results months before they appear in a journal. The catch: arXiv does not have a search API the way Google does, but it does expose **RSS feeds** for every subject category. Bloomy News scrapes 13 arXiv RSS feeds covering the relevant subjects.
- **GitHub Trending** is a page on github.com that lists repositories gaining stars fast. The HTML is structured enough to parse directly. Bloomy News uses this to surface newly-popular open-source AI projects.
- **NewsAPI** ([newsapi.org](https://newsapi.org)) is a paid (with a free tier) service that aggregates news from 80,000+ sources and lets you query by keyword. You need an API key. Without one, this scraper is skipped.
- **Cybersecurity feeds** are RSS feeds from five security publications (SecurityWeek, Krebs on Security, Hacker News, BleepingComputer, AWS/GCP/Azure security blogs). They are free, public RSS feeds.
- **Finnhub** ([finnhub.io](https://finnhub.io)) is a financial data API. The free tier covers market news. You need an API key. Without one, this scraper is skipped.
- **Google News** is Google's news aggregation service. It exposes RSS feeds for arbitrary search queries (e.g., `q=AI+regulation+site:reuters.com`). Bloomy News uses 14 of these for topics that no other source covers well.
- **Markets** is a hand-written scraper for general market headlines (indices, crypto summaries, forex). It is the fallback when Finnhub is not configured.

### RSS, APIs, and HTML scraping

Every web scraper eventually falls into one of three categories:

- **RSS / Atom feeds.** RSS (Really Simple Syndication) and Atom are XML-based formats for publishing "here is my latest content" in a machine-readable way. A feed URL looks like `https://example.com/feed.xml` and contains a list of items with title, link, publish date, and summary. Scraping an RSS feed is just downloading the XML and parsing the items. Most blogs, news sites, and academic repositories have a feed — even if it is not advertised.
- **REST APIs.** An API (Application Programming Interface) is a contract for how programs talk to each other. A REST API exposes **endpoints** (URLs) that return structured data (usually JSON) when you send a properly-formatted request. The contract is documented somewhere (a "docs" page) and usually requires an **API key** for authentication and rate limiting. NewsAPI, Finnhub, and the GitHub API are all REST APIs.
- **HTML scraping.** When neither a feed nor an API exists, you download the HTML of a page and parse it. This is fragile — the page layout can change at any time and break your scraper. Bloomy News uses HTML scraping only as a last resort, for sources that genuinely have no other option.

### Classifiers and categories

A **classifier** is a function that takes an input (in our case, an article's title and summary) and assigns it to one of a fixed set of labels (the **categories**). The simplest kind of classifier is a **keyword matcher**: count how many times each category's keywords appear, pick the one with the highest count. That is exactly what Bloomy News does. It is not as accurate as a fine-tuned neural network, but it is:

- **Deterministic** — same input always gives the same output.
- **Inspectable** — you can see exactly why an article ended up in a category by reading the keyword table.
- **Free** — no GPU, no API cost, no model download.
- **Fast** — microseconds per article.

For a private aggregator where the categories are stable and the volume is small (a few hundred articles a day), keyword matching is the right tool. You do not need a transformer to put "Tesla unveils new battery" into Finance.

The six categories in Bloomy News are:

| Category         | What goes here                                                                      |
| ---------------- | ----------------------------------------------------------------------------------- |
| `LLM`            | News and papers about large language models specifically: GPT, Claude, Llama, etc. |
| `Neural Nets`    | General deep learning research: new architectures, training tricks, optimizers.    |
| `ML Research`    | Machine learning more broadly: theory, statistics, classical ML, evaluation.       |
| `AI Applications`| Products and tools built with AI: chatbots, copilots, image generators, agents.    |
| `Finance`        | Markets, stocks, crypto, fintech, regulation, earnings.                           |
| `Cybersecurity`  | Vulnerabilities, breaches, security research, advisories, patches.                 |

If a non-arXiv article matches no keyword above a threshold, it is labeled `Uncategorized` rather than being forced into the closest fit.

### Deduplication

The same article often appears in multiple sources. A press release gets picked up by Reuters, Bloomberg, and Yahoo Finance within minutes. arXiv papers get **versioned** — the author posts v1, gets feedback, posts v2 with revisions, posts v3 with a typo fix — and the new versions are technically new entries in the RSS feed.

Bloomy News has two deduplication layers:

1. **arXiv version dedup.** Strips the `vN` suffix from arXiv IDs at ingestion. `2401.12345v1` and `2401.12345v3` are treated as the same paper.
2. **Jaccard title similarity.** For every incoming article, the most recent 200 titles in the same category are compared via **Jaccard similarity**: the size of the intersection of the two word sets, divided by the size of the union. A score above **0.80** means the titles share more than 80% of their words, and the new article is treated as a duplicate. Jaccard similarity is a classic information-retrieval metric; it is what Google used in the 1990s before embeddings took over.

### Storage

Bloomy News uses two storage layers:

- **SQLite database** (`news.db`) — the primary store. SQLite is a file-based database engine; the entire database is a single file on disk. It supports SQL queries, transactions, and indexes. We enable **WAL mode** (Write-Ahead Logging) for concurrent reads, and an **FTS5** full-text index for fast search.
- **Filesystem archive** (`<Category>/<YYYY-MM-DD>/<slug>.md.gz`) — a per-category, per-date folder of compressed Markdown files. This is the human-readable, gitignoreable historical record.

At read time, the dashboard reads from the database first. The filesystem archive is the fallback for older articles and a debugging tool.

### The local server, the scheduler, and Telegram

- **Local HTTP server** (`dashboard/serve.py`) — serves the three HTML pages, the CSS, the JavaScript, and a small JSON API. It binds to `127.0.0.1:8080`, which is the **loopback** address — your machine can reach it, your network cannot. If you ran it on `0.0.0.0`, anyone on your Wi-Fi could open the dashboard. We deliberately don't.
- **Scheduler** (`scripts/scheduler.py`) — a small loop that runs the pipeline twice a day. It uses the **Windows registry** on Windows (the `HKCU\...\Run` key is the standard place for "start this at login" entries) and a foreground loop on Linux/macOS that you can wrap with `cron`, `systemd`, or `launchd`.
- **Telegram bot** (`scripts/telegram_bot.py`) — uses the [Telegram Bot API](https://core.telegram.org/bots/api) to post the daily digest. You create a bot via [@BotFather](https://t.me/BotFather), get a token, and the bot posts messages to whichever channel you add it to. Telegram is a free, reliable channel for short digests — much cheaper than running a web server with push notifications.

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
├── docs/                 # deep technical docs
├── .env.example          # template for the 3 optional API keys
├── pyproject.toml
└── requirements.txt
```

<details>
<summary><strong>Full feature list</strong></summary>

- **8 scrapers** — arXiv (13 RSS feeds), GitHub trending, NewsAPI, dedicated cybersecurity feeds (SecurityWeek, Krebs, Hacker News, BleepingComputer, AWS/GCP/Azure security blogs), Finnhub finance news, Google News (14 query feeds), and Markets.
- **6-category classifier** — LLM, Neural Nets, ML Research, AI Applications, Finance, Cybersecurity — with arXiv subject as a strong prior, multi-tag output, and a graceful `Uncategorized` fallback when no keyword matches.
- **Two-layer deduplication** — Jaccard title similarity (≥0.80) for general articles + arXiv version tracking (v1/v2/v3 of the same paper collapse to one entry).
- **SQLite primary store** with WAL mode, FTS5 full-text index, and atomic writes. Filesystem archive of compressed `.md.gz` files per category for historical articles.
- **3-page dashboard** at `http://127.0.0.1:8080` — landing (hero + category grid + recent), filters (calendar + search + multi-select dropdowns), bookmarks (starred articles, GitHub-starred style).
- **Dark / light theme** persisted in `localStorage`, WCAG-AA contrast ratios, full keyboard navigation, screen-reader landmarks.
- **Bookmarks with star buttons** on every article card and in the side panel, persisted server-side with input validation (ID pattern, 1 KB body cap, 5K bookmark cap).
- **Telegram digest** — top 3 articles per category (18 max) to the main channel; inline buttons to open the source and save to bookmarks.
- **12-hour scheduler** with smart catch-up — if the laptop was off at 12:00, the next run happens at startup (after a 60s delay), not at the next checkpoint.
- **Zero external services** beyond the free-tier APIs and Telegram. No database server, no Redis, no Docker, no cloud function.

**No cloud. No accounts. No telemetry.** Your data stays on your machine, and the dashboard is only reachable on `127.0.0.1`.

</details>

<details>
<summary><strong>Prerequisites — what you need to install before Bloomy News</strong></summary>

- **Python 3.8 or newer.** Tested on 3.8, 3.9, 3.10, 3.11, and 3.12. If you do not have Python, download it from [python.org](https://python.org) and check "Add to PATH" on Windows. To check what you have, run `python --version` in a terminal.
- **pip** — Python's package manager. It ships with Python, so if you have Python, you have pip. Run `pip --version` to confirm.
- **git** — a version-control tool. You need it to clone the repository. Download from [git-scm.com](https://git-scm.com). Run `git --version` to confirm.
- **A terminal** — PowerShell on Windows, Terminal.app or iTerm2 on macOS, any terminal on Linux. You will type a few commands.
- **~50 MB of free disk** for the SQLite database and the historical `.md.gz` archive.
- **Windows 10 or 11** for the registry-based autostart scheduler. On Linux/macOS, the scheduler works as a foreground loop or can be wrapped with `cron` / `systemd` / `launchd`.
- **A Telegram bot token** (optional, but recommended) — create one in five minutes by talking to [@BotFather](https://t.me/BotFather) on Telegram.
- **NewsAPI key** (optional) — free tier at [newsapi.org](https://newsapi.org). 100 requests per day.
- **Finnhub key** (optional) — free tier at [finnhub.io](https://finnhub.io). 60 requests per minute.

That is the entire prerequisite list. No Docker, no Node.js, no database server, no system services.

</details>

<details>
<summary><strong>Installation — step by step, every platform</strong></summary>

### 1. Clone the repository

Cloning means "download a copy of the project to your machine". `git clone` creates a new folder named `bloomy-news` in your current directory and copies the entire project history into it.

```bash
git clone https://github.com/aaru-sh/bloomy-news.git
cd bloomy-news
```

On Windows PowerShell, use `;` instead of `&&` to chain commands:

```powershell
git clone https://github.com/aaru-sh/bloomy-news.git; Set-Location bloomy-news
```

### 2. Install Python dependencies

The project depends on exactly one external package: `requests` (used by the Telegram bot and the system health check). Everything else comes from the Python standard library: `sqlite3`, `urllib.request`, `http.server`, `json`, `re`, `hashlib`, `gzip`, `argparse`, `subprocess`, `logging`, `pathlib`, `datetime`, `collections`.

```bash
pip install -r requirements.txt
```

You can also install the project as an editable package if you prefer:

```bash
pip install -e .
```

Both approaches do the same thing. The `-e` flag (editable) means your changes to the source code take effect without re-installing; the `-r requirements.txt` form is simpler and works for non-developers.

### 3. Configure secrets (optional)

A **secret** is something you do not want to publish — an API key, a bot token, a password. In software projects, secrets live in a file named `.env` (short for "environment") that is **gitignored** (excluded from version control so it never gets pushed to GitHub). Every developer copies a template named `.env.example`, renames it to `.env`, and fills in their own secrets.

```bash
cp .env.example .env
```

Now edit `.env` and fill in any of the three optional keys:

```bash
TELEGRAM_BOT_TOKEN=123456789:ABCdef-GHIjkl_MNOpqrSTUvwxYZ
NEWS_API_KEY=your_newsapi_key_here
FINNHUB_API_KEY=your_finnhub_key_here
```

If a key is missing, the corresponding scraper is skipped silently. The pipeline **never crashes on missing config** — the goal is that you can run it with zero configuration and see the arXiv + GitHub + cybersecurity scrapers work, then add keys later to enable more.

### 4. Configure Telegram channels (optional)

If you want the Telegram digest, edit `config/telegram.json` and set the channel IDs for your own bot and channels. The format is the standard Telegram chat ID (supergroup channels start with `-100`, then have the channel's numeric ID).

A JSON file is a plain text file with a strict syntax for structured data. If you are not familiar with JSON, the shape is `"key": "value"` for strings, `{ ... }` for objects, and `[ ... ]` for lists. Editors like VS Code highlight the syntax and catch missing commas.

### 5. Run the pipeline

```bash
python news_tool.py
python dashboard/generate_data.py
python dashboard/serve.py
```

The three commands do three different things:

- `news_tool.py` runs the eight scrapers, classifies the new articles, deduplicates, and posts to Telegram.
- `dashboard/generate_data.py` reads the SQLite database and writes a single JSON file (`dashboard/data/dashboard_data.json`) that the dashboard pages load.
- `dashboard/serve.py` starts the local HTTP server on `127.0.0.1:8080`.

Open <http://127.0.0.1:8080> in your browser.

### 6. Verify your install

```bash
python scripts/smoke_test.py
# or, if you have make:
make smoke
```

This runs 10 self-contained checks (Python version, dependencies, config files, no hardcoded paths, database init, server start, classifier, secrets precedence) and prints clear `[OK]` / `[FAIL]` lines with remediation hints. It exits 0 on success, 1 on failure, and never touches your real `news.db`.

</details>

<details>
<summary><strong>Configuration — every option in one place</strong></summary>

All configuration is **environment-driven**. The order of precedence is:

1. Real environment variables (highest)
2. `.env` file in the project root
3. `config/*.json` files with `${VAR}` placeholder expansion
4. Built-in defaults (lowest)

### Environment variables

| Variable               | Required | Default       | Used by                                  |
| ---------------------- | -------- | ------------- | ---------------------------------------- |
| `TELEGRAM_BOT_TOKEN`   | no       | _placeholder_ | `scripts/telegram_bot.py`                |
| `TELEGRAM_CHAT_ID`     | no       | _placeholder_ | `scripts/telegram_bot.py`                |
| `NEWS_API_KEY`         | no       | _placeholder_ | `news_tool.py` (NewsAPI scraper)         |
| `FINNHUB_API_KEY`      | no       | _placeholder_ | `news_tool.py` (Finnhub scraper)         |
| `ARXIV_RATE_LIMIT`     | no       | `3.0`         | `news_tool.py` (seconds between requests) |
| `LOG_LEVEL`            | no       | `INFO`        | All scripts                              |
| `HTTP_PROXY`           | no       | _none_        | All `urllib` / `requests` calls          |
| `HTTPS_PROXY`          | no       | _none_        | All `urllib` / `requests` calls          |

### Config files

Three JSON files in `config/` carry the per-source and per-channel settings that don't belong in env vars:

| File                     | What it holds                                              |
| ------------------------ | ---------------------------------------------------------- |
| `config/sources.json`    | All feed URLs, API endpoints, and per-source tuning        |
| `config/categories.json` | The category keyword tables used by the classifier         |
| `config/telegram.json`   | Bot token placeholder + channel IDs (main + 6 sub-channels) |

Any string value in these files can use `${VAR}` placeholder syntax, expanded at load time by `secrets.py`. For example, `config/telegram.json` might have:

```json
{
  "bot_token": "${TELEGRAM_BOT_TOKEN}",
  "main_channel_id": "${TELEGRAM_MAIN_CHANNEL_ID}",
  "sub_channels": {
    "LLM":     "${TELEGRAM_LLM_CHANNEL_ID}",
    "Finance": "${TELEGRAM_FINANCE_CHANNEL_ID}"
  }
}
```

The placeholder is never resolved with a real value into a tracked file — only `.env` (gitignored) carries the real value. This means a real bot token can never accidentally end up in your git history.

### Adding new feeds

For RSS / Atom feeds, edit `config/sources.json` and add the URL to the right category. For full custom scrapers (JSON APIs that need parsing), see [docs/SCRAPERS.md](docs/SCRAPERS.md).

For Telegram sub-channels, add a new `TELEGRAM_<NAME>_CHANNEL_ID` entry to `.env` and reference it in `config/telegram.json`.

For new classification keywords, edit `config/categories.json`. The keyword format and scoring rules are in [docs/CLASSIFIER.md](docs/CLASSIFIER.md).

</details>

<details>
<summary><strong>Usage — every command and API endpoint</strong></summary>

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
python scripts/scheduler.py --install    # one-time: register HKCU\...\Run\BloomyScheduler
python scripts/scheduler.py --status     # show last-run state
python scripts/scheduler.py --run-now    # run pipeline once and exit
python scripts/scheduler.py              # foreground loop (Ctrl+C to stop)
python scripts/scheduler.py --uninstall  # remove registry entry
```

### Dashboard API endpoints

All endpoints return JSON. All error responses use 4xx with a JSON body.

| Method | Path                       | Description                              |
| ------ | -------------------------- | ---------------------------------------- |
| GET    | `/api/articles`            | List articles, supports `?limit=N`       |
| GET    | `/api/bookmarks`           | List bookmarked article IDs              |
| POST   | `/api/bookmarks/toggle`    | Toggle bookmark for `{id: "..."}`        |
| GET    | `/api/stats`               | Per-category counts + total article count |

</details>

<details>
<summary><strong>How it works — the pipeline, classification, and dedup</strong></summary>

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
                  └── bookmarks.html  (starred articles)
```

### Classification

`classify_article(title, summary, source=None, arxiv_category=None)` returns `(category, confidence, tags, subcategory)`.

The algorithm is keyword scoring with a strong prior:

1. **arXiv prior.** If the source is arXiv, the arXiv subject category (`cs.CL` for computation and language, `cs.LG` for machine learning, `q-fin.ST` for financial statistics, etc.) is mapped to one of the 6 categories with high confidence (≥0.9) and used as the primary signal. This is reliable because arXiv authors self-categorize.
2. **Keyword scoring.** Otherwise, every word in the title and summary is scored against `CATEGORY_KEYWORDS` in `news_tool.py`. Each match is weighted by where it appears (title vs. body) and how specific the keyword is.
3. **Top-category wins.** The top-scoring category wins. If no keyword matches above the threshold, the article is labeled `Uncategorized` (confidence 0.0) instead of being forced into a category.
4. **Multi-tag output.** All keywords that matched (across all categories) are returned as a tag list, capped at 5.

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

- **No state file** → run now (catch-up), then schedule
- **State >12h old** → run now (catch-up), then schedule
- **State <12h old** → wait for the next 12 AM / 12 PM checkpoint

The two checkpoint hours are `(0, 12)` — midnight and noon local time. This is configurable at the top of `scripts/scheduler.py`.

### Storage layout

Two-tier, write-both, read-DB-first:

- **SQLite** (`news.db`, WAL mode) — primary store. Holds `articles`, `dedup_log`, and an FTS5 virtual table for full-text search. `generate_data.py` reads from here.
- **Filesystem** (`<Category>/<YYYY-MM-DD>/<slug>.md.gz`) — historical archive. `generate_data.py` walks these only for articles missing from the DB (e.g., before a DB migration or for snapshots).

The `news.db` file is the source of truth at runtime. The `.md.gz` archives are a debuggable, gitignoreable history.

</details>

<details>
<summary><strong>Project structure — the full file tree</strong></summary>

```
bloomy-news/
├── .env.example                template for the 3 optional API keys
├── .github/                    GitHub templates + CI
│   ├── ISSUE_TEMPLATE/
│   │   ├── bug_report.md
│   │   ├── feature_request.md
│   │   └── config.yml         disables blank issues, links to Discussions
│   ├── PULL_REQUEST_TEMPLATE.md
│   ├── workflows/
│   │   └── test.yml           CI: unit + smoke on Python 3.8 – 3.12
│   └── dependabot.yml         weekly pip updates
├── .gitignore
├── CHANGELOG.md               Keep-a-Changelog
├── CODE_OF_CONDUCT.md         Contributor Covenant 2.1
├── CONTRIBUTING.md            bug reports, PR guidelines, code style
├── CITATION.cff               CFF metadata for "Cite this repository"
├── LICENSE                    MIT
├── Makefile                   `make run|test|smoke|install|clean` shortcuts
├── README.md                  the file you're reading
├── RELEASE_NOTES.md           pre-formatted notes for the GitHub Release UI
├── SECURITY.md                threat model + reporting policy
├── pyproject.toml             PEP 621 metadata; `pip install -e .` works
├── requirements.txt           `requests>=2.28.0` (the only external dep)
│
├── config/                    tracked JSON, ${VAR} placeholders only
│   ├── categories.json        classification keyword rules
│   ├── sources.json           API endpoints + 13 arXiv feeds + 14 Google News feeds
│   └── telegram.json          bot placeholder + 7 channel IDs
│
├── dashboard/                 3-page local UI + HTTP server
│   ├── index.html             landing: hero + category cards + recent
│   ├── filters.html           search + calendar + multi-tag chips
│   ├── bookmarks.html         starred articles
│   ├── style.css              ~1628 lines, dark/light, WCAG-AA contrast
│   ├── app.js                 landing JS (star buttons, side panel, theme)
│   ├── app-filters.js         filter page JS (calendar, search, dropdowns)
│   ├── app-bookmarks.js       bookmarks page JS (un-star, side panel)
│   ├── favicon.svg
│   ├── serve.py               local HTTP server (127.0.0.1:8080, ThreadingHTTPServer)
│   ├── generate_data.py       DB-primary JSON builder with atomic write
│   └── data/                  runtime-generated (gitignored except .gitkeep)
│
├── database.py                SQLite layer: articles, dedup_log, FTS5, Jaccard
├── news_tool.py               pipeline: 8 scrapers, classifier, dedup, telegram poster
├── secrets.py                 env + config loader with ${VAR} expansion
│
├── scripts/
│   ├── check_system.py        health check (Python version, deps, .env, news.db)
│   ├── scheduler.py           12h background loop with catch-up
│   ├── smoke_test.py          10-check fresh-install verifier
│   └── telegram_bot.py        daily digest poster (top 3 per category)
│
├── tests/
│   ├── test_fixes.py          18 unit tests
│   └── test_fresh_install.py  12 fresh-install + server smoke tests
│
├── docs/                      extended technical documentation
│   ├── ARCHITECTURE.md
│   ├── CLASSIFIER.md
│   ├── CONFIGURATION.md
│   ├── DEDUP.md
│   ├── DEPLOYMENT.md
│   ├── PROJECT_STRUCTURE.md
│   └── SCRAPERS.md
│
├── logs/                      runtime logs (gitignored, .gitkeep tracked)
│
└── category folders (gitignored, .gitkeep tracked) — historical article archive
    ├── LLM/
    ├── Neural-Nets/
    ├── ML-Research/
    ├── AI-Applications/
    ├── Finance/
    └── Cybersecurity/
```

**Where to add things:**

| You want to…              | Touch this file / folder                                                  |
| ------------------------- | ------------------------------------------------------------------------- |
| Add an RSS feed           | `config/sources.json`                                                     |
| Add a JSON-API scraper    | `news_tool.py` (and document in `docs/SCRAPERS.md`)                       |
| Add a category            | `news_tool.py` (CATEGORIES + CATEGORY_KEYWORDS) + `config/categories.json` + all 3 `dashboard/app*.js` |
| Add a dashboard page      | `dashboard/<name>.html` + `dashboard/app-<name>.js` + register in `dashboard/serve.py` |
| Add a Telegram sub-channel| `.env` (add `TELEGRAM_<NAME>_CHANNEL_ID`) + `config/telegram.json`         |
| Add an env var            | `.env.example` + `secrets.py` (loader) + `docs/CONFIGURATION.md`          |
| Change the 12h cadence    | `scripts/scheduler.py` (CHECKPOINT_HOURS tuple)                            |
| Change the dedup threshold| `database.py` (JACCARD_THRESHOLD constant) + `docs/DEDUP.md`              |

</details>

<details>
<summary><strong>Development — tests, Makefile, adding scrapers, code style</strong></summary>

### Running tests

```bash
python -m unittest discover -s tests -v
# or, with make:
make test
```

30 tests cover:

- `title_similarity` — Jaccard edge cases (identical, partial, normalized, empty)
- Classifier fallback — `Uncategorized` path, no false AI-Applications assignment
- ID validation — `^[a-zA-Z0-9_-]{1,64}$` pattern
- Secrets loader — env-overrides-config precedence, `${VAR}` expansion
- Bookmark API input limits — body cap, bookmark cap
- Scheduler state machine — catch-up at no-state / old-state / recent-state, next-checkpoint calc
- **Fresh-install** — all 5 module paths derive from `__file__` (no hardcoded machine paths); `init_db()` creates the schema at the project root; `serve.py` returns valid empty JSON when `dashboard_data.json` is missing; the bookmark API accepts/validates IDs end-to-end over a real HTTP server.

For a user-facing health check (no test runner required), see `python scripts/smoke_test.py` (`make smoke`) — it is the same idea as the fresh-install test, but packaged as a single command for end users.

CI: `.github/workflows/test.yml` runs the full 30-test suite + the 10-check smoke test on every push and PR, across Python 3.8 – 3.12 on Ubuntu.

### Common tasks (Makefile)

```bash
make install              # pip install -r requirements.txt
make test                 # run the test suite
make pipeline             # run the news pipeline once
make server               # start the dashboard server (foreground)
make run                  # one-shot: health + server + pipeline + regen
make scheduler-install    # install scheduler as Windows autostart
make scheduler-uninstall  # remove scheduler autostart
make scheduler-status     # print scheduler state
make scheduler-run        # run the scheduler pipeline once and exit
make clean                # delete news.db, dashboard data, .last_run
```

All targets are pure cross-platform. Override the interpreter with `make PYTHON=python3 ...` if `python3` isn't on your PATH.

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

</details>

<details>
<summary><strong>Deployment — Windows, Linux, macOS, and Telegram setup</strong></summary>

### Background scheduling on Windows

```bash
python scripts/scheduler.py --install
```

This registers `HKCU\Software\Microsoft\Windows\CurrentVersion\Run\BloomyScheduler` with the value:

```
C:\Path\To\pythonw.exe "C:\Path\To\bloomy-news\scripts\scheduler.py"
```

On every login, Windows starts the scheduler in the background (no console window, `pythonw.exe`). The scheduler then loops forever, running the pipeline at midnight and noon local time, with startup catch-up.

To remove: `python scripts/scheduler.py --uninstall`.

### Background scheduling on Linux / macOS

The scheduler works as a foreground loop. Wrap it with your platform's init system:

- **systemd** — create a user service that runs `python scripts/scheduler.py`
- **cron** — add `0 0,12 * * * cd /path/to/bloomy-news && python news_tool.py && python dashboard/generate_data.py`
- **launchd** — create a `LaunchAgent` plist

The `scripts/scheduler.py --status` command works the same on all platforms.

### Telegram setup

1. Create a bot via [@BotFather](https://t.me/BotFather). Save the token to `.env` as `TELEGRAM_BOT_TOKEN`.
2. Create a channel, add the bot as an administrator with "post messages" permission.
3. Get the channel ID — send a message in the channel, then call `https://api.telegram.org/bot<token>/getUpdates` and read the `chat.id` from the response.
4. Put the channel ID (with the `-100` prefix) into `config/telegram.json` as `main_channel_id`.
5. Run `python news_tool.py` once. The digest should post within a few minutes.

</details>

<details>
<summary><strong>Security — what the project does and how to report issues</strong></summary>

- **Dashboard server binds `127.0.0.1`** only — not reachable from your LAN.
- **Bookmark API validates** the article ID against `^[a-zA-Z0-9_-]{1,64}$`, caps request bodies at 1 KB, and caps the bookmark list at 5,000 entries. All exceeded limits return `400` or `413`.
- **Atomic writes** for `bookmarks.json`, `dashboard_data.json`, `.last_run`, and the SQLite WAL mode guarantee no torn writes on crash.
- **Secrets are env-only.** Real values never appear in any tracked JSON or HTML file. `secrets.py` is the single reader; placeholder values like `${TELEGRAM_BOT_TOKEN}` are expanded at runtime.
- **CORS is restricted** to `http://localhost:8080`. All responses carry `X-Content-Type-Options: nosniff`, `X-Frame-Options: DENY`, `Referrer-Policy: no-referrer`, and `Cache-Control: no-store` for API endpoints.
- **HTML escaping** in the dashboard: all article text passes through `escapeHtml()` before `innerHTML` assignment. URL fields pass through `safeUrl()` which only allows `http://` and `https://`.
- **`.env` is gitignored.** A scan of every tracked file confirms no real tokens, API keys, or channel IDs.

If you find a security issue, please open a private advisory instead of a public issue. See [SECURITY.md](SECURITY.md) for the threat model and contact channels.

</details>

<details>
<summary><strong>Troubleshooting — 6 common issues, one line each</strong></summary>

- **"Skipped - no API key" everywhere** — your `.env` is missing or malformed. Copy `.env.example` to `.env` and fill in the keys you have. The pipeline never crashes on missing keys.
- **Dashboard says "Failed to load articles"** — run `python dashboard/generate_data.py` to regenerate the data file. If the file is corrupt, the server logs the JSON parse error to `logs/server.log`.
- **Scheduler says "Pipeline failed" but logs look fine** — check `logs/pipeline_stdout.log` and `logs/scheduler.log`. The most common cause is a `config/sources.json` syntax error after a manual edit. Validate with `python -c "import json; json.load(open('config/sources.json'))"`.
- **Telegram digest doesn't post** — verify the bot token with `curl https://api.telegram.org/bot<token>/getMe`. Verify the bot is an admin in the channel with "post messages" permission. Check the channel ID — it must be a supergroup ID starting with `-100`. Check `logs/pipeline_stdout.log` for the `Telegram` section.
- **arXiv scraper returns 0 articles** — arXiv occasionally rate-limits unauthenticated requests. The scraper already retries 3 times with exponential backoff. If you're consistently rate-limited, the request will show up in `logs/pipeline.log` as `HTTP 429`.
- **Card borders look invisible on your monitor** — the card border opacity (`rgba(255,255,255,0.4)`) is tuned for a typical laptop screen at 100% brightness. On high-brightness HDR displays it may look subtle. Edit the value in `dashboard/style.css` and reload.

If something else looks off, run `python scripts/smoke_test.py` first — it catches the common mistakes in 10 seconds.

</details>

<details>
<summary><strong>Roadmap — what's coming next</strong></summary>

- Discord / Slack digest in addition to Telegram
- WebSocket-based live updates (replace the "refresh to see new" pattern)
- Per-user authentication for the dashboard (when run on a server instead of localhost)
- Embedding-based semantic dedup (in addition to Jaccard) for better cross-language detection
- RSS aggregator mode (read `OPML` of favorite feeds)
- A "training" mode for the classifier — accept user corrections to teach new keywords

</details>

---

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) for bug reports, feature requests, and pull request guidelines.

## License

[MIT](LICENSE) — see the license file for details.

## Acknowledgments

- arXiv for hosting open-access research
- The RSS feeds that publish under permissive terms (SecurityWeek, Krebs on Security, BleepingComputer, the cloud-provider security blogs)
- The Python community for a standard library rich enough that this project needs only one external dependency
