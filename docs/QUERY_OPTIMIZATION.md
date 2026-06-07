# Query Optimization Guide

This document covers query performance analysis, identified slow patterns, and optimization strategies for `news.db`.

## 1. Current Query Performance Baseline

Run `scripts/query_analyzer.py` to generate a live baseline report:

```bash
python scripts/query_analyzer.py
```

Key metrics reported:
- Table row counts and on-disk sizes
- Index page counts and sizes
- EXPLAIN QUERY PLAN output for each critical query
- Whether queries use indexes or fall back to full table scans
- ANALYZE statistics update

## 2. Identified Slow Queries and Fixes

### 2.1 Full Table Scan: `cleanup_old_articles()`

**Problem:** `database.py:287` runs `SELECT id, published, created_at FROM articles` with no WHERE clause. Every row is loaded into Python, parsed, and filtered.

**Impact:** O(N) on every cleanup run. With 50k+ rows this takes seconds.

**Fix options:**
1. Add a generated column `published_iso TEXT GENERATED ALWAYS AS (...)` that stores a normalized ISO timestamp, then filter in SQL.
2. At minimum, add `WHERE published != '' OR created_at != ''` to skip empty rows.

```sql
-- Option 1: add a normalized column for SQL-side filtering
ALTER TABLE articles ADD COLUMN published_iso TEXT;
UPDATE articles SET published_iso = published WHERE published != '';
CREATE INDEX idx_articles_pub_iso ON articles(published_iso);
-- Then cleanup becomes:
-- DELETE FROM articles WHERE published_iso < datetime('now', '-30 days')
```

### 2.2 LIKE '%pattern%' Queries

**Problem:** `is_duplicate()` (line 214), `_like_search_ids()` (line 505), and `search_articles()` (line 762) all use `LIKE '%word%'` which prevents index usage.

**Impact:** Full table scan per LIKE pattern. Three LIKE columns = three scans.

**Fix:** FTS5 is already configured and used as the primary search path. Ensure FTS5 triggers stay synchronized. The LIKE fallback is acceptable for rare edge cases but should log a warning when triggered so you know FTS5 has fallen behind.

### 2.3 N+1 Pattern: `get_today_top_per_category()`

**Problem:** `database.py:774-783` fetches distinct categories, then loops with one query per category.

**Impact:** 1 + N queries where N = number of categories (typically 6-10).

**Fix:** Single query with window function:

```sql
SELECT * FROM (
    SELECT *, ROW_NUMBER() OVER (PARTITION BY category ORDER BY confidence DESC, id DESC) as rn
    FROM articles
    WHERE category != '' AND date(published) = date('now')
)
WHERE rn <= 3
ORDER BY category, rn;
```

### 2.4 Multiple Queries in `get_stats()`

**Problem:** `database.py:731-745` runs 4 separate queries: category counts, today count, total count, source counts.

**Fix:** Combine into 1-2 queries:

```sql
-- Single query for category counts + today count:
SELECT category, COUNT(*) as cnt,
       SUM(CASE WHEN date(published) = date('now') THEN 1 ELSE 0 END) as today_cnt
FROM articles
GROUP BY category
ORDER BY cnt DESC;
```

### 2.5 `date(published)` Prevents Index Usage

**Problem:** `database.py:670-674`, `database.py:735`, `database.py:780` all use `date(published) = date('now')`. Wrapping the column in a function prevents index usage.

**Fix:** Store dates in a consistent format and filter with range comparisons:

```sql
-- Instead of: WHERE date(published) = date('now')
-- Use: WHERE published >= datetime('now', 'start of day')
--       AND published < datetime('now', 'start of day', '+1 day')
```

### 2.6 `substr()` in `set_bookmarked_by_hash_prefix()`

**Problem:** `database.py:643-644` uses `WHERE substr(content_hash, 1, 16) = ?` which prevents index usage on `content_hash`.

**Fix:** Add a dedicated prefix column or use `LIKE` prefix matching (which can use indexes):

```sql
-- Option A: prefix column
ALTER TABLE articles ADD COLUMN content_hash_prefix TEXT;
UPDATE articles SET content_hash_prefix = substr(content_hash, 1, 16);
CREATE INDEX idx_articles_hash_prefix ON articles(content_hash_prefix);
-- Then: WHERE content_hash_prefix = ?

-- Option B: LIKE prefix (can use index if NOT leading wildcard)
WHERE content_hash LIKE 'abc123def456%'  -- leading literal, index-friendly
```

## 3. Index Strategy

### Existing Indexes

| Index | Column(s) | Purpose |
|-------|-----------|---------|
| `idx_articles_category` | `category` | Category filter |
| `idx_articles_published` | `published` | Date sort |
| `idx_articles_source` | `source` | Source filter |
| `idx_articles_content_hash` | `content_hash` | Dedup lookup |
| `idx_articles_arxiv_id` | `arxiv_id` | ArXiv dedup |
| `idx_articles_is_read` | `is_read` | Read status filter |
| `idx_articles_bookmarked` | `bookmarked` | Bookmark filter |
| `idx_articles_url_unique` | `url` (partial) | URL uniqueness |

### Recommended Additional Indexes

```sql
-- Composite index for the most common query pattern (date sort + id tiebreak)
CREATE INDEX idx_articles_pub_id ON articles(published DESC, id DESC);

-- Composite index for category-filtered date queries
CREATE INDEX idx_articles_cat_pub_id ON articles(category, published DESC, id DESC);

-- For is_read filter with date sort
CREATE INDEX idx_articles_read_pub ON articles(is_read, published DESC);
```

### Index Trade-offs

- Each index adds ~10-15% write overhead per INSERT/UPDATE.
- With ~3000 articles/month the write cost is negligible.
- Composite indexes are more valuable than single-column indexes for multi-condition queries.

## 4. WAL Mode Benefits

WAL (Write-Ahead Logging) mode is already enabled in `get_connection()`:

```python
conn.execute("PRAGMA journal_mode=WAL")
```

**Benefits for this workload:**
- **Concurrent reads:** Multiple readers don't block each other or the writer.
- **Faster writes:** Writes go to the WAL file without locking the main database.
- **Crash recovery:** WAL is an append-only log; corruption risk is lower.
- **Checkpoint control:** `PRAGMA wal_autocheckpoint=1000` (default) flushes WAL to the main DB periodically.

**Monitoring:**
```sql
PRAGMA journal_mode;          -- should return 'wal'
PRAGMA wal_autocheckpoint;    -- default 1000 pages (~4MB)
PRAGMA wal_checkpoint(PASSIVE); -- manual checkpoint without blocking readers
```

**When to force checkpoint:**
- Before long read-only periods (e.g., dashboard serving)
- When the WAL file grows large (>10MB)

## 5. Connection Pooling Considerations

The current implementation opens a new `sqlite3.connect()` for every function call. SQLite handles this safely due to its file-level locking, but there are trade-offs:

### Current Approach (No Pooling)
- Simple, correct, no thread-safety concerns.
- Each connection pays the WAL mode setup cost (one PRAGMA per connection).
- Adequate for the current workload (~100-500 queries/day).

### If Scaling Needed
- Use `check_same_thread=False` for shared connections across threads.
- Use a `threading.Lock` around connection access.
- Consider `sqlite3.pool` or a library like `sqlalchemy` with `StaticPool`.
- Set `PRAGMA cache_size = -64000` (64MB) per connection to reduce disk I/O.

### For This Project
No pooling is needed at current scale. The per-call connection pattern is idiomatic for SQLite and avoids complexity.

## 6. How to Run EXPLAIN QUERY PLAN

### Manual Analysis

```sql
-- Attach to the database
sqlite3 news.db

-- Run EXPLAIN QUERY PLAN on any query
EXPLAIN QUERY PLAN
SELECT * FROM articles
WHERE category = 'LLM'
ORDER BY published DESC, id DESC
LIMIT 50;

-- Look for SCAN vs SEARCH in output:
-- SCAN = full table scan (bad for large tables)
-- SEARCH = index lookup (good)
-- USING INDEX = covering index (best)
```

### Automated Analysis

```bash
python scripts/query_analyzer.py
```

This runs EXPLAIN QUERY PLAN on all critical queries and reports:
- Which queries use indexes vs full scans
- Table and index sizes
- Missing index suggestions
- Runs ANALYZE to update statistics

### Interpreting Output

- **`SCAN TABLE articles`** -- Full table scan, no index used
- **`SEARCH TABLE articles USING INDEX idx_...`** -- Index lookup
- **`USING INDEX idx_...`** -- Covering index (data read from index only)
- **`USE TEMP B-TREE FOR ORDER BY`** -- Sorting done in temp file (add index)

## 7. How to Profile Query Performance

### Timing Queries

```bash
# Enable timing in SQLite CLI
sqlite3 news.db
.headers on
.timer on

# Run query and see timing
SELECT * FROM articles WHERE category = 'LLM' ORDER BY published DESC LIMIT 50;
```

### Python Profiling

```python
import time
from database import get_connection

conn = get_connection()
start = time.perf_counter()
# ... run query ...
elapsed = time.perf_counter() - start
print(f"Query took {elapsed*1000:.2f}ms")
conn.close()
```

### PRAGMA Profiling

```sql
-- Enable statement profiling
PRAGMA profiling_mode = SPECIFIC;
PRAGMA profile_list;

-- Run queries, then check:
SELECT * FROM sqlite_stat_stmts ORDER BY exec_count DESC;
```

### Recommended Profiling Workflow

1. Run `python scripts/query_analyzer.py` for baseline.
2. Add indexes suggested by the analyzer.
3. Re-run analyzer to verify index usage.
4. Monitor query times in production logs.
5. Re-run ANALYZE monthly or after large data imports.

## Summary of Recommendations

| Priority | Issue | Impact | Fix |
|----------|-------|--------|-----|
| HIGH | `cleanup_old_articles` full scan | O(N) on cleanup | Add normalized date column |
| HIGH | LIKE '%pattern%' in dedup | 3x full scan per insert | Rely on FTS5, log LIKE fallback |
| MEDIUM | N+1 in `get_today_top_per_category` | 1+N queries | Single query with ROW_NUMBER() |
| MEDIUM | `date(published)` prevents index | No index on date filter | Range comparison on raw column |
| MEDIUM | Missing composite indexes | Sorts without index | Add `(published, id)` composite |
| LOW | 4-query burst in `get_stats` | 4 round trips | Combine into 1-2 queries |
| LOW | `substr()` in bookmark prefix | Prevents index | Add prefix column |
