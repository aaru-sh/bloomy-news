#!/usr/bin/env python3
"""Generate dashboard data JSON from the SQLite database (with legacy .md.gz fallback)."""
import json
import gzip
import os
import re
import sys
import hashlib
import html
from pathlib import Path
from datetime import date, timedelta
from collections import defaultdict

BASE = Path(__file__).parent.parent.resolve()
sys.path.insert(0, str(BASE))

CATEGORIES = ["LLM", "Neural-Nets", "ML-Research", "AI-Applications", "Finance", "Cybersecurity", "Uncategorized"]

def compute_hash(entry):
    unique_str = f"{entry.get('url', '')}{entry.get('title', '')}"
    return hashlib.sha256(unique_str.encode("utf-8")).hexdigest()

def clean_text(text):
    """Clean HTML entities and excess whitespace from text."""
    # Double unescape for nested entities like &amp;nbsp;
    text = html.unescape(html.unescape(text))
    text = re.sub(r'<[^>]+>', '', text)
    text = re.sub(r'\s+', ' ', text).strip()
    return text

def is_useless_summary(summary, title):
    """Check if a summary is just the title repeated or pure HTML junk."""
    if not summary:
        return True
    # Normalize for comparison: lowercase, strip punctuation, collapse spaces
    def normalize(s):
        s = s.lower().strip()
        s = re.sub(r'[^a-z0-9\s]', '', s)
        s = re.sub(r'\s+', ' ', s)
        return s
    title_n = normalize(title)
    summary_n = normalize(summary)
    if not title_n:
        return True
    # Summary is essentially the title
    if summary_n == title_n:
        return True
    # Summary starts with title and adds very little
    if summary_n.startswith(title_n) and len(summary_n) < len(title_n) + 20:
        return True
    # Title starts with summary (summary is substring of title)
    if title_n.startswith(summary_n) and len(summary_n) > len(title_n) * 0.8:
        return True
    # Summary is too short to be useful
    if len(summary) < 15:
        return True
    return False

def parse_markdown_content(content, cat, sub_dir_name):
    """Parse a markdown file into an entry dict. Handles 3 formats:
    Format 1 (arXiv): ## Summary\\nAbstract: ... (multi-line)
    Format 2 (inline): plain text between metadata and **Tags**
    Format 3 (Google News): ## Summary\\nHTML-encoded content (often just title)
    """
    entry = {
        "category": cat,
        "subcategory": sub_dir_name,
        "title": "",
        "url": "",
        "summary": "",
        "source": "",
        "published": "",
        "tags": [],
    }

    lines = content.split("\n")

    # Pass 1: Extract metadata and collect all text sources
    in_summary = False
    summary_lines = []
    inline_text_lines = []
    found_tags = False

    for i, line in enumerate(lines):
        stripped = line.strip()

        if stripped.startswith("# ") and not entry["title"]:
            entry["title"] = stripped[2:].strip()
        elif stripped.startswith("**Source**:") or stripped.startswith("Source:"):
            entry["source"] = stripped.split(":", 1)[1].strip().replace("**", "")
        elif stripped.startswith("**URL**:") or stripped.startswith("URL:"):
            entry["url"] = stripped.split(":", 1)[1].strip().replace("**", "")
        elif stripped.startswith("**Published**:") or stripped.startswith("Published:"):
            entry["published"] = stripped.split(":", 1)[1].strip().replace("**", "")
        elif stripped.startswith("**Tags**:") or stripped.startswith("Tags:"):
            tag_str = stripped.split(":", 1)[1].strip().replace("**", "")
            entry["tags"] = [t.strip() for t in tag_str.split(",") if t.strip()]
            found_tags = True
            in_summary = False
        elif stripped.startswith("## Summary"):
            in_summary = True
        elif in_summary and stripped:
            summary_lines.append(stripped)
        elif not found_tags and not in_summary and stripped and not stripped.startswith("**") and not stripped.startswith("#") and not stripped.startswith("Category:"):
            # Collect inline text (between metadata and tags)
            if stripped and not stripped.startswith("Source") and not stripped.startswith("URL") and not stripped.startswith("Published"):
                inline_text_lines.append(stripped)

    # Build summary from best available source
    # Priority: inline text (real content) > ## Summary (if useful) > title
    summary = ""

    # Try inline text first (real article descriptions)
    if inline_text_lines:
        raw = " ".join(inline_text_lines)
        cleaned = clean_text(raw)
        if not is_useless_summary(cleaned, entry["title"]):
            summary = cleaned

    # Try ## Summary section only if inline text wasn't useful
    if not summary and summary_lines:
        raw = " ".join(summary_lines)
        cleaned = clean_text(raw)
        if not is_useless_summary(cleaned, entry["title"]):
            summary = cleaned

    # Last resort: use title
    if not summary and entry["title"]:
        summary = entry["title"]

    entry["summary"] = summary
    return entry

def load_from_database():
    """Load all articles from the SQLite database (primary source)."""
    try:
        import database
        rows = database.get_articles(limit=100000, offset=0)
    except Exception as e:
        print(f"  Warning: database load failed: {e}")
        return []
    entries = []
    for row in rows:
        try:
            tags = json.loads(row.get('categories') or '[]')
        except (TypeError, ValueError):
            tags = []
        entries.append({
            "title": row.get('title', ''),
            "url": row.get('url', ''),
            "summary": row.get('summary', ''),
            "source": row.get('source', 'unknown'),
            "published": row.get('published', ''),
            "category": row.get('category', 'Uncategorized'),
            "subcategory": row.get('subcategory', 'news'),
            "tags": tags,
            "severity": "",
            "arxiv_id": row.get('arxiv_id', ''),
        })
    return entries


def load_all_categorized():
    """Load categorized entries: database first, then filesystem for historical articles."""
    entries = load_from_database()
    db_count = len(entries)

    db_urls = {e.get('url', '') for e in entries if e.get('url')}
    db_titles = {e.get('title', '').lower().strip() for e in entries if e.get('title')}

    fs_count = 0
    for cat in CATEGORIES:
        cat_dir = BASE / cat
        if not cat_dir.exists():
            continue
        for sub_dir in cat_dir.iterdir():
            if not sub_dir.is_dir():
                continue
            for md_file in sub_dir.glob("*.md.gz"):
                try:
                    with gzip.open(md_file, "rt", encoding="utf-8") as f:
                        content = f.read()
                    entry = parse_markdown_content(content, cat, sub_dir.name)
                    if not entry["title"]:
                        continue
                    url = entry.get("url", "")
                    title_lower = entry["title"].lower().strip()
                    if url and url in db_urls:
                        continue
                    if title_lower in db_titles:
                        continue
                    entries.append(entry)
                    fs_count += 1
                except Exception:
                    continue
    print(f"  Loaded {db_count} from DB, {fs_count} from filesystem (historical)")
    return entries

def load_from_raw():
    """Fallback: load from raw data files."""
    entries = []
    raw_dirs = {
        "arxiv": BASE / "raw" / "arxiv",
        "github": BASE / "raw" / "github",
        "newsapi": BASE / "raw" / "newsapi",
        "cybersec": BASE / "raw" / "cybersec",
        "finnhub": BASE / "raw" / "finnhub",
    }
    for source, dirpath in raw_dirs.items():
        if dirpath.exists():
            for jsonl_file in dirpath.glob("*.jsonl"):
                with open(jsonl_file, "r", encoding="utf-8") as f:
                    for line in f:
                        line = line.strip()
                        if line:
                            try:
                                entries.append(json.loads(line))
                            except json.JSONDecodeError:
                                continue
    return entries

def _is_today(published_str, today_iso):
    """Check if a published date string is today, supporting ISO and RFC 822."""
    if not published_str:
        return False
    if len(published_str) >= 10 and published_str[:10] == today_iso:
        return True
    try:
        from email.utils import parsedate_to_datetime
        dt = parsedate_to_datetime(published_str)
        return dt.date().isoformat() == today_iso
    except (ValueError, TypeError):
        return False

def build_dashboard_data():
    """Build the complete dashboard data structure."""
    entries = load_all_categorized()

    today = date.today().isoformat()
    today_count = 0
    category_counts = defaultdict(int)
    storage_bytes = 0

    # Count storage
    for cat in CATEGORIES:
        cat_dir = BASE / cat
        if cat_dir.exists():
            for f in cat_dir.rglob("*.md.gz"):
                storage_bytes += f.stat().st_size

    # Process entries
    articles = []
    seen_hashes = set()

    for entry in entries:
        entry_hash = compute_hash(entry)

        # Skip duplicates
        if entry_hash in seen_hashes:
            continue
        seen_hashes.add(entry_hash)

        category = entry.get("category", "Uncategorized")
        subcategory = entry.get("subcategory", "news")
        published = entry.get("published", "")

        # Count today's articles (handle both ISO and RFC 822 formats)
        if published and _is_today(published, today):
            today_count += 1

        category_counts[category] += 1

        articles.append({
            "id": entry_hash[:16],
            "title": entry.get("title", "Untitled"),
            "url": entry.get("url", ""),
            "source": entry.get("source", "unknown"),
            "published": published,
            "summary": entry.get("summary", "")[:2000],
            "category": category,
            "subcategory": subcategory,
            "tags": entry.get("tags", [])[:6],
            "severity": entry.get("severity", ""),
            "arxiv_id": entry.get("arxiv_id", ""),
        })

    # Sort by date descending
    articles.sort(key=lambda x: x.get("published", ""), reverse=True)

    stats = {
        "total": len(articles),
        "today": today_count,
        "categories": dict(category_counts),
        "storage": f"{storage_bytes / 1024:.1f} KB" if storage_bytes < 1048576 else f"{storage_bytes / 1048576:.1f} MB",
    }

    return {
        "generated": today,
        "stats": stats,
        "articles": articles,
    }

def main():
    import os, tempfile
    data = build_dashboard_data()

    output_dir = BASE / "dashboard" / "data"
    output_dir.mkdir(parents=True, exist_ok=True)
    output_file = output_dir / "dashboard_data.json"

    fd, tmp_path = tempfile.mkstemp(
        dir=output_dir,
        prefix='.dashboard_data_',
        suffix='.tmp'
    )
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False)
        os.replace(tmp_path, output_file)
    except Exception:
        if os.path.exists(tmp_path):
            os.unlink(tmp_path)
        raise

    print(f"Dashboard data generated: {output_file}")
    print(f"  Articles: {data['stats']['total']}")
    print(f"  Today: {data['stats']['today']}")
    print(f"  Storage: {data['stats']['storage']}")

if __name__ == "__main__":
    main()
