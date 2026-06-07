"""Classifier performance benchmarks.

Measures the latency of classify_article across all categories and
both classification paths (keyword vs embedding). The embedding path
requires sentence-transformers; benchmarks skip gracefully when
unavailable so CI can run keyword-only benchmarks without GPU deps.

Run with: python -m pytest tests/benchmarks/test_classifier_benchmarks.py --benchmark-only
"""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from classifier import (
    classify_article,
    _classify_keywords,
    CATEGORY_EXAMPLES,
    EMBEDDING_AVAILABLE,
)


# ---------------------------------------------------------------------------
# Fixtures: representative articles for each category
# ---------------------------------------------------------------------------
CATEGORY_ARTICLES = {
    "LLM": {
        "title": "GPT-5 rumored to launch in Q3 with multimodal capabilities",
        "summary": "OpenAI's next-generation large language model promises major reasoning improvements.",
    },
    "Neural-Nets": {
        "title": "Vision Transformers outperform CNNs on ImageNet at scale",
        "summary": "New attention mechanism reduces transformer memory by 4x for image classification.",
    },
    "ML-Research": {
        "title": "Reinforcement learning beats humans at Diplomacy strategy game",
        "summary": "Self-supervised learning on ImageNet closes gap to supervised methods.",
    },
    "AI-Applications": {
        "title": "GitHub Copilot launches agent mode for autonomous refactoring",
        "summary": "Enterprise customers deploy retrieval-augmented chat for support.",
    },
    "Finance": {
        "title": "S&P 500 closes at record high on cooling inflation data",
        "summary": "Federal Reserve holds interest rates steady at 5.25-5.50%.",
    },
    "Cybersecurity": {
        "title": "Critical CVE-2024-3094 in xz-utils enables SSH backdoor",
        "summary": "Ransomware group LockBit disrupted by international law enforcement.",
    },
}

UNKNOWN_ARTICLE = {
    "title": "Local bakery wins award for best sourdough bread in town",
    "summary": "The annual baking competition saw over 200 entries this year.",
}


# ---------------------------------------------------------------------------
# Benchmark: classify_article for each category
# ---------------------------------------------------------------------------
class TestClassifierPerCategoryBenchmarks:
    """Benchmark classify_article latency for each known category."""

    def test_classify_llm(self, benchmark):
        """Benchmark classification of an LLM article."""
        article = CATEGORY_ARTICLES["LLM"]
        result = benchmark(classify_article, article)
        assert isinstance(result, tuple)
        assert len(result) == 5
        assert isinstance(result[0], str)

    def test_classify_neural_nets(self, benchmark):
        """Benchmark classification of a Neural-Nets article."""
        article = CATEGORY_ARTICLES["Neural-Nets"]
        result = benchmark(classify_article, article)
        assert isinstance(result, tuple)

    def test_classify_ml_research(self, benchmark):
        """Benchmark classification of an ML-Research article."""
        article = CATEGORY_ARTICLES["ML-Research"]
        result = benchmark(classify_article, article)
        assert isinstance(result, tuple)

    def test_classify_ai_applications(self, benchmark):
        """Benchmark classification of an AI-Applications article."""
        article = CATEGORY_ARTICLES["AI-Applications"]
        result = benchmark(classify_article, article)
        assert isinstance(result, tuple)

    def test_classify_finance(self, benchmark):
        """Benchmark classification of a Finance article."""
        article = CATEGORY_ARTICLES["Finance"]
        result = benchmark(classify_article, article)
        assert isinstance(result, tuple)

    def test_classify_cybersecurity(self, benchmark):
        """Benchmark classification of a Cybersecurity article."""
        article = CATEGORY_ARTICLES["Cybersecurity"]
        result = benchmark(classify_article, article)
        assert isinstance(result, tuple)

    def test_classify_unknown(self, benchmark):
        """Benchmark classification of an article with no category signal."""
        result = benchmark(classify_article, UNKNOWN_ARTICLE)
        assert isinstance(result, tuple)
        assert result[0] == "Uncategorized"

    def test_classify_empty_input(self, benchmark):
        """Benchmark classification of empty article."""
        result = benchmark(classify_article, {"title": "", "summary": ""})
        assert isinstance(result, tuple)
        assert result[0] == "Uncategorized"


# ---------------------------------------------------------------------------
# Benchmark: keyword-only classification
# ---------------------------------------------------------------------------
class TestKeywordClassifierBenchmarks:
    """Benchmark the keyword classification path directly."""

    def test_keyword_classify_llm(self, benchmark):
        """Benchmark keyword classification of an LLM article."""
        article = CATEGORY_ARTICLES["LLM"]
        result = benchmark(_classify_keywords, article)
        assert isinstance(result, tuple)
        assert result[0] in ("LLM", "AI-Applications", "Neural-Nets", "ML-Research")

    def test_keyword_classify_finance(self, benchmark):
        """Benchmark keyword classification of a Finance article."""
        article = CATEGORY_ARTICLES["Finance"]
        result = benchmark(_classify_keywords, article)
        assert isinstance(result, tuple)

    def test_keyword_classify_cybersecurity(self, benchmark):
        """Benchmark keyword classification of a Cybersecurity article."""
        article = CATEGORY_ARTICLES["Cybersecurity"]
        result = benchmark(_classify_keywords, article)
        assert isinstance(result, tuple)

    def test_keyword_classify_unknown(self, benchmark):
        """Benchmark keyword classification with no keyword matches."""
        result = benchmark(_classify_keywords, UNKNOWN_ARTICLE)
        assert isinstance(result, tuple)
        assert result[0] == "Uncategorized"

    @pytest.mark.skipif(not EMBEDDING_AVAILABLE, reason="sentence-transformers not installed")
    def test_keyword_vs_embedding_same_category(self, benchmark):
        """Benchmark keyword path alone for comparison with embedding path.

        The benchmark runs the keyword classifier; the embedding path
        is benchmarked separately via classify_article. This lets you
        compare keyword vs embedding latency in the benchmark report.
        """
        article = CATEGORY_ARTICLES["LLM"]
        result = benchmark(_classify_keywords, article)
        assert isinstance(result, tuple)


# ---------------------------------------------------------------------------
# Benchmark: batch classification
# ---------------------------------------------------------------------------
class TestClassifierBatchBenchmarks:
    """Benchmark classifying multiple articles in sequence."""

    def test_classify_all_categories(self, benchmark):
        """Benchmark classifying one article per category (6 total)."""
        articles = list(CATEGORY_ARTICLES.values())

        def run():
            return [classify_article(a) for a in articles]

        results = benchmark(run)
        assert len(results) == 6
        assert all(isinstance(r, tuple) for r in results)
