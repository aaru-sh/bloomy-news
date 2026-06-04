"""Smoke tests for the most critical fixes in Bloomy News."""
import os
import sys
import json
import sqlite3
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch, MagicMock

BASE = Path(__file__).parent.parent
sys.path.insert(0, str(BASE))
sys.path.insert(0, str(BASE / 'dashboard'))


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
        primary, conf, tags, subcat = news_tool.classify_article({
            "title": "XYZ random unrelated text",
            "summary": "nothing in here matches anything either"
        })
        self.assertEqual(primary, "Uncategorized")
        self.assertEqual(conf, 0.0)
        self.assertEqual(tags, [])

    def test_llm_match(self):
        import news_tool
        primary, conf, tags, subcat = news_tool.classify_article({
            "title": "New transformer architecture for large language models",
            "summary": "GPT and BERT comparison"
        })
        self.assertEqual(primary, "LLM")
        self.assertGreater(conf, 0.0)

    def test_no_fallback_to_ai_applications(self):
        import news_tool
        primary, conf, tags, subcat = news_tool.classify_article({
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


if __name__ == '__main__':
    unittest.main()
