import os
import sqlite3
import json
import hashlib
import re
import tempfile
import threading
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

logger = logging.getLogger(__name__)

BASE = Path(__file__).parent.resolve()
DB_PATH = BASE / "news.db"

EMBEDDING_DIM = 384
EMBEDDING_DTYPE = "float32"

MAX_ARTICLE_AGE_DAYS = 30

Article = Dict[str, Any]
ArticleList = List[Article]

def get_connection() -> sqlite3.Connection:
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    return conn

def init_db() -> None:
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
            bookmarked INTEGER NOT NULL DEFAULT 0,
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
        conn.execute("ALTER TABLE articles ADD COLUMN bookmarked INTEGER NOT NULL DEFAULT 0")
        conn.commit()
    except Exception:
        pass

    try:
        conn.execute("CREATE INDEX IF NOT EXISTS idx_articles_bookmarked ON articles(bookmarked)")
        conn.commit()
    except Exception:
        pass

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

    try:
        null_rows = conn.execute(
            "SELECT id, title FROM articles WHERE title_words IS NULL OR title_words = ''"
        ).fetchall()
        if null_rows:
            for row in null_rows:
                words = extract_title_words(row['title'] or '')
                conn.execute(
                    "UPDATE articles SET title_words = ? WHERE id = ?",
                    (words, row['id']),
                )
            conn.commit()
    except Exception:
        pass

    conn.close()

def compute_hash(article: Article) -> str:
    raw = (article.get('url', '') or '') + (article.get('title', '') or '')
    return hashlib.sha256(raw.encode('utf-8')).hexdigest()

STOP_WORDS = {'the','a','an','is','are','was','were','be','been','being',
              'have','has','had','do','does','did','will','would','could',
              'should','may','might','shall','can','to','of','in','for',
              'on','with','at','by','from','as','new','also','says','said'}

def extract_title_words(title: str) -> str:
    words: Set[str] = set()
    for w in title.split():
        w = w.lower().strip('.,!?;:()"\'')
        if w and w not in STOP_WORDS:
            words.add(w)
    return ' '.join(sorted(words))

def parse_arxiv_id(url: str) -> Optional[str]:
    match = re.search(r'(\d{4}\.\d{4,5})(?:v\d+)?', url or '')
    if match:
        return match.group(1)
    return None

def _normalize_title_words(title: str) -> Set[str]:
    if not title:
        return set()
    return {w.lower().strip('.,!?;:()"\'') for w in title.split()
            if w and w.lower().strip('.,!?;:()"\'') not in STOP_WORDS}


def title_similarity(title1: str, title2: str, pre_processed: bool = False) -> float:
    if not title1 or not title2:
        return 0.0
    if pre_processed:
        words1 = set(title1.split())
        words2 = set(title2.split())
    else:
        words1 = _normalize_title_words(title1)
        words2 = _normalize_title_words(title2)
    if not words1 or not words2:
        return 0.0
    intersection = words1 & words2
    union = words1 | words2
    return len(intersection) / len(union)

def is_duplicate(title: str, url: str, summary: str = '', conn: Optional[sqlite3.Connection] = None) -> Tuple[bool, Optional[int], float, Optional[str]]:
    """Check whether the given article is a duplicate of one already stored.

    If `conn` is provided, uses it (the caller manages the connection and
    transaction). If `conn` is None, opens a fresh connection, runs the
    query read-only, and closes the connection before returning. Mixing
    the two is fine: each call is self-contained.
    """
    own_conn = conn is None
    if own_conn:
        conn = get_connection()
    assert conn is not None
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
        if not title_words:
            return False, None, 0.0, None
        significant_words = [w for w in title_words.split() if len(w) >= 4]
        if not significant_words:
            return False, None, 0.0, None
        like_clause = " OR ".join(["title_words LIKE ?"] * len(significant_words))
        like_params = [f'%{w}%' for w in significant_words]
        rows = conn.execute(f"""
            SELECT id, title, title_words FROM articles
            WHERE published > datetime('now', '-7 days')
            AND ({like_clause})
            ORDER BY id DESC LIMIT 200
        """, like_params).fetchall()
        for row in rows:
            if row['title_words']:
                sim = title_similarity(title_words, row['title_words'], pre_processed=True)
            else:
                sim = title_similarity(title, row['title'] or '')
            if sim >= 0.80:
                return True, row['id'], sim, 'title_similarity'
        return False, None, 0.0, None
    finally:
        if own_conn:
            conn.close()

def cleanup_old_articles(max_age_days: int = MAX_ARTICLE_AGE_DAYS) -> int:
    """Delete articles older than max_age_days to bound DB size.

    Article age is determined by `published` (handling both ISO 8601 and
    RFC 2822 formats stored by various scrapers); falls back to
    `created_at` for articles with an empty `published`. Also prunes
    `dedup_log` entries older than 7 days since they're debug-only audit
    data with no operational value long-term.

    Date parsing happens in Python (not SQL) because SQLite's `date()`
    function returns NULL for RFC 2822 strings, which the live DB
    contains. With ~3000 rows per month the in-Python scan is fast
    enough; if this ever needs to scale, switch to a generated
    `published_iso` column.

    Returns the number of articles deleted. Set `max_age_days=0` to
    disable the cleanup entirely (returns 0, no DB writes).
    """
    if max_age_days <= 0:
        return 0

    from datetime import datetime, timedelta, timezone
    import email.utils

    cutoff = datetime.now(timezone.utc) - timedelta(days=max_age_days)

    def _parse_article_date(published: str, created_at: str):
        """Return a timezone-aware datetime for the article, or None."""
        if published:
            stripped = published.strip()
            iso = stripped.replace("Z", "+00:00") if stripped.endswith("Z") else stripped
            try:
                dt = datetime.fromisoformat(iso)
                if dt.tzinfo is None:
                    dt = dt.replace(tzinfo=timezone.utc)
                return dt
            except (ValueError, TypeError):
                pass
            try:
                dt = email.utils.parsedate_to_datetime(stripped)
                if dt is not None and dt.tzinfo is None:
                    dt = dt.replace(tzinfo=timezone.utc)
                return dt
            except (TypeError, ValueError):
                pass
        if created_at:
            for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%d"):
                try:
                    return datetime.strptime(created_at, fmt).replace(tzinfo=timezone.utc)
                except ValueError:
                    continue
        return None

    conn = get_connection()
    try:
        rows = conn.execute(
            "SELECT id, published, created_at FROM articles"
        ).fetchall()
        to_delete = []
        for row in rows:
            article_date = _parse_article_date(
                row["published"] or "", row["created_at"] or ""
            )
            if article_date is not None and article_date < cutoff:
                to_delete.append(row["id"])

        if not to_delete:
            return 0

        placeholders = ",".join("?" * len(to_delete))
        cursor = conn.execute(
            f"DELETE FROM articles WHERE id IN ({placeholders})", to_delete
        )
        deleted = cursor.rowcount

        if deleted > 0:
            conn.execute(
                """
                DELETE FROM dedup_log
                WHERE created_at != ''
                  AND date(created_at) < date('now', '-7 days')
                """
            )

        conn.commit()
        logger.info(
            "cleanup_old_articles: deleted %d articles older than %d days",
            deleted, max_age_days,
        )
        return deleted
    except Exception as e:
        conn.rollback()
        logger.error("cleanup_old_articles failed: %s", e)
        return 0
    finally:
        conn.close()


def log_duplicate(content_hash: str, title: str, similar_id: Optional[int], score: float, method: Optional[str], conn: Optional[sqlite3.Connection] = None) -> None:
    """Record a duplicate-detection event in the dedup_log table.

    If `conn` is provided, uses it (caller manages commit/rollback).
    If `conn` is None, opens a fresh connection and commits the insert
    before closing. Use a shared conn for batch dedup logging so all
    inserts commit (or roll back) together.
    """
    own_conn = conn is None
    if own_conn:
        conn = get_connection()
    assert conn is not None
    try:
        conn.execute("""
            INSERT INTO dedup_log (content_hash, title, similar_to_id, similarity_score, method)
            VALUES (?, ?, ?, ?, ?)
        """, (content_hash, title, similar_id, score, method))
        if own_conn:
            conn.commit()
    finally:
        if own_conn:
            conn.close()

def _serialize_embedding(embedding: Any) -> Optional[bytes]:
    """Convert a numpy array (or raw bytes/None) to a BLOB-storable value.

    Accepts a numpy ndarray (calls tobytes()), a bytes/bytearray (returned
    as-is), or None (returned as None so the column stores NULL).
    """
    if embedding is None:
        return None
    if isinstance(embedding, (bytes, bytearray)):
        return bytes(embedding)
    if hasattr(embedding, "tobytes"):
        return embedding.tobytes()
    raise TypeError(
        f"embedding must be a numpy array, bytes, or None; got {type(embedding).__name__}"
    )


def store_article(article: Article, conn: Optional[sqlite3.Connection] = None, embedding: Any = None) -> Tuple[bool, Optional[int]]:
    """Insert an article if it's not a duplicate.

    If `conn` is provided, uses it (caller manages commit/rollback). The
    internal calls to is_duplicate() and log_duplicate() reuse the same
    conn so all DB work for one article happens in one transaction.

    If `conn` is None, opens a fresh connection, commits the insert (or
    rollback on error), and closes before returning.

    The optional `embedding` argument is the article's vector
    representation (numpy array, bytes, or None). When provided it is
    serialized to a BLOB and stored in the `articles.embedding` column;
    when None the column is left NULL. Default is None, which preserves
    the historical behavior for callers that don't compute embeddings.
    """
    own_conn = conn is None
    if own_conn:
        conn = get_connection()
    assert conn is not None
    try:
        title = article.get('title', '')
        url = article.get('url', '')
        summary = article.get('summary', '')
        is_dup, similar_id, score, method = is_duplicate(title, url, summary, conn=conn)
        if is_dup:
            log_duplicate(compute_hash(article), title, similar_id, score, method, conn=conn)
            return False, similar_id
        arxiv_id = parse_arxiv_id(url) or ''
        title_words = extract_title_words(title)
        categories = json.dumps(article.get('tags', []))
        embedding_blob = _serialize_embedding(embedding)
        cursor = conn.execute("""
            INSERT INTO articles (title, url, summary, source, category, subcategory,
                                  published, author, content_hash, arxiv_id,
                                  title_words, categories, confidence, embedding)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
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
            article.get('confidence', 0.0),
            embedding_blob,
        ))
        if own_conn:
            conn.commit()
        article_id = cursor.lastrowid
        return True, article_id
    except Exception as e:
        if own_conn:
            conn.rollback()
        return False, None
    finally:
        if own_conn:
            conn.close()


def load_article_embedding(article_id: int, conn: Optional[sqlite3.Connection] = None) -> Any:
    """Reconstruct the numpy embedding vector stored for `article_id`.

    Returns the float32 array of shape (EMBEDDING_DIM,) on success, or
    None when the article has no embedding stored (NULL column) or no
    row matches the id. Asserts the stored byte length matches
    EMBEDDING_DIM * 4 (the float32 byte size) so a corrupt or
    truncated blob fails loudly rather than silently reshaping.
    """
    own_conn = conn is None
    if own_conn:
        conn = get_connection()
    assert conn is not None
    try:
        row = conn.execute(
            "SELECT embedding FROM articles WHERE id = ?", (article_id,)
        ).fetchone()
        if row is None or row["embedding"] is None:
            return None
        import numpy as np
        blob = bytes(row["embedding"])
        expected = EMBEDDING_DIM * 4
        if len(blob) != expected:
            raise ValueError(
                f"embedding blob for article {article_id} is {len(blob)} bytes; "
                f"expected {expected} for {EMBEDDING_DIM}-dim {EMBEDDING_DTYPE}"
            )
        return np.frombuffer(blob, dtype=EMBEDDING_DTYPE)
    finally:
        if own_conn:
            conn.close()

def _has_fts5_table(conn: sqlite3.Connection) -> bool:
    """Return True if the articles_fts virtual table is configured.

    The check hits sqlite_master on the supplied connection so the result
    is per-DB and works correctly when tests swap DB_PATH between cases.
    """
    try:
        row = conn.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name='articles_fts'"
        ).fetchone()
        return row is not None
    except Exception:
        return False


def _fts_search_ids(conn: sqlite3.Connection, query: str, limit: int = 500) -> Optional[List[int]]:
    """Run FTS5 search; return list of rowids, [] for no matches, or None on failure.

    Returns None to signal "FTS5 is not available, fall back to LIKE".
    Returns [] for a legitimate empty result set.
    """
    if not _has_fts5_table(conn):
        return None
    try:
        fts_query = ' OR '.join(f'"{w}"' for w in query.split() if w)
        if not fts_query:
            return None
        rows = conn.execute(
            "SELECT rowid FROM articles_fts WHERE articles_fts MATCH ? ORDER BY rank LIMIT ?",
            (fts_query, limit),
        ).fetchall()
        return [r[0] for r in rows]
    except Exception:
        return None


def _like_search_ids(conn: sqlite3.Connection, query: str, limit: int = 500) -> List[int]:
    """LIKE-based fallback used when FTS5 is unavailable or the FTS5 query is invalid."""
    like = f"%{query}%"
    rows = conn.execute(
        "SELECT id FROM articles "
        "WHERE title LIKE ? OR summary LIKE ? OR title_words LIKE ? "
        "ORDER BY published DESC, id DESC LIMIT ?",
        (like, like, like, limit),
    ).fetchall()
    return [r[0] for r in rows]


def get_articles(category: Optional[str] = None, source: Optional[str] = None, date_from: Optional[str] = None, date_to: Optional[str] = None, search: Optional[str] = None, is_read: Optional[bool] = None, limit: int = 50, offset: int = 0) -> ArticleList:
    conn = get_connection()
    try:
        conditions = []
        params: List[Any] = []
        if category:
            conditions.append("a.category = ?")
            params.append(category)
        if source:
            conditions.append("a.source = ?")
            params.append(source)
        if date_from:
            # Use SQLite's date() so date-only inputs (e.g. "2025-12-15")
            # match full ISO timestamps in the column ("2025-12-15T10:30:00").
            conditions.append("date(a.published) >= date(?)")
            params.append(date_from)
        if date_to:
            conditions.append("date(a.published) <= date(?)")
            params.append(date_to)
        if is_read is not None:
            conditions.append("a.is_read = ?")
            params.append(1 if is_read else 0)
        if search:
            fts_ids = _fts_search_ids(conn, search)
            if fts_ids is None:
                # FTS5 unavailable or invalid query: fall back to LIKE so the
                # search degrades gracefully on builds without articles_fts.
                like_ids = _like_search_ids(conn, search)
                if not like_ids:
                    return []
                placeholders = ",".join("?" * len(like_ids))
                conditions.append(f"a.id IN ({placeholders})")
                params.extend(like_ids)
            elif fts_ids:
                placeholders = ",".join("?" * len(fts_ids))
                conditions.append(f"a.id IN ({placeholders})")
                params.extend(fts_ids)
            else:
                # FTS5 returned no matches - legitimate empty result.
                return []
        where = " WHERE " + " AND ".join(conditions) if conditions else ""
        query = f"SELECT * FROM articles a{where} ORDER BY a.published DESC, a.id DESC LIMIT ? OFFSET ?"
        params.extend([limit, offset])
        rows = conn.execute(query, params).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()

def get_article_by_id(id: int) -> Optional[Article]:
    conn = get_connection()
    try:
        row = conn.execute("SELECT * FROM articles WHERE id = ?", (id,)).fetchone()
        return dict(row) if row else None
    finally:
        conn.close()

def mark_read(id: int) -> None:
    conn = get_connection()
    try:
        conn.execute("UPDATE articles SET is_read = 1 WHERE id = ?", (id,))
        conn.commit()
    finally:
        conn.close()


def mark_read_batch(ids: List[int]) -> int:
    """Mark multiple articles as read in a single transaction.

    No-op for an empty list. Skips silently if any id is missing - safer
    than raising in batch contexts like the Telegram poster.
    """
    if not ids:
        return 0
    placeholders = ",".join("?" * len(ids))
    conn = get_connection()
    try:
        cur = conn.execute(
            f"UPDATE articles SET is_read = 1 WHERE id IN ({placeholders})",
            ids,
        )
        conn.commit()
        return cur.rowcount
    finally:
        conn.close()


def set_bookmarked(article_id: int, value: bool) -> None:
    """Set the bookmarked column for a single article by integer id.

    New articles default to 0; this function is the only writer for the
    column once the row exists. No-op if the id is unknown.
    """
    conn = get_connection()
    try:
        conn.execute(
            "UPDATE articles SET bookmarked = ? WHERE id = ?",
            (1 if value else 0, article_id),
        )
        conn.commit()
    finally:
        conn.close()


def is_bookmarked(article_id: int) -> bool:
    """Return True if the article is currently bookmarked.

    Unknown ids return False (the default value of the column).
    """
    conn = get_connection()
    try:
        row = conn.execute(
            "SELECT bookmarked FROM articles WHERE id = ?", (article_id,)
        ).fetchone()
        return bool(row["bookmarked"]) if row else False
    finally:
        conn.close()


def set_bookmarked_by_hash_prefix(prefix: str, value: bool) -> bool:
    """Mirror a JSON bookmark toggle to the articles table.

    The dashboard's article id is the first 16 hex chars of the SHA-256
    of `url + title` (see generate_data.compute_hash). serve.py uses this
    prefix to identify articles; the DB stores the full content_hash.
    Returns True if a row was updated, False if no article matched the
    prefix (e.g. historical articles not yet in the DB).
    """
    conn = get_connection()
    try:
        cur = conn.execute(
            "UPDATE articles SET bookmarked = ? WHERE substr(content_hash, 1, 16) = ?",
            (1 if value else 0, prefix),
        )
        conn.commit()
        return cur.rowcount > 0
    finally:
        conn.close()


def get_bookmarked_article_ids() -> List[int]:
    """Return the integer ids of all currently-bookmarked articles."""
    conn = get_connection()
    try:
        rows = conn.execute(
            "SELECT id FROM articles WHERE bookmarked = 1"
        ).fetchall()
        return [r["id"] for r in rows]
    finally:
        conn.close()


def count_articles_today_by_category() -> Dict[str, int]:
    """Return {category: count} for articles published today (UTC)."""
    conn = get_connection()
    try:
        rows = conn.execute("""
            SELECT category, COUNT(*) AS cnt
            FROM articles
            WHERE date(published) = date('now')
            GROUP BY category
        """).fetchall()
        return {r["category"]: r["cnt"] for r in rows}
    finally:
        conn.close()

BOOKMARKS_FILE = BASE / "dashboard" / "data" / "bookmarks.json"
_BOOKMARKS_LOCK = threading.Lock()

def get_bookmarks() -> List[str]:
    """Get list of bookmarked article IDs.

    Tolerates both file shapes seen in the wild: a bare JSON list
    (the historical database format) and a ``{"bookmarks": [...]}`` dict
    (the format serve.py writes). Always returns a list of ID strings.
    """
    if not BOOKMARKS_FILE.exists():
        return []
    try:
        with open(BOOKMARKS_FILE, 'r', encoding='utf-8') as f:
            data = json.load(f)
    except (OSError, json.JSONDecodeError):
        return []
    if isinstance(data, list):
        return data
    if isinstance(data, dict) and isinstance(data.get("bookmarks"), list):
        return data["bookmarks"]
    return []

def toggle_bookmark(article_id: str) -> bool:
    """Toggle bookmark status. Returns True if now bookmarked.

    Atomic write: tempfile in the target directory + os.replace, serialized
    across threads via _BOOKMARKS_LOCK so concurrent toggles cannot
    interleave and corrupt the file.
    """
    with _BOOKMARKS_LOCK:
        bookmarks = get_bookmarks()
        if article_id in bookmarks:
            bookmarks.remove(article_id)
            starred = False
        else:
            bookmarks.append(article_id)
            starred = True
        BOOKMARKS_FILE.parent.mkdir(parents=True, exist_ok=True)
        tmp_fd, tmp_path = tempfile.mkstemp(dir=BOOKMARKS_FILE.parent)
        try:
            with os.fdopen(tmp_fd, 'w', encoding='utf-8') as f:
                json.dump(bookmarks, f)
            os.replace(tmp_path, BOOKMARKS_FILE)
        except Exception:
            try:
                os.unlink(tmp_path)
            except OSError:
                pass
            raise
    return starred

def get_stats() -> Dict[str, Any]:
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

def search_articles(query: str, limit: int = 20) -> ArticleList:
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

def get_today_top_per_category(limit_per_cat: int = 3) -> Dict[str, ArticleList]:
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

def migrate_from_files() -> Tuple[int, int]:
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
                except Exception as e:
                    logger.warning("Migration skipped %s: %s", md_file, e)
                    continue
    print(f"Migration: {imported} imported, {skipped} skipped")
    return imported, skipped

if __name__ == "__main__":
    init_db()
    print("Database initialized.")
