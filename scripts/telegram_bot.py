#!/usr/bin/env python3
"""Telegram Bot - Posts daily digest with inline keyboards to channel and sub-channels."""
import json
import html
import re
import sys
import time
import sqlite3
import requests
from pathlib import Path
from datetime import date

BASE = Path(__file__).parent.parent.resolve()
DB_PATH = BASE / "news.db"
CONFIG_PATH = BASE / "config" / "telegram.json"
LOG_DIR = BASE / "logs"
LOG_DIR.mkdir(exist_ok=True)
LOG_FILE = LOG_DIR / "telegram_bot.log"


def _log(msg):
    """Print to stdout and append to log file (no external deps)."""
    print(msg)
    try:
        with open(LOG_FILE, "a", encoding="utf-8") as f:
            f.write(f"{date.today().isoformat()}T{time.strftime('%H:%M:%S')} {msg}\n")
    except OSError:
        pass

MAX_MSG_LENGTH = 4096
RETRY_DELAY = 2

CATEGORIES = ["LLM", "Neural-Nets", "ML-Research", "AI-Applications", "Finance", "Cybersecurity"]
EMOJIS = {
    "LLM": "\U0001f9e0", "Neural-Nets": "\U0001f52c", "ML-Research": "\U0001f4ca",
    "AI-Applications": "\U0001f916", "Finance": "\U0001f4b0", "Cybersecurity": "\U0001f512"
}


def get_db():
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    return conn


def load_config():
    if not CONFIG_PATH.exists():
        print("Telegram config not found. Skipping.")
        return None
    with open(CONFIG_PATH, "r", encoding="utf-8-sig") as f:
        config = json.load(f)
    if config.get("bot_token", "").startswith("YOUR_"):
        print("Telegram bot_token not configured. Skipping.")
        return None
    return config


def clean_text(text):
    text = html.unescape(text)
    text = text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    for ch in ("*", "_", "`", "[", "]", "~"):
        text = text.replace(ch, "")
    return text.strip()


def truncate_summary(summary, max_words=50):
    summary = clean_text(summary)
    words = summary.split()
    if len(words) > max_words:
        summary = " ".join(words[:max_words]) + "..."
    if len(summary) > 450:
        summary = summary[:447] + "..."
    return summary


def send_message(token, chat_id, text, reply_markup=None):
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    payload = {
        "chat_id": chat_id,
        "text": text,
        "parse_mode": "HTML",
        "disable_web_page_preview": True,
    }
    if reply_markup:
        payload["reply_markup"] = reply_markup

    for attempt in range(2):
        try:
            r = requests.post(url, json=payload, timeout=15)
            result = r.json()
            if result.get("ok"):
                return True
            print(f"  Telegram error: {result.get('description', 'unknown')}")
        except Exception as e:
            print(f"  Telegram request failed: {e}")
        if attempt == 0:
            time.sleep(RETRY_DELAY)
    return False


def split_message(text, limit=MAX_MSG_LENGTH):
    if len(text) <= limit:
        return [text]
    parts = []
    while text:
        if len(text) <= limit:
            parts.append(text)
            break
        idx = text.rfind("\n", 0, limit)
        if idx == -1:
            idx = limit
        parts.append(text[:idx])
        text = text[idx:].lstrip("\n")
    return parts


def send_long_message(token, chat_id, text, reply_markup=None):
    parts = split_message(text)
    for i, part in enumerate(parts):
        extra = reply_markup if (i == len(parts) - 1 and reply_markup) else None
        if not send_message(token, chat_id, part, extra):
            return False
    return True


def get_articles_by_category(conn, category, limit=5):
    rows = conn.execute("""
        SELECT * FROM articles
        WHERE category = ? AND date(published) = date('now')
        ORDER BY published DESC
        LIMIT ?
    """, (category, limit)).fetchall()
    return [dict(row) for row in rows]


def get_today_counts(conn):
    counts = {}
    for cat in CATEGORIES:
        row = conn.execute(
            "SELECT COUNT(*) as cnt FROM articles WHERE category = ? AND date(published) = date('now')",
            (cat,)
        ).fetchone()
        counts[cat] = row["cnt"] if row else 0
    return counts


def mark_articles_read(conn, article_ids):
    if not article_ids:
        return
    placeholders = ",".join("?" * len(article_ids))
    conn.execute(f"UPDATE articles SET is_read = 1 WHERE id IN ({placeholders})", article_ids)
    conn.commit()


def format_main_digest(articles_by_category, today_counts):
    today = date.today().strftime("%B %d, %Y")
    total = sum(len(v) for v in articles_by_category.values())

    lines = []
    lines.append(f"\U0001f4f0 <b>Bloomy Daily</b> \u2014 {today}")
    lines.append("")

    for cat in CATEGORIES:
        articles = articles_by_category.get(cat, [])
        count = today_counts.get(cat, 0)
        emoji = EMOJIS.get(cat, "\U0001f4f0")
        lines.append(f"{emoji} <b>{cat}</b> ({count} new)")

        if not articles:
            lines.append("  No articles today.")
            lines.append("")
            continue

        for i, art in enumerate(articles[:3], 1):
            title = clean_text(art.get("title", "Untitled"))[:100]
            summary = truncate_summary(art.get("summary", ""), max_words=40)
            lines.append(f"{i}. <b>{title}</b>")
            if summary:
                lines.append(f"   {summary}")
            lines.append("")

        lines.append("\u2500" * 28)

    lines.append(f"<b>{total} articles total</b>")
    lines.append(f"\U0001f4ca Full archive: @Bloomy_news_archive")

    return "\n".join(lines)


def format_category_post(category, articles):
    today = date.today().strftime("%B %d, %Y")
    emoji = EMOJIS.get(category, "\U0001f4f0")

    lines = []
    lines.append(f"{emoji} <b>{category} Update</b> \u2014 {today}")
    lines.append("")

    for i, art in enumerate(articles, 1):
        title = clean_text(art.get("title", "Untitled"))[:120]
        summary = truncate_summary(art.get("summary", ""), max_words=50)
        lines.append(f"<b>{i}. {title}</b>")
        if summary:
            lines.append(f"{summary}")
        lines.append("")

    return "\n".join(lines)


def build_article_keyboard(articles):
    keyboard = []
    for art in articles:
        url = art.get("url", "")
        title = clean_text(art.get("title", "Read"))[:40]
        if url:
            keyboard.append([{"text": f"\U0001f517 {title}", "url": url}])
    return {"inline_keyboard": keyboard} if keyboard else None


def get_channel_id_from_config(category):
    try:
        with open(CONFIG_PATH, "r", encoding="utf-8-sig") as f:
            config = json.load(f)
        return config.get("category_channels", {}).get(category, "")
    except Exception:
        return ""


def format_channel_links(config):
    lines = []
    lines.append("\U0001f4cc <b>Category Channels:</b>")
    usernames = config.get("category_usernames", {})
    for cat in CATEGORIES:
        username = usernames.get(cat, "")
        label = username if username else "Join our channel for daily updates"
        lines.append(f"\u2022 {EMOJIS[cat]} {cat}: @{label}")
    return "\n".join(lines)


def post_to_category_channels(token, category_channels, articles_by_category):
    posted_ids = []
    for cat, channel_id in category_channels.items():
        articles = articles_by_category.get(cat, [])
        if not articles:
            continue
        emoji = EMOJIS.get(cat, "\U0001f4f0")
        print(f"  Posting {len(articles)} articles to {cat}...")
        text = format_category_post(cat, articles[:5])
        kb = build_article_keyboard(articles[:5])
        if send_message(token, channel_id, text, kb):
            posted_ids.extend(a["id"] for a in articles[:5])
        else:
            print(f"  Failed to post to {cat} channel, continuing...")
    return posted_ids


def post_daily_digest():
    config = load_config()
    if not config:
        return

    token = config["bot_token"]
    main_channel = config.get("main_channel_id", "")
    category_channels = config.get("category_channels", {})

    if not main_channel:
        print("No main channel configured. Skipping.")
        return

    print("Telegram Bot - Posting daily digest...")

    conn = get_db()
    articles_by_category = {}
    for cat in CATEGORIES:
        articles_by_category[cat] = get_articles_by_category(conn, cat, limit=5)

    today_counts = get_today_counts(conn)
    total = sum(len(v) for v in articles_by_category.values())

    if total == 0:
        print("  No articles today. Skipping.")
        conn.close()
        return

    print(f"  Sending digest with {total} articles...")
    digest_text = format_main_digest(articles_by_category, today_counts)
    send_long_message(token, main_channel, digest_text)

    print("  Posting channel links...")
    links_text = format_channel_links(config)
    send_message(token, main_channel, links_text)

    posted_ids = post_to_category_channels(token, category_channels, articles_by_category)
    mark_articles_read(conn, posted_ids)

    conn.close()
    print("Telegram posting complete.")


if __name__ == "__main__":
    post_daily_digest()
