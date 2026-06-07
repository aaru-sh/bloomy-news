#!/usr/bin/env python3
"""Database indexing audit and optimization for news.db.

Creates missing indexes idempotently, runs ANALYZE, and reports
before/after stats. Safe to run repeatedly.
"""
import sqlite3
import os
import sys
from pathlib import Path

DB_PATH = Path(__file__).parent.parent / "news.db"

# Indexes to ensure exist. Each is (name, sql).
# Columns use the actual schema names from database.py.
INDEXES = [
    (
        "idx_articles_published",
        "CREATE INDEX IF NOT EXISTS idx_articles_published ON articles(published)",
    ),
    (
        "idx_articles_source",
        "CREATE INDEX IF NOT EXISTS idx_articles_source ON articles(source)",
    ),
    (
        "idx_articles_category",
        "CREATE INDEX IF NOT EXISTS idx_articles_category ON articles(category)",
    ),
    (
        "idx_articles_content_hash",
        "CREATE INDEX IF NOT EXISTS idx_articles_content_hash ON articles(content_hash)",
    ),
    (
        "idx_articles_is_read",
        "CREATE INDEX IF NOT EXISTS idx_articles_is_read ON articles(is_read)",
    ),
    (
        "idx_articles_arxiv_id",
        "CREATE INDEX IF NOT EXISTS idx_articles_arxiv_id ON articles(arxiv_id)",
    ),
    (
        "idx_articles_bookmarked",
        "CREATE INDEX IF NOT EXISTS idx_articles_bookmarked ON articles(bookmarked)",
    ),
    (
        "idx_articles_url_unique",
        "CREATE UNIQUE INDEX IF NOT EXISTS idx_articles_url_unique ON articles(url) WHERE url IS NOT NULL",
    ),
    # Composite index for get_today_top_per_category: filters by category,
    # orders by confidence DESC, id DESC.
    (
        "idx_articles_cat_confidence",
        "CREATE INDEX IF NOT EXISTS idx_articles_cat_confidence ON articles(category, confidence DESC, id DESC)",
    ),
    # Composite index for date-range + category queries (avoids full scan
    # when both filters are active).
    (
        "idx_articles_category_published",
        "CREATE INDEX IF NOT EXISTS idx_articles_category_published ON articles(category, published DESC)",
    ),
    # dedup_log: content_hash is used for exact-match dedup checks.
    (
        "idx_dedup_log_content_hash",
        "CREATE INDEX IF NOT EXISTS idx_dedup_log_content_hash ON dedup_log(content_hash)",
    ),
]


def get_index_count(conn: sqlite3.Connection) -> int:
    row = conn.execute(
        "SELECT COUNT(*) AS cnt FROM sqlite_master WHERE type='index' AND name NOT LIKE 'sqlite_%'"
    ).fetchone()
    return row["cnt"]


def get_db_size_kb() -> float:
    if not DB_PATH.exists():
        return 0.0
    return DB_PATH.stat().st_size / 1024


def list_existing_indexes(conn: sqlite3.Connection) -> list:
    rows = conn.execute(
        "SELECT name, tbl_name, sql FROM sqlite_master "
        "WHERE type='index' AND name NOT LIKE 'sqlite_%' ORDER BY name"
    ).fetchall()
    return [(r["name"], r["tbl_name"], r["sql"]) for r in rows]


def main():
    if not DB_PATH.exists():
        print(f"ERROR: Database not found at {DB_PATH}")
        sys.exit(1)

    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")

    print("=" * 60)
    print("Database Indexing Audit")
    print("=" * 60)

    # --- Before stats ---
    before_count = get_index_count(conn)
    before_size = get_db_size_kb()
    print(f"\nBEFORE: {before_count} indexes, DB size: {before_size:.1f} KB")

    existing = list_existing_indexes(conn)
    print("\nExisting indexes:")
    for name, tbl, sql in existing:
        print(f"  {name} ON {tbl}")

    # --- Create missing indexes ---
    print("\n--- Creating indexes ---")
    created = 0
    for name, sql in INDEXES:
        already = any(n == name for n, _, _ in existing)
        if already:
            print(f"  SKIP  {name} (already exists)")
        else:
            print(f"  CREATE {name}")
            conn.execute(sql)
            conn.commit()
            created += 1

    if created > 0:
        print(f"\n  Created {created} new index(es)")
    else:
        print("\n  All indexes already present")

    # --- Run ANALYZE for query planner ---
    print("\nRunning ANALYZE to update query planner statistics...")
    conn.execute("ANALYZE")
    conn.commit()
    print("  ANALYZE complete")

    # --- After stats ---
    after_count = get_index_count(conn)
    after_size = get_db_size_kb()
    print(f"\nAFTER:  {after_count} indexes, DB size: {after_size:.1f} KB")

    if after_size > before_size:
        print(f"  Size increase: {after_size - before_size:.1f} KB")
    elif after_size == before_size and created == 0:
        print("  No size change (all indexes already existed)")

    # --- Full index listing ---
    print("\nFinal index listing:")
    for name, tbl, sql in list_existing_indexes(conn):
        print(f"  {name} -> {tbl}")

    conn.close()
    print("\nDone.")


if __name__ == "__main__":
    main()
