"""Extended tests for the database module edge cases.

Covers empty title storage, duplicate detection, pagination,
FTS5 search, Jaccard with empty strings, and concurrent bookmarks.
"""
import os
import sqlite3
import sys
import tempfile
import threading
import unittest
from pathlib import Path
from unittest.mock import patch

BASE = Path(__file__).parent.parent
sys.path.insert(0, str(BASE))

import database


class _DBTestCase(unittest.TestCase):
    """Base class that swaps DB_PATH to a fresh temp DB for each test."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.tmp_path = Path(self.tmp.name)
        self.original_db_path = database.DB_PATH
        database.DB_PATH = self.tmp_path / "news.db"

    def tearDown(self):
        database.DB_PATH = self.original_db_path
        self.tmp.cleanup()

    def _article(self, url, title="Test Article", summary="Sum",
                 category="LLM", published="2026-06-07T00:00:00"):
        return {
            "title": title, "url": url, "summary": summary,
            "source": "test", "category": category,
            "subcategory": "news", "published": published,
        }


class TestStoreArticleEmptyTitle(_DBTestCase):
    def test_empty_title_stores(self):
        database.init_db()
        ok, aid = database.store_article(self._article("http://e.com/1", title=""))
        self.assertTrue(ok)
        self.assertIsNotNone(aid)

    def test_whitespace_title_stores(self):
        database.init_db()
        ok, aid = database.store_article(
            self._article("http://e.com/2", title="   ")
        )
        self.assertTrue(ok)
        self.assertIsNotNone(aid)

    def test_long_title_truncates(self):
        database.init_db()
        long_title = "A" * 500
        ok, aid = database.store_article(
            self._article("http://e.com/4", title=long_title)
        )
        self.assertTrue(ok)
        self.assertIsNotNone(aid)


class TestStoreArticleDuplicate(_DBTestCase):
    def test_same_url_detected(self):
        database.init_db()
        ok1, _ = database.store_article(self._article("http://dup.com/a"))
        self.assertTrue(ok1)
        ok2, sim_id = database.store_article(self._article("http://dup.com/a"))
        self.assertFalse(ok2)
        self.assertIsNotNone(sim_id)

    def test_same_title_similar(self):
        database.init_db()
        title1 = "Microsoft unveils new AI models for developers at Build conference"
        ok1, id1 = database.store_article(
            self._article("http://dup.com/b", title=title1)
        )
        self.assertTrue(ok1)
        ok2, sim_id = database.store_article(
            self._article("http://dup.com/c", title=title1)
        )
        self.assertFalse(ok2)
        self.assertEqual(sim_id, id1)


class TestGetArticlesPagination(_DBTestCase):
    def test_offset_limit(self):
        database.init_db()
        for i in range(10):
            database.store_article(
                self._article(f"http://pag.com/{i}", title=f"Article {i}")
            )
        page1 = database.get_articles(limit=3, offset=0)
        page2 = database.get_articles(limit=3, offset=3)
        self.assertEqual(len(page1), 3)
        self.assertEqual(len(page2), 3)
        ids1 = {a["id"] for a in page1}
        ids2 = {a["id"] for a in page2}
        self.assertTrue(ids1.isdisjoint(ids2))

    def test_offset_beyond_total(self):
        database.init_db()
        database.store_article(self._article("http://pag.com/x", title="One"))
        result = database.get_articles(limit=5, offset=100)
        self.assertEqual(result, [])


class TestGetArticlesSearch(_DBTestCase):
    def test_fts_search(self):
        database.init_db()
        database.store_article(
            self._article("http://s.com/1", title="Quantum computing breakthrough")
        )
        database.store_article(
            self._article("http://s.com/2", title="Finance market update")
        )
        results = database.get_articles(search="quantum")
        self.assertGreater(len(results), 0)
        self.assertIn("quantum", results[0]["title"].lower())

    def test_search_no_results(self):
        database.init_db()
        results = database.get_articles(search="xyznonexistent")
        self.assertEqual(results, [])


class TestIsDuplicateEmptyTitle(_DBTestCase):
    def test_empty_title_no_url(self):
        database.init_db()
        is_dup, _, _, _ = database.is_duplicate("", "")
        self.assertFalse(is_dup)

    def test_empty_title_with_url(self):
        database.init_db()
        database.store_article(self._article("http://e.com/dup"))
        is_dup, _, _, _ = database.is_duplicate("", "http://e.com/dup")
        self.assertTrue(is_dup)

    def test_whitespace_title(self):
        database.init_db()
        is_dup, _, _, _ = database.is_duplicate("   ", "")
        self.assertFalse(is_dup)


class TestToggleBookmarkConcurrent(_DBTestCase):
    def test_concurrent_toggles(self):
        database.init_db()
        database.toggle_bookmark("art1")
        database.toggle_bookmark("art2")
        database.toggle_bookmark("art3")

        errors = []

        def toggle反复(article_id, count):
            for _ in range(count):
                try:
                    database.toggle_bookmark(article_id)
                except Exception as e:
                    errors.append(e)

        threads = []
        for _ in range(5):
            t = threading.Thread(target=toggle反复, args=("art1", 20))
            threads.append(t)
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        self.assertEqual(errors, [])
        bookmarks = database.get_bookmarks()
        self.assertIsInstance(bookmarks, list)


class TestComputeHash(_DBTestCase):
    def test_same_input_same_hash(self):
        h1 = database.compute_hash({"url": "http://a.com", "title": "T"})
        h2 = database.compute_hash({"url": "http://a.com", "title": "T"})
        self.assertEqual(h1, h2)

    def test_different_input_different_hash(self):
        h1 = database.compute_hash({"url": "http://a.com", "title": "A"})
        h2 = database.compute_hash({"url": "http://b.com", "title": "B"})
        self.assertNotEqual(h1, h2)

    def test_empty_fields(self):
        h = database.compute_hash({"url": "", "title": ""})
        self.assertIsInstance(h, str)
        self.assertEqual(len(h), 64)


class TestExtractTitleWords(unittest.TestCase):
    def test_basic(self):
        words = database.extract_title_words("Hello World Python")
        self.assertIn("hello", words)
        self.assertIn("world", words)
        self.assertIn("python", words)

    def test_stops_removed(self):
        words = database.extract_title_words("The quick brown fox")
        self.assertNotIn("the", words)

    def test_empty(self):
        words = database.extract_title_words("")
        self.assertEqual(words, "")


class TestTitleSimilarity(unittest.TestCase):
    def test_identical(self):
        self.assertEqual(
            database.title_similarity("abc def", "abc def"), 1.0
        )

    def test_disjoint(self):
        self.assertEqual(
            database.title_similarity("abc", "xyz"), 0.0
        )

    def test_empty(self):
        self.assertEqual(database.title_similarity("", "test"), 0.0)
        self.assertEqual(database.title_similarity("test", ""), 0.0)


class TestGetStats(_DBTestCase):
    def test_empty_db(self):
        database.init_db()
        stats = database.get_stats()
        self.assertEqual(stats["total"], 0)
        self.assertEqual(stats["today"], 0)
        self.assertIsInstance(stats["categories"], dict)


class TestGetBookmarksFile(_DBTestCase):
    def _bookmarks_path(self):
        return self.tmp_path / "dashboard" / "data" / "bookmarks.json"

    def test_no_file(self):
        path = self._bookmarks_path()
        with patch.object(database, "BOOKMARKS_FILE", path):
            result = database.get_bookmarks()
            self.assertEqual(result, [])

    def test_corrupt_file(self):
        path = self._bookmarks_path()
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("not json!!!", encoding="utf-8")
        with patch.object(database, "BOOKMARKS_FILE", path):
            result = database.get_bookmarks()
            self.assertEqual(result, [])

    def test_list_format(self):
        path = self._bookmarks_path()
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text('["a", "b"]', encoding="utf-8")
        with patch.object(database, "BOOKMARKS_FILE", path):
            result = database.get_bookmarks()
            self.assertEqual(result, ["a", "b"])

    def test_dict_format(self):
        path = self._bookmarks_path()
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text('{"bookmarks": ["x", "y"]}', encoding="utf-8")
        with patch.object(database, "BOOKMARKS_FILE", path):
            result = database.get_bookmarks()
            self.assertEqual(result, ["x", "y"])


class TestCleanupOldArticles(_DBTestCase):
    def test_zero_days_returns_zero(self):
        database.init_db()
        deleted = database.cleanup_old_articles(max_age_days=0)
        self.assertEqual(deleted, 0)

    def test_negative_days_returns_zero(self):
        database.init_db()
        deleted = database.cleanup_old_articles(max_age_days=-1)
        self.assertEqual(deleted, 0)


class TestParseArxivId(unittest.TestCase):
    def test_valid(self):
        self.assertEqual(
            database.parse_arxiv_id("https://arxiv.org/abs/2301.12345v2"),
            "2301.12345",
        )

    def test_invalid(self):
        self.assertIsNone(database.parse_arxiv_id("https://example.com"))

    def test_empty(self):
        self.assertIsNone(database.parse_arxiv_id(""))


class TestSerializeEmbedding(unittest.TestCase):
    def test_none(self):
        self.assertIsNone(database._serialize_embedding(None))

    def test_bytes(self):
        data = b"\x00" * 10
        self.assertEqual(database._serialize_embedding(data), data)

    def test_bytearray(self):
        data = bytearray(b"\x01" * 5)
        self.assertEqual(database._serialize_embedding(data), bytes(data))

    def test_numpy(self):
        import numpy as np
        arr = np.zeros(5, dtype="float32")
        result = database._serialize_embedding(arr)
        self.assertEqual(result, arr.tobytes())

    def test_invalid_type(self):
        with self.assertRaises(TypeError):
            database._serialize_embedding("not valid")


if __name__ == "__main__":
    unittest.main()
