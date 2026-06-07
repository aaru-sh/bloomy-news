#!/usr/bin/env python3
"""Database query analyzer for news.db.

Runs EXPLAIN QUERY PLAN on key queries, reports index usage,
table sizes, and suggests missing indexes.
"""
import sqlite3
import sys
from pathlib import Path

BASE = Path(__file__).parent.parent.resolve()
DB_PATH = BASE / "news.db"

# Key queries extracted from database.py, labeled for analysis
QUERIES = {
    # --- Full table scan (no WHERE) ---
    "cleanup_old_articles": {
        "sql": "SELECT id, published, created_at FROM articles",
        "source": "database.py:287",
        "issue": "Full table scan - no WHERE clause, loads entire table into Python",
    },
    # --- LIKE '%pattern%' (bypasses indexes) ---
    "is_duplicate_title_words": {
        "sql": """
            SELECT id, title, title_words FROM articles
            WHERE published > datetime('now', '-7 days')
            AND (title_words LIKE ? OR title_words LIKE ? OR title_words LIKE ?)
            ORDER BY id DESC LIMIT 200
        """,
        "source": "database.py:214-219",
        "issue": "LIKE '%word%' on title_words prevents index usage",
    },
    "like_search_fallback": {
        "sql": """
            SELECT id FROM articles
            WHERE title LIKE ? OR summary LIKE ? OR title_words LIKE ?
            ORDER BY published DESC, id DESC LIMIT 500
        """,
        "source": "database.py:505-510",
        "issue": "Three LIKE '%query%' columns; sort without composite index",
    },
    "search_articles_like_fallback": {
        "sql": """
            SELECT * FROM articles
            WHERE title LIKE ? OR summary LIKE ? OR title_words LIKE ?
            ORDER BY published DESC, id DESC LIMIT ?
        """,
        "source": "database.py:762-766",
        "issue": "LIKE '%query%' fallback when FTS5 unavailable",
    },
    # --- Multiple queries in one function ---
    "get_stats_categories": {
        "sql": "SELECT category, COUNT(*) as cnt FROM articles GROUP BY category ORDER BY cnt DESC",
        "source": "database.py:734",
        "issue": "Part of 4-query burst in get_stats()",
    },
    "get_stats_today": {
        "sql": "SELECT COUNT(*) as cnt FROM articles WHERE date(published) = date('now')",
        "source": "database.py:735",
        "issue": "Uses date() function on column - prevents index usage",
    },
    "get_stats_total": {
        "sql": "SELECT COUNT(*) as cnt FROM articles",
        "source": "database.py:736",
        "issue": "Part of 4-query burst",
    },
    "get_stats_sources": {
        "sql": "SELECT source, COUNT(*) as cnt FROM articles GROUP BY source ORDER BY cnt DESC LIMIT 10",
        "source": "database.py:737",
        "issue": "Part of 4-query burst",
    },
    # --- N+1 pattern ---
    "get_today_top_per_category_distinct": {
        "sql": "SELECT DISTINCT category FROM articles WHERE category != ''",
        "source": "database.py:774",
        "issue": "First query of N+1: fetches categories",
    },
    "get_today_top_per_category_loop": {
        "sql": """
            SELECT * FROM articles
            WHERE category = ? AND date(published) = date('now')
            ORDER BY confidence DESC, id DESC LIMIT ?
        """,
        "source": "database.py:778-781",
        "issue": "N+1: executed once per distinct category",
    },
    # --- Composite index candidates ---
    "get_articles_default": {
        "sql": "SELECT * FROM articles a ORDER BY a.published DESC, a.id DESC LIMIT ? OFFSET ?",
        "source": "database.py:555",
        "issue": "Sorts on (published, id) - no composite index exists",
    },
    "get_articles_with_category": {
        "sql": "SELECT * FROM articles a WHERE a.category = ? ORDER BY a.published DESC, a.id DESC LIMIT ? OFFSET ?",
        "source": "database.py:555",
        "issue": "Filter + sort - composite index on (category, published, id) needed",
    },
    # --- Bookmark hash prefix (substr scan) ---
    "set_bookmarked_by_hash_prefix": {
        "sql": "UPDATE articles SET bookmarked = ? WHERE substr(content_hash, 1, 16) = ?",
        "source": "database.py:643-644",
        "issue": "substr() on column prevents index usage",
    },
    # --- count_articles_today (function on column) ---
    "count_articles_today": {
        "sql": """
            SELECT category, COUNT(*) AS cnt
            FROM articles
            WHERE date(published) = date('now')
            GROUP BY category
        """,
        "source": "database.py:669-673",
        "issue": "date() function on published prevents index usage",
    },
}


def get_connection() -> sqlite3.Connection:
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    return conn


def _get_plan_conn() -> sqlite3.Connection:
    """Connection for EXPLAIN queries - no row_factory so tuples work."""
    conn = sqlite3.connect(str(DB_PATH))
    return conn


def analyze_query_plan(_conn: sqlite3.Connection, label: str, sql: str) -> dict:
    """Run EXPLAIN QUERY PLAN and return structured results.

    Uses a separate plain-tuple connection because EXPLAIN output is
    positional (id, parent, detail) and sqlite3.Row dicts don't parse
    reliably for plan analysis. Dummy bindings are supplied for any
    ``?`` placeholders so parameterized queries can be explained.
    """
    import re as _re
    plan_conn = _get_plan_conn()
    try:
        # Count ? placeholders and supply dummy string values
        param_count = sql.count("?")
        dummy = [""] * param_count
        plan_rows = plan_conn.execute(
            f"EXPLAIN QUERY PLAN {sql.strip()}", dummy
        ).fetchall()
        # Convert all rows to string representations for analysis
        plan_lines = [str(row) for row in plan_rows]
        plan_text = "\n".join(plan_lines)
        # Check for scan/index keywords across all columns
        full_repr = repr(plan_rows)
        uses_scan = "SCAN" in full_repr
        uses_search = "SEARCH" in full_repr
        uses_temp_btree = "TEMP B-TREE" in full_repr or "USE TEMP" in full_repr
        uses_index = uses_search or ("USING INDEX" in full_repr)
        return {
            "label": label,
            "sql": sql.strip(),
            "plan": plan_text,
            "uses_full_scan": uses_scan and not uses_search,
            "uses_index": uses_index,
            "uses_temp_sort": uses_temp_btree,
        }
    except Exception as e:
        return {
            "label": label,
            "sql": sql.strip(),
            "plan": f"ERROR: {e}",
            "uses_full_scan": False,
            "uses_index": False,
            "uses_temp_sort": False,
        }
    finally:
        plan_conn.close()


def get_table_stats(conn: sqlite3.Connection) -> dict:
    """Return row counts, page counts, and size for each table."""
    tables = {}
    for row in conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
    ).fetchall():
        name = row["name"]
        if name.startswith("sqlite_"):
            continue
        info = conn.execute(f"PRAGMA table_info({name})").fetchall()
        count = conn.execute(f"SELECT COUNT(*) as cnt FROM {name}").fetchone()["cnt"]
        page_count = conn.execute(f"PRAGMA page_count({name})").fetchone()
        page_size = conn.execute("PRAGMA page_size").fetchone()
        freelist = conn.execute(f"PRAGMA freelist_count({name})").fetchone()
        pages = page_count[0] if page_count else 0
        psize = page_size[0] if page_size else 4096
        free = freelist[0] if freelist else 0
        tables[name] = {
            "columns": [dict(c) for c in info],
            "row_count": count,
            "pages": pages,
            "page_size": psize,
            "size_bytes": pages * psize,
            "free_pages": free,
        }
    return tables


def get_index_stats(conn: sqlite3.Connection) -> list:
    """List all indexes with their tables and sizes."""
    indexes = []
    for row in conn.execute(
        "SELECT name, tbl_name, sql FROM sqlite_master WHERE type='index' ORDER BY tbl_name, name"
    ).fetchall():
        idx_name = row["name"]
        tbl_name = row["tbl_name"]
        # Get page count for this index
        try:
            info = conn.execute(f"PRAGMA index_info({idx_name})").fetchall()
            page_count = conn.execute(f"PRAGMA page_count({idx_name})").fetchone()
            pages = page_count[0] if page_count else 0
            page_size = conn.execute("PRAGMA page_size").fetchone()
            psize = page_size[0] if page_size else 4096
        except Exception:
            pages = 0
            psize = 0
        indexes.append({
            "name": idx_name,
            "table": tbl_name,
            "sql": row["sql"],
            "pages": pages,
            "size_bytes": pages * psize,
            "columns": [dict(c) for c in info],
        })
    return indexes


def suggest_indexes(conn: sqlite3.Connection) -> list:
    """Analyze table stats and suggest missing indexes."""
    suggestions = []
    table_stats = get_table_stats(conn)

    articles = table_stats.get("articles", {})
    row_count = articles.get("row_count", 0)

    if row_count < 100:
        suggestions.append(f"Only {row_count} rows - optimization may be premature.")
        return suggestions

    existing = {r["name"] for r in get_index_stats(conn)}

    # Composite index for ORDER BY published DESC, id DESC
    if "idx_articles_published_id" not in existing:
        suggestions.append(
            "CREATE INDEX idx_articles_published_id ON articles(published DESC, id DESC) -- "
            "covers ORDER BY in get_articles(), search fallbacks"
        )

    # Composite index for category + published + id (covers sort tiebreak)
    if "idx_articles_cat_pub_id" not in existing:
        suggestions.append(
            "CREATE INDEX idx_articles_cat_pub_id ON articles(category, published DESC, id DESC) -- "
            "covers get_today_top_per_category(), category-filtered get_articles() with sort"
        )

    # Composite index for (is_read, published)
    if "idx_articles_read_pub" not in existing:
        suggestions.append(
            "CREATE INDEX idx_articles_read_pub ON articles(is_read, published DESC) -- "
            "covers is_read filter + sort in get_articles()"
        )

    # Composite index for (bookmarked, published)
    if "idx_articles_bmk_pub" not in existing:
        suggestions.append(
            "CREATE INDEX idx_articles_bmk_pub ON articles(bookmarked, published DESC) -- "
            "covers bookmarked filter + sort"
        )

    # FTS5 is already configured, but warn if missing
    try:
        has_fts = conn.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name='articles_fts'"
        ).fetchone() is not None
    except Exception:
        has_fts = False
    if not has_fts:
        suggestions.append(
            "FTS5 virtual table missing -- LIKE fallbacks are ~10x slower than FTS5 MATCH"
        )

    return suggestions


def run_analyze(conn: sqlite3.Connection) -> None:
    """Run ANALYZE to update SQLite query planner statistics."""
    conn.execute("ANALYZE")
    conn.commit()


def main():
    print("=" * 70)
    print("  NEWS.DB QUERY ANALYSIS REPORT")
    print("=" * 70)

    if not DB_PATH.exists():
        print(f"\nDatabase not found: {DB_PATH}")
        sys.exit(1)

    conn = get_connection()

    # 1. Table sizes
    print("\n--- TABLE SIZES ---\n")
    table_stats = get_table_stats(conn)
    for name, info in table_stats.items():
        size_kb = info["size_bytes"] / 1024
        print(f"  {name}: {info['row_count']} rows, {info['pages']} pages ({size_kb:.1f} KB), {info['free_pages']} free pages")

    # 2. Index sizes
    print("\n--- INDEXES ---\n")
    indexes = get_index_stats(conn)
    for idx in indexes:
        size_kb = idx["size_bytes"] / 1024
        cols = ", ".join(c["name"] for c in idx["columns"])
        print(f"  {idx['name']} on {idx['table']}({cols}) - {idx['pages']} pages ({size_kb:.1f} KB)")
        if idx["sql"]:
            print(f"    {idx['sql']}")

    # 3. Query plan analysis
    print("\n--- QUERY PLAN ANALYSIS ---\n")
    scan_count = 0
    index_count = 0
    temp_sort_count = 0
    for label, info in QUERIES.items():
        result = analyze_query_plan(conn, label, info["sql"])
        if result["uses_full_scan"]:
            status = "FULL SCAN"
            scan_count += 1
        elif result["uses_index"]:
            status = "INDEX OK"
            index_count += 1
        else:
            status = "CHECK"
        if result.get("uses_temp_sort"):
            temp_sort_count += 1
        print(f"  [{status}] {label}")
        print(f"    Source: {info['source']}")
        print(f"    Issue: {info['issue']}")
        for line in str(result["plan"]).split("\n"):
            if line.strip():
                print(f"    Plan: {line.strip()}")
        print()

    print(f"  Summary: {index_count} use index, {scan_count} full scan, {temp_sort_count} temp sort")

    # 4. Missing index suggestions
    print("\n--- INDEX SUGGESTIONS ---\n")
    suggestions = suggest_indexes(conn)
    if suggestions:
        for s in suggestions:
            print(f"  {s}")
    else:
        print("  No missing indexes identified.")

    # 5. WAL mode status
    print("\n--- WAL MODE ---\n")
    journal = conn.execute("PRAGMA journal_mode").fetchone()[0]
    print(f"  Current journal mode: {journal}")
    if journal == "wal":
        print("  WAL mode is enabled - good for read-heavy workloads")
        wal_auto = conn.execute("PRAGMA wal_autocheckpoint").fetchone()[0]
        print(f"  Auto-checkpoint interval: {wal_auto} pages")
    else:
        print("  WARNING: WAL mode is NOT enabled. Set PRAGMA journal_mode=WAL")

    # 6. Run ANALYZE
    print("\n--- RUNNING ANALYZE ---\n")
    try:
        run_analyze(conn)
        print("  ANALYZE completed successfully - statistics updated")
    except Exception as e:
        print(f"  ANALYZE failed: {e}")

    # 7. Post-analyze plan re-check
    print("\n--- POST-ANALYZE PLAN RE-CHECK ---\n")
    for label, info in QUERIES.items():
        result = analyze_query_plan(conn, label, info["sql"])
        if result["uses_full_scan"]:
            status = "FULL SCAN"
        elif result["uses_index"]:
            status = "INDEX OK"
        else:
            status = "CHECK"
        sort_note = " [TEMP SORT]" if result.get("uses_temp_sort") else ""
        print(f"  [{status}]{sort_note} {label}")

    conn.close()
    print("\n" + "=" * 70)
    print("  Analysis complete.")
    print("=" * 70)


if __name__ == "__main__":
    main()
