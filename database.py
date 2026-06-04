import sqlite3
import json
import hashlib
import re
from pathlib import Path

BASE = Path(__file__).parent.resolve()
DB_PATH = BASE / "news.db"

def get_connection():
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    return conn

def init_db():
    conn = get_connection()
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS articles (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            url TEXT,
            summary TEXT DEFAULT '',
            source TEXT DEFAULT '',
            category TEXT DEFAULT '',
            subcategory TEXT DEFAULT 'news',
            published TEXT DEFAULT '',
            author TEXT DEFAULT '',
            content_hash TEXT DEFAULT '',
            arxiv_id TEXT DEFAULT '',
            title_words TEXT DEFAULT '',
            categories TEXT DEFAULT '[]',
            confidence REAL DEFAULT 0.0,
            is_read INTEGER DEFAULT 0,
            is_starred INTEGER DEFAULT 0,
            embedding BLOB,
            created_at TEXT DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS dedup_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            content_hash TEXT NOT NULL,
            title TEXT NOT NULL,
            similar_to_id INTEGER,
            similarity_score REAL DEFAULT 0.0,
            method TEXT DEFAULT 'url',
            created_at TEXT DEFAULT (datetime('now'))
        );

        CREATE INDEX IF NOT EXISTS idx_articles_category ON articles(category);
        CREATE INDEX IF NOT EXISTS idx_articles_published ON articles(published);
        CREATE INDEX IF NOT EXISTS idx_articles_source ON articles(source);
        CREATE INDEX IF NOT EXISTS idx_articles_content_hash ON articles(content_hash);
        CREATE INDEX IF NOT EXISTS idx_articles_arxiv_id ON articles(arxiv_id);
        CREATE INDEX IF NOT EXISTS idx_articles_is_read ON articles(is_read);
        CREATE UNIQUE INDEX IF NOT EXISTS idx_articles_url_unique ON articles(url) WHERE url IS NOT NULL;
    """)
    conn.commit()

    try:
        conn.execute("""
            CREATE VIRTUAL TABLE IF NOT EXISTS articles_fts USING fts5(
                title, summary, categories, content='articles', content_rowid='id'
            )
        """)
        conn.commit()
    except Exception:
        pass

    try:
        conn.execute("""
            CREATE TRIGGER IF NOT EXISTS articles_ai AFTER INSERT ON articles BEGIN
                INSERT INTO articles_fts(rowid, title, summary, categories)
                VALUES (new.id, new.title, new.summary, new.categories);
            END
        """)
        conn.execute("""
            CREATE TRIGGER IF NOT EXISTS articles_ad AFTER DELETE ON articles BEGIN
                INSERT INTO articles_fts(articles_fts, rowid, title, summary, categories)
                VALUES('delete', old.id, old.title, old.summary, old.categories);
            END
        """)
        conn.execute("""
            CREATE TRIGGER IF NOT EXISTS articles_au AFTER UPDATE ON articles BEGIN
                INSERT INTO articles_fts(articles_fts, rowid, title, summary, categories)
                VALUES('delete', old.id, old.title, old.summary, old.categories);
                INSERT INTO articles_fts(rowid, title, summary, categories)
                VALUES (new.id, new.title, new.summary, new.categories);
            END
        """)
        conn.commit()
    except Exception:
        pass

    conn.close()

def compute_hash(article):
    raw = (article.get('url', '') or '') + (article.get('title', '') or '')
    return hashlib.sha256(raw.encode('utf-8')).hexdigest()

STOP_WORDS = {'the','a','an','is','are','was','were','be','been','being',
              'have','has','had','do','does','did','will','would','could',
              'should','may','might','shall','can','to','of','in','for',
              'on','with','at','by','from','as','new','also','says','said'}

def extract_title_words(title):
    words = set()
    for w in title.split():
        w = w.lower().strip('.,!?;:()"\'')
        if w and w not in STOP_WORDS:
            words.add(w)
    return ' '.join(sorted(words))

def parse_arxiv_id(url):
    match = re.search(r'(\d{4}\.\d{4,5})(?:v\d+)?', url or '')
    if match:
        return match.group(1)
    return None

def _normalize_title_words(title):
    if not title:
        return set()
    return {w.lower().strip('.,!?;:()"\'') for w in title.split()
            if w and w.lower().strip('.,!?;:()"\'') not in STOP_WORDS}


def title_similarity(title1, title2):
    if not title1 or not title2:
        return 0.0
    words1 = _normalize_title_words(title1)
    words2 = _normalize_title_words(title2)
    if not words1 or not words2:
        return 0.0
    intersection = words1 & words2
    union = words1 | words2
    return len(intersection) / len(union)

def is_duplicate(title, url, summary=''):
    conn = get_connection()
    try:
        if url:
            row = conn.execute("SELECT id FROM articles WHERE url = ?", (url,)).fetchone()
            if row:
                return True, row['id'], 1.0, 'url'
        arxiv_id = parse_arxiv_id(url or '')
        if arxiv_id:
            row = conn.execute("SELECT id FROM articles WHERE arxiv_id = ?", (arxiv_id,)).fetchone()
            if row:
                return True, row['id'], 1.0, 'arxiv_id'
        title_words = extract_title_words(title)
        rows = conn.execute("""
            SELECT id, title, title_words FROM articles
            WHERE published > datetime('now', '-7 days')
            ORDER BY id DESC LIMIT 200
        """).fetchall()
        for row in rows:
            existing = row['title_words'] or row['title']
            sim = title_similarity(title_words, existing)
            if sim >= 0.80:
                return True, row['id'], sim, 'title_similarity'
        return False, None, 0.0, None
    finally:
        conn.close()

def log_duplicate(content_hash, title, similar_id, score, method):
    conn = get_connection()
    try:
        conn.execute("""
            INSERT INTO dedup_log (content_hash, title, similar_to_id, similarity_score, method)
            VALUES (?, ?, ?, ?, ?)
        """, (content_hash, title, similar_id, score, method))
        conn.commit()
    finally:
        conn.close()

def store_article(article):
    conn = get_connection()
    try:
        title = article.get('title', '')
        url = article.get('url', '')
        summary = article.get('summary', '')
        is_dup, similar_id, score, method = is_duplicate(title, url, summary)
        if is_dup:
            log_duplicate(compute_hash(article), title, similar_id, score, method)
            return False, similar_id
        arxiv_id = parse_arxiv_id(url) or ''
        title_words = extract_title_words(title)
        categories = json.dumps(article.get('tags', []))
        cursor = conn.execute("""
            INSERT INTO articles (title, url, summary, source, category, subcategory,
                                  published, author, content_hash, arxiv_id,
                                  title_words, categories, confidence)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            title, url, summary,
            article.get('source', ''),
            article.get('category', ''),
            article.get('subcategory', 'news'),
            article.get('published', ''),
            article.get('author', ''),
            compute_hash(article),
            arxiv_id,
            title_words,
            categories,
            article.get('confidence', 0.0)
        ))
        conn.commit()
        article_id = cursor.lastrowid
        return True, article_id
    except Exception as e:
        conn.rollback()
        return False, None
    finally:
        conn.close()

def get_articles(category=None, source=None, date_from=None, date_to=None, search=None, is_read=None, limit=50, offset=0):
    conn = get_connection()
    try:
        conditions = []
        params = []
        if category:
            conditions.append("category = ?")
            params.append(category)
        if source:
            conditions.append("source = ?")
            params.append(source)
        if date_from:
            conditions.append("published >= ?")
            params.append(date_from)
        if date_to:
            conditions.append("published <= ?")
            params.append(date_to)
        if is_read is not None:
            conditions.append("is_read = ?")
            params.append(1 if is_read else 0)
        if search:
            conditions.append("(title LIKE ? OR summary LIKE ?)")
            params.extend([f'%{search}%', f'%{search}%'])
        where = " WHERE " + " AND ".join(conditions) if conditions else ""
        query = f"SELECT * FROM articles{where} ORDER BY published DESC, id DESC LIMIT ? OFFSET ?"
        params.extend([limit, offset])
        rows = conn.execute(query, params).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()

def get_article_by_id(id):
    conn = get_connection()
    try:
        row = conn.execute("SELECT * FROM articles WHERE id = ?", (id,)).fetchone()
        return dict(row) if row else None
    finally:
        conn.close()

def mark_read(id):
    conn = get_connection()
    try:
        conn.execute("UPDATE articles SET is_read = 1 WHERE id = ?", (id,))
        conn.commit()
    finally:
        conn.close()

def mark_starred(id):
    conn = get_connection()
    try:
        row = conn.execute("SELECT is_starred FROM articles WHERE id = ?", (id,)).fetchone()
        if row:
            new_val = 0 if row['is_starred'] else 1
            conn.execute("UPDATE articles SET is_starred = ? WHERE id = ?", (new_val, id))
            conn.commit()
            return new_val
        return None
    finally:
        conn.close()

BOOKMARKS_FILE = BASE / "dashboard" / "data" / "bookmarks.json"

def get_bookmarks():
    """Get list of bookmarked article IDs."""
    if BOOKMARKS_FILE.exists():
        with open(BOOKMARKS_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    return []

def toggle_bookmark(article_id):
    """Toggle bookmark status. Returns True if now bookmarked."""
    bookmarks = get_bookmarks()
    if article_id in bookmarks:
        bookmarks.remove(article_id)
        starred = False
    else:
        bookmarks.append(article_id)
        starred = True
    BOOKMARKS_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(BOOKMARKS_FILE, 'w', encoding='utf-8') as f:
        json.dump(bookmarks, f)
    return starred

def get_stats():
    conn = get_connection()
    try:
        cats = conn.execute("SELECT category, COUNT(*) as cnt FROM articles GROUP BY category ORDER BY cnt DESC").fetchall()
        today = conn.execute("SELECT COUNT(*) as cnt FROM articles WHERE date(published) = date('now')").fetchone()
        total = conn.execute("SELECT COUNT(*) as cnt FROM articles").fetchone()
        by_source = conn.execute("SELECT source, COUNT(*) as cnt FROM articles GROUP BY source ORDER BY cnt DESC LIMIT 10").fetchall()
        return {
            'categories': {r['category']: r['cnt'] for r in cats},
            'today': today['cnt'],
            'total': total['cnt'],
            'sources': {r['source']: r['cnt'] for r in by_source}
        }
    finally:
        conn.close()

def search_articles(query, limit=20):
    conn = get_connection()
    try:
        try:
            fts_query = ' OR '.join(f'"{w}"' for w in query.split() if w)
            rows = conn.execute("""
                SELECT a.* FROM articles a
                JOIN articles_fts f ON a.id = f.rowid
                WHERE articles_fts MATCH ?
                ORDER BY rank LIMIT ?
            """, (fts_query, limit)).fetchall()
            if rows:
                return [dict(r) for r in rows]
        except Exception:
            pass
        rows = conn.execute("""
            SELECT * FROM articles
            WHERE title LIKE ? OR summary LIKE ? OR title_words LIKE ?
            ORDER BY published DESC, id DESC LIMIT ?
        """, (f'%{query}%', f'%{query}%', f'%{query}%', limit)).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()

def get_today_top_per_category(limit_per_cat=3):
    conn = get_connection()
    try:
        cats = conn.execute("SELECT DISTINCT category FROM articles WHERE category != ''").fetchall()
        result = {}
        for c in cats:
            cat = c['category']
            rows = conn.execute("""
                SELECT * FROM articles
                WHERE category = ? AND date(published) = date('now')
                ORDER BY confidence DESC, id DESC LIMIT ?
            """, (cat, limit_per_cat)).fetchall()
            result[cat] = [dict(r) for r in rows]
        return result
    finally:
        conn.close()

def migrate_from_files():
    import gzip
    conn = get_connection()
    try:
        count = conn.execute("SELECT COUNT(*) as cnt FROM articles").fetchone()['cnt']
        if count > 0:
            print(f"Migration skipped - database already has {count} articles")
            return 0, 0
    finally:
        conn.close()
    categories = ['LLM', 'Neural-Nets', 'ML-Research', 'AI-Applications', 'Finance', 'Cybersecurity']
    imported = skipped = 0
    for cat in categories:
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
                    entry = {"category": cat, "subcategory": sub_dir.name}
                    for line in content.split("\n"):
                        if line.startswith("# "):
                            entry["title"] = line[2:].strip()
                        elif line.startswith("Source:"):
                            entry["source"] = line.split(":", 1)[1].strip()
                        elif line.startswith("URL:"):
                            entry["url"] = line.split(":", 1)[1].strip()
                        elif line.startswith("Published:"):
                            entry["published"] = line.split(":", 1)[1].strip()
                        elif line.startswith("Summary:") or line.startswith("Key Points:"):
                            entry["summary"] = line.split(":", 1)[1].strip()
                    if entry.get("title"):
                        is_new, _ = store_article(entry)
                        if is_new:
                            imported += 1
                        else:
                            skipped += 1
                except:
                    continue
    print(f"Migration: {imported} imported, {skipped} skipped")
    return imported, skipped

if __name__ == "__main__":
    init_db()
    print("Database initialized.")
