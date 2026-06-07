# Database Documentation

## Schema Overview

SQLite database at `news.db` with WAL mode enabled.

### `articles` table

| Column | Type | Default | Description |
|---|---|---|---|
| `id` | INTEGER | AUTOINCREMENT | Primary key |
| `title` | TEXT | NOT NULL | Article title |
| `url` | TEXT | nullable | Article URL |
| `summary` | TEXT | `''` | Article summary |
| `source` | TEXT | `''` | Source identifier (e.g. "hacker_news", "arxiv") |
| `category` | TEXT | `''` | Category (LLM, Neural-Nets, ML-Research, etc.) |
| `subcategory` | TEXT | `'news'` | Subcategory |
| `published` | TEXT | `''` | Publication date (ISO 8601 or RFC 2822) |
| `author` | TEXT | `''` | Article author |
| `content_hash` | TEXT | `''` | SHA-256 of url+title for dedup |
| `arxiv_id` | TEXT | `''` | ArXiv paper ID (e.g. "2301.12345") |
| `title_words` | TEXT | `''` | Space-separated significant title words (for similarity) |
| `categories` | TEXT | `'[]'` | JSON array of tags |
| `confidence` | REAL | `0.0` | Classifier confidence score |
| `is_read` | INTEGER | `0` | Read flag (0/1) |
| `bookmarked` | INTEGER | `0` | Bookmarked flag (0/1) |
| `embedding` | BLOB | NULL | 384-dim float32 vector for semantic search |
| `created_at` | TEXT | `datetime('now')` | Row creation timestamp |

### `dedup_log` table

| Column | Type | Default | Description |
|---|---|---|---|
| `id` | INTEGER | AUTOINCREMENT | Primary key |
| `content_hash` | TEXT | NOT NULL | Hash of the duplicate article |
| `title` | TEXT | NOT NULL | Title of the duplicate |
| `similar_to_id` | INTEGER | nullable | ID of the article it duplicates |
| `similarity_score` | REAL | `0.0` | Similarity score (0.0-1.0) |
| `method` | TEXT | `'url'` | Dedup method: url, arxiv_id, title_similarity |
| `created_at` | TEXT | `datetime('now')` | When the duplicate was detected |

### `articles_fts` (FTS5 virtual table)

Full-text search index on `title`, `summary`, `categories`. Kept in sync via INSERT/UPDATE/DELETE triggers on `articles`.

---

## Indexes

| Index | Table | Column(s) | Purpose |
|---|---|---|---|
| `idx_articles_category` | articles | `category` | Category filtering in `get_articles()`, `get_today_top_per_category()`, `get_stats()` |
| `idx_articles_published` | articles | `published` | Date-range queries, ORDER BY published DESC |
| `idx_articles_source` | articles | `source` | Per-source filtering in `get_articles()`, `get_stats()` |
| `idx_articles_content_hash` | articles | `content_hash` | Dedup lookups in `is_duplicate()` |
| `idx_articles_arxiv_id` | articles | `arxiv_id` | ArXiv dedup in `is_duplicate()` |
| `idx_articles_is_read` | articles | `is_read` | Read/unread filtering |
| `idx_articles_url_unique` | articles | `url` (partial, WHERE url IS NOT NULL) | UNIQUE constraint + URL dedup |
| `idx_articles_bookmarked` | articles | `bookmarked` | Bookmark queries in `get_bookmarked_article_ids()` |
| `idx_articles_cat_confidence` | articles | `(category, confidence DESC, id DESC)` | Composite for `get_today_top_per_category()` |
| `idx_articles_category_published` | articles | `(category, published DESC)` | Composite for category+date range queries |
| `idx_dedup_log_content_hash` | dedup_log | `content_hash` | Dedup log lookups |

---

## Query Patterns and Index Usage

### `is_duplicate()` — called for every article ingestion

| Condition | Index used | Notes |
|---|---|---|
| `WHERE url = ?` | `idx_articles_url_unique` | Exact match, fast |
| `WHERE arxiv_id = ?` | `idx_articles_arxiv_id` | Exact match, fast |
| `WHERE title_words LIKE ?` | **No index** | Full scan of recent 7 days of rows; mitigated by `published > datetime('now', '-7 days')` limiting scope |
| `ORDER BY id DESC LIMIT 200` | Primary key | Fast after row filtering |

### `get_articles()` — main listing endpoint

| Filter | Index used |
|---|---|
| `category = ?` | `idx_articles_category` |
| `source = ?` | `idx_articles_source` |
| `date(a.published) >= date(?)` | **No index** | `date()` wrapping prevents index use; full scan on filtered subset |
| `is_read = ?` | `idx_articles_is_read` |
| `ORDER BY published DESC, id DESC` | Partial (after filtering) |

### `get_today_top_per_category()`

Uses `idx_articles_cat_confidence` composite index. The `date(published) = date('now')` filter can't use `idx_articles_published` directly due to `date()` wrapping, but the composite on `(category, confidence DESC, id DESC)` helps once rows are filtered by category.

### `cleanup_old_articles()`

Full scan of `articles` table (intentional — must parse every row's date in Python due to mixed ISO/RFC 2822 formats). Acceptable at current scale (~3000 rows/month).

### `get_stats()`

- `GROUP BY category` — benefits from `idx_articles_category`
- `GROUP BY source` — benefits from `idx_articles_source`

---

## WAL Mode

Write-Ahead Logging is enabled via `PRAGMA journal_mode=WAL` in `get_connection()`.

**Benefits:**
- Readers don't block writers (concurrent read/write access)
- Write transactions are faster (append-only WAL vs read-modify-write rollback)
- Crash recovery is more reliable (WAL is atomic)
- Checkpointing reclaims WAL space periodically

**Notes:**
- WAL files (`news.db-wal`, `news.db-shm`) are normal and expected
- WAL auto-checkpoints at 1000 pages by default (configurable)
- For backup, copy all three files: `news.db`, `news.db-wal`, `news.db-shm`

---

## Backup Strategy

### Quick backup (hot, no downtime)

```bash
# SQLite online backup via CLI
sqlite3 news.db ".backup news_backup_$(date +%Y%m%d).db"

# Or copy all WAL files for a consistent snapshot
cp news.db news.db-wal news.db-shm /backup/location/
```

### Automated backup

```bash
# Cron: daily backup at 3 AM
0 3 * * * cd /path/to/News && sqlite3 news.db ".backup backups/news_$(date +\%Y\%m\%d).db"
```

### Restore

```bash
sqlite3 news_restored.db < news_backup_YYYYMMDD.db
```

---

## Migration Strategy

Schema changes are applied via `init_db()` in `database.py`. All DDL uses `CREATE TABLE IF NOT EXISTS` and `CREATE INDEX IF NOT EXISTS` so re-running is idempotent.

**For adding new columns:**

```python
# In init_db(), wrap in try/except for idempotency:
try:
    conn.execute("ALTER TABLE articles ADD COLUMN new_col TYPE DEFAULT value")
    conn.commit()
except Exception:
    pass  # Column already exists
```

**For adding indexes:**

```python
# Run scripts/add_indexes.py — idempotent, reports stats
python scripts/add_indexes.py
```

**For complex migrations:**

1. Write migration SQL in a script under `scripts/`
2. Test on a copy of the database first
3. Run against production
4. Verify with `PRAGMA index_list(articles)`

---

## Performance Tips

### ANALYZE

Run after significant data changes to update the query planner's statistics:

```sql
ANALYZE;
```

The `scripts/add_indexes.py` script runs ANALYZE automatically.

### VACUUM

Reclaims unused space and defragments the database. Run periodically (e.g., monthly) or after large deletions:

```sql
VACUUM;
```

**Warning:** VACUUM rewrites the entire database file. It requires 2x the DB size in free disk space and blocks concurrent access.

### Index Maintenance

- SQLite automatically maintains B-tree indexes on INSERT/UPDATE/DELETE
- No manual reindexing needed under normal operation
- If an index becomes corrupt, drop and recreate it:

```sql
DROP INDEX IF EXISTS idx_articles_category;
CREATE INDEX idx_articles_category ON articles(category);
```

### Query Optimization

- Avoid `SELECT *` when only a few columns are needed (reduces I/O)
- Use `EXPLAIN QUERY PLAN` to verify index usage:

```sql
EXPLAIN QUERY PLAN
SELECT * FROM articles WHERE category = 'LLM' ORDER BY published DESC;
```

- The `date()` function wrapping on `published` prevents index usage for date filters. If date-range performance becomes critical, add a generated column or store dates in a parseable format.
- LIKE patterns with leading wildcards (`%query%`) cannot use B-tree indexes — that's why FTS5 is used for text search.
