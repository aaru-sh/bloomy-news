# Scrapers

This document explains how the existing scrapers work and how to add a new one.

## Scraper contract

Every scraper is a top-level function in `news_tool.py` with this signature:

```python
def scrape_<name>() -> list[dict]:
    """Return a list of articles in the canonical shape."""
```

The canonical article shape is:

```python
{
    "id":          str,    # unique; arxiv normalized ID or sha256(title+url)
    "title":       str,    # required, no truncation
    "summary":     str,    # may be "" if no summary is available
    "url":         str,    # canonical source URL
    "source":      str,    # human-readable: "arXiv cs.CL", "KrebsOnSecurity", etc.
    "published":   str,    # ISO 8601, e.g. "2026-06-04T10:30:00"
    "arxiv_category": str | None,  # only for arXiv articles
    "raw":         dict,   # full original payload, stored in articles.raw_json
}
```

`category`, `subcategory`, `confidence`, and `tags` are filled in by `classify_article()` after the scraper returns. Scrapers don't set these.

## Existing scrapers

### `scrape_arxiv()` — 13 RSS feeds

Fetches the RSS feed for each arXiv subject category listed in `config/sources.json` under `arxiv_rss`. Parses with `feedparser`, normalizes the version suffix out of the ID, and sets `arxiv_category` from the URL path. The first 5 entries per feed are kept (arXiv feeds can be huge).

This is the only scraper that sets `arxiv_category`, which the classifier uses as a strong prior.

### `scrape_github()` — 1 repo

Fetches the README of the `VoltAgent/awesome-ai-agent-papers` repo (a curated list of agent research papers). Parses markdown links to extract paper titles and URLs. Each entry in the README becomes one article.

The raw README is cached in memory for 1 hour to avoid hammering the GitHub API on warm runs.

### `scrape_newsapi()` — top headlines

Hits the NewsAPI `top-headlines` endpoint for three categories (technology, science, business). 15 articles per category. Requires `NEWS_API_KEY`; skipped if not set.

### `scrape_cybersecurity()` — 7 security RSS feeds

Aggregates 7 dedicated security blogs: SecurityWeek, The Hacker News, Krebs on Security, BleepingComputer, AWS Security Blog, Google Cloud Security, and Microsoft Defender for Cloud. Fetches all 7 in sequence, parses with `feedparser`, de-duplicates within the run by URL.

### `scrape_finance()` — Finnhub market news

Hits the Finnhub `/news?category=general` endpoint. 15 articles. Requires `FINNHUB_API_KEY`; skipped if not set.

### `scrape_tech()` — RSS aggregator

This is a generic scraper that pulls from a list of tech RSS feeds defined inline in `news_tool.py` (e.g., TechCrunch, Ars Technica, The Verge). Not configurable via `config/sources.json` — if you want to add a tech feed, edit the source list in the function.

### `scrape_google_news()` — 14 query feeds

Fetches 14 Google News RSS search feeds defined in `config/sources.json` under `google_news_rss`. Each feed is a search query (e.g., "large language model OR LLM OR GPT", "cybersecurity OR data breach", "stock market OR trading"). The first 5 results per feed are kept.

### `scrape_markets()` — additional finance feeds

A second finance-focused scraper with feeds like Bloomberg Markets, Reuters Business, MarketWatch. Same generic pattern as `scrape_tech()`.

## The fetch helper

All scrapers use the `fetch_json()` and `fetch_text()` helpers at the top of `news_tool.py`:

```python
def fetch_json(url, timeout=15):
    """GET url, parse JSON, return dict. None on any error."""
    try:
        r = requests.get(url, timeout=timeout, headers={"User-Agent": "Bloomy/1.0"})
        r.raise_for_status()
        return r.json()
    except (requests.RequestException, ValueError) as e:
        log(f"fetch_json({url}) failed: {e}")
        return None

def fetch_text(url, timeout=15):
    """GET url, return text. None on any error."""
    try:
        r = requests.get(url, timeout=timeout, headers={"User-Agent": "Bloomy/1.0"})
        r.raise_for_status()
        return r.text
    except requests.RequestException as e:
        log(f"fetch_text({url}) failed: {e}")
        return None
```

Both helpers log the error and return `None`. Scraper code checks for `None` and skips that source. **Never let a single failed fetch crash the whole pipeline.**

## Adding a new scraper

### 1. Decide what to scrape

Before writing code, answer:

- **What's the URL pattern?** (RSS, JSON API, or HTML page to parse)
- **Does it need an API key?** If yes, add it to `config/sources.json` and `.env.example`, and add a `config.py` getter.
- **How many articles per run?** Aim for 5-15. More floods the dashboard; fewer misses interesting items.
- **What's the article shape?** Map it to the canonical shape (id, title, summary, url, source, published).

### 2. Add the function

```python
def scrape_reddit_subreddit(subreddit: str = "MachineLearning") -> list[dict]:
    """Scrape top posts from a subreddit's RSS feed."""
    url = f"https://www.reddit.com/r/{subreddit}/.rss"
    text = fetch_text(url)
    if not text:
        return []

    articles = []
    try:
        feed = feedparser.parse(text)
        for entry in feed.entries[:15]:
            articles.append({
                "id": hash_id(entry.title, entry.link),
                "title": entry.title,
                "summary": _strip_html(getattr(entry, "summary", "")),
                "url": entry.link,
                "source": f"r/{subreddit}",
                "published": _normalize_date(getattr(entry, "published", "")),
                "arxiv_category": None,
                "raw": {"title": entry.title, "link": entry.link},
            })
    except Exception as e:
        log(f"scrape_reddit_subreddit parse error: {e}")
    return articles
```

Notes:

- Use `hash_id(title, url)` for non-arXiv sources. It's a SHA-256 of `title + url`, which gives a stable, deterministic ID.
- `_strip_html()` removes any HTML tags from the summary before storage. Without this, a Reddit summary like `<a href="...">link</a>` would show up literally in the dashboard.
- `_normalize_date()` converts RSS RFC 822 dates or ISO 8601 to a consistent format. If the date is missing, return an empty string — the database stores `NULL`.

### 3. Wire it into the pipeline

In `run_pipeline()`:

```python
def run_pipeline():
    articles = []
    articles.extend(scrape_arxiv())
    articles.extend(scrape_github())
    # ... existing scrapers ...
    articles.extend(scrape_reddit_subreddit("MachineLearning"))   # <-- new

    # dedup, classify, insert
    ...
```

### 4. Add a config entry (optional)

If the scraper has multiple sources, list them in `config/sources.json`:

```json
{
  "reddit_rss": {
    "MachineLearning": "https://www.reddit.com/r/MachineLearning/.rss",
    "LocalLLaMA": "https://www.reddit.com/r/LocalLLaMA/.rss"
  }
}
```

And have the scraper iterate over `config["reddit_rss"]`. The `config.py` loader gives you the parsed config via `load_config("sources.json")` (or you can read it directly with `json.load(open(...))` since the file is in the project root).

### 5. Add a test

If the parser is non-trivial, add a test in `tests/test_fixes.py` covering at least one happy-path example. Example:

```python
class TestRedditScraper(unittest.TestCase):
    def test_extracts_article_id_from_url(self):
        from news_tool import hash_id
        id1 = hash_id("Test title", "https://example.com/post/123")
        id2 = hash_id("Test title", "https://example.com/post/123")
        self.assertEqual(id1, id2, "hash_id should be deterministic")
```

### 6. Update the README

Add a row to the "Scrapers" table in the README. Note the source, output categories, and any API key requirement.

---

## Common pitfalls

### HTML entities in titles

Many RSS feeds have titles like `AT&amp;T announces 5G` (double-escaped). Decode twice in the parser, or use `html.unescape()` from the stdlib. The `news_tool.py` helper `_decode_html()` does this.

### Timezones

`published` should be a string. Either an ISO 8601 with timezone (e.g., `2026-06-04T10:30:00+00:00`) or an empty string. Don't try to convert to a `datetime` in the scraper — let the dashboard's `formatDateShort()` handle it.

### Rate limits

If you hit a rate limit, the scraper should fail gracefully (return `[]`) and the next run will try again. Don't add aggressive retry logic in the scraper; the existing `fetch_json` retries 3x with exponential backoff.

For sources with strict rate limits (e.g., Twitter, GitHub API), consider caching results in memory and only refreshing every N minutes. The `scrape_github()` function does this with a 1-hour cache.

### HTML in summaries

If the source returns HTML in the summary (most do), use the `_strip_html()` helper to remove tags. The dashboard's `escapeHtml()` will then re-escape the remaining text, which is correct.

### Untrusted URLs

The dashboard's `safeUrl()` only allows `http://` and `https://` schemes. If a source returns URLs with other schemes (e.g., `javascript:`, `data:`), the dashboard will render them as `#`. The scraper doesn't need to validate URLs — `safeUrl()` does it for the display layer.

---

## See also

- [ARCHITECTURE.md](ARCHITECTURE.md) — how scrapers fit into the pipeline
- [CLASSIFIER.md](CLASSIFIER.md) — what happens to articles after the scraper returns them
- [DEDUP.md](DEDUP.md) — what happens to duplicate articles after scraping
