"""Tests for the bookmarked column in the articles table (v1.4.2).

Covers:
  - init_db() creates the bookmarked column on a fresh DB
  - The migration ALTER TABLE adds the column to a pre-existing DB
  - set_bookmarked / is_bookmarked round-trip
  - set_bookmarked_by_hash_prefix lookup by the 16-char dashboard id
  - get_bookmarked_article_ids
  - New articles default to bookmarked = 0
"""
import sqlite3
import sys
import tempfile
import unittest
from pathlib import Path

BASE = Path(__file__).parent.parent
sys.path.insert(0, str(BASE))

import database


class TestBookmarkedColumn(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.tmp_path = Path(self.tmp.name)
        self.original_db_path = database.DB_PATH
        database.DB_PATH = self.tmp_path / "news.db"

    def tearDown(self):
        database.DB_PATH = self.original_db_path
        self.tmp.cleanup()

    def _article(self, url: str, title: str = "Test Article") -> dict:
        return {
            "title": title,
            "url": url,
            "summary": "Test summary",
            "source": "test",
            "category": "Test",
            "subcategory": "news",
            "published": "2024-01-01T00:00:00",
        }

    def test_init_db_creates_bookmarked_column(self):
        database.init_db()
        conn = sqlite3.connect(str(database.DB_PATH))
        cols = [r[1] for r in conn.execute("PRAGMA table_info(articles)").fetchall()]
        conn.close()
        self.assertIn("bookmarked", cols)

    def test_migration_adds_bookmarked_column_to_old_db(self):
        """init_db() must ALTER TABLE to add bookmarked on a DB that pre-dates the column."""
        conn = sqlite3.connect(str(database.DB_PATH))
        conn.executescript("""
            CREATE TABLE articles (
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
                embedding BLOB,
                created_at TEXT DEFAULT (datetime('now'))
            );
            CREATE TABLE dedup_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                content_hash TEXT NOT NULL,
                title TEXT NOT NULL,
                similar_to_id INTEGER,
                similarity_score REAL DEFAULT 0.0,
                method TEXT DEFAULT 'url',
                created_at TEXT DEFAULT (datetime('now'))
            );
        """)
        conn.commit()
        cols_before = [r[1] for r in conn.execute("PRAGMA table_info(articles)").fetchall()]
        self.assertNotIn("bookmarked", cols_before)
        conn.close()

        database.init_db()

        conn = sqlite3.connect(str(database.DB_PATH))
        cols_after = [r[1] for r in conn.execute("PRAGMA table_info(articles)").fetchall()]
        conn.close()
        self.assertIn("bookmarked", cols_after)

    def test_set_bookmarked_round_trip(self):
        database.init_db()
        _, article_id = database.store_article(self._article("http://example.com/round-trip"))
        self.assertFalse(database.is_bookmarked(article_id))

        database.set_bookmarked(article_id, True)
        self.assertTrue(database.is_bookmarked(article_id))

        database.set_bookmarked(article_id, False)
        self.assertFalse(database.is_bookmarked(article_id))

    def test_set_bookmarked_unknown_id_is_noop(self):
        database.init_db()
        database.set_bookmarked(999999, True)
        self.assertFalse(database.is_bookmarked(999999))

    def test_set_bookmarked_by_hash_prefix_matches_article(self):
        database.init_db()
        article = self._article("http://example.com/prefix")
        _, article_id = database.store_article(article)
        prefix = database.compute_hash(article)[:16]

        result = database.set_bookmarked_by_hash_prefix(prefix, True)
        self.assertTrue(result)
        self.assertTrue(database.is_bookmarked(article_id))

    def test_set_bookmarked_by_hash_prefix_unknown_returns_false(self):
        database.init_db()
        result = database.set_bookmarked_by_hash_prefix("deadbeefdeadbeef", True)
        self.assertFalse(result)

    def test_get_bookmarked_article_ids(self):
        database.init_db()
        _, id1 = database.store_article(self._article("http://example.com/a"))
        _, id2 = database.store_article(self._article("http://example.com/b"))
        _, id3 = database.store_article(self._article("http://example.com/c"))

        database.set_bookmarked(id1, True)
        database.set_bookmarked(id3, True)
        self.assertEqual(database.get_bookmarked_article_ids(), sorted([id1, id3]))

        database.set_bookmarked(id1, False)
        self.assertEqual(database.get_bookmarked_article_ids(), [id3])

    def test_new_articles_default_to_not_bookmarked(self):
        database.init_db()
        _, article_id = database.store_article(self._article("http://example.com/default"))
        self.assertFalse(database.is_bookmarked(article_id))


if __name__ == "__main__":
    unittest.main()
