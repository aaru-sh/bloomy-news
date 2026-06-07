"""Database performance benchmarks for critical write and read paths.

Uses a temporary SQLite database for each benchmark session to avoid
contaminating the production news.db. The fixtures seed the database
with realistic article counts so benchmarks reflect real-world
query plans (index usage, FTS5, etc.).

Run with: python -m pytest tests/benchmarks/test_database_benchmarks.py --benchmark-only
"""
import json
import tempfile
import sqlite3
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

import database as db

# ---------------------------------------------------------------------------
# Fixtures: temporary database with seeded data
# ---------------------------------------------------------------------------
_SEED_ARTICLES = 500


@pytest.fixture(scope="module")
def bench_db(tmp_path_factory):
    """Create a temporary database seeded with _SEED_ARTICLES articles."""
    tmp_dir = tmp_path_factory.mktemp("bench_db")
    db_path = tmp_dir / "bench.db"
    original_db_path = db.DB_PATH

    db.DB_PATH = db_path
    db.init_db()

    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    try:
        for i in range(_SEED_ARTICLES):
            article = {
                "title": f"Benchmark article {i}: Topic {i % 20} about {'LLM' if i % 3 == 0 else 'Finance' if i % 3 == 1 else 'Cybersecurity'}",
                "url": f"https://example.com/article-{i}",
                "summary": f"This is a summary for benchmark article number {i}.",
                "source": ["techcrunch", "arxiv", "github", "bleepingcomputer"][i % 4],
                "category": ["LLM", "Finance", "Cybersecurity", "Neural-Nets", "ML-Research", "AI-Applications"][i % 6],
                "subcategory": "news",
                "published": f"2024-01-{(i % 28) + 1:02d}T10:00:00Z",
                "author": f"Author {i % 10}",
            }
            db.store_article(article, conn=conn)
        conn.commit()
    finally:
        conn.close()

    yield db_path

    db.DB_PATH = original_db_path


# ---------------------------------------------------------------------------
# store_article benchmarks
# ---------------------------------------------------------------------------
class TestStoreArticleBenchmarks:
    """Benchmark single-article insertion into the database."""

    def test_store_article(self, benchmark, bench_db):
        """Benchmark storing a single new article (with dedup check)."""
        counter = [_SEED_ARTICLES]

        def run():
            article = {
                "title": f"Benchmark store_article {counter[0]}",
                "url": f"https://example.com/store-{counter[0]}",
                "summary": "New article summary for benchmark.",
                "source": "benchmark",
                "category": "LLM",
                "subcategory": "news",
                "published": "2024-06-01T10:00:00Z",
            }
            counter[0] += 1
            return db.store_article(article)

        result = benchmark(run)
        assert result[0] is True  # new article stored

    def test_store_article_with_embedding(self, benchmark, bench_db):
        """Benchmark storing an article with an embedding vector."""
        import numpy as np

        counter = [_SEED_ARTICLES + 10000]

        def run():
            article = {
                "title": f"Benchmark embedding {counter[0]}",
                "url": f"https://example.com/emb-{counter[0]}",
                "summary": "Article with embedding for benchmark.",
                "source": "benchmark",
                "category": "Neural-Nets",
                "subcategory": "news",
                "published": "2024-06-01T10:00:00Z",
            }
            embedding = np.random.rand(db.EMBEDDING_DIM).astype(db.EMBEDDING_DTYPE)
            counter[0] += 1
            return db.store_article(article, embedding=embedding)

        result = benchmark(run)
        assert result[0] is True


# ---------------------------------------------------------------------------
# is_duplicate benchmarks
# ---------------------------------------------------------------------------
class TestIsDuplicateBenchmarks:
    """Benchmark duplicate detection for various input shapes."""

    def test_is_duplicate_url_match(self, benchmark, bench_db):
        """Benchmark is_duplicate when the URL already exists."""
        def run():
            return db.is_duplicate(
                "Nonexistent title",
                "https://example.com/article-100",  # exists in seed data
            )

        result = benchmark(run)
        assert result[0] is True  # found duplicate by URL

    def test_is_duplicate_no_match(self, benchmark, bench_db):
        """Benchmark is_duplicate with a unique URL and title."""
        counter = [_SEED_ARTICLES + 20000]

        def run():
            result = db.is_duplicate(
                f"Unique title {counter[0]}",
                f"https://example.com/unique-{counter[0]}",
            )
            counter[0] += 1
            return result

        result = benchmark(run)
        assert result[0] is False

    def test_is_duplicate_title_similarity(self, benchmark, bench_db):
        """Benchmark is_duplicate title-similarity fallback path."""
        # Article-0 title: "Benchmark article 0: Topic 0 about LLM"
        def run():
            return db.is_duplicate(
                "Benchmark article 0: Topic 0 about LLM",
                "https://example.com/does-not-exist",
            )

        result = benchmark(run)
        # May or may not find a match depending on similarity threshold
        assert isinstance(result[0], bool)


# ---------------------------------------------------------------------------
# get_articles benchmarks
# ---------------------------------------------------------------------------
class TestGetArticlesBenchmarks:
    """Benchmark article retrieval with various filters and limits."""

    def test_get_articles_limit_10(self, benchmark, bench_db):
        """Benchmark retrieving the 10 most recent articles."""
        result = benchmark(lambda: db.get_articles(limit=10))
        assert isinstance(result, list)
        assert len(result) == 10

    def test_get_articles_limit_100(self, benchmark, bench_db):
        """Benchmark retrieving the 100 most recent articles."""
        result = benchmark(lambda: db.get_articles(limit=100))
        assert isinstance(result, list)
        assert len(result) == 100

    def test_get_articles_by_category(self, benchmark, bench_db):
        """Benchmark retrieving articles filtered by category."""
        result = benchmark(lambda: db.get_articles(category="LLM", limit=20))
        assert isinstance(result, list)

    def test_get_articles_by_source(self, benchmark, bench_db):
        """Benchmark retrieving articles filtered by source."""
        result = benchmark(lambda: db.get_articles(source="techcrunch", limit=20))
        assert isinstance(result, list)

    def test_get_articles_search(self, benchmark, bench_db):
        """Benchmark FTS5/like-based search."""
        result = benchmark(lambda: db.get_articles(search="LLM", limit=20))
        assert isinstance(result, list)


# ---------------------------------------------------------------------------
# get_bookmarks / bookmark operations
# ---------------------------------------------------------------------------
class TestBookmarkBenchmarks:
    """Benchmark bookmark-related operations."""

    def test_get_bookmarks(self, benchmark, bench_db):
        """Benchmark reading bookmarks from JSON file."""
        result = benchmark(db.get_bookmarks)
        assert isinstance(result, list)
