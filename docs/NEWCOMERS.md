# Concepts for newcomers

This document is a plain-English primer for people who are new to the AI/ML field. If you have built news aggregators or scrapers before, you can skip it — the [README](../README.md) is for you.

---

## What this project does, in plain English

A **news aggregator** is a program that reads articles from many different websites and combines them in one place. The "many different websites" part is interesting because every website publishes news differently. Some expose a feed (a small, structured file that says "here are my latest 20 articles"). Some offer an **API** (an official door for programs to ask for the latest articles). Some have neither, and you have to parse the HTML yourself. Bloomy News does all three.

Bloomy News runs **eight scrapers** (one per source type) and writes the result into a single **SQLite database** file. After the articles are in the database, three things happen:

1. A **classifier** looks at each article's title and summary and decides which of six **categories** it belongs to (LLM, Neural Nets, ML Research, AI Applications, Finance, Cybersecurity). The default classifier is a hand-written keyword matcher — no neural network, no GPU, no API cost. It is fast, deterministic, and runs offline. If `sentence-transformers` is installed (see [Classification](#classification) below), an embedding-based classifier kicks in automatically — higher accuracy on ambiguous titles, at the cost of a one-time ~80 MB model download and ~1 GB of disk for PyTorch.
2. A **deduplicator** removes articles that are essentially the same. The same press release often appears on five different sites, and arXiv papers get re-posted as the authors update them; both cases are caught.
3. Two **publishers** make the data visible: a local HTTP **dashboard** at `http://127.0.0.1:8080` (only reachable from your own machine), and a **Telegram digest** that posts the top three articles per category to a channel of your choice.

A **scheduler** repeats the whole process every 12 hours — at 12:00 and 24:00 local time. If your machine was asleep at 12:00, the scheduler runs the pipeline as soon as you start it again (with a 60-second delay so it doesn't fight with the boot process), and then resumes the 12-hour cadence.

The whole project is **one folder, one Python interpreter, and three optional API keys**. No Docker, no Postgres, no Redis, no cloud function, no telemetry.

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

*You are reading `docs/NEWCOMERS.md`. When you are ready to install, head back to the [README](../README.md).*
