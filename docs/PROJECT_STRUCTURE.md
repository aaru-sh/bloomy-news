# Project structure

The full file tree. For the friendly overview, see the
[README](../README.md#whats-in-the-box).

```
bloomy-news/
├── .env.example                template for the 3 optional API keys
├── .github/                    GitHub templates + CI
│   ├── ISSUE_TEMPLATE/
│   │   ├── bug_report.md
│   │   ├── feature_request.md
│   │   └── config.yml        disables blank issues, links to Discussions
│   ├── PULL_REQUEST_TEMPLATE.md
│   ├── workflows/
│   │   └── test.yml           CI: unit + smoke on Python 3.8 – 3.12
│   └── dependabot.yml         weekly pip updates
├── .gitignore
├── CHANGELOG.md                Keep-a-Changelog
├── CODE_OF_CONDUCT.md          Contributor Covenant 2.1
├── CONTRIBUTING.md             bug reports, PR guidelines, code style
├── CITATION.cff                CFF metadata for "Cite this repository"
├── LICENSE                     MIT
├── Makefile                    `make run|test|smoke|install|clean` shortcuts
├── README.md                   the file you're reading about
├── RELEASE_NOTES.md            pre-formatted notes for the GitHub Release UI
├── SECURITY.md                 threat model + reporting policy
├── pyproject.toml              PEP 621 metadata; `pip install -e .` works
├── requirements.txt            `requests>=2.28.0` (the only external dep)
│
├── config/                     tracked JSON, ${VAR} placeholders only
│   ├── categories.json         classification keyword rules
│   ├── sources.json            API endpoints + 13 arXiv feeds + 14 Google News feeds
│   └── telegram.json           bot placeholder + 7 channel IDs
│
├── dashboard/                  3-page local UI + HTTP server
│   ├── index.html              landing: hero + category cards + recent
│   ├── filters.html            search + calendar + multi-tag chips
│   ├── bookmarks.html          starred articles
│   ├── style.css               ~1628 lines, dark/light, WCAG-AA contrast
│   ├── app.js                  landing JS (star buttons, side panel, theme)
│   ├── app-filters.js          filter page JS (calendar, search, dropdowns)
│   ├── app-bookmarks.js        bookmarks page JS (un-star, side panel)
│   ├── favicon.svg
│   ├── serve.py                local HTTP server (127.0.0.1:8080, ThreadingHTTPServer)
│   ├── generate_data.py        DB-primary JSON builder with atomic write
│   └── data/                   runtime-generated (gitignored except .gitkeep)
│
├── database.py                 SQLite layer: articles, dedup_log, FTS5, Jaccard
├── news_tool.py                pipeline: 8 scrapers, classifier, dedup, telegram poster
├── secrets.py                  env + config loader with ${VAR} expansion
│
├── scripts/
│   ├── check_system.py         health check (Python version, deps, .env, news.db)
│   ├── scheduler.py            12h background loop with catch-up
│   ├── smoke_test.py           10-check fresh-install verifier
│   └── telegram_bot.py         daily digest poster (top 3 per category)
│
├── tests/
│   ├── test_fixes.py           18 unit tests
│   └── test_fresh_install.py   12 fresh-install + server smoke tests
│
├── docs/                       extended technical documentation
│   ├── ARCHITECTURE.md
│   ├── CLASSIFIER.md
│   ├── CONFIGURATION.md        (this section lives here)
│   ├── DEDUP.md
│   ├── DEPLOYMENT.md
│   ├── PROJECT_STRUCTURE.md    (this file)
│   └── SCRAPERS.md
│
├── logs/                       runtime logs (gitignored, .gitkeep tracked)
│
└── category folders (gitignored, .gitkeep tracked) — historical article archive
    ├── LLM/
    ├── Neural-Nets/
    ├── ML-Research/
    ├── AI-Applications/
    ├── Finance/
    └── Cybersecurity/
```

---

## File-size cheat sheet

| File                       | Approx size | Why it's the size it is        |
| -------------------------- | ----------- | ------------------------------ |
| `dashboard/style.css`      | ~1628 lines | Dark + light themes, 6 category palettes, responsive, focus-visible, animations |
| `docs/ARCHITECTURE.md`     | ~280 lines  | System diagram + design notes  |
| `docs/SCRAPERS.md`         | ~220 lines  | One section per scraper family |
| `docs/CLASSIFIER.md`       | ~190 lines  | Keyword table + scoring rules  |
| `news_tool.py`             | ~1400 lines | 8 scrapers + classifier + dedup + orchestrator |
| `database.py`              | ~700 lines  | Articles + FTS5 + dedup log + atomic writes + migrations |
| `dashboard/serve.py`       | ~400 lines  | HTTP server + 4 API endpoints + 3 static pages |
| `dashboard/generate_data.py` | ~250 lines | DB-primary read, FS-walk fallback, atomic JSON write |

---

## Where to add things

| You want to…              | Touch this file / folder                                  |
| ------------------------- | --------------------------------------------------------- |
| Add an RSS feed           | `config/sources.json`                                     |
| Add a JSON-API scraper    | `news_tool.py` (and document in `docs/SCRAPERS.md`)       |
| Add a category            | `news_tool.py` (CATEGORIES + CATEGORY_KEYWORDS) + `config/categories.json` + all 3 `dashboard/app*.js` |
| Add a dashboard page      | `dashboard/<name>.html` + `dashboard/app-<name>.js` + register in `dashboard/serve.py` |
| Add a Telegram sub-channel| `.env` (add `TELEGRAM_<NAME>_CHANNEL_ID`) + `config/telegram.json` |
| Add an env var            | `.env.example` + `secrets.py` (loader) + `docs/CONFIGURATION.md` |
| Change the 12h cadence    | `scripts/scheduler.py` (CHECKPOINT_HOURS tuple)          |
| Change the dedup threshold| `database.py` (JACCARD_THRESHOLD constant) + `docs/DEDUP.md` |
