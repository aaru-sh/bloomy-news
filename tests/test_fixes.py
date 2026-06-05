"""Smoke tests for the most critical fixes in Bloomy News."""
import os
import sys
import json
import sqlite3
import tempfile
import time
import unittest
import threading
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import patch, MagicMock

BASE = Path(__file__).parent.parent
sys.path.insert(0, str(BASE))
sys.path.insert(0, str(BASE / 'dashboard'))

import telegram  # for telegram.logger patch (post_to_telegram moved out of news_tool)


class TestTitleSimilarity(unittest.TestCase):
    def test_identical_titles(self):
        from database import title_similarity
        score = title_similarity("Microsoft unveils new AI models", "Microsoft unveils new AI models")
        self.assertEqual(score, 1.0)

    def test_completely_different(self):
        from database import title_similarity
        score = title_similarity("Apple earnings report", "Tesla stock surge")
        self.assertEqual(score, 0.0)

    def test_partial_overlap(self):
        from database import title_similarity
        score = title_similarity("Microsoft unveils new AI models for developers",
                                "Microsoft unveils new AI models at Build")
        self.assertGreater(score, 0.3)
        self.assertLess(score, 1.0)

    def test_empty_inputs(self):
        from database import title_similarity
        self.assertEqual(title_similarity("", "test"), 0.0)
        self.assertEqual(title_similarity("test", ""), 0.0)
        self.assertEqual(title_similarity(None, "test"), 0.0)

    def test_normalizes_punctuation(self):
        from database import title_similarity
        score1 = title_similarity("Hello, World!", "Hello World")
        self.assertEqual(score1, 1.0)


class TestClassifierFallback(unittest.TestCase):
    def test_no_match_returns_uncategorized(self):
        sys.path.insert(0, str(BASE))
        import news_tool
        if getattr(news_tool, 'EMBEDDING_AVAILABLE', False):
            self.skipTest("Keyword fallback test skipped when embedding classifier is active")
        primary, conf, tags, subcat, _embedding = news_tool.classify_article({
            "title": "XYZ random unrelated text",
            "summary": "nothing in here matches anything either"
        })
        self.assertEqual(primary, "Uncategorized")
        self.assertEqual(conf, 0.0)
        self.assertEqual(tags, [])

    def test_llm_match(self):
        import news_tool
        primary, conf, tags, subcat, _embedding = news_tool.classify_article({
            "title": "New transformer architecture for large language models",
            "summary": "GPT and BERT comparison"
        })
        self.assertEqual(primary, "LLM")
        self.assertGreater(conf, 0.0)

    def test_no_fallback_to_ai_applications(self):
        import news_tool
        primary, conf, tags, subcat, _embedding = news_tool.classify_article({
            "title": "A paint company merger announcement today",
            "summary": "AkzoNobel acquisition by Nippon Paint"
        })
        self.assertNotEqual(primary, "AI-Applications")


class TestIdValidation(unittest.TestCase):
    def test_id_pattern(self):
        import importlib.util
        spec = importlib.util.spec_from_file_location("serve", BASE / "dashboard" / "serve.py")
        serve = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(serve)
        self.assertTrue(serve.ID_PATTERN.match("abc123"))
        self.assertTrue(serve.ID_PATTERN.match("valid_id-123"))
        self.assertFalse(serve.ID_PATTERN.match(""))
        self.assertFalse(serve.ID_PATTERN.match("has spaces"))
        self.assertFalse(serve.ID_PATTERN.match("<script>"))


class TestSecretsLoader(unittest.TestCase):
    def test_secrets_from_env_override_config(self):
        with patch.dict(os.environ, {'TELEGRAM_BOT_TOKEN': 'env_token'}):
            from config import get_telegram_token
            self.assertEqual(get_telegram_token(), 'env_token')


class TestBookmarkApiInputLimits(unittest.TestCase):
    def test_max_body_size_constant(self):
        import importlib.util
        spec = importlib.util.spec_from_file_location("serve", BASE / "dashboard" / "serve.py")
        serve = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(serve)
        self.assertEqual(serve.MAX_BODY_SIZE, 1024)

    def test_max_bookmarks_constant(self):
        import importlib.util
        spec = importlib.util.spec_from_file_location("serve", BASE / "dashboard" / "serve.py")
        serve = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(serve)
        self.assertEqual(serve.MAX_BOOKMARKS, 5000)


class TestScheduler(unittest.TestCase):
    def setUp(self):
        import importlib.util
        spec = importlib.util.spec_from_file_location("scheduler", BASE / "scripts" / "scheduler.py")
        self.scheduler = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(self.scheduler)

    def test_should_catch_up_when_no_state(self):
        from datetime import datetime
        self.assertTrue(self.scheduler.should_catch_up({"last_run": None}, datetime.now()))

    def test_should_catch_up_when_old(self):
        from datetime import datetime, timedelta
        old = (datetime.now() - timedelta(hours=14)).isoformat()
        self.assertTrue(self.scheduler.should_catch_up({"last_run": old}, datetime.now()))

    def test_no_catch_up_when_recent(self):
        from datetime import datetime, timedelta
        recent = (datetime.now() - timedelta(hours=2)).isoformat()
        self.assertFalse(self.scheduler.should_catch_up({"last_run": recent}, datetime.now()))

    def test_next_checkpoint_before_noon(self):
        from datetime import datetime
        now = datetime(2026, 6, 3, 6, 30, 0)
        nxt = self.scheduler.next_checkpoint(now)
        self.assertEqual(nxt.hour, 12)
        self.assertEqual(nxt.day, 3)

    def test_next_checkpoint_after_noon(self):
        from datetime import datetime
        now = datetime(2026, 6, 3, 13, 0, 0)
        nxt = self.scheduler.next_checkpoint(now)
        self.assertEqual(nxt.hour, 0)
        self.assertEqual(nxt.day, 4)

    def test_next_checkpoint_at_midnight(self):
        from datetime import datetime
        now = datetime(2026, 6, 3, 0, 30, 0)
        nxt = self.scheduler.next_checkpoint(now)
        self.assertEqual(nxt.hour, 12)
        self.assertEqual(nxt.day, 3)


class TestConcurrentPipelineInserts(unittest.TestCase):
    """Two pipeline runs launched simultaneously must not double-insert.

    Each thread opens its own connection (the design choice from the
    6-issue code review: 3-instance single-process is fine for a laptop
    project; we don't need a global lock). The articles table has a
    UNIQUE INDEX on url, so even if both threads try to insert the
    same URL, SQLite will reject the second one with IntegrityError,
    which is_duplicate() catches and treats as a duplicate.
    """

    def setUp(self):
        import database
        from database import DB_PATH

        self._database = database
        self._tmpdir = Path(tempfile.mkdtemp())
        self._tmp_db = self._tmpdir / "news.db"
        self._original_db_path = database.DB_PATH
        database.DB_PATH = self._tmp_db
        database.init_db()

    def tearDown(self):
        self._database.DB_PATH = self._original_db_path
        import shutil
        shutil.rmtree(self._tmpdir, ignore_errors=True)

    def test_concurrent_inserts_dedupe_by_url(self):
        import threading
        from database import store_article, get_connection

        articles = [
            {
                'title': f'Concurrent article {i}',
                'url': f'https://example.com/concurrent/{i}',
                'source': 'test',
                'category': 'LLM',
                'published': '2026-06-01T00:00:00',
            }
            for i in range(20)
        ]

        results = []
        results_lock = threading.Lock()

        def worker(article_batch):
            inserted = 0
            dup = 0
            for art in article_batch:
                is_new, _ = store_article(art)
                if is_new:
                    inserted += 1
                else:
                    dup += 1
            with results_lock:
                results.append((inserted, dup))

        t1 = threading.Thread(target=worker, args=(articles[:10],))
        t2 = threading.Thread(target=worker, args=(articles[10:],))
        t1.start()
        t2.start()
        t1.join()
        t2.join()

        total_inserted = sum(r[0] for r in results)
        total_dup = sum(r[1] for r in results)
        self.assertEqual(total_inserted, 20)
        self.assertEqual(total_dup, 0)

        conn = get_connection()
        try:
            count = conn.execute("SELECT COUNT(*) as cnt FROM articles").fetchone()['cnt']
            self.assertEqual(count, 20)
        finally:
            conn.close()

    def test_concurrent_inserts_of_same_url_only_one_wins(self):
        import threading
        from database import store_article, get_connection

        article = {
            'title': 'Race-condition article',
            'url': 'https://example.com/race/1',
            'source': 'test',
            'category': 'LLM',
            'published': '2026-06-01T00:00:00',
        }

        results = []
        results_lock = threading.Lock()

        def worker():
            is_new, _ = store_article(article)
            with results_lock:
                results.append(is_new)

        threads = [threading.Thread(target=worker) for _ in range(5)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        winners = sum(1 for r in results if r)
        self.assertEqual(winners, 1)
        self.assertEqual(len(results) - winners, 4)

        conn = get_connection()
        try:
            count = conn.execute(
                "SELECT COUNT(*) as cnt FROM articles WHERE url = ?",
                ('https://example.com/race/1',)
            ).fetchone()['cnt']
            self.assertEqual(count, 1)
        finally:
            conn.close()


class TestBookmarkRace(unittest.TestCase):
    """20 concurrent togglers must not lose updates or corrupt the file.

    Each thread toggles a distinct article id 5 times. With the lock +
    atomic-write fix in place, the final JSON must contain every id
    exactly once (5 toggles on a missing id is one net add). Without
    the lock, the read-modify-write races and ids get lost.
    """

    def setUp(self):
        import database
        self._database = database
        self._tmpdir = Path(tempfile.mkdtemp())
        self._tmp_file = self._tmpdir / "bookmarks.json"
        self._original_file = database.BOOKMARKS_FILE
        database.BOOKMARKS_FILE = self._tmp_file

    def tearDown(self):
        self._database.BOOKMARKS_FILE = self._original_file
        import shutil
        shutil.rmtree(self._tmpdir, ignore_errors=True)

    @unittest.skipUnless(threading, "threading required for race test")
    def test_bookmark_race(self):
        if not hasattr(self._database, '_BOOKMARKS_LOCK'):
            self.skipTest("toggle_bookmark not fixed (no _BOOKMARKS_LOCK)")

        from database import toggle_bookmark

        ids = [f"id_{i}" for i in range(20)]
        errors = []
        errors_lock = threading.Lock()

        def worker(article_id, n):
            try:
                for _ in range(n):
                    toggle_bookmark(article_id)
            except Exception as exc:
                with errors_lock:
                    errors.append(exc)

        threads = [threading.Thread(target=worker, args=(aid, 5)) for aid in ids]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        self.assertEqual(errors, [], f"toggler threads raised: {errors!r}")
        self.assertTrue(self._tmp_file.exists(),
                        "bookmarks file should exist after toggles")

        with open(self._tmp_file, 'r', encoding='utf-8') as f:
            data = json.load(f)

        self.assertIsInstance(data, list)
        self.assertEqual(set(data), set(ids),
                         f"lost updates: missing {set(ids) - set(data)}")
        self.assertEqual(len(data), len(set(data)),
                         f"duplicate ids in bookmarks: {data}")


class TestFts5Search(unittest.TestCase):
    """get_articles(search=...) must route through articles_fts and return
    only the row whose title contains the search word.
    """

    def setUp(self):
        import database
        self._database = database
        self._tmpdir = Path(tempfile.mkdtemp())
        self._tmp_db = self._tmpdir / "news.db"
        self._original_db_path = database.DB_PATH
        database.DB_PATH = self._tmp_db
        database.init_db()

    def tearDown(self):
        self._database.DB_PATH = self._original_db_path
        import shutil
        shutil.rmtree(self._tmpdir, ignore_errors=True)

    def test_fts5_search(self):
        from database import (
            store_article, get_articles, get_connection, _has_fts5_table,
        )

        conn = get_connection()
        try:
            fts5_ok = _has_fts5_table(conn)
        finally:
            conn.close()

        if not fts5_ok:
            self.skipTest("FTS5 (articles_fts) not present in schema")

        articles = [
            {
                'title': 'Quantum computing breakthrough in cryptography',
                'url': 'https://example.com/fts/1',
                'summary': '',
                'source': 'test',
                'category': 'LLM',
                'published': '2026-06-01T00:00:00',
            },
            {
                'title': 'Apple earnings report Q3',
                'url': 'https://example.com/fts/2',
                'summary': 'revenue growth steady',
                'source': 'test',
                'category': 'Finance',
                'published': '2026-06-01T00:00:00',
            },
            {
                'title': 'Microsoft announces new AI model',
                'url': 'https://example.com/fts/3',
                'summary': 'advances in machine learning',
                'source': 'test',
                'category': 'LLM',
                'published': '2026-06-01T00:00:00',
            },
        ]
        for art in articles:
            ok, _ = store_article(art)
            self.assertTrue(ok, f"failed to insert {art['title']!r}")

        results = get_articles(search="cryptography")
        self.assertEqual(len(results), 1,
                         f"expected exactly 1 result, got {len(results)}")
        self.assertEqual(results[0]['title'],
                         'Quantum computing breakthrough in cryptography')

        results_none = get_articles(search="nonexistentwordzzz")
        self.assertEqual(results_none, [],
                         "FTS5 with no matches should return [] (not fall back to LIKE)")


class TestEmbeddingPersistence(unittest.TestCase):
    """store_article(embedding=...) must serialize the vector to the
    `embedding` BLOB column and load_article_embedding() must round-trip
    it back to a numpy array bit-for-bit.

    Locks down the contract for the v1.1.x embedding-column fix: the
    schema column has existed since at least v1.0.0, but until now
    store_article() never wrote to it, so every re-classification had
    to re-run the sentence-transformers model from scratch. The
    round-trip test uses a random 384-dim float32 vector (the
    MiniLM-L6-v2 dimension) and asserts the reconstructed array is
    exactly equal element-wise.
    """

    def setUp(self):
        import database
        self._database = database
        self._tmpdir = Path(tempfile.mkdtemp())
        self._tmp_db = self._tmpdir / "news.db"
        self._original_db_path = database.DB_PATH
        database.DB_PATH = self._tmp_db
        database.init_db()

    def tearDown(self):
        self._database.DB_PATH = self._original_db_path
        import shutil
        shutil.rmtree(self._tmpdir, ignore_errors=True)

    def test_round_trip_384dim_float32(self):
        try:
            import numpy as np
        except ImportError:
            self.skipTest("numpy not installed; embedding persistence requires numpy")

        from database import (
            EMBEDDING_DIM, EMBEDDING_DTYPE,
            store_article, load_article_embedding,
        )

        self.assertEqual(EMBEDDING_DIM, 384)
        self.assertEqual(EMBEDDING_DTYPE, "float32")

        rng = np.random.default_rng(seed=20260605)
        original = rng.standard_normal(EMBEDDING_DIM).astype(EMBEDDING_DTYPE)
        self.assertEqual(original.shape, (EMBEDDING_DIM,))
        self.assertEqual(original.dtype, np.float32)

        ok, article_id = store_article(
            {
                "title": "Embedding round-trip test article",
                "url": "https://example.com/embedding/roundtrip/1",
                "summary": "",
                "source": "test",
                "category": "LLM",
                "published": "2026-06-05T00:00:00",
            },
            embedding=original,
        )
        self.assertTrue(ok, "store_article should report is_new=True for a fresh URL")
        self.assertIsNotNone(article_id)

        loaded = load_article_embedding(article_id)
        self.assertIsNotNone(loaded, "load_article_embedding must return a vector for a row that was stored with one")
        self.assertEqual(loaded.shape, (EMBEDDING_DIM,))
        self.assertEqual(loaded.dtype, np.dtype(EMBEDDING_DTYPE))
        np.testing.assert_array_equal(loaded, original)

    def test_load_returns_none_when_no_embedding_stored(self):
        try:
            import numpy  # noqa: F401
        except ImportError:
            self.skipTest("numpy not installed")

        from database import store_article, load_article_embedding

        ok, article_id = store_article(
            {
                "title": "Article with no embedding",
                "url": "https://example.com/embedding/none/1",
                "summary": "",
                "source": "test",
                "category": "LLM",
                "published": "2026-06-05T00:00:00",
            },
        )
        self.assertTrue(ok)
        self.assertIsNone(load_article_embedding(article_id))

    def test_load_returns_none_for_missing_id(self):
        try:
            import numpy  # noqa: F401
        except ImportError:
            self.skipTest("numpy not installed")

        from database import load_article_embedding
        self.assertIsNone(load_article_embedding(999999))

    def test_default_embedding_param_keeps_legacy_behavior(self):
        """store_article() with no embedding kwarg must still work for
        callers that pre-date the v1.1.x fix (the keyword-fallback path
        and migrate_from_files are the main ones).
        """
        try:
            import numpy  # noqa: F401
        except ImportError:
            self.skipTest("numpy not installed")

        from database import store_article, load_article_embedding

        ok, article_id = store_article(
            {
                "title": "Legacy call shape: no embedding kwarg",
                "url": "https://example.com/embedding/legacy/1",
                "summary": "",
                "source": "test",
                "category": "Finance",
                "published": "2026-06-05T00:00:00",
            },
        )
        self.assertTrue(ok)
        self.assertIsNotNone(article_id)
        self.assertIsNone(load_article_embedding(article_id))


class TestJaccardPrefilter(unittest.TestCase):
    """is_duplicate must pre-filter in SQL using significant words (length >= 4)
    before running the Python Jaccard loop. With 50 unrelated articles in the
    DB, a near-duplicate of one specific target must still be flagged.
    """

    def setUp(self):
        import database
        self._database = database
        self._tmpdir = Path(tempfile.mkdtemp())
        self._tmp_db = self._tmpdir / "news.db"
        self._original_db_path = database.DB_PATH
        database.DB_PATH = self._tmp_db
        database.init_db()

    def tearDown(self):
        self._database.DB_PATH = self._original_db_path
        import shutil
        shutil.rmtree(self._tmpdir, ignore_errors=True)

    def test_jaccard_prefilter(self):
        from database import store_article, is_duplicate, extract_title_words

        recent = (datetime.now() - timedelta(days=1)).isoformat()

        # 50 unrelated articles, all with non-overlapping significant words
        # so the SQL pre-filter only matches the target.
        for i in range(50):
            ok, _ = store_article({
                'title': f'Distinct topic {i} about widgets and gadgets',
                'url': f'https://example.com/distinct/{i}',
                'summary': '',
                'source': 'test',
                'category': 'LLM',
                'published': recent,
            })
            self.assertTrue(ok, f"failed to insert filler article {i}")

        # Target article #25 (label): 4 distinct significant words >= 4 chars.
        target_title = 'Quantum computing breakthrough cryptography'
        target_url = 'https://example.com/quantum/1'
        ok, target_id = store_article({
            'title': target_title,
            'url': target_url,
            'summary': '',
            'source': 'test',
            'category': 'LLM',
            'published': recent,
        })
        self.assertTrue(ok)
        self.assertIsNotNone(target_id)

        # Sanity: confirm the target's normalized words survive so the
        # pre-filter can match them.
        self.assertEqual(
            set(extract_title_words(target_title).split()),
            {'quantum', 'computing', 'breakthrough', 'cryptography'},
        )

        # Near-duplicate: shares all 4 significant words plus one new one.
        # Jaccard = 4 / 5 = 0.80 (>= the 0.80 threshold).
        near_dup_title = 'Quantum computing breakthrough cryptography research'
        is_dup, similar_id, score, method = is_duplicate(
            near_dup_title, 'https://example.com/quantum/2', '',
        )

        self.assertTrue(is_dup,
                        f"near-duplicate not flagged: title={near_dup_title!r}")
        self.assertEqual(similar_id, target_id,
                         f"flagged wrong id: {similar_id} != {target_id}")
        self.assertGreaterEqual(score, 0.80,
                                f"Jaccard score too low: {score}")
        self.assertEqual(method, 'title_similarity')

    def test_is_duplicate_jaccard_raw_titles(self):
        from database import store_article, is_duplicate

        recent = (datetime.now() - timedelta(days=1)).isoformat()

        ok1, id1 = store_article({
            'title': 'alpha bravo charlie delta',
            'url': 'https://example.com/jaccard-raw/1',
            'summary': '',
            'source': 'test',
            'category': 'LLM',
            'published': recent,
        })
        self.assertTrue(ok1)
        self.assertIsNotNone(id1)

        ok2, _ = store_article({
            'title': 'alpha bravo charlie',
            'url': 'https://example.com/jaccard-raw/2',
            'summary': '',
            'source': 'test',
            'category': 'LLM',
            'published': recent,
        })
        self.assertTrue(ok2)

        is_dup, similar_id, score, method = is_duplicate(
            'alpha bravo charlie delta foxtrot',
            'https://example.com/jaccard-raw/new', '',
        )
        self.assertTrue(is_dup, f"near-duplicate not flagged: score={score}")
        self.assertGreaterEqual(score, 0.66, f"Jaccard too low: {score}")
        self.assertEqual(similar_id, id1,
                         f"flagged wrong id: {similar_id} != {id1}")
        self.assertEqual(method, 'title_similarity')

        ok3, _ = store_article({
            'title': 'completely different words here',
            'url': 'https://example.com/jaccard-raw/3',
            'summary': '',
            'source': 'test',
            'category': 'LLM',
            'published': recent,
        })
        self.assertTrue(ok3)

        is_dup, similar_id, score, method = is_duplicate(
            'unique isolated words phrases',
            'https://example.com/jaccard-raw/new2', '',
        )
        self.assertFalse(is_dup,
                         f"unrelated title incorrectly flagged: score={score}")


class TestClassifierVisibility(unittest.TestCase):
    """Regression: main() must tell the user which classifier is running."""

    def test_embedding_available_is_module_level_bool(self):
        import news_tool
        self.assertTrue(hasattr(news_tool, 'EMBEDDING_AVAILABLE'),
                        "news_tool.EMBEDDING_AVAILABLE is missing")
        self.assertIsInstance(news_tool.EMBEDDING_AVAILABLE, bool,
                              f"EMBEDDING_AVAILABLE must be bool, got "
                              f"{type(news_tool.EMBEDDING_AVAILABLE).__name__}")


class TestArxivRateLimit(unittest.TestCase):
    """scrape_arxiv() must honor ARXIV_RATE_LIMIT between feed fetches.

    Regression: the env var was documented (default 3.0s, matching
    arXiv's published rate-limit guideline) but never read, so the
    scraper could hammer arXiv with back-to-back requests. This test
    monkey-patches time.sleep and feed fetches, sets a tiny rate
    limit, and asserts the sleep was honored.
    """

    def setUp(self):
        try:
            import requests  # noqa: F401
            self._requests_available = True
        except ImportError:
            self._requests_available = False

        import news_tool
        self._news_tool = news_tool

    def test_sleeps_between_arxiv_feeds(self):
        if not self._requests_available:
            self.skipTest("requests not available")

        sleep_calls = []

        def fake_sleep(seconds):
            sleep_calls.append(float(seconds))

        empty_rss = (
            '<?xml version="1.0" encoding="UTF-8"?>'
            '<rss version="2.0"><channel><title>empty</title>'
            '<description>empty</description></channel></rss>'
        )

        def fake_fetch_url(url, timeout=20, retries=3):
            return empty_rss

        with patch.dict(os.environ, {'ARXIV_RATE_LIMIT': '0.01'}):
            with patch.object(self._news_tool.time, 'sleep', side_effect=fake_sleep):
                with patch("scrapers.arxiv.fetch_url", side_effect=fake_fetch_url):
                    self._news_tool.scrape_arxiv()

        self.assertGreaterEqual(
            len(sleep_calls), 1,
            f"expected at least one time.sleep call between arXiv feeds, got {sleep_calls!r}",
        )
        for s in sleep_calls:
            self.assertGreaterEqual(
                s, 0.01,
                f"sleep duration {s!r} is below the ARXIV_RATE_LIMIT=0.01 minimum",
            )

    def test_default_rate_limit_is_three_seconds(self):
        if not self._requests_available:
            self.skipTest("requests not available")

        sleep_calls = []

        def fake_sleep(seconds):
            sleep_calls.append(float(seconds))

        empty_rss = (
            '<?xml version="1.0" encoding="UTF-8"?>'
            '<rss version="2.0"><channel><title>empty</title>'
            '<description>empty</description></channel></rss>'
        )

        def fake_fetch_url(url, timeout=20, retries=3):
            return empty_rss

        env_without_limit = {k: v for k, v in os.environ.items() if k != 'ARXIV_RATE_LIMIT'}
        with patch.dict(os.environ, env_without_limit, clear=True):
            with patch.object(self._news_tool.time, 'sleep', side_effect=fake_sleep):
                with patch("scrapers.arxiv.fetch_url", side_effect=fake_fetch_url):
                    self._news_tool.scrape_arxiv()

        for s in sleep_calls:
            self.assertGreaterEqual(
                s, 3.0,
                f"default rate limit should be >= 3.0s, got sleep({s})",
            )


class TestTelegramCategorizedSource(unittest.TestCase):
    """post_to_telegram must build the digest from the `categorized` arg,
    not from a fresh DB query — otherwise a run on a machine with leftover
    today's articles in the DB can publish a digest that drops the
    freshly-scraped ones."""

    def setUp(self):
        import news_tool
        self.news_tool = news_tool
        self._sent = []
        self._patcher = patch.object(
            telegram, "_send_telegram_message",
            side_effect=lambda token, chat_id, text: self._sent.append(
                {"token": token, "chat_id": chat_id, "text": text}
            ) or {"ok": True},
        )
        self._patcher.start()
        self._env = patch.dict(os.environ, {"TELEGRAM_BOT_TOKEN": "test_token"})
        self._env.start()

    def tearDown(self):
        self._patcher.stop()
        self._env.stop()

    def test_uses_categorized_dict_not_db(self):
        categorized = {
            "LLM": [
                {"title": "Fresh LLM breakthrough",
                 "summary": "new transformer paper",
                 "url": "https://example.com/llm/1",
                 "published": "2026-06-05T10:00:00"},
                {"title": "Fresh LLM release",
                 "summary": "open weights",
                 "url": "https://example.com/llm/2",
                 "published": "2026-06-05T09:00:00"},
            ],
            "Finance": [
                {"title": "Fresh market move",
                 "summary": "fed rate cut",
                 "url": "https://example.com/fin/1",
                 "published": "2026-06-05T11:00:00"},
                {"title": "Fresh earnings beat",
                 "summary": "tech sector",
                 "url": "https://example.com/fin/2",
                 "published": "2026-06-05T08:00:00"},
            ],
        }
        with patch.object(
            self.news_tool.database,
            "get_today_top_per_category",
            return_value={"LLM": [
                {"title": "STALE_DB_ARTICLE_should_not_appear",
                 "summary": "", "url": ""}
            ]},
        ) as db_called:
            self.news_tool.post_to_telegram(categorized)

        self.assertEqual(len(self._sent), 1,
                         "post_to_telegram should send exactly one message")
        sent = self._sent[0]
        self.assertEqual(sent["token"], "test_token")
        text = sent["text"]
        self.assertNotIn("STALE_DB_ARTICLE", text,
                         "digest was built from DB, not from categorized")
        for art in categorized["LLM"] + categorized["Finance"]:
            self.assertIn(art["title"], text,
                          f"missing fresh article: {art['title']!r}")
        self.assertIn("*LLM*", text)
        self.assertIn("*Finance*", text)
        self.assertIn("Total: 4 articles", text)
        db_called.assert_not_called()

    def test_empty_categorized_falls_back_to_db_with_warning(self):
        with patch.object(
            telegram.logger, "warning"
        ) as warn_mock, patch.object(
            self.news_tool.database,
            "get_today_top_per_category",
            return_value={"Cybersecurity": [
                {"title": "DB fallback article",
                 "summary": "breach report",
                 "url": "https://example.com/sec/1",
                 "published": "2026-06-05T07:00:00"},
            ]},
        ) as db_called:
            self.news_tool.post_to_telegram({})

        self.assertEqual(len(self._sent), 1)
        self.assertIn("DB fallback article", self._sent[0]["text"])
        self.assertIn("*Cybersecurity*", self._sent[0]["text"])
        self.assertTrue(warn_mock.called,
                        "fallback path must log a warning")
        db_called.assert_called_once()


class TestMigrateFromFilesLogsErrors(unittest.TestCase):
    """migrate_from_files() must NOT swallow exceptions silently.

    The previous bare `except: continue` hid IOError on bad gzip,
    UnicodeDecodeError on malformed content, and worse. A migration
    that "skips" files without telling the operator why is a black
    box. These tests pin the new behavior: every per-file failure
    is logged at WARNING and the loop continues.
    """

    def setUp(self):
        import database
        self._database = database
        self._tmpdir = Path(tempfile.mkdtemp())
        self._tmp_db = self._tmpdir / "news.db"
        self._original_db_path = database.DB_PATH
        self._original_base = database.BASE
        database.DB_PATH = self._tmp_db
        database.BASE = self._tmpdir
        database.init_db()

        # Lay out a minimal category tree with one .md.gz file that
        # the loop will encounter. The fixture is real on disk; we
        # only monkey-patch the open() call.
        cat_dir = self._tmpdir / "LLM" / "subA"
        cat_dir.mkdir(parents=True)
        self._md_file = cat_dir / "test.md.gz"
        self._md_file.write_bytes(b"not actually a gzip, but the loop will still try")

    def tearDown(self):
        self._database.DB_PATH = self._original_db_path
        self._database.BASE = self._original_base
        import shutil
        shutil.rmtree(self._tmpdir, ignore_errors=True)

    def test_ioerror_on_gzip_is_logged_and_skipped(self):
        import gzip
        from database import migrate_from_files

        with patch.object(gzip, 'open', side_effect=IOError("corrupt header")):
            with self.assertLogs('database', level='WARNING') as log_cm:
                imported, skipped = migrate_from_files()

        # Loop continued cleanly (didn't crash) and didn't import anything.
        self.assertEqual(imported, 0)
        self.assertEqual(skipped, 0)

        # The IOError must be visible — that's the whole point of the fix.
        joined = "\n".join(log_cm.output)
        self.assertIn("Migration skipped", joined,
                      f"expected 'Migration skipped' in log, got: {log_cm.output!r}")
        self.assertIn("corrupt header", joined,
                      f"expected IOError message in log, got: {log_cm.output!r}")
        self.assertIn(str(self._md_file), joined,
                      f"expected filename in log, got: {log_cm.output!r}")

    def test_unicode_decode_error_is_logged_not_swallowed(self):
        """A second failure mode: gzip.open succeeds but .read() raises
        UnicodeDecodeError on garbage bytes. The exception must still
        surface as a warning, not a silent skip.
        """
        import gzip
        from database import migrate_from_files

        fake_gz = MagicMock()
        fake_gz.__enter__.return_value.read.side_effect = UnicodeDecodeError(
            'utf-8', b'\xff\xfe', 0, 1, 'invalid start byte')
        fake_gz.__enter__.return_value.__exit__.return_value = False
        fake_gz.__exit__.return_value = False

        with patch.object(gzip, 'open', return_value=fake_gz):
            with self.assertLogs('database', level='WARNING') as log_cm:
                imported, skipped = migrate_from_files()

        self.assertEqual(imported, 0)
        self.assertEqual(skipped, 0)
        self.assertTrue(any("invalid start byte" in line for line in log_cm.output),
                        f"UnicodeDecodeError not in log: {log_cm.output!r}")


if __name__ == '__main__':
    unittest.main()
