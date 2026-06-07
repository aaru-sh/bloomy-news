"""Extended tests for the classifier module edge cases.

Covers empty inputs, embedding fallback path, keyword-only path,
confidence thresholds, and return shape.
"""
import sys
import unittest
from pathlib import Path
from unittest.mock import patch, MagicMock

BASE = Path(__file__).parent.parent
sys.path.insert(0, str(BASE))

import classifier
from classifier import (
    classify_article,
    _classify_keywords,
    _classify_embedding,
    KEYWORD_MINIMUM_ACCURACY,
    EMBEDDING_MINIMUM_ACCURACY,
    COMBINED_MINIMUM_ACCURACY,
    CATEGORY_EXAMPLES,
)


def _article(title="", summary="", url=""):
    return {"title": title, "summary": summary, "url": url}


class TestClassifyEmptyTitle(unittest.TestCase):
    def test_empty_title_empty_summary(self):
        cat, conf, tags, subcat, emb = classify_article(_article("", ""))
        self.assertEqual(cat, "Uncategorized")
        self.assertEqual(conf, 0.0)
        self.assertIsInstance(tags, list)
        self.assertIsInstance(subcat, str)
        self.assertIsNone(emb)

    def test_empty_title_with_summary(self):
        cat, conf, tags, subcat, emb = classify_article(
            _article("", "stock market surges on earnings report")
        )
        self.assertEqual(cat, "Finance")
        self.assertGreater(conf, 0.0)

    def test_none_title(self):
        cat, conf, tags, subcat, emb = classify_article(
            {"title": None, "summary": "test"}
        )
        self.assertIsInstance(cat, str)
        self.assertGreaterEqual(conf, 0.0)


class TestClassifyEmptySummary(unittest.TestCase):
    def test_title_only_llm(self):
        cat, conf, tags, subcat, emb = classify_article(
            _article("New GPT-5 model released with fine-tuning support")
        )
        self.assertEqual(cat, "LLM")
        self.assertGreater(conf, 0.0)

    def test_title_only_cybersecurity(self):
        cat, conf, tags, subcat, emb = classify_article(
            _article("Critical security vulnerability found in Linux kernel")
        )
        self.assertEqual(cat, "Cybersecurity")

    def test_summary_only(self):
        cat, conf, tags, subcat, emb = classify_article(
            _article("", "stock market surges on strong earnings report")
        )
        self.assertEqual(cat, "Finance")


class TestClassifyEmbeddingFallback(unittest.TestCase):
    def test_fallback_when_model_fails(self):
        with patch.object(classifier, "_embedding_load_failed", False):
            with patch.object(classifier, "_embedding_model", None):
                with patch.object(classifier, "EMBEDDING_AVAILABLE", True):
                    with patch(
                        "classifier.SentenceTransformer",
                        side_effect=Exception("OOM"),
                    ):
                        cat, conf, tags, subcat, emb = classify_article(
                            _article("stock market surges on earnings report", "")
                        )
                        self.assertEqual(cat, "Finance")
                        self.assertIsNone(emb)

    def test_fallback_when_model_is_none(self):
        with patch.object(classifier, "_embedding_model", None):
            with patch.object(classifier, "_embedding_load_failed", True):
                cat, conf, tags, subcat, emb = classify_article(
                    _article("Major data breach exposes records", "")
                )
                self.assertIsInstance(cat, str)
                self.assertIsNone(emb)


class TestClassifyKeywordOnly(unittest.TestCase):
    def test_keyword_path_standalone(self):
        cat, conf, tags, subcat, emb = _classify_keywords(
            _article("New GPT-5 model released with fine-tuning support")
        )
        self.assertEqual(cat, "LLM")
        self.assertIsNone(emb)

    def test_keyword_finance(self):
        cat, conf, tags, subcat, emb = _classify_keywords(
            _article("stock market surges on strong earnings report")
        )
        self.assertEqual(cat, "Finance")

    def test_keyword_uncategorized(self):
        cat, conf, tags, subcat, emb = _classify_keywords(
            _article("random unrelated title about cooking recipes")
        )
        self.assertEqual(cat, "Uncategorized")
        self.assertEqual(conf, 0.0)


class TestClassifyConfidenceThresholds(unittest.TestCase):
    def test_keyword_minimum_is_float(self):
        self.assertIsInstance(KEYWORD_MINIMUM_ACCURACY, float)
        self.assertGreater(KEYWORD_MINIMUM_ACCURACY, 0.0)
        self.assertLessEqual(KEYWORD_MINIMUM_ACCURACY, 1.0)

    def test_embedding_minimum_is_float(self):
        self.assertIsInstance(EMBEDDING_MINIMUM_ACCURACY, float)
        self.assertGreater(EMBEDDING_MINIMUM_ACCURACY, 0.0)
        self.assertLessEqual(EMBEDDING_MINIMUM_ACCURACY, 1.0)

    def test_combined_minimum_is_float(self):
        self.assertIsInstance(COMBINED_MINIMUM_ACCURACY, float)
        self.assertGreater(COMBINED_MINIMUM_ACCURACY, 0.0)
        self.assertLessEqual(COMBINED_MINIMUM_ACCURACY, 1.0)

    def test_embedding_ge_combined(self):
        self.assertGreaterEqual(
            EMBEDDING_MINIMUM_ACCURACY, COMBINED_MINIMUM_ACCURACY
        )

    def test_combined_ge_keyword(self):
        self.assertGreaterEqual(
            COMBINED_MINIMUM_ACCURACY, KEYWORD_MINIMUM_ACCURACY
        )


class TestClassifyReturnShape(unittest.TestCase):
    def test_returns_5_tuple(self):
        result = classify_article(_article("GPT-5 announced", "OpenAI new model"))
        self.assertEqual(len(result), 5)

    def test_types(self):
        cat, conf, tags, subcat, emb = classify_article(
            _article("Test article", "Some summary")
        )
        self.assertIsInstance(cat, str)
        self.assertIsInstance(conf, (int, float))
        self.assertIsInstance(tags, list)
        self.assertIsInstance(subcat, str)
        self.assertGreaterEqual(conf, 0.0)
        self.assertLessEqual(conf, 1.0)

    def test_embedding_is_none_or_array(self):
        _, _, _, _, emb = classify_article(_article("Test", ""))
        if emb is not None:
            import numpy as np
            self.assertIsInstance(emb, np.ndarray)
            self.assertEqual(emb.ndim, 1)


class TestCategoryExamples(unittest.TestCase):
    def test_all_categories_have_examples(self):
        self.assertEqual(len(CATEGORY_EXAMPLES), 6)
        for cat, examples in CATEGORY_EXAMPLES.items():
            self.assertIsInstance(examples, list)
            self.assertGreater(len(examples), 0, f"{cat} has no examples")


if __name__ == "__main__":
    unittest.main()
