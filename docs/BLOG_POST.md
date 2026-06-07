# Bloomy News: A self-hosted AI news aggregator that actually works

**Show HN: I built a self-hosted news aggregator that scrapes 8 sources, classifies articles with AI, deduplicates with Jaccard similarity, and delivers a daily Telegram digest — all from a single Python process with zero cloud dependencies.**

---

## The problem

I follow AI research, machine learning, cybersecurity, and finance. That means monitoring arXiv, GitHub trending, SecurityWeek, Krebs on Security, Finnhub, NewsAPI, Google News, and a dozen other feeds. Every day.

I tried Feedly. I tried Inoreader. I tried building custom RSS readers. The problem was always the same: too many sources, too much noise, no classification, and every solution wants me to log into their cloud.

I wanted something different: a local tool that pulls fresh articles twice a day, sorts them into categories I care about, removes duplicates, and shows the result in a dashboard I can actually use. No accounts. No telemetry. No cloud.

So I built it.

## What it does

Bloomy News is a self-hosted news desk that runs on your own machine. It does four things:

1. **Scrapes 8 sources** — arXiv (13 RSS feeds), GitHub trending, NewsAPI, cybersecurity blogs, finance news, tech feeds, Google News, and market data
2. **Classifies articles** into 6 categories using AI — LLM, Neural Networks, ML Research, AI Applications, Finance, Cybersecurity
3. **Deduplicates** using Jaccard title similarity and arXiv version tracking
4. **Delivers digests** via a local dashboard and Telegram bot

The whole pipeline runs as a single Python process. No Docker, no Node.js, no database server. Just Python 3.8+ and one `pip install`.

## How it works

Here's the architecture in one diagram:

```
  ┌─────────────────────────────────────────────────────┐
  │              scripts/scheduler.py                    │
  │         (background loop, 12h cadence)               │
  └──────────────────────┬──────────────────────────────┘
                         │
                         v
               ┌─────────────────┐
               │   news_tool.py  │
               │   (pipeline)    │
               └────────┬────────┘
                        │
           ┌────────────┼────────────┐
           v            v            v
     ┌──────────┐ ┌──────────┐ ┌──────────┐
     │ arXiv    │ │ GitHub   │ │ NewsAPI  │
     │ (13 RSS) │ │ trending │ │          │
     └────┬─────┘ └────┬─────┘ └────┬─────┘
          │             │             │
     ┌────┴─────┐ ┌────┴─────┐ ┌────┴─────┐
     │Cybersec  │ │ Finance  │ │ Google   │
     │ feeds    │ │ + Tech   │ │ News     │
     └────┬─────┘ └────┬─────┘ └────┬─────┘
          │             │             │
          └─────────────┼─────────────┘
                        │
                        v
              ┌──────────────────┐
              │ classifier.py    │
              │ (keyword +       │
              │  embedding)      │
              └────────┬─────────┘
                       │
                       v
              ┌──────────────────┐
              │ database.py      │
              │ (SQLite + WAL +  │
              │  FTS5 + Jaccard  │
              │  + arXiv dedup)  │
              └────────┬─────────┘
                       │
              ┌────────┴────────┐
              v                 v
  ┌───────────────────┐ ┌─────────────────────┐
  │ dashboard/        │ │ telegram.py         │
  │ (3-page local UI) │ │ (daily digest)      │
  └───────────────────┘ └─────────────────────┘
```

The pipeline runs sequentially through the scrapers, classifies each article, deduplicates against the database, stores everything in SQLite, then optionally posts a Telegram digest with the top 3 articles per category.

## Key features

### AI classification with two modes

The classifier has two paths, and it picks automatically based on what's installed:

**Keyword mode** (default, zero deps) — every word in the title and summary is scored against curated keyword tables. The arXiv subject category acts as a strong prior (`cs.CL` → LLM, `cs.LG` → ML Research, `q-fin.ST` → Finance). Fast, deterministic, offline. If nothing crosses the threshold, the article lands in `Uncategorized` instead of being forced into the wrong bucket.

**Embedding mode** (opt-in, `sentence-transformers`) — the title+summary is encoded with `all-MiniLM-L6-v2` and compared by cosine similarity against per-category semantic centroids built from curated example titles. Higher accuracy on ambiguous headlines. Falls back to keywords automatically if the model fails to load.

```python
# The classifier picks the best path automatically
from classifier import classify_article

# Returns (category, confidence, tags, subcategory, embedding)
cat, conf, tags, sub, emb = classify_article(article)
# → ("LLM", 0.87, ["LLM"], "news", <np.ndarray>)
```

### Two-layer deduplication

Nobody wants to see the same arXiv paper three times because it was posted as v1, v2, and v3. Bloomy News handles this at two levels:

1. **arXiv version stripping** — `2401.12345v2` becomes `2401.12345` at ingestion time, so the same paper is stored once regardless of how many versions appear in the feed.

2. **Jaccard title similarity** — for every incoming article, the most recent 200 titles in the same category are compared using word-set Jaccard similarity. If any match exceeds 0.80, the article is rejected as a duplicate.

```python
from database import is_duplicate_title

# Compares against recent titles in the same category
is_duplicate_title("New LLM beats GPT-4 on reasoning", "LLM")
# → False

is_duplicate_title("New LLM beats GPT-4 on reasoning benchmarks", "LLM")
# → True (Jaccard > 0.80 against similar title)
```

### 30-day retention

The SQLite database stays small by automatically purging articles older than 30 days. Historical articles are archived as compressed `.md.gz` files in per-category folders — a human-readable backup that doubles as a debugging tool.

### Local-only by design

The dashboard server binds to `127.0.0.1` only. Not reachable from your LAN. No cloud services beyond the free-tier APIs you optionally configure. Your data stays on your machine.

### One-command deployment

```bash
# Clone, install, run. That's it.
git clone https://github.com/aaru-sh/bloomy-news.git
cd bloomy-news
pip install -r requirements.txt
python news_tool.py
```

On Windows, the scheduler registers itself as a startup item so the pipeline runs automatically at login:

```bash
python scripts/scheduler.py --install
```

## Getting started

**1. Install:**

```bash
git clone https://github.com/aaru-sh/bloomy-news.git
cd bloomy-news
pip install -r requirements.txt
```

**2. Run the pipeline:**

```bash
python news_tool.py
```

**3. Start the dashboard:**

```bash
python dashboard/generate_data.py
python dashboard/serve.py
```

Open `http://127.0.0.1:8080` in your browser. The landing page shows a hero section, category cards with live counts, and the most recent articles. The filters page has a calendar picker, full-text search, and multi-select dropdowns. The bookmarks page lets you star articles for later.

The pipeline works with zero API keys. NewsAPI, Finnhub, and Telegram are optional — just add keys to `.env` when you want them. The arXiv, GitHub, cybersecurity, and Google News scrapers work out of the box.

## Technical highlights

- **131 tests** with 68% coverage across unit tests, integration tests, and a smoke test that verifies a fresh install in 10 seconds
- **CI/CD** via GitHub Actions — the full test suite + smoke test runs on every push across Python 3.8–3.12
- **mypy** for static type checking on core modules
- **SQLite WAL mode** with atomic writes for crash safety — no torn writes if the process is killed mid-run
- **FTS5 full-text search** for fast article lookup
- **ES5-compatible JavaScript** in the dashboard — no arrow functions, no `const`/`let`, no template literals. Works in every browser.
- **WCAG-AA contrast ratios** in both dark and light themes
- **Zero external services** beyond free-tier APIs — no Redis, no Docker, no cloud function

## What's next

The roadmap includes:

- **Discord / Slack digest** — daily digests via webhooks or bot tokens
- **WebSocket live updates** — real-time feed without manual refresh
- **Semantic dedup** — sentence-embedding similarity alongside Jaccard for better cross-language detection
- **RSS aggregator mode** — ingest arbitrary feeds, accept OPML import/export
- **Classifier training** — let users label articles and retrain from feedback
- **Multi-user support** — authentication, per-user preferences, isolated digests

## Contributing

Contributions are welcome. Check out the [good first issues](https://github.com/aaru-sh/bloomy-news/labels/good%20first%20issue) for starter tasks, or open a thread in [GitHub Discussions](https://github.com/aaru-sh/bloomy-news/discussions) with ideas or questions.

The project follows PEP 8 for Python, ES5 for JavaScript, and semantic HTML with ARIA only where semantics fail.

## Links

- **GitHub:** [github.com/aaru-sh/bloomy-news](https://github.com/aaru-sh/bloomy-news)
- **License:** MIT
- **Docs:** [docs/](https://github.com/aaru-sh/bloomy-news/tree/main/docs) — ARCHITECTURE.md, CLASSIFIER.md, DEDUP.md, SCRAPERS.md, and more

---

*Built with Python 3.8+. Powered by arXiv, GitHub, NewsAPI, SecurityWeek, Krebs on Security, BleepingComputer, Finnhub, Google News, and the Python standard library.*
