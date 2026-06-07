"""Integration tests for the Bloomy News pipeline.

Tests the full scrape → classify → store → digest flow, dashboard
server endpoints, and scheduler logic using mocked HTTP and real
SQLite databases in temporary directories.
"""
import json
import os
import shutil
import sqlite3
import tempfile
import unittest
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import MagicMock, patch, PropertyMock

import database
from classifier import classify_article
from scrapers._http import Article, ArticleList


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

def _make_article(
    title: str,
    url: str = "https://example.com/article",
    summary: str = "Test summary",
    source: str = "TestSource",
    published: str = "2025-01-15T10:00:00",
    **extra,
) -> Article:
    """Build a minimal article dict for testing."""
    base = {
        "title": title,
        "url": url,
        "summary": summary,
        "source": source,
        "published": published,
        "author": "Test Author",
    }
    base.update(extra)
    return base


def _mock_http_response(body: str, status: int = 200):
    """Return a MagicMock that mimics urllib response."""
    resp = MagicMock()
    resp.read.return_value = body.encode("utf-8")
    resp.__enter__ = lambda s: s
    resp.__exit__ = MagicMock(return_value=False)
    resp.status = status
    resp.getcode.return_value = status
    return resp


def _fake_rss_xml(title: str = "Test Article", link: str = "https://example.com/art1",
                   desc: str = "Test summary", pub_date: str = "Mon, 15 Jan 2025 10:00:00 +0000") -> str:
    """Build a minimal RSS XML document."""
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0">
  <channel>
    <title>Test Feed</title>
    <item>
      <title>{title}</title>
      <link>{link}</link>
      <description>{desc}</description>
      <pubDate>{pub_date}</pubDate>
    </item>
  </channel>
</rss>"""


# ---------------------------------------------------------------------------
# Base class — sets up a temp DB for every test
# ---------------------------------------------------------------------------

class _IntegrationBase(unittest.TestCase):
    """Provide a fresh temp directory and a pointed-at-temp DB for each test."""

    def setUp(self):
        self._tmpdir = tempfile.mkdtemp(prefix="news_test_")
        self._orig_db_path = database.DB_PATH
        database.DB_PATH = Path(self._tmpdir) / "test_news.db"
        database.init_db()

    def tearDown(self):
        database.DB_PATH = self._orig_db_path
        shutil.rmtree(self._tmpdir, ignore_errors=True)


# ===================================================================
# 1. Full pipeline flow tests
# ===================================================================

class TestFullPipelineFlow(_IntegrationBase):
    """Tests 1-5: scrape → classify → store → digest with mocked HTTP."""

    @patch("scrapers._http.urllib.request.urlopen")
    def test_full_pipeline_scrape_to_store(self, mock_urlopen):
        """Mock HTTP, run classify → store, verify articles appear in DB."""
        articles = [
            _make_article(
                "Large language models achieve breakthrough reasoning",
                url="https://example.com/llm1",
                summary="GPT-5 shows 30% improvement on ARC benchmark",
                source="arXiv",
            ),
            _make_article(
                "Critical zero-day in OpenSSL allows remote code execution",
                url="https://example.com/cyber1",
                summary="CVE-2025-9999 affects OpenSSL 3.x series",
                source="BleepingComputer",
            ),
        ]

        conn = database.get_connection()
        try:
            for art in articles:
                cat, conf, tags, subcat, emb = classify_article(art)
                art["category"] = cat
                art["confidence"] = conf
                art["tags"] = tags
                art["subcategory"] = subcat
                database.store_article(art, conn=conn, embedding=emb)
            conn.commit()
        finally:
            conn.close()

        stored = database.get_articles(limit=10)
        self.assertEqual(len(stored), 2)
        titles = {a["title"] for a in stored}
        self.assertIn("Large language models achieve breakthrough reasoning", titles)
        self.assertIn("Critical zero-day in OpenSSL allows remote code execution", titles)

    def test_pipeline_dedup(self):
        """Store the same article twice, verify no duplicates."""
        art = _make_article(
            "Duplicate test article for dedup check",
            url="https://example.com/dup1",
        )

        is_new1, id1 = database.store_article(art)
        self.assertTrue(is_new1)
        self.assertIsNotNone(id1)

        is_new2, id2 = database.store_article(art)
        self.assertFalse(is_new2)
        self.assertEqual(id2, id1)

        stored = database.get_articles(limit=10)
        self.assertEqual(len(stored), 1)

    def test_pipeline_classifier_categories(self):
        """Verify articles land in expected categories."""
        cases = [
            ("Claude 4 introduces 1M token context window", "LLM"),
            ("Deep learning neural network for image classification", "Neural-Nets"),
            ("Machine learning reinforcement learning benchmark study", "ML-Research"),
            ("Artificial intelligence tool for autonomous refactoring", "AI-Applications"),
            ("Stock market investor portfolio earnings report", "Finance"),
            ("Critical vulnerability discovered in xz-utils security flaw", "Cybersecurity"),
        ]
        for title, expected_cat in cases:
            with self.subTest(title=title):
                art = _make_article(title, summary=title)
                cat, conf, tags, subcat, emb = classify_article(art)
                self.assertEqual(cat, expected_cat,
                                 f"Expected {expected_cat} for '{title}', got {cat}")

    @patch("telegram._send_telegram_message")
    @patch("telegram.get_telegram_token")
    @patch.object(Path, "exists", return_value=True)
    def test_pipeline_telegram_digest(self, mock_exists, mock_get_token, mock_send):
        """Run store then digest, mock Telegram send, verify message format."""
        mock_get_token.return_value = "fake:token"
        mock_send.return_value = {"ok": True}

        tg_path = Path(self._tmpdir) / "config" / "telegram.json"
        tg_path.parent.mkdir(parents=True, exist_ok=True)
        tg_path.write_text(json.dumps({"main_channel_id": "12345"}), encoding="utf-8")

        articles = {
            "LLM": [_make_article(
                "GPT-5 launches with multimodal capabilities",
                url="https://example.com/gpt5",
                published="2025-06-07T08:00:00",
            )],
        }
        conn = database.get_connection()
        try:
            for cat, arts in articles.items():
                for a in arts:
                    c, conf, tags, subcat, emb = classify_article(a)
                    a["category"] = cat
                    a["confidence"] = conf
                    a["tags"] = tags
                    a["subcategory"] = subcat
                    database.store_article(a, conn=conn, embedding=emb)
            conn.commit()
        finally:
            conn.close()

        import telegram
        telegram.BASE = Path(self._tmpdir)
        telegram.post_to_telegram(articles)

        mock_send.assert_called_once()
        args = mock_send.call_args
        token_arg = args[0][0]
        chat_arg = args[0][1]
        msg_text = args[0][2]
        self.assertEqual(token_arg, "fake:token")
        self.assertEqual(chat_arg, "12345")
        self.assertIn("GPT-5 launches with multimodal capabilities", msg_text)
        self.assertIn("LLM", msg_text)

    def test_pipeline_bookmark_roundtrip(self):
        """Store an article, bookmark it, verify bookmark persists."""
        art = _make_article(
            "Bookmark roundtrip test article",
            url="https://example.com/bookmark1",
        )
        is_new, article_id = database.store_article(art)
        self.assertTrue(is_new)
        self.assertIsNotNone(article_id)

        self.assertFalse(database.is_bookmarked(article_id))

        database.set_bookmarked(article_id, True)
        self.assertTrue(database.is_bookmarked(article_id))

        database.set_bookmarked(article_id, False)
        self.assertFalse(database.is_bookmarked(article_id))

        database.set_bookmarked(article_id, True)
        ids = database.get_bookmarked_article_ids()
        self.assertIn(article_id, ids)


# ===================================================================
# 2. Dashboard server tests
# ===================================================================

class TestDashboardServer(_IntegrationBase):
    """Tests 6-10: serve.py API endpoints."""

    def _get_handler(self):
        """Create a DashboardHandler wired to our temp DB."""
        from dashboard.serve import DashboardHandler
        handler = MagicMock(spec=DashboardHandler)
        handler.wfile = MagicMock()
        handler.headers = {}
        handler.path = "/api/articles"
        handler.rfile = MagicMock()
        return handler

    def _make_data_file(self, articles=None):
        """Write a dashboard_data.json with the given articles."""
        data_dir = Path(self._tmpdir) / "dashboard" / "data"
        data_dir.mkdir(parents=True, exist_ok=True)
        data_file = data_dir / "dashboard_data.json"
        payload = {
            "generated": "2025-06-07T12:00:00",
            "stats": {"total": len(articles or []), "today": 0},
            "articles": articles or [],
        }
        data_file.write_text(json.dumps(payload), encoding="utf-8")
        return data_file

    def _make_bookmarks_file(self, bookmark_ids=None):
        """Write a bookmarks.json."""
        data_dir = Path(self._tmpdir) / "dashboard" / "data"
        data_dir.mkdir(parents=True, exist_ok=True)
        bm_file = data_dir / "bookmarks.json"
        payload = {"bookmarks": bookmark_ids or []}
        bm_file.write_text(json.dumps(payload), encoding="utf-8")
        return bm_file

    def test_server_articles_endpoint(self):
        """GET /api/articles returns JSON with articles list."""
        import dashboard.serve as serve_mod

        original_data_dir = serve_mod.DATA_DIR
        original_data_file = serve_mod.DATA_FILE
        serve_mod.DATA_DIR = Path(self._tmpdir) / "dashboard" / "data"
        serve_mod.DATA_FILE = serve_mod.DATA_DIR / "dashboard_data.json"

        try:
            self._make_data_file(articles=[
                {"title": "Test Article 1", "url": "https://example.com/1"},
                {"title": "Test Article 2", "url": "https://example.com/2"},
            ])

            data = serve_mod.load_data()
            self.assertIn("articles", data)
            self.assertEqual(len(data["articles"]), 2)
            self.assertEqual(data["articles"][0]["title"], "Test Article 1")
        finally:
            serve_mod.DATA_DIR = original_data_dir
            serve_mod.DATA_FILE = original_data_file

    def test_server_bookmarks_endpoint(self):
        """GET /api/bookmarks returns JSON with bookmarks list."""
        import dashboard.serve as serve_mod

        original_data_dir = serve_mod.DATA_DIR
        original_bookmarks_file = serve_mod.BOOKMARKS_FILE
        serve_mod.DATA_DIR = Path(self._tmpdir) / "dashboard" / "data"
        serve_mod.BOOKMARKS_FILE = serve_mod.DATA_DIR / "bookmarks.json"

        try:
            self._make_bookmarks_file(["abc123", "def456"])

            data = serve_mod.load_bookmarks()
            self.assertIn("bookmarks", data)
            self.assertEqual(data["bookmarks"], ["abc123", "def456"])
        finally:
            serve_mod.DATA_DIR = original_data_dir
            serve_mod.BOOKMARKS_FILE = original_bookmarks_file

    def test_server_toggle_bookmark(self):
        """POST to /api/bookmarks/toggle, verify DB and file update."""
        import dashboard.serve as serve_mod

        original_data_dir = serve_mod.DATA_DIR
        original_bookmarks_file = serve_mod.BOOKMARKS_FILE
        serve_mod.DATA_DIR = Path(self._tmpdir) / "dashboard" / "data"
        serve_mod.DATA_DIR.mkdir(parents=True, exist_ok=True)
        serve_mod.BOOKMARKS_FILE = serve_mod.DATA_DIR / "bookmarks.json"

        try:
            serve_mod.BOOKMARKS_FILE.write_text(
                json.dumps({"bookmarks": []}), encoding="utf-8"
            )

            art = _make_article("Toggle test article", url="https://example.com/toggle1")
            is_new, article_id = database.store_article(art)
            content_hash = database.compute_hash(art)
            hash_prefix = content_hash[:16]

            body = json.dumps({"id": hash_prefix}).encode("utf-8")
            payload = {"id": hash_prefix}

            bookmarks = serve_mod.load_bookmarks()
            bm_list = bookmarks.get("bookmarks", [])
            if hash_prefix in bm_list:
                bm_list.remove(hash_prefix)
                starred = False
            else:
                bm_list.append(hash_prefix)
                starred = True
            bookmarks["bookmarks"] = bm_list
            serve_mod.save_bookmarks_atomic(bookmarks)

            database.set_bookmarked_by_hash_prefix(hash_prefix, starred)

            reloaded = serve_mod.load_bookmarks()
            self.assertIn(hash_prefix, reloaded["bookmarks"])
            self.assertTrue(database.is_bookmarked(article_id))
        finally:
            serve_mod.DATA_DIR = original_data_dir
            serve_mod.BOOKMARKS_FILE = original_bookmarks_file

    def test_server_search(self):
        """GET /api/articles?q=test verifies FTS5 search works."""
        art = _make_article(
            "Integration test search article",
            url="https://example.com/search1",
            summary="This article is about integration testing",
        )
        database.store_article(art)

        results = database.search_articles("integration", limit=10)
        self.assertTrue(len(results) >= 1)
        self.assertTrue(
            any("integration" in (a.get("title", "").lower() + " " + a.get("summary", "").lower())
                for a in results)
        )

        results = database.search_articles("nonexistentxyzzy", limit=10)
        self.assertEqual(len(results), 0)

    def test_server_no_cache_headers(self):
        """Verify Cache-Control headers on non-API static files."""
        from dashboard.serve import DashboardHandler
        import http.server

        handler = MagicMock(spec=DashboardHandler)
        handler.path = "/index.html"
        handler.send_header = MagicMock()
        handler.request_version = "HTTP/1.1"
        handler._headers_buffer = []
        handler.wfile = MagicMock()

        with patch.object(http.server.BaseHTTPRequestHandler, "end_headers"):
            DashboardHandler.end_headers(handler)

        calls = {c[0][0]: c[0][1] for c in handler.send_header.call_args_list}
        self.assertIn("Cache-Control", calls)
        self.assertEqual(calls["Cache-Control"], "no-store, must-revalidate")
        self.assertIn("Pragma", calls)
        self.assertEqual(calls["Pragma"], "no-cache")

    def test_server_api_cache_headers(self):
        """Verify API endpoints use per-endpoint cache control."""
        from dashboard.serve import DashboardHandler

        handler = MagicMock(spec=DashboardHandler)
        handler.path = "/api/articles"
        handler.send_header = MagicMock()
        handler.end_headers = MagicMock()
        handler.wfile = MagicMock()
        handler.request_version = "HTTP/1.1"
        handler.headers = {"Accept-Encoding": "identity"}

        data = {"articles": []}
        content = json.dumps(data).encode("utf-8")
        handler.wfile.write = MagicMock()

        handler.send_response = MagicMock()

        DashboardHandler._send_json(handler, data, cache_max_age=10)

        calls = {c[0][0]: c[0][1] for c in handler.send_header.call_args_list}
        self.assertIn("Cache-Control", calls)
        self.assertEqual(calls["Cache-Control"], "public, max-age=10")


# ===================================================================
# 3. Scheduler tests
# ===================================================================

class TestScheduler(_IntegrationBase):
    """Tests 11-12: scheduler catch-up detection and state machine."""

    def test_scheduler_catchup_detection(self):
        """Verify scheduler detects missed runs."""
        import sys
        sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
        import scheduler

        now = datetime(2025, 6, 7, 14, 0, 0)

        state_no_run = {"last_run": None, "last_status": None}
        self.assertTrue(scheduler.should_catch_up(state_no_run, now))

        recent = (now - timedelta(hours=2)).isoformat()
        state_recent = {"last_run": recent, "last_status": "ok"}
        self.assertFalse(scheduler.should_catch_up(state_recent, now))

        old = (now - timedelta(hours=13)).isoformat()
        state_old = {"last_run": old, "last_status": "ok"}
        self.assertTrue(scheduler.should_catch_up(state_old, now))

        bad_format = {"last_run": "not-a-date", "last_status": "ok"}
        self.assertTrue(scheduler.should_catch_up(bad_format, now))

    def test_scheduler_state_machine(self):
        """Verify state transitions (idle → running → idle)."""
        import sys
        sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
        import scheduler

        state_file = Path(self._tmpdir) / ".last_run"

        original_state_file = scheduler.STATE_FILE
        scheduler.STATE_FILE = state_file
        try:
            self.assertFalse(state_file.exists())

            state = scheduler.load_state()
            self.assertEqual(state, {"last_run": None, "last_status": None})

            scheduler.save_state({"last_run": "2025-06-07T12:00:00", "last_status": "ok"})
            self.assertTrue(state_file.exists())
            loaded = json.loads(state_file.read_text(encoding="utf-8"))
            self.assertEqual(loaded["last_run"], "2025-06-07T12:00:00")
            self.assertEqual(loaded["last_status"], "ok")

            scheduler.save_state({"last_run": "2025-06-07T12:30:00", "last_status": "failed"})
            loaded = json.loads(state_file.read_text(encoding="utf-8"))
            self.assertEqual(loaded["last_status"], "failed")

            state = scheduler.load_state()
            self.assertEqual(state["last_run"], "2025-06-07T12:30:00")
            self.assertEqual(state["last_status"], "failed")
        finally:
            scheduler.STATE_FILE = original_state_file

    def test_scheduler_next_checkpoint(self):
        """Verify next_checkpoint returns the correct upcoming time."""
        import sys
        sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
        import scheduler

        now = datetime(2025, 6, 7, 14, 0, 0)
        nxt = scheduler.next_checkpoint(now)
        self.assertEqual(nxt.hour, 0)
        self.assertEqual(nxt.day, 8)

        now = datetime(2025, 6, 7, 6, 0, 0)
        nxt = scheduler.next_checkpoint(now)
        self.assertEqual(nxt.hour, 12)
        self.assertEqual(nxt.day, 7)

        now = datetime(2025, 6, 7, 13, 0, 0)
        nxt = scheduler.next_checkpoint(now)
        self.assertEqual(nxt.hour, 0)
        self.assertEqual(nxt.day, 8)


# ===================================================================
# 4. Database utility tests
# ===================================================================

class TestDatabaseUtilities(_IntegrationBase):
    """Additional database-level integration checks."""

    def test_get_articles_category_filter(self):
        """get_articles filters by category."""
        for cat in ("LLM", "Finance", "LLM"):
            art = _make_article(
                f"Article in {cat} category {cat}",
                url=f"https://example.com/{cat}_{id(art) if 'art' in dir() else cat}",
            )
            is_new, _ = database.store_article(art)
            if is_new:
                database.set_bookmarked(database.get_articles(limit=1)[-1]["id"], False)

        database.store_article(_make_article("LLM transformer advances", url="https://ex.com/l1"))
        database.store_article(_make_article("Bitcoin surges past 100K", url="https://ex.com/f1"))

        llm_arts = database.get_articles(category="LLM", limit=10)
        for a in llm_arts:
            self.assertEqual(a["category"], "LLM")

    def test_cleanup_old_articles(self):
        """cleanup_old_articles removes old entries."""
        old_art = _make_article(
            "Very old article",
            url="https://example.com/old1",
            published=(datetime.utcnow() - timedelta(days=60)).isoformat(),
        )
        database.store_article(old_art)

        fresh_art = _make_article(
            "Fresh article",
            url="https://example.com/fresh1",
            published=datetime.utcnow().isoformat(),
        )
        database.store_article(fresh_art)

        deleted = database.cleanup_old_articles(max_age_days=30)
        self.assertGreaterEqual(deleted, 1)

        remaining = database.get_articles(limit=100)
        titles = [a["title"] for a in remaining]
        self.assertNotIn("Very old article", titles)

    def test_compute_hash_deterministic(self):
        """compute_hash returns the same value for same input."""
        art = _make_article("Hash test", url="https://example.com/hash1")
        h1 = database.compute_hash(art)
        h2 = database.compute_hash(art)
        self.assertEqual(h1, h2)
        self.assertEqual(len(h1), 64)

    def test_title_similarity(self):
        """title_similarity returns correct values for known pairs."""
        s1 = database.title_similarity("GPT-5 launch", "GPT-5 launch")
        self.assertAlmostEqual(s1, 1.0)

        s2 = database.title_similarity("GPT-5 launch", "Completely different title about cooking")
        self.assertLess(s2, 0.2)

    def test_log_duplicate_creates_entry(self):
        """log_duplicate inserts into dedup_log."""
        database.log_duplicate("abc123", "Test dup title", 42, 0.95, "url")
        conn = database.get_connection()
        try:
            row = conn.execute("SELECT * FROM dedup_log WHERE content_hash = ?", ("abc123",)).fetchone()
            self.assertIsNotNone(row)
            self.assertEqual(row["title"], "Test dup title")
            self.assertAlmostEqual(row["similarity_score"], 0.95)
        finally:
            conn.close()


if __name__ == "__main__":
    unittest.main()
