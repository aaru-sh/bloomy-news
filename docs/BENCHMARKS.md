# Performance Benchmarks

This project uses [pytest-benchmark](https://pytest-benchmark.readthedocs.io/) for
automated performance regression testing across scrapers, the classifier, and the
database layer.

## Running Benchmarks

```bash
# Run all benchmarks and save results
bash scripts/run_benchmarks.sh

# Run a specific benchmark file
python -m pytest tests/benchmarks/test_database_benchmarks.py --benchmark-only

# Run a specific class or test
python -m pytest tests/benchmarks/test_classifier_benchmarks.py::TestClassifierPerCategoryBenchmarks::test_classify_llm --benchmark-only

# Compare with a previous run (requires saved JSON)
python -m pytest tests/benchmarks/ --benchmark-only --benchmark-compare=benchmark_results/benchmarks.json
```

## Comparing Benchmarks Across Commits

1. **Save baseline results** on the main branch:
   ```bash
   bash scripts/run_benchmarks.sh   # writes benchmark_results/benchmarks.json
   git add benchmark_results/benchmarks.json
   git commit -m "chore: update benchmark baseline"
   ```

2. **Run benchmarks** on a feature branch and compare:
   ```bash
   python -m pytest tests/benchmarks/ --benchmark-only --benchmark-compare=benchmark_results/benchmarks.json
   ```

3. **CI integration** (future): run benchmarks on every PR, post a summary
   comment with regressions highlighted, and fail the check if any test
   regresses by more than 20%.

## Interpreting Results

Each benchmark produces:

| Column | Meaning |
|--------|---------|
| `min` | Fastest iteration time |
| `max` | Slowest iteration time |
| `mean` | Average iteration time |
| `stddev` | Standard deviation across iterations |
| `rounds` | Number of iterations run |
| `iqr` | Interquartile range (spread of the middle 50%) |
| `ops` | Operations per second (1/mean) |
| `rounds` | Total iterations completed |

**What to look for:**
- A large `stddev` relative to `mean` indicates unstable benchmarks (check for background processes).
- A drop in `ops` across commits signals a regression.
- The `iqr` column is more robust than `stddev` for detecting regressions when iteration counts are low.

## Benchmark Categories

### Scraper Benchmarks (`test_scraper_benchmarks.py`)

Measure pure parsing throughput for each scraper's core logic.
Network I/O is mocked — benchmarks isolate CPU work only.

- **RSS parsing** (`parse_rss`): feedparser path for RSS 2.0 and Atom feeds
- **RSS regex fallback** (`_parse_rss_regex`): legacy regex parser
- **GitHub HTML parsing**: regex-based trending page extraction
- **Large feed parsing**: 20-item feed (the per-feed cap)

### Database Benchmarks (`test_database_benchmarks.py`)

Measure SQLite read/write performance on a seeded temporary database
(500 articles). Isolates DB logic from network and parsing.

- **`store_article`**: single-article insert with dedup check (10 rounds)
- **`store_article` with embedding**: insert with float32 vector blob (10 rounds)
- **`is_duplicate` URL match**: URL-based dedup hit (50 rounds)
- **`is_duplicate` no match**: unique article path (50 rounds)
- **`is_duplicate` title similarity**: fuzzy title matching (50 rounds)
- **`get_articles` limit=10**: small result set (20 rounds)
- **`get_articles` limit=100**: large result set (10 rounds)
- **`get_articles` by category**: filtered query (20 rounds)
- **`get_articles` by source**: filtered query (20 rounds)
- **`get_articles` search**: FTS5/full-text search (20 rounds)
- **`get_bookmarks`**: JSON file read (10 rounds)

### Classifier Benchmarks (`test_classifier_benchmarks.py`)

Measure classification latency per category and across both classification
paths (keyword vs embedding).

- **Per-category classification**: one benchmark per known category
- **Unknown input**: articles with no category signal
- **Keyword-only benchmarks**: isolate the keyword path for latency comparison
- **Batch classification**: classify all 6 categories sequentially

## CI Integration (Planned)

Future CI workflow:
1. Run benchmarks on every PR against `main`.
2. Compare results with the checked-in baseline (`benchmark_results/benchmarks.json`).
3. Post a summary comment on the PR with regressions (>20% slower) highlighted.
4. Fail the check if any benchmark regresses by more than 20%.

To opt out of CI benchmarks, add `@pytest.mark.slow` to specific tests and
filter with `-m "not slow"` in the workflow.
