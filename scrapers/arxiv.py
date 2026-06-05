"""arXiv scraper: 13 CS/ML/stat/finance feeds, 3+ second rate limit."""
import os
import time
from typing import List, Tuple

from ._http import fetch_url, ArticleList
from ._rss import parse_rss


def scrape_arxiv() -> ArticleList:
    # arXiv asks for >= 3 seconds between requests; configurable via ARXIV_RATE_LIMIT env var.
    rate_limit = float(os.environ.get('ARXIV_RATE_LIMIT', '3.0'))
    print("  [1/8] arXiv ML/AI papers...")
    feeds: List[Tuple[str, str]] = [
        ("https://rss.arxiv.org/rss/cs.AI", "cs.AI"),
        ("https://rss.arxiv.org/rss/cs.LG", "cs.LG"),
        ("https://rss.arxiv.org/rss/cs.CL", "cs.CL"),
        ("https://rss.arxiv.org/rss/cs.CV", "cs.CV"),
        ("https://rss.arxiv.org/rss/cs.NE", "cs.NE"),
        ("https://rss.arxiv.org/rss/cs.RO", "cs.RO"),
        ("https://rss.arxiv.org/rss/cs.IR", "cs.IR"),
        ("https://rss.arxiv.org/rss/cs.MA", "cs.MA"),
        ("https://rss.arxiv.org/rss/cs.HC", "cs.HC"),
        ("https://rss.arxiv.org/rss/stat.ML", "stat.ML"),
        ("https://rss.arxiv.org/rss/eess.SP", "eess.SP"),
        ("https://rss.arxiv.org/rss/q-fin.ST", "q-fin.ST"),
        ("https://rss.arxiv.org/rss/cs.CR", "cs.CR"),
    ]
    articles: ArticleList = []
    for i, (url, cat) in enumerate(feeds):
        if i > 0:
            time.sleep(rate_limit)
        content = fetch_url(url)
        if content:
            arts = parse_rss(content, "arxiv")
            for a in arts:
                a["subcategory"] = cat
            articles.extend(arts)
    print(f"    Found {len(articles)} papers")
    return articles
