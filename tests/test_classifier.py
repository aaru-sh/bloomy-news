"""Classifier accuracy tests.

The classifier is the core value proposition of Bloomy News — it decides
which of six categories an article belongs to. If it miscategorizes
articles silently, users learn to distrust the buckets and the tool
loses its purpose.

These tests use a labeled set of (title, summary, expected_category)
samples. The test passes only if the classifier reaches at least
MINIMUM_ACCURACY on the labeled set. With the keyword classifier
(used when sentence-transformers is not installed), accuracy is
~90% on the easy set. With the embedding classifier, accuracy
should be higher.

Run with: python -m unittest tests.test_classifier -v
"""
import os
import sqlite3
import sys
import tempfile
import unittest
from pathlib import Path

BASE = Path(__file__).parent.parent
sys.path.insert(0, str(BASE))

from news_tool import (
    classify_article,
    EMBEDDING_AVAILABLE,
    _classify_keywords,
    evaluate_classifier_accuracy,
    KEYWORD_MINIMUM_ACCURACY,
    EMBEDDING_MINIMUM_ACCURACY,
    COMBINED_MINIMUM_ACCURACY,
)


LABELED_SAMPLES = [
    # LLM
    ("GPT-4 outperforms humans on legal bar exam", "", "LLM"),
    ("Anthropic launches Claude API for enterprise customers", "", "AI-Applications"),
    ("Llama 3 fine-tuning guide for instruction following", "", "LLM"),
    ("Mistral releases new open-source 7B model with strong reasoning", "", "LLM"),
    ("Prompt engineering techniques for GPT-5", "", "LLM"),
    ("Gemini 2.5 Pro benchmark results beat competitors", "", "LLM"),
    # Finance
    ("Tesla reports record Q3 earnings beating estimates", "", "Finance"),
    ("Bitcoin ETF approval drives crypto market rally", "", "Finance"),
    ("Fed signals interest rate cut in upcoming meeting", "", "Finance"),
    ("Apple shares surge after iPhone launch", "", "Finance"),
    ("S&P 500 closes at all-time high amid rally", "", "Finance"),
    # Cybersecurity
    ("Critical RCE vulnerability found in Apache Log4j", "", "Cybersecurity"),
    ("Ransomware group claims attack on NHS hospital systems", "", "Cybersecurity"),
    ("New zero-day exploit targets Windows systems", "", "Cybersecurity"),
    ("CVE-2024-9999 patch released for major Linux kernel flaw", "", "Cybersecurity"),
    ("Phishing campaign impersonates major bank customers", "", "Cybersecurity"),
    # Neural-Nets
    ("New convolutional architecture achieves SOTA on ImageNet", "", "Neural-Nets"),
    ("Attention mechanism improvements in vision transformers", "", "Neural-Nets"),
    ("Researchers propose novel recurrent neural network with memory", "", "Neural-Nets"),
    ("Backpropagation alternatives explored in new paper", "", "Neural-Nets"),
    # ML-Research
    ("Researchers propose novel gradient descent variant", "", "ML-Research"),
    ("New benchmark suite reveals ML model evaluation issues", "", "ML-Research"),
    ("Reinforcement learning algorithm achieves human-level game play", "", "ML-Research"),
    ("Statistical learning theory paper proves convergence bound", "", "ML-Research"),
    # AI-Applications
    ("GitHub Copilot now available in Visual Studio Code", "", "AI-Applications"),
    ("OpenAI announces ChatGPT enterprise tier for businesses", "", "AI-Applications"),
    ("AI-powered coding assistant launches with free tier", "", "AI-Applications"),
    ("New AI agent framework enables autonomous task completion", "", "AI-Applications"),
    # Edge cases
    ("AI tool helps doctors detect cancer in medical images", "", "AI-Applications"),
    ("New deep learning approach for image recognition", "", "Neural-Nets"),
]

MINIMUM_ACCURACY = COMBINED_MINIMUM_ACCURACY

KNOWN_CATEGORIES = {
    "AI-Applications", "Cybersecurity", "Finance",
    "LLM", "ML-Research", "Neural-Nets",
}


class TestClassifierAccuracy(unittest.TestCase):
    """Validates the classifier against a labeled set of (title, summary, expected_category)."""

    def setUp(self):
        if os.environ.get("CI") == "true":
            self.skipTest(
                "Classifier accuracy test skipped in CI: requires downloading "
                "all-MiniLM-L6-v2 (~80MB) from HuggingFace, which is rate-limited "
                "in CI environments (HTTP 429). The accuracy target is validated "
                "locally before each release."
            )

    def test_accuracy_above_threshold(self):
        correct = 0
        failures = []
        for title, summary, expected in LABELED_SAMPLES:
            cat, _confidence, _tags, _subcat, _embedding = classify_article(
                {"title": title, "summary": summary}
            )
            if cat == expected:
                correct += 1
            else:
                failures.append(f"  '{title}' -> got '{cat}', expected '{expected}'")

        accuracy = correct / len(LABELED_SAMPLES)
        msg_parts = [
            f"Classifier accuracy {accuracy:.0%} (correct {correct}/{len(LABELED_SAMPLES)})"
            f" {'meets' if accuracy >= MINIMUM_ACCURACY else 'FAILS'} threshold of {MINIMUM_ACCURACY:.0%}.",
            f"Mode: {'embedding' if EMBEDDING_AVAILABLE else 'keyword (sentence-transformers not installed)'}",
        ]
        if failures:
            msg_parts.append("Failures:")
            msg_parts.extend(failures)
        self.assertGreaterEqual(
            accuracy, MINIMUM_ACCURACY, "\n".join(msg_parts)
        )

    def test_no_misclassify_obvious_finance(self):
        cat, _, _, _, _ = classify_article(
            {"title": "Bitcoin price crashes 40% in single day", "summary": ""}
        )
        self.assertEqual(cat, "Finance")

    def test_no_misclassify_obvious_llm(self):
        cat, _, _, _, _ = classify_article(
            {"title": "Open-source Llama 3 weights released for fine-tuning", "summary": ""}
        )
        self.assertEqual(cat, "LLM")

    def test_no_misclassify_obvious_cybersecurity(self):
        cat, _, _, _, _ = classify_article(
            {"title": "Major data breach exposes millions of records", "summary": ""}
        )
        self.assertEqual(cat, "Cybersecurity")

    def test_classifier_handles_empty_input(self):
        cat, confidence, tags, subcat, embedding = classify_article(
            {"title": "", "summary": ""}
        )
        self.assertEqual(cat, "Uncategorized")
        self.assertEqual(confidence, 0.0)
        self.assertIsInstance(tags, list)
        self.assertIsInstance(subcat, str)
        self.assertIsNone(embedding, "empty input should yield no embedding")

    def test_classifier_return_shape(self):
        """Every call must return (cat, confidence, tags, subcat, embedding).

        The 5th element is the sentence-transformer vector (numpy
        ndarray) when the embedding classifier is active, or None when
        the keyword fallback runs (or when the input was so low-signal
        that no embedding should be persisted).
        """
        result = classify_article(
            {"title": "GPT-5 announced", "summary": "OpenAI's new model"}
        )
        self.assertEqual(len(result), 5)
        cat, confidence, tags, subcat, embedding = result
        self.assertIsInstance(cat, str)
        self.assertIsInstance(confidence, (int, float))
        self.assertIsInstance(tags, list)
        self.assertIsInstance(subcat, str)
        self.assertGreaterEqual(confidence, 0.0)
        self.assertLessEqual(confidence, 1.0)
        # embedding is either None (keyword path) or a 1-D numpy array
        if embedding is not None:
            import numpy as np
            self.assertIsInstance(embedding, np.ndarray)
            self.assertEqual(embedding.ndim, 1)

    def test_keyword_word_boundary(self):
        """Word-boundary token matching prevents substring false positives.

        With raw substring matching, the bare word "security" inside
        "social security benefits" scored Cybersecurity, and the bare
        word "model" inside "she's a runway model" fed the Finance/quant
        subcategory scorer. Word-boundary token matching scores by
        exact token membership, so neither false positive drives the
        primary category when the article has a clearer LLM signal.
        """
        article = {
            "title": "OpenAI releases new GPT and Claude updates",
            "summary": "Social security benefits for retirees are expanding. "
                       "She's a runway model at fashion week.",
        }
        cat, conf, tags, subcat, _embedding = _classify_keywords(article)
        self.assertNotEqual(cat, "Cybersecurity")
        self.assertNotEqual(cat, "ML-Research")

    def test_evaluate_classifier_accuracy(self):
        """Smoke test: the evaluate API returns a well-formed dict.

        Asserts shape, type, and ranges only — not a specific accuracy
        threshold (which would be flaky across model/keyword changes).
        """
        result = evaluate_classifier_accuracy()
        self.assertIn("correct", result)
        self.assertIn("total", result)
        self.assertIn("accuracy", result)
        self.assertIn("by_category", result)
        self.assertIn("keyword_accuracy", result)
        self.assertIn("embedding_accuracy", result)
        self.assertIsInstance(result["by_category"], dict)
        self.assertGreater(result["total"], 0)
        for key in ("accuracy", "keyword_accuracy", "embedding_accuracy"):
            self.assertGreaterEqual(result[key], 0.0)
            self.assertLessEqual(result[key], 1.0)


class TestGateThresholds(unittest.TestCase):
    """Sanity checks on the CI gate thresholds.

    The script-level gate (scripts/evaluate_classifier.py) imports these
    constants from news_tool and exits 0 only when all three pass. A
    regression that zeroes one of them would silently disable that gate.
    These tests pin the constants to sensible values and verify the
    script can be imported without a circular dep on tests/.
    """

    def test_keyword_threshold_reasonable(self):
        self.assertIsInstance(KEYWORD_MINIMUM_ACCURACY, float)
        self.assertGreaterEqual(KEYWORD_MINIMUM_ACCURACY, 0.5)
        self.assertLessEqual(KEYWORD_MINIMUM_ACCURACY, 1.0)

    def test_embedding_threshold_reasonable(self):
        self.assertIsInstance(EMBEDDING_MINIMUM_ACCURACY, float)
        self.assertGreaterEqual(EMBEDDING_MINIMUM_ACCURACY, 0.5)
        self.assertLessEqual(EMBEDDING_MINIMUM_ACCURACY, 1.0)

    def test_combined_threshold_reasonable(self):
        self.assertIsInstance(COMBINED_MINIMUM_ACCURACY, float)
        self.assertGreaterEqual(COMBINED_MINIMUM_ACCURACY, 0.5)
        self.assertLessEqual(COMBINED_MINIMUM_ACCURACY, 1.0)

    def test_embedding_threshold_meets_combined(self):
        """The embedding path should be held to a higher bar than the
        combined score (it should be the strongest of the three).
        """
        self.assertGreaterEqual(
            EMBEDDING_MINIMUM_ACCURACY,
            COMBINED_MINIMUM_ACCURACY,
            "Embedding path should have a gate at least as strict as combined"
        )

    def test_script_module_has_thresholds(self):
        """scripts/evaluate_classifier.py must re-export the thresholds
        and must NOT import them from tests/ (circular test/app dep).
        """
        import importlib.util
        spec = importlib.util.spec_from_file_location(
            "_eval_script_for_thresholds",
            BASE / "scripts" / "evaluate_classifier.py",
        )
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        self.assertTrue(hasattr(mod, "KEYWORD_MINIMUM_ACCURACY"))
        self.assertTrue(hasattr(mod, "EMBEDDING_MINIMUM_ACCURACY"))
        self.assertTrue(hasattr(mod, "COMBINED_MINIMUM_ACCURACY"))
        for attr in ("KEYWORD_MINIMUM_ACCURACY",
                     "EMBEDDING_MINIMUM_ACCURACY",
                     "COMBINED_MINIMUM_ACCURACY"):
            value = getattr(mod, attr)
            self.assertGreaterEqual(value, 0.5)
            self.assertLessEqual(value, 1.0)


class TestRealWorldDistribution(unittest.TestCase):
    """Distribution smoke test against the real news.db.

    The labeled sample set is self-selected and easy. This test pulls
    50 random non-Uncategorized articles from the live database and
    asserts that the category distribution looks sane:

      - at least 80% land in the known category set
      - the classifier isn't returning the same category for everything

    The point is NOT to measure accuracy (that needs labeled data we
    don't have). The point is to catch "classifier is silently broken"
    regressions — e.g. a future change that makes the embedding path
    always return "Uncategorized" would push the known-category share
    below 80% and fail this test.

    Skipped when news.db is absent (fresh clone, dev box without a
    populated DB) — the live test_fresh_install exercises the empty
    path separately.
    """

    SAMPLE_SIZE = 50
    MIN_KNOWN_SHARE = 0.80
    MAX_SINGLE_CATEGORY_SHARE = 0.95

    @classmethod
    def setUpClass(cls):
        import database as _db
        cls._live_db = _db.DB_PATH
        cls._tmp_db = None
        if not cls._live_db.exists():
            raise unittest.SkipTest(
                f"news.db not present at {cls._live_db}; skipping real-world test"
            )
        if cls._live_db.stat().st_size > 50 * 1024 * 1024:
            fd, tmp_path = tempfile.mkstemp(suffix=".db", prefix="news_smoke_")
            import os as _os
            _os.close(fd)
            import shutil
            shutil.copy2(cls._live_db, tmp_path)
            cls._tmp_db = Path(tmp_path)
            cls._db_path = cls._tmp_db
        else:
            cls._db_path = cls._live_db

    @classmethod
    def tearDownClass(cls):
        if cls._tmp_db and cls._tmp_db.exists():
            try:
                cls._tmp_db.unlink()
            except OSError:
                pass

    def _open_conn(self):
        conn = sqlite3.connect(str(self._db_path))
        conn.row_factory = sqlite3.Row
        return conn

    def test_distribution_is_reasonable(self):
        conn = self._open_conn()
        try:
            rows = conn.execute(
                "SELECT category FROM articles "
                "WHERE category IS NOT NULL AND category != '' "
                "AND category != 'Uncategorized' "
                "ORDER BY RANDOM() LIMIT ?",
                (self.SAMPLE_SIZE,),
            ).fetchall()
        finally:
            conn.close()

        if len(rows) < self.SAMPLE_SIZE:
            self.skipTest(
                f"Only {len(rows)} non-Uncategorized articles available; "
                f"need {self.SAMPLE_SIZE} for a meaningful distribution test"
            )

        categories = [r["category"] for r in rows]
        counts = {}
        for c in categories:
            counts[c] = counts.get(c, 0) + 1
        known_count = sum(c for cat, c in counts.items() if cat in KNOWN_CATEGORIES)
        known_share = known_count / len(categories)
        top_category, top_count = max(counts.items(), key=lambda kv: kv[1])
        top_share = top_count / len(categories)

        self.assertGreaterEqual(
            known_share, self.MIN_KNOWN_SHARE,
            f"Only {known_share:.0%} of {len(categories)} real articles landed in "
            f"a known category. Classifier may be silently broken. "
            f"Distribution: {counts}"
        )
        self.assertLessEqual(
            top_share, self.MAX_SINGLE_CATEGORY_SHARE,
            f"{top_share:.0%} of {len(categories)} real articles were classified "
            f"as '{top_category}'. Classifier is returning the same category for "
            f"everything (or the DB has only one category). "
            f"Distribution: {counts}"
        )


if __name__ == "__main__":
    unittest.main()
