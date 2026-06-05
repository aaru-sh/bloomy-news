"""Telegram digest poster.

Builds a Markdown digest from freshly-categorized articles, falls
back to a date-filtered DB query on empty input, and POSTs to the
Telegram Bot API. The _send_telegram_message function is intentionally
extracted at module scope so tests can monkey-patch it without
touching urllib.
"""
import json
import logging
import urllib.request
from datetime import date
from pathlib import Path
from typing import Any, Dict, List, Tuple

import database
from config import get_telegram_token

from scrapers._http import Article, ArticleList

CategoryMap = Dict[str, ArticleList]

TELEGRAM_CATEGORIES: List[str] = ["LLM", "Neural-Nets", "ML-Research",
                                  "AI-Applications", "Finance", "Cybersecurity"]
TELEGRAM_EMOJIS: Dict[str, str] = {
    "LLM": "🧠", "Neural-Nets": "🔬", "ML-Research": "📊",
    "AI-Applications": "🤖", "Finance": "💰", "Cybersecurity": "🔒",
}
TELEGRAM_LIMIT_PER_CAT: int = 3

BASE = Path(__file__).parent.resolve()

logger = logging.getLogger(__name__)


def _select_top_articles(articles: ArticleList, limit: int = TELEGRAM_LIMIT_PER_CAT) -> ArticleList:
    """Pick up to `limit` articles, newest first by `published` if any
    article carries one, otherwise preserve insertion order."""
    if len(articles) <= limit:
        return list(articles)
    has_published = any((a.get("published") or "").strip() for a in articles)
    if has_published:
        return sorted(articles,
                      key=lambda a: a.get("published") or "",
                      reverse=True)[:limit]
    return list(articles[:limit])


def _format_digest(per_category: CategoryMap, limit_per_cat: int = TELEGRAM_LIMIT_PER_CAT) -> Tuple[str, int]:
    """Build the Telegram digest Markdown from a {category: [articles]} dict.

    Renders the canonical category order and caps each section at
    `limit_per_cat` articles. Returns (text, total_articles).
    """
    msg = f"📰 *Bloomy Daily Digest*\n"
    msg += f"📅 {date.today()}\n"
    msg += f"{'═' * 30}\n\n"

    total = 0
    for cat in TELEGRAM_CATEGORIES:
        articles = per_category.get(cat, [])
        if not articles:
            continue
        shown = articles[:limit_per_cat]
        emoji = TELEGRAM_EMOJIS.get(cat, "📰")
        msg += f"{emoji} *{cat}* ({len(shown)})\n"
        for i, art in enumerate(shown, 1):
            title = art.get('title', 'Untitled')[:80]
            summary = art.get('summary', '')[:100]
            url = art.get('url', '')
            msg += f"{i}\\. *{title}*\n"
            if summary:
                msg += f"   {summary}...\n"
            if url:
                msg += f"   [Read more]({url})\n"
            msg += "\n"
        total += len(shown)

    msg += f"{'─' * 30}\n"
    msg += f"*Total: {total} articles*\n"
    return msg, total


def _send_telegram_message(token: str, chat_id: str, text: str) -> Dict[str, Any]:
    """POST a message to the Telegram Bot API and return the parsed JSON.

    Extracted as a module-level function so tests can monkey-patch it
    without touching urllib.
    """
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    data = json.dumps({
        "chat_id": chat_id,
        "text": text,
        "parse_mode": "Markdown",
        "disable_web_page_preview": True,
    }).encode("utf-8")
    req = urllib.request.Request(url, data=data,
                                 headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=10) as resp:
        return json.loads(resp.read())


def post_to_telegram(categorized: CategoryMap) -> None:
    """Post the daily digest to Telegram.

    `categorized` is the dict of freshly-scraped articles this pipeline
    run just inserted, keyed by category. We build the digest from it
    directly so the message reflects what THIS run scraped, not
    whatever happens to be in the DB today (which can include older
    entries from earlier runs and would cause fresh articles to be
    missed when the DB has date-filtered rows from previous runs).

    Falls back to database.get_today_top_per_category() with a logged
    warning if `categorized` is empty (defensive - covers partial
    pipeline failures where Phase 2 stored nothing).
    """
    tg_path = BASE / "config" / "telegram.json"
    if not tg_path.exists():
        print("  Skipping Telegram - not configured")
        return

    with open(tg_path, encoding="utf-8-sig") as f:
        tg_config = json.load(f)

    token = get_telegram_token()
    main_channel = tg_config.get("main_channel_id", "")

    if not token or not main_channel:
        print("  Skipping Telegram - not configured")
        return

    has_fresh = bool(categorized) and any(categorized.values())
    if has_fresh:
        per_category = {cat: _select_top_articles(arts)
                        for cat, arts in categorized.items()
                        if arts}
        source = "fresh pipeline scrape"
    else:
        logger.warning(
            "post_to_telegram called with empty categorized dict; "
            "falling back to database.get_today_top_per_category()"
        )
        per_category = database.get_today_top_per_category(
            limit_per_cat=TELEGRAM_LIMIT_PER_CAT)
        source = "DB fallback (date-filtered)"

    msg, total = _format_digest(per_category,
                                limit_per_cat=TELEGRAM_LIMIT_PER_CAT)

    try:
        result = _send_telegram_message(token, main_channel, msg)
        if result.get("ok"):
            print("  Telegram digest sent!")
            logger.info(
                f"Telegram digest sent successfully "
                f"({total} articles, {source})"
            )
        else:
            print(f"  Telegram error: {result.get('description')}")
            logger.error(f"Telegram error: {result.get('description')}")
    except Exception as e:
        print(f"  Telegram request failed: {e}")
        logger.error(f"Telegram request failed: {e}")
