#!/usr/bin/env python3
"""Bloomy News Excavator - pipeline orchestrator.

This module is the slim entry point: it composes the 8 scrapers from
the scrapers/ package, hands each article to classifier.classify_article,
persists via database.store_article, then calls telegram.post_to_telegram.

The scraper, classifier, and Telegram logic live in their own modules.
This file re-exports the public symbols so existing tests and external
callers continue to work via `from news_tool import scrape_arxiv, ...`
and `news_tool.scrape_arxiv()` attribute access.
"""
import importlib.util
import json
import logging
import os
import shutil
import sys
import time
import urllib.request
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Tuple

import database
from config import get_finnhub_key, get_newsapi_key, get_telegram_token

from scrapers import (
    Article,
    ArticleList,
    CATEGORY_KEYWORDS,
    SUBCATEGORY_KEYWORDS,
    STOPWORDS,
    fetch_json,
    fetch_url,
    parse_rss,
    resolve_google_news_redirect,
    scrape_arxiv,
    scrape_cybersec,
    scrape_finance,
    scrape_github,
    scrape_google_news,
    scrape_markets,
    scrape_newsapi,
    scrape_tech,
    _FILTERED_CATEGORY_KEYWORDS,
    _FILTERED_SUBCATEGORY_KEYWORDS,
    _filter_keywords,
    _keyword_tokens,
    _parse_rss_regex,
    _tokenize,
)
from classifier import (
    CATEGORY_EXAMPLES,
    ClassifyResult,
    EMBEDDING_AVAILABLE,
    KEYWORD_MINIMUM_ACCURACY,
    EMBEDDING_MINIMUM_ACCURACY,
    COMBINED_MINIMUM_ACCURACY,
    _classify_embedding,
    _classify_keywords,
    classify_article,
)
from telegram import (
    CategoryMap,
    TELEGRAM_CATEGORIES,
    TELEGRAM_EMOJIS,
    TELEGRAM_LIMIT_PER_CAT,
    _format_digest,
    _select_top_articles,
    _send_telegram_message,
    post_to_telegram,
)

BASE = Path(__file__).parent.resolve()

LOG_DIR = BASE / "logs"
LOG_DIR.mkdir(exist_ok=True)

logger = logging.getLogger(__name__)


def _load_labeled_samples() -> List[Tuple[str, str, str]]:
    """Load LABELED_SAMPLES from tests/test_classifier.py.

    Importing the test module gives a single source of truth: when the
    labeled set is updated for a new release, the accuracy eval picks
    it up automatically.
    """
    test_path = BASE / "tests" / "test_classifier.py"
    spec = importlib.util.spec_from_file_location("_classifier_tests_eval", test_path)
    if spec is None or spec.loader is None:
        raise RuntimeError("failed to load test_classifier.py for accuracy eval")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return list(mod.LABELED_SAMPLES)


def evaluate_classifier_accuracy(limit: int = 200) -> dict:
    """Run the labeled sample set through both classifiers.

    Returns {"correct": N, "total": T, "accuracy": P, "by_category": {...}}
    where "correct" counts a sample as correct if EITHER classifier
    produced the expected category. Per-classifier accuracy and a
    per-category breakdown are also returned. Prints a one-line CLI
    summary.
    """
    samples = _load_labeled_samples()[:limit]

    keyword_correct = 0
    embedding_correct = 0
    combined_correct = 0
    by_category: Dict[str, Dict[str, int]] = {}

    for title, summary, expected in samples:
        article = {"title": title, "summary": summary}

        kw_cat, _, _, _, _ = _classify_keywords(article)
        kw_match = (kw_cat == expected)
        if kw_match:
            keyword_correct += 1

        emb_cat, _, _, _, _ = _classify_embedding(article)
        emb_match = (emb_cat == expected)
        if emb_match:
            embedding_correct += 1

        if kw_match or emb_match:
            combined_correct += 1

        cat_stats = by_category.setdefault(
            expected,
            {"total": 0, "keyword_correct": 0, "embedding_correct": 0,
             "combined_correct": 0},
        )
        cat_stats["total"] += 1
        if kw_match:
            cat_stats["keyword_correct"] += 1
        if emb_match:
            cat_stats["embedding_correct"] += 1
        if kw_match or emb_match:
            cat_stats["combined_correct"] += 1

    total = len(samples)
    accuracy = combined_correct / total if total else 0.0
    keyword_accuracy = keyword_correct / total if total else 0.0
    embedding_accuracy = embedding_correct / total if total else 0.0

    summary_line = (
        f"Accuracy: {accuracy*100:.1f}% ({combined_correct}/{total})  "
        f"keyword={keyword_accuracy*100:.1f}%  "
        f"embedding={embedding_accuracy*100:.1f}%"
    )
    print(summary_line)

    return {
        "correct": combined_correct,
        "total": total,
        "accuracy": accuracy,
        "keyword_accuracy": keyword_accuracy,
        "embedding_accuracy": embedding_accuracy,
        "by_category": by_category,
    }


def main() -> None:
    logger.info("=" * 60)
    logger.info("Bloomy NEWS EXCAVATOR - Starting")
    logger.info("=" * 60)

    database.init_db()

    print("\nPHASE 1: SCRAPING")
    print("-" * 40)
    rate_limit = float(os.environ.get('ARXIV_RATE_LIMIT', '3.0'))
    print(f"  arXiv rate limit: {rate_limit}s per feed")

    all_articles: ArticleList = []
    scrapers = [
        ("arXiv", scrape_arxiv),
        ("GitHub", scrape_github),
        ("NewsAPI", scrape_newsapi),
        ("Cybersecurity", scrape_cybersec),
        ("Finance", scrape_finance),
        ("Tech", scrape_tech),
        ("Google News", scrape_google_news),
        ("Markets", scrape_markets),
    ]

    error_count = 0
    for name, scraper in scrapers:
        try:
            articles = scraper()
            all_articles.extend(articles)
            logger.info(f"{name}: {len(articles)} articles")
        except Exception as e:
            error_count += 1
            logger.error(f"{name} scraper failed: {e}")
            print(f"  ERROR: {name} scraper failed: {e}")

    all_articles = [a for a in all_articles if a.get('title') and len(a['title']) > 10]
    print(f"\n  Total scraped: {len(all_articles)}")

    print("\nPHASE 2: CLASSIFY & STORE")
    print("-" * 40)

    categorized: CategoryMap = defaultdict(list)
    new_count = dup_count = 0

    conn = database.get_connection()
    try:
        for article in all_articles:
            category, confidence, tags, subcategory, embedding = classify_article(article)
            article['category'] = category
            article['confidence'] = confidence
            article['tags'] = tags
            article['subcategory'] = subcategory

            is_new, article_id = database.store_article(article, conn=conn, embedding=embedding)
            if is_new:
                new_count += 1
                categorized[category].append(article)
                logger.info(f"Stored: {article['title'][:60]} -> {category} (conf={confidence:.2f})")
            else:
                dup_count += 1
                logger.info(f"Duplicate: {article['title'][:60]}")

        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()

    classifier_mode = "embedding" if EMBEDDING_AVAILABLE else "keyword (install sentence-transformers for better accuracy)"
    print(f"  Classifier: {classifier_mode}")
    print(f"  New: {new_count} | Duplicates: {dup_count}")
    for cat in sorted(categorized.keys()):
        print(f"  {cat}: {len(categorized[cat])}")

    print("\nPHASE 3: TELEGRAM")
    print("-" * 40)

    try:
        post_to_telegram(categorized)
    except Exception as e:
        logger.error(f"Telegram posting failed: {e}")
        print(f"  ERROR: Telegram failed: {e}")

    print("\nPHASE 4: MAINTENANCE")
    print("-" * 40)

    raw_dir = BASE / "raw"
    if raw_dir.exists():
        shutil.rmtree(raw_dir, ignore_errors=True)
        logger.info("Cleaned up raw data directory")
        print("  Raw files cleaned")

    deleted = database.cleanup_old_articles()
    if deleted:
        print(f"  Pruned {deleted} articles older than {database.MAX_ARTICLE_AGE_DAYS} days")
    else:
        print(f"  No articles older than {database.MAX_ARTICLE_AGE_DAYS} days to prune")

    print("\n" + "=" * 60)
    print("  DONE!")
    print(f"  Scraped: {len(all_articles)} | New: {new_count} | Duplicates: {dup_count} | Errors: {error_count}")
    print(f"  Database: {database.DB_PATH}")
    print("=" * 60)

    logger.info(f"Pipeline complete: {len(all_articles)} scraped, {new_count} new, {dup_count} duplicates, {error_count} errors")


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "evaluate":
        print(json.dumps(evaluate_classifier_accuracy(), indent=2))
    else:
        main()
