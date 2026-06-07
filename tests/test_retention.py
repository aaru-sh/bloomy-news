"""Tests for cleanup_old_articles() in database.py (v1.2.1).

Covers:
  - MAX_ARTICLE_AGE_DAYS constant is 30
  - cleanup_old_articles(0) is a no-op (returns 0, no DB writes)
  - Deletes articles with published older than threshold
  - Keeps articles newer than threshold
  - Handles empty published via created_at fallback
  - Prunes dedup_log entries older than 7 days
  - Returns correct count of deleted articles
  - Works on a fresh DB and on a pre-existing DB with mixed dates
"""
import sqlite3
import sys
import tempfile
import unittest
from datetime import datetime, timedelta
from pathlib import Path

BASE = Path(__file__).parent.parent
sys.path.insert(0, str(BASE))

import database


class TestRetentionConstant(unittest.TestCase):
    def test_max_article_age_days_is_30(self):
        self.assertEqual(database.MAX_ARTICLE_AGE_DAYS, 30)


class TestCleanupOldArticles(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        self.tmp_path = Path(self.tmp.name)
        self.original_db_path = database.DB_PATH
        database.DB_PATH = self.tmp_path / "news.db"
        database.init_db()

    def tearDown(self):
        database.DB_PATH = self.original_db_path
        try:
            self.tmp.cleanup()
        except (OSError, PermissionError):
            pass

    def _insert_article(self, published: str, created_at: str = "") -> int:
        """Insert a raw article row bypassing dedup, returns the new id."""
        conn = database.get_connection()
        try:
            cur = conn.execute(
                """
                INSERT INTO articles
                    (title, url, published, source, category, created_at)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (f"Title {published}", f"http://test/{published}", published, "test", "Test", created_at),
            )
            conn.commit()
            return cur.lastrowid
        finally:
            conn.close()

    def test_cleanup_zero_days_is_noop(self):
        old_pub = (datetime.now() - timedelta(days=365)).strftime("%Y-%m-%d")
        self._insert_article(old_pub)
        before = sqlite3.connect(str(database.DB_PATH)).execute(
            "SELECT COUNT(*) FROM articles"
        ).fetchone()[0]
        deleted = database.cleanup_old_articles(max_age_days=0)
        after = sqlite3.connect(str(database.DB_PATH)).execute(
            "SELECT COUNT(*) FROM articles"
        ).fetchone()[0]
        self.assertEqual(deleted, 0)
        self.assertEqual(before, after)

    def test_deletes_articles_older_than_threshold(self):
        old_pub = (datetime.now() - timedelta(days=60)).strftime("%Y-%m-%d")
        new_pub = (datetime.now() - timedelta(days=5)).strftime("%Y-%m-%d")
        self._insert_article(old_pub)
        self._insert_article(new_pub)
        deleted = database.cleanup_old_articles(max_age_days=30)
        self.assertEqual(deleted, 1)
        remaining = sqlite3.connect(str(database.DB_PATH)).execute(
            "SELECT published FROM articles"
        ).fetchall()
        self.assertEqual(len(remaining), 1)
        self.assertEqual(remaining[0][0], new_pub)

    def test_keeps_articles_within_threshold(self):
        new_pub = (datetime.now() - timedelta(days=10)).strftime("%Y-%m-%d")
        self._insert_article(new_pub)
        deleted = database.cleanup_old_articles(max_age_days=30)
        self.assertEqual(deleted, 0)

    def test_handles_rfc_2822_published(self):
        """Real scrapers store published as RFC 2822. SQLite's date() should parse it."""
        old_pub = (datetime.now() - timedelta(days=60)).strftime("%a, %d %b %Y %H:%M:%S GMT")
        self._insert_article(old_pub)
        deleted = database.cleanup_old_articles(max_age_days=30)
        self.assertEqual(deleted, 1)

    def test_empty_published_uses_created_at(self):
        """Articles with empty published fall back to created_at for the cutoff."""
        old_created = (datetime.now() - timedelta(days=60)).strftime("%Y-%m-%d %H:%M:%S")
        self._insert_article(published="", created_at=old_created)
        deleted = database.cleanup_old_articles(max_age_days=30)
        self.assertEqual(deleted, 1)

    def test_empty_published_with_recent_created_at_kept(self):
        new_created = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        self._insert_article(published="", created_at=new_created)
        deleted = database.cleanup_old_articles(max_age_days=30)
        self.assertEqual(deleted, 0)

    def test_prunes_old_dedup_log_entries(self):
        """dedup_log entries older than 7 days should be deleted during cleanup."""
        old_log = (datetime.now() - timedelta(days=30)).strftime("%Y-%m-%d %H:%M:%S")
        recent_log = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        old_pub = (datetime.now() - timedelta(days=60)).strftime("%Y-%m-%d")
        self._insert_article(old_pub)

        conn = database.get_connection()
        conn.execute(
            "INSERT INTO dedup_log (content_hash, title, created_at) VALUES (?, ?, ?)",
            ("abc123", "Old dup", old_log),
        )
        conn.execute(
            "INSERT INTO dedup_log (content_hash, title, created_at) VALUES (?, ?, ?)",
            ("def456", "Recent dup", recent_log),
        )
        conn.commit()
        conn.close()

        database.cleanup_old_articles(max_age_days=30)

        conn = sqlite3.connect(str(database.DB_PATH))
        remaining = conn.execute("SELECT content_hash FROM dedup_log").fetchall()
        conn.close()
        self.assertEqual(len(remaining), 1)
        self.assertEqual(remaining[0][0], "def456")

    def test_returns_correct_count(self):
        for i in range(5):
            old_pub = (datetime.now() - timedelta(days=60 + i)).strftime("%Y-%m-%d")
            self._insert_article(old_pub)
        for i in range(3):
            new_pub = (datetime.now() - timedelta(days=i + 1)).strftime("%Y-%m-%d")
            self._insert_article(new_pub)
        deleted = database.cleanup_old_articles(max_age_days=30)
        self.assertEqual(deleted, 5)

    def test_default_threshold_is_30_days(self):
        """No-arg call should delete articles older than MAX_ARTICLE_AGE_DAYS."""
        old_pub = (datetime.now() - timedelta(days=31)).strftime("%Y-%m-%d")
        boundary_pub = (datetime.now() - timedelta(days=29)).strftime("%Y-%m-%d")
        self._insert_article(old_pub)
        self._insert_article(boundary_pub)
        deleted = database.cleanup_old_articles()
        self.assertEqual(deleted, 1)

    def test_negative_threshold_is_noop(self):
        old_pub = (datetime.now() - timedelta(days=365)).strftime("%Y-%m-%d")
        self._insert_article(old_pub)
        deleted = database.cleanup_old_articles(max_age_days=-1)
        self.assertEqual(deleted, 0)


class TestCleanupOnLiveDB(unittest.TestCase):
    """Smoke test: cleanup_old_articles on the real DB should not crash
    and should not delete recent articles (oldest is ~6 days)."""

    def test_live_db_keeps_recent_articles(self):
        if not database.DB_PATH.exists():
            self.skipTest("live news.db not present")
        before = database.DB_PATH.stat().st_size
        deleted = database.cleanup_old_articles()
        after = database.DB_PATH.stat().st_size
        # All current articles are within 7 days of 2026-06-07, so 0 should be deleted.
        self.assertEqual(deleted, 0)
        self.assertEqual(before, after)


if __name__ == "__main__":
    unittest.main()
