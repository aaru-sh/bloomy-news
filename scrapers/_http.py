"""HTTP fetching + source name + article type aliases.

This is the lowest layer of the scraper stack. The 8 scraper modules
import fetch_url / fetch_json / Article / ArticleList from here, and
parse_rss reads SOURCE_NAMES to map the canonical source_key
("arxiv", "github", "finnhub", ...) to the human-friendly display
name ("arXiv", "GitHub", "Finnhub", ...) used in the dashboard and
Telegram digest.

The Article / ArticleList aliases are defined here (not in
scrapers/__init__.py) to avoid a circular import: __init__.py
imports the individual scraper modules, and they all import
the type aliases from _http.
"""
import json
import logging
import time
import urllib.request
from typing import Any, Dict, List, Optional

Article = Dict[str, Any]
ArticleList = List[Article]

logger = logging.getLogger(__name__)

SOURCE_NAMES = {
    "arxiv": "arXiv",
    "github": "GitHub",
    "newsapi": "NewsAPI",
    "google-news": "Google News",
    "bleepingcomputer": "BleepingComputer",
    "thehackersnews": "TheHackersNews",
    "finnhub": "Finnhub",
    "techcrunch": "TechCrunch",
    "reuters": "Reuters",
}


def fetch_url(url: str, timeout: int = 20, retries: int = 3) -> Optional[str]:
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "Accept": "application/rss+xml, application/xml, text/xml, */*",
    }

    for attempt in range(retries):
        try:
            req = urllib.request.Request(url, headers=headers)
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                return resp.read().decode("utf-8", errors="replace")
        except Exception as e:
            logger.warning(f"Attempt {attempt + 1}/{retries} failed for {url}: {e}")
            if attempt < retries - 1:
                time.sleep(2 ** attempt)

    logger.error(f"All {retries} attempts failed for {url}")
    return None


def fetch_json(url: str, timeout: int = 20) -> Any:
    content = fetch_url(url, timeout)
    if content:
        try:
            return json.loads(content)
        except json.JSONDecodeError:
            return None
    return None
