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
import sys
import unittest
from pathlib import Path

BASE = Path(__file__).parent.parent
sys.path.insert(0, str(BASE))

from news_tool import classify_article, EMBEDDING_AVAILABLE, _classify_keywords, evaluate_classifier_accuracy


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

MINIMUM_ACCURACY = 0.90


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
        self.assertIsInstance(result["by_category"], dict)
        self.assertGreater(result["total"], 0)
        self.assertGreaterEqual(result["accuracy"], 0.0)
        self.assertLessEqual(result["accuracy"], 1.0)


if __name__ == "__main__":
    unittest.main()
