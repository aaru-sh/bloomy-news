"""Extended tests for the telegram module.

Covers digest formatting, emoji mapping, article limiting,
send success/failure, and post_to_telegram config-missing path.
"""
import json
import sys
import tempfile
import unittest
from datetime import date
from pathlib import Path
from unittest.mock import patch, MagicMock

BASE = Path(__file__).parent.parent
sys.path.insert(0, str(BASE))

import telegram
from telegram import (
    _format_digest,
    _select_top_articles,
    _send_telegram_message,
    post_to_telegram,
    TELEGRAM_CATEGORIES,
    TELEGRAM_EMOJIS,
    TELEGRAM_LIMIT_PER_CAT,
)


def _article(title="Test Title", url="http://example.com", summary="Sum",
             published="", category="LLM"):
    return {
        "title": title, "url": url, "summary": summary,
        "published": published, "category": category,
    }


class TestFormatDigestEmpty(unittest.TestCase):
    def test_empty_category_map(self):
        text, total = _format_digest({})
        self.assertEqual(total, 0)
        self.assertIn("Total: 0 articles", text)

    def test_all_categories_empty(self):
        text, total = _format_digest({cat: [] for cat in TELEGRAM_CATEGORIES})
        self.assertEqual(total, 0)
        self.assertIn("Total: 0 articles", text)


class TestFormatDigestSingleCategory(unittest.TestCase):
    def test_single_category(self):
        articles = [_article(f"Art {i}") for i in range(2)]
        text, total = _format_digest({"LLM": articles})
        self.assertEqual(total, 2)
        self.assertIn("LLM", text)
        self.assertIn("Art 0", text)
        self.assertIn("Art 1", text)

    def test_category_not_in_map(self):
        text, total = _format_digest({"LLM": [_article()]})
        self.assertEqual(total, 1)
        self.assertNotIn("Finance", text)


class TestFormatDigestEmojiMapping(unittest.TestCase):
    def test_all_categories_have_emojis(self):
        for cat in TELEGRAM_CATEGORIES:
            self.assertIn(cat, TELEGRAM_EMOJIS)
            self.assertIsInstance(TELEGRAM_EMOJIS[cat], str)

    def test_emojis_appear_in_digest(self):
        articles = [_article()]
        text, _ = _format_digest({"LLM": articles})
        self.assertIn(TELEGRAM_EMOJIS["LLM"], text)


class TestFormatDigestMaxArticles(unittest.TestCase):
    def test_respects_limit_per_category(self):
        articles = [_article(f"Art {i}") for i in range(10)]
        text, total = _format_digest({"LLM": articles}, limit_per_cat=3)
        self.assertEqual(total, 3)
        self.assertNotIn("Art 3", text)
        self.assertIn("Art 0", text)

    def test_custom_limit(self):
        articles = [_article(f"Art {i}") for i in range(5)]
        text, total = _format_digest({"LLM": articles}, limit_per_cat=5)
        self.assertEqual(total, 5)

    def test_fewer_than_limit(self):
        articles = [_article("Only")]
        text, total = _format_digest({"LLM": articles}, limit_per_cat=3)
        self.assertEqual(total, 1)


class TestSelectTopArticles(unittest.TestCase):
    def test_no_limit(self):
        articles = [_article(f"A{i}") for i in range(2)]
        result = _select_top_articles(articles, limit=5)
        self.assertEqual(len(result), 2)

    def test_sorts_by_published_desc(self):
        arts = [
            _article("Old", published="2024-01-01"),
            _article("New", published="2024-06-01"),
            _article("Mid", published="2024-03-01"),
        ]
        result = _select_top_articles(arts, limit=2)
        titles = [a["title"] for a in result]
        self.assertEqual(titles, ["New", "Mid"])


class TestSendTelegramMessage(unittest.TestCase):
    @patch("telegram.urllib.request.urlopen")
    def test_success(self, mock_urlopen):
        mock_resp = MagicMock()
        mock_resp.read.return_value = json.dumps({"ok": True}).encode()
        mock_resp.__enter__ = lambda s: s
        mock_resp.__exit__ = MagicMock(return_value=False)
        mock_urlopen.return_value = mock_resp

        result = _send_telegram_message("token123", "chat456", "hello")
        self.assertTrue(result["ok"])
        mock_urlopen.assert_called_once()

    @patch("telegram.urllib.request.urlopen", side_effect=ConnectionError("fail"))
    def test_failure(self, mock_urlopen):
        with self.assertRaises(ConnectionError):
            _send_telegram_message("token", "chat", "text")


class TestPostToTelegramNoConfig(unittest.TestCase):
    @patch("telegram.get_telegram_token", return_value=None)
    def test_no_token(self, mock_get_token):
        with tempfile.TemporaryDirectory() as tmpdir:
            tg_path = Path(tmpdir) / "config" / "telegram.json"
            tg_path.parent.mkdir(parents=True, exist_ok=True)
            tg_path.write_text(json.dumps({"main_channel_id": "12345"}), encoding="utf-8")
            with patch.object(telegram, "BASE", Path(tmpdir)):
                post_to_telegram({})
        mock_get_token.assert_called()

    @patch("telegram.get_telegram_token", return_value="")
    def test_empty_token(self, mock_get_token):
        with tempfile.TemporaryDirectory() as tmpdir:
            tg_path = Path(tmpdir) / "config" / "telegram.json"
            tg_path.parent.mkdir(parents=True, exist_ok=True)
            tg_path.write_text(json.dumps({"main_channel_id": "12345"}), encoding="utf-8")
            with patch.object(telegram, "BASE", Path(tmpdir)):
                post_to_telegram({"LLM": [_article()]})

    def test_no_telegram_config_file(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch.object(telegram, "BASE", Path(tmpdir)):
                post_to_telegram({})


class TestPostToTelegramSuccess(unittest.TestCase):
    @patch("telegram._send_telegram_message", return_value={"ok": True})
    @patch("telegram.get_telegram_token", return_value="token123")
    def test_posts_fresh_articles(self, mock_get_token, mock_send):
        with tempfile.TemporaryDirectory() as tmpdir:
            cfg_dir = Path(tmpdir) / "config"
            cfg_dir.mkdir()
            (cfg_dir / "telegram.json").write_text(
                json.dumps({"main_channel_id": "chat123"})
            )
            with patch.object(telegram, "BASE", Path(tmpdir)):
                articles = [_article("Fresh LLM", published="2024-06-01")]
                post_to_telegram({"LLM": articles})
                mock_send.assert_called_once()
                call_args = mock_send.call_args
                self.assertEqual(call_args[0][0], "token123")
                self.assertEqual(call_args[0][1], "chat123")


class TestPostToTelegramFailure(unittest.TestCase):
    @patch("telegram._send_telegram_message", side_effect=Exception("network error"))
    @patch("telegram.get_telegram_token", return_value="token123")
    def test_handles_network_error(self, mock_get_token, mock_send):
        with tempfile.TemporaryDirectory() as tmpdir:
            cfg_dir = Path(tmpdir) / "config"
            cfg_dir.mkdir()
            (cfg_dir / "telegram.json").write_text(
                json.dumps({"main_channel_id": "chat123"})
            )
            with patch.object(telegram, "BASE", Path(tmpdir)):
                post_to_telegram({"LLM": [_article()]})
                mock_send.assert_called_once()

    @patch("telegram._send_telegram_message", return_value={"ok": False, "description": "bad"})
    @patch("telegram.get_telegram_token", return_value="token123")
    def test_handles_api_error(self, mock_get_token, mock_send):
        with tempfile.TemporaryDirectory() as tmpdir:
            cfg_dir = Path(tmpdir) / "config"
            cfg_dir.mkdir()
            (cfg_dir / "telegram.json").write_text(
                json.dumps({"main_channel_id": "chat123"})
            )
            with patch.object(telegram, "BASE", Path(tmpdir)):
                post_to_telegram({"LLM": [_article()]})
                mock_send.assert_called_once()


class TestPostToTelegramEmptyFallback(unittest.TestCase):
    @patch("telegram.database.get_today_top_per_category", return_value={})
    @patch("telegram._send_telegram_message", return_value={"ok": True})
    @patch("telegram.get_telegram_token", return_value="token123")
    def test_empty_categorized_triggers_db_fallback(self, mock_get_token, mock_send, mock_db):
        with tempfile.TemporaryDirectory() as tmpdir:
            cfg_dir = Path(tmpdir) / "config"
            cfg_dir.mkdir()
            (cfg_dir / "telegram.json").write_text(
                json.dumps({"main_channel_id": "chat123"})
            )
            with patch.object(telegram, "BASE", Path(tmpdir)):
                post_to_telegram({})
                mock_db.assert_called_once()
                mock_send.assert_called_once()


if __name__ == "__main__":
    unittest.main()
