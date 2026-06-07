#!/usr/bin/env python3
"""Benchmarking suite for the Bloomy News pipeline.

Measures performance of: scrapers (parsing only, mocked HTTP),
classifier (keyword + optional embedding), SQLite database operations,
and dashboard server HTTP responses.  Outputs a formatted table and
saves raw results to JSON for cross-run comparison.

Usage:
    python scripts/benchmark.py                  # full benchmark
    python scripts/benchmark.py --scraper-only   # scrapers only
    python scripts/benchmark.py --db-only        # database only
    python scripts/benchmark.py --server-only    # server only
    python scripts/benchmark.py --output out.json
    python scripts/benchmark.py --compare previous.json
"""
import argparse
import hashlib
import http.server
import json
import os
import re
import socket
import sys
import tempfile
import threading
import time
import urllib.request
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
from unittest.mock import patch

# ---------------------------------------------------------------------------
# Ensure the project root is importable
# ---------------------------------------------------------------------------
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

# ---------------------------------------------------------------------------
# Synthetic fixture data
# ---------------------------------------------------------------------------
MOCK_RSS_TEMPLATE = """\
<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0">
<channel>
  <title>{title}</title>
  <link>https://example.com</link>
  <description>Benchmark feed</description>
  {items}
</channel>
</rss>"""

MOCK_RSS_ITEM = """\
<item>
  <title>{title}</title>
  <link>https://example.com/article/{idx}</link>
  <description>Summary for article {idx} about {topic}.</description>
  <pubDate>Mon, 01 Jan 2026 12:00:00 +0000</pubDate>
  <author>Bench Author</author>
</item>"""

MOCK_GITHUB_HTML = """\
<html><body>
<article>
  <h2><a href="/user/repo-{idx}">user / repo-{idx}</a></h2>
  <p class="col-9">A {topic} repository</p>
</article>
</body></html>"""

MOCK_NEWSAPI_JSON = {
    "status": "ok",
    "articles": [
        {"title": f"NewsAPI article {i}", "url": f"https://newsapi.example.com/{i}",
         "description": f"Description for article {i}", "source": {"name": "NewsAPI"},
         "publishedAt": "2026-01-01T00:00:00Z"}
        for i in range(10)
    ],
}

CATEGORIES = ["LLM", "Neural-Nets", "ML-Research", "AI-Applications", "Finance", "Cybersecurity"]

SAMPLE_ARTICLES: List[Dict[str, Any]] = [
    {"title": "GPT-5 launched with multimodal reasoning capabilities",
     "url": "https://example.com/gpt5", "summary": "OpenAI releases GPT-5 with vision, audio, and tool-use.",
     "source": "TechCrunch", "published": "2026-06-01T10:00:00Z", "category": "", "tags": []},
    {"title": "Critical CVE in Linux kernel allows privilege escalation",
     "url": "https://example.com/cve", "summary": "A critical zero-day vulnerability affects all kernel versions.",
     "source": "BleepingComputer", "published": "2026-06-01T11:00:00Z", "category": "", "tags": []},
    {"title": "Bitcoin surges past $120K on ETF inflows",
     "url": "https://example.com/btc", "summary": "Bitcoin hits new all-time high driven by institutional demand.",
     "source": "Reuters", "published": "2026-06-01T12:00:00Z", "category": "", "tags": []},
    {"title": "Diffusion models surpass GANs on ImageNet benchmarks",
     "url": "https://example.com/diffusion", "summary": "New diffusion architecture sets SOTA on ImageNet classification.",
     "source": "arXiv", "published": "2026-06-01T13:00:00Z", "category": "", "tags": []},
    {"title": "GitHub Copilot adds autonomous refactoring agent",
     "url": "https://example.com/copilot", "summary": "Copilot can now refactor entire codebases with a single prompt.",
     "source": "GitHub", "published": "2026-06-01T14:00:00Z", "category": "", "tags": []},
    {"title": "Reinforcement learning beats humans at Diplomacy",
     "url": "https://example.com/rl-diplomacy", "summary": "Meta AI demonstrates superhuman play in the board game Diplomacy.",
     "source": "Meta AI", "published": "2026-06-01T15:00:00Z", "category": "", "tags": []},
    {"title": "Vision Transformers outperform CNNs at scale",
     "url": "https://example.com/vit", "summary": "ViT-Large achieves state-of-the-art on ImageNet-21k.",
     "source": "Google Research", "published": "2026-06-01T16:00:00Z", "category": "", "tags": []},
    {"title": "S&P 500 closes at record high on cooling inflation",
     "url": "https://example.com/sp500", "summary": "U.S. equities rally as inflation data comes in below expectations.",
     "source": "CNBC", "published": "2026-06-01T17:00:00Z", "category": "", "tags": []},
    {"title": "Ransomware group disrupted by international operation",
     "url": "https://example.com/ransomware", "summary": "Law enforcement seizes infrastructure of major ransomware group.",
     "source": "TheHackersNews", "published": "2026-06-01T18:00:00Z", "category": "", "tags": []},
    {"title": "Claude 4 introduces 1M token context window",
     "url": "https://example.com/claude4", "summary": "Anthropic releases Claude 4 with a 1M context window.",
     "source": "Anthropic", "published": "2026-06-01T19:00:00Z", "category": "", "tags": []},
]


def _build_rss_xml(source_key: str, n_items: int = 15, topic: str = "technology") -> str:
    items = "\n".join(
        MOCK_RSS_ITEM.format(title=f"{source_key} Article {i}", idx=i, topic=topic)
        for i in range(n_items)
    )
    return MOCK_RSS_TEMPLATE.format(title=source_key, items=items)


def _make_articles(n: int) -> List[Dict[str, Any]]:
    """Return n articles cycled from SAMPLE_ARTICLES with unique URLs."""
    out = []
    for i in range(n):
        base = SAMPLE_ARTICLES[i % len(SAMPLE_ARTICLES)]
        a = dict(base)
        a["url"] = f"{base['url']}-{i}"
        a["title"] = f"{base['title']} #{i}"
        out.append(a)
    return out


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def _now() -> float:
    return time.perf_counter()


def _fmt_time(seconds: float) -> str:
    if seconds < 0.001:
        return f"{seconds * 1_000_000:.0f} us"
    if seconds < 1.0:
        return f"{seconds * 1000:.1f} ms"
    return f"{seconds:.2f} s"


def _fmt_rate(count: int, seconds: float) -> str:
    if seconds == 0:
        return "inf"
    rate = count / seconds
    if rate < 1:
        return f"{rate:.2f} art/s"
    return f"{rate:.0f} art/s"


# ---------------------------------------------------------------------------
# 1. Scraper benchmarks (mock HTTP, measure parsing only)
# ---------------------------------------------------------------------------
def bench_scrapers() -> Dict[str, Any]:
    print("\n" + "=" * 60)
    print("SCRAPER BENCHMARKS  (HTTP mocked, parsing only)")
    print("=" * 60)

    from scrapers._rss import parse_rss
    from scrapers.github import scrape_github
    from scrapers.newsapi import scrape_newsapi
    from scrapers._http import fetch_url, fetch_json

    results: Dict[str, Any] = {}

    # --- RSS-based scrapers ------------------------------------------------
    rss_sources = {
        "arxiv":       ("arxiv",       15, "machine learning"),
        "tech":        ("techcrunch",  15, "technology"),
        "cybersec":    ("cybersec",    12, "cybersecurity"),
        "finance":     ("YahooFinance",12, "finance"),
        "google_news": ("google-news", 15, "artificial intelligence"),
        "markets":     ("CNBC",        10, "markets"),
    }

    for label, (source_key, n_items, topic) in rss_sources.items():
        rss_xml = _build_rss_xml(source_key, n_items, topic)
        t0 = _now()
        articles = parse_rss(rss_xml, source_key)
        elapsed = _now() - t0
        count = len(articles)
        results[label] = {
            "count": count,
            "elapsed_s": round(elapsed, 6),
            "rate": round(count / elapsed, 1) if elapsed > 0 else 0,
        }
        print(f"  {label:15s}  {count:3d} articles  {_fmt_time(elapsed):>10s}  "
              f"({_fmt_rate(count, elapsed)})")

    # --- GitHub (HTML parsing) ---------------------------------------------
    html_pages = [MOCK_GITHUB_HTML.format(idx=i, topic="python") for i in range(3)]

    def mock_fetch_url(url, **kwargs):
        idx = int(re.search(r"/(\d+)", url).group(1)) if re.search(r"/(\d+)", url) else 0
        return html_pages[idx % len(html_pages)]

    with patch("scrapers.github.fetch_url", side_effect=mock_fetch_url):
        t0 = _now()
        arts = scrape_github()
        elapsed = _now() - t0
        count = len(arts)
        results["github"] = {
            "count": count,
            "elapsed_s": round(elapsed, 6),
            "rate": round(count / elapsed, 1) if elapsed > 0 else 0,
        }
        print(f"  {'github':15s}  {count:3d} articles  {_fmt_time(elapsed):>10s}  "
              f"({_fmt_rate(count, elapsed)})")

    # --- NewsAPI (JSON parsing) ---------------------------------------------
    with patch("scrapers.newsapi.fetch_json", return_value=MOCK_NEWSAPI_JSON):
        with patch("scrapers.newsapi.get_newsapi_key", return_value="fake-key"):
            t0 = _now()
            arts = scrape_newsapi()
            elapsed = _now() - t0
            count = len(arts)
            results["newsapi"] = {
                "count": count,
                "elapsed_s": round(elapsed, 6),
                "rate": round(count / elapsed, 1) if elapsed > 0 else 0,
            }
            print(f"  {'newsapi':15s}  {count:3d} articles  {_fmt_time(elapsed):>10s}  "
                  f"({_fmt_rate(count, elapsed)})")

    # --- Aggregate ----------------------------------------------------------
    total_articles = sum(r["count"] for r in results.values())
    total_time = sum(r["elapsed_s"] for r in results.values())
    results["_aggregate"] = {
        "total_articles": total_articles,
        "total_time_s": round(total_time, 6),
        "avg_rate": round(total_articles / total_time, 1) if total_time > 0 else 0,
    }
    print(f"\n  TOTAL: {total_articles} articles in {_fmt_time(total_time)} "
          f"({_fmt_rate(total_articles, total_time)})")
    return results


# ---------------------------------------------------------------------------
# 2. Classifier benchmarks
# ---------------------------------------------------------------------------
def bench_classifier() -> Dict[str, Any]:
    print("\n" + "=" * 60)
    print("CLASSIFIER BENCHMARKS")
    print("=" * 60)

    from classifier import _classify_keywords, _classify_embedding, EMBEDDING_AVAILABLE

    articles = _make_articles(100)
    results: Dict[str, Any] = {}

    # --- Keyword classifier ------------------------------------------------
    t0 = _now()
    for a in articles:
        _classify_keywords(a)
    elapsed = _now() - t0
    results["keyword"] = {
        "count": 100,
        "elapsed_s": round(elapsed, 6),
        "rate": round(100 / elapsed, 1) if elapsed > 0 else 0,
    }
    print(f"  {'keyword':15s}  100 articles  {_fmt_time(elapsed):>10s}  "
          f"({_fmt_rate(100, elapsed)})")

    # --- Embedding classifier (if available) --------------------------------
    if EMBEDDING_AVAILABLE:
        t0 = _now()
        for a in articles:
            _classify_embedding(a)
        elapsed = _now() - t0
        results["embedding"] = {
            "count": 100,
            "elapsed_s": round(elapsed, 6),
            "rate": round(100 / elapsed, 1) if elapsed > 0 else 0,
        }
        print(f"  {'embedding':15s}  100 articles  {_fmt_time(elapsed):>10s}  "
              f"({_fmt_rate(100, elapsed)})")
    else:
        results["embedding"] = {"status": "unavailable"}
        print(f"  {'embedding':15s}  (not installed)")

    return results


# ---------------------------------------------------------------------------
# 3. Database benchmarks
# ---------------------------------------------------------------------------
def bench_database() -> Dict[str, Any]:
    print("\n" + "=" * 60)
    print("DATABASE BENCHMARKS  (isolated temp DB)")
    print("=" * 60)

    import database as db

    results: Dict[str, Any] = {}

    # Create isolated temp database
    tmp_dir = tempfile.mkdtemp(prefix="bench_db_")
    tmp_db = Path(tmp_dir) / "bench.db"

    # Monkey-patch DB_PATH
    original_db_path = db.DB_PATH
    db.DB_PATH = tmp_db
    try:
        db.init_db()

        articles = _make_articles(100)

        # --- store_article (100 articles) -----------------------------------
        t0 = _now()
        stored_ids = []
        for a in articles:
            is_new, aid = db.store_article(a)
            if aid is not None:
                stored_ids.append(aid)
        elapsed = _now() - t0
        results["store_article"] = {
            "count": len(stored_ids),
            "elapsed_s": round(elapsed, 6),
            "rate": round(len(stored_ids) / elapsed, 1) if elapsed > 0 else 0,
        }
        print(f"  {'store_article':25s}  {len(stored_ids):3d} ops  {_fmt_time(elapsed):>10s}  "
              f"({_fmt_rate(len(stored_ids), elapsed)})")

        # --- get_articles (various sizes) -----------------------------------
        for limit in [10, 50, 100, 500]:
            t0 = _now()
            rows = db.get_articles(limit=limit)
            elapsed = _now() - t0
            results[f"get_articles_{limit}"] = {
                "count": len(rows),
                "elapsed_s": round(elapsed, 6),
                "rate": round(len(rows) / elapsed, 1) if elapsed > 0 else 0,
            }
            print(f"  {'get_articles':25s}  limit={limit:<4d}  {_fmt_time(elapsed):>10s}  "
                  f"(returned {len(rows)})")

        # --- is_duplicate (100 lookups) -------------------------------------
        t0 = _now()
        for a in articles[:100]:
            db.is_duplicate(a["title"], a["url"], a.get("summary", ""))
        elapsed = _now() - t0
        results["is_duplicate"] = {
            "count": 100,
            "elapsed_s": round(elapsed, 6),
            "rate": round(100 / elapsed, 1) if elapsed > 0 else 0,
        }
        print(f"  {'is_duplicate':25s}  100 ops  {_fmt_time(elapsed):>10s}  "
              f"({_fmt_rate(100, elapsed)})")

        # --- cleanup_old_articles(30) ---------------------------------------
        # Insert some old articles to make cleanup meaningful
        old_article = {
            "title": "Old article from last year",
            "url": "https://example.com/old-1",
            "summary": "This is an old article.",
            "published": "2024-01-01T00:00:00Z",
            "category": "LLM",
            "source": "test",
        }
        for i in range(5):
            a = dict(old_article)
            a["url"] = f"https://example.com/old-{i}"
            a["title"] = f"Old article {i}"
            db.store_article(a)

        t0 = _now()
        deleted = db.cleanup_old_articles(30)
        elapsed = _now() - t0
        results["cleanup_old_articles"] = {
            "count": deleted,
            "elapsed_s": round(elapsed, 6),
        }
        print(f"  {'cleanup_old_articles(30)':25s}  {_fmt_time(elapsed):>10s}  "
              f"(deleted {deleted})")

    finally:
        db.DB_PATH = original_db_path
        # Cleanup temp files
        try:
            tmp_db.unlink(missing_ok=True)
            Path(tmp_dir).rmdir()
        except OSError:
            pass

    return results


# ---------------------------------------------------------------------------
# 4. Server benchmarks
# ---------------------------------------------------------------------------
def bench_server() -> Dict[str, Any]:
    print("\n" + "=" * 60)
    print("SERVER BENCHMARKS  (embedded server on random port)")
    print("=" * 60)

    import database as db

    results: Dict[str, Any] = {}

    port = _free_port()
    host = "127.0.0.1"

    # Import the handler from serve.py
    sys.path.insert(0, str(PROJECT_ROOT / "dashboard"))
    from serve import DashboardHandler

    # Ensure data file exists with some content for the server to serve
    data_dir = PROJECT_ROOT / "dashboard" / "data"
    data_dir.mkdir(parents=True, exist_ok=True)
    data_file = data_dir / "dashboard_data.json"

    # Generate minimal data if absent
    if not data_file.exists():
        sample = {"generated": datetime.now(timezone.utc).date().isoformat(),
                  "stats": {"total": 0, "today": 0, "categories": {}},
                  "articles": []}
        with open(data_file, "w", encoding="utf-8") as f:
            json.dump(sample, f)

    server = http.server.ThreadingHTTPServer((host, port), DashboardHandler)
    server_thread = threading.Thread(target=server.serve_forever, daemon=True)
    server_thread.start()
    time.sleep(0.1)  # let the server bind

    base = f"http://{host}:{port}"

    try:
        # --- Cold /api/articles ---------------------------------------------
        t0 = _now()
        with urllib.request.urlopen(f"{base}/api/articles", timeout=5) as resp:
            body = resp.read()
            status_cold = resp.status
        elapsed_cold = _now() - t0
        results["articles_cold"] = {
            "status": status_cold,
            "elapsed_s": round(elapsed_cold, 6),
            "payload_bytes": len(body),
        }
        print(f"  {'GET /api/articles':25s}  cold  {_fmt_time(elapsed_cold):>10s}  "
              f"({len(body):,} bytes, {status_cold})")

        # --- Warm /api/articles (3 requests) --------------------------------
        warm_times = []
        for _ in range(3):
            t0 = _now()
            with urllib.request.urlopen(f"{base}/api/articles", timeout=5) as resp:
                resp.read()
            warm_times.append(_now() - t0)
        avg_warm = sum(warm_times) / len(warm_times)
        results["articles_warm"] = {
            "requests": 3,
            "avg_elapsed_s": round(avg_warm, 6),
            "min_elapsed_s": round(min(warm_times), 6),
            "max_elapsed_s": round(max(warm_times), 6),
        }
        print(f"  {'GET /api/articles':25s}  warm x3  {_fmt_time(avg_warm):>10s}  "
              f"(min {_fmt_time(min(warm_times))})")

        # --- /api/bookmarks -------------------------------------------------
        t0 = _now()
        with urllib.request.urlopen(f"{base}/api/bookmarks", timeout=5) as resp:
            bm_body = resp.read()
            status_bm = resp.status
        elapsed_bm = _now() - t0
        results["bookmarks"] = {
            "status": status_bm,
            "elapsed_s": round(elapsed_bm, 6),
            "payload_bytes": len(bm_body),
        }
        print(f"  {'GET /api/bookmarks':25s}          {_fmt_time(elapsed_bm):>10s}  "
              f"({len(bm_body):,} bytes, {status_bm})")

        # --- /api/stats -----------------------------------------------------
        t0 = _now()
        with urllib.request.urlopen(f"{base}/api/stats", timeout=5) as resp:
            stats_body = resp.read()
            status_st = resp.status
        elapsed_st = _now() - t0
        results["stats"] = {
            "status": status_st,
            "elapsed_s": round(elapsed_st, 6),
            "payload_bytes": len(stats_body),
        }
        print(f"  {'GET /api/stats':25s}             {_fmt_time(elapsed_st):>10s}  "
              f"({len(stats_body):,} bytes, {status_st})")

    finally:
        server.shutdown()

    return results


# ---------------------------------------------------------------------------
# 5. Report generation
# ---------------------------------------------------------------------------
def _print_summary(all_results: Dict[str, Any]) -> None:
    print("\n" + "=" * 60)
    print("BENCHMARK SUMMARY")
    print("=" * 60)
    print(f"{'Component':<30s} {'Metric':<25s} {'Value':>15s}")
    print("-" * 70)

    if "scrapers" in all_results:
        agg = all_results["scrapers"].get("_aggregate", {})
        print(f"{'Scrapers':30s} {'total articles':25s} {agg.get('total_articles', 0):>15d}")
        print(f"{'':30s} {'total time':25s} {_fmt_time(agg.get('total_time_s', 0)):>15s}")
        print(f"{'':30s} {'avg rate':25s} {_fmt_rate(agg.get('total_articles', 0), agg.get('total_time_s', 1)):>15s}")

    if "classifier" in all_results:
        kw = all_results["classifier"].get("keyword", {})
        print(f"{'Classifier (keyword)':30s} {'100 articles':25s} {_fmt_time(kw.get('elapsed_s', 0)):>15s}")
        emb = all_results["classifier"].get("embedding", {})
        if emb.get("status") != "unavailable":
            print(f"{'Classifier (embedding)':30s} {'100 articles':25s} {_fmt_time(emb.get('elapsed_s', 0)):>15s}")

    if "database" in all_results:
        db_r = all_results["database"]
        sa = db_r.get("store_article", {})
        sa_count = sa.get("count", 0)
        sa_time = sa.get("elapsed_s", 0)
        print(f"{'Database store_article':30s} {str(sa_count) + ' ops':25s} {_fmt_time(sa_time):>15s}")
        dup = db_r.get("is_duplicate", {})
        dup_count = dup.get("count", 0)
        dup_time = dup.get("elapsed_s", 0)
        print(f"{'Database is_duplicate':30s} {str(dup_count) + ' ops':25s} {_fmt_time(dup_time):>15s}")

    if "server" in all_results:
        srv = all_results["server"]
        cold = srv.get("articles_cold", {})
        print(f"{'Server /api/articles':30s} {'cold':25s} {_fmt_time(cold.get('elapsed_s', 0)):>15s}")
        warm = srv.get("articles_warm", {})
        print(f"{'':30s} {'warm avg':25s} {_fmt_time(warm.get('avg_elapsed_s', 0)):>15s}")

    print("-" * 70)


def _compare(current: Dict[str, Any], previous: Dict[str, Any]) -> None:
    print("\n" + "=" * 60)
    print("COMPARISON WITH PREVIOUS RUN")
    print("=" * 60)
    print(f"{'Metric':<35s} {'Previous':>12s} {'Current':>12s} {'Delta':>12s}")
    print("-" * 70)

    comparisons = [
        ("Scrapers total articles", "scrapers", "_aggregate", "total_articles"),
        ("Scrapers total time (s)", "scrapers", "_aggregate", "total_time_s"),
        ("Classifier keyword 100 art (s)", "classifier", "keyword", "elapsed_s"),
        ("DB store_article (s)", "database", "store_article", "elapsed_s"),
        ("DB is_duplicate (s)", "database", "is_duplicate", "elapsed_s"),
        ("Server articles cold (s)", "server", "articles_cold", "elapsed_s"),
        ("Server articles warm avg (s)", "server", "articles_warm", "avg_elapsed_s"),
    ]

    for label, section, key, metric in comparisons:
        prev_val = current.get(section, {}).get(key, {}).get(metric)
        curr_val = previous.get(section, {}).get(key, {}).get(metric)
        if prev_val is None or curr_val is None:
            continue
        try:
            delta = curr_val - prev_val
            if isinstance(prev_val, float) and prev_val != 0:
                pct = (delta / prev_val) * 100
                delta_str = f"{delta:+.4f} ({pct:+.1f}%)"
            else:
                delta_str = f"{delta:+g}"
        except TypeError:
            delta_str = "N/A"
        print(f"{label:35s} {prev_val:>12g} {curr_val:>12g} {delta_str:>12s}")

    print("-" * 70)


# ---------------------------------------------------------------------------
# 6. CLI
# ---------------------------------------------------------------------------
def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="Benchmark the Bloomy News pipeline components.",
    )
    group = p.add_mutually_exclusive_group()
    group.add_argument("--scraper-only", action="store_true",
                       help="Only benchmark scrapers")
    group.add_argument("--db-only", action="store_true",
                       help="Only benchmark database operations")
    group.add_argument("--server-only", action="store_true",
                       help="Only benchmark the dashboard server")
    group.add_argument("--classifier-only", action="store_true",
                       help="Only benchmark the classifier")
    p.add_argument("--output", type=str, default=None,
                   help="Custom output path for results JSON")
    p.add_argument("--compare", type=str, default=None,
                   help="Path to previous benchmark results to compare")
    return p.parse_args()


def main() -> None:
    args = parse_args()
    run_bench = not (args.scraper_only or args.db_only
                     or args.server_only or args.classifier_only)

    print(f"News Pipeline Benchmark  --  {datetime.now(timezone.utc).isoformat()}")
    print(f"Python {sys.version}")

    all_results: Dict[str, Any] = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "python": sys.version,
    }

    if run_bench or args.scraper_only:
        all_results["scrapers"] = bench_scrapers()

    if run_bench or args.classifier_only:
        all_results["classifier"] = bench_classifier()

    if run_bench or args.db_only:
        all_results["database"] = bench_database()

    if run_bench or args.server_only:
        all_results["server"] = bench_server()

    _print_summary(all_results)

    # Save results
    out_path = args.output or str(PROJECT_ROOT / "benchmark_results.json")
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(all_results, f, indent=2, ensure_ascii=False)
    print(f"\nResults saved to: {out_path}")

    # Compare with previous run
    if args.compare:
        prev_path = Path(args.compare)
        if prev_path.exists():
            with open(prev_path, "r", encoding="utf-8") as f:
                previous = json.load(f)
            _compare(all_results, previous)
        else:
            print(f"\nWarning: comparison file not found: {prev_path}")


if __name__ == "__main__":
    main()
