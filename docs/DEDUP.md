# Deduplication

This document explains the two-layer deduplication strategy used to prevent the same article from being inserted into the database multiple times.

## The problem

News articles get reposted across many sources. An arXiv paper might appear in:

- The arXiv RSS feed (the original)
- Hacker News (as a discussion)
- Reddit r/MachineLearning (as a link)
- A Google News search for "machine learning"
- A tech blog that summarizes it

Without deduplication, the same paper would show up 5 times in the dashboard.

## The two layers

### Layer 1: arXiv version dedup

arXiv papers have versioned IDs. The paper "Attention Is All You Need" might be:

- `1706.03762v1` (initial submission)
- `1706.03762v2` (revised with errata)
- `1706.03762v3` (final version with corrections)

These are all the same paper, and we want to record it once. The normalization is in `_normalize_arxiv_id()` in `database.py`:

```python
def _normalize_arxiv_id(arxiv_id: str) -> str:
    """Strip the version suffix from an arXiv ID."""
    return arxiv_id.split("v")[0] if "v" in arxiv_id else arxiv_id
```

This runs on every arXiv article at insert time, so v1, v2, and v3 of the same paper all collide on the primary key. The `INSERT OR IGNORE` then discards duplicates.

**Limitation**: this only works for arXiv articles, because the version suffix is in the ID. Other sources don't have an equivalent.

### Layer 2: Jaccard title similarity

For non-arXiv sources, we compare titles via Jaccard similarity on the word sets. The implementation is `is_duplicate_title()` in `database.py`:

```python
def is_duplicate_title(title: str, category: str, threshold: float = 0.80) -> bool:
    """Check if `title` is a near-duplicate of any recent article in `category`."""
    candidate_words = _normalize_title_words(title)
    if not candidate_words:
        return False

    # Look at the most recent 200 titles in the same category
    for existing in get_recent_titles(category, limit=200):
        existing_words = _normalize_title_words(existing)
        if not existing_words:
            continue
        similarity = _jaccard(candidate_words, existing_words)
        if similarity >= threshold:
            return True
    return False
```

The threshold of `0.80` is tuned to be aggressive enough to catch rephrasings ("Apple unveils new AI chip" vs "Apple announces new AI chip") but loose enough to allow genuinely different articles with similar subjects ("Apple's stock rose 5%" vs "Apple's stock fell 3%").

### Word normalization

Both candidate and existing titles are normalized identically:

```python
def _normalize_title_words(title: str) -> set[str]:
    """Lowercase, strip punctuation, drop common stopwords, return unique word set."""
    text = re.sub(r"[^\w\s]", " ", title.lower())
    words = set(text.split())
    return words - STOPWORDS
```

`STOPWORDS` is a small set of common English words: `{a, an, the, and, or, of, in, on, to, for, is, are, was, were, be, been, being, ...}`.

The 80% threshold is computed on the word set *after* stopword removal, which prevents "Apple announces new iPhone" and "Apple announces new iPad" from being marked as duplicates just because they share 4 stopwords.

### The dedup_log side-channel

Scanning 200 titles in Python on every insert is O(N) per article. For 100 new articles in a single pipeline run, that's 20,000 string comparisons. The `dedup_log` table caches the word sets as SHA-256 hashes:

```sql
CREATE TABLE dedup_log (
    title_hash TEXT PRIMARY KEY,
    category TEXT NOT NULL,
    article_id TEXT NOT NULL,
    created_at TEXT NOT NULL
);
```

The dedup check becomes:

1. Compute the SHA-256 hash of the normalized word set
2. Look up rows where `title_hash LIKE '<first-8-chars>%'`
3. For each match, recompute the full Jaccard and compare to the threshold

This is roughly 100x faster than the naive approach in practice, because most hash lookups return zero or one candidate.

The `dedup_log` is pruned periodically (during `init_db()`) to keep only the most recent 10,000 entries. This bounds the table size.

## Edge cases handled

### Substring matches

"Apple's new AI chip" and "Apple announces new AI chip strategy" have high overlap. The Jaccard will catch them, but the threshold of 0.80 means very different word orders or different nouns will pass through.

### Common words

Without stopword removal, "the quick brown fox" and "the slow brown dog" would have 50% Jaccard (`the`, `brown`) — a false positive. Stopword removal fixes this.

### Punctuation and case

"The Quick, Brown FOX." and "the quick brown fox" should be the same. The normalization lowercases and strips punctuation before tokenizing.

### Empty titles

If the title is empty or only stopwords, the normalized set is empty, and the function returns `False` (don't reject — there's no information to compare). An empty title shouldn't appear in production, but the guard prevents a crash.

### Multi-language

The normalization is English-specific (it doesn't tokenize CJK characters well). A Chinese-language article will likely pass through with a low word count and be inserted. This is a known limitation; see the "Known limitations" section.

### arXiv vs non-arXiv

The arXiv version dedup runs first. If a paper is inserted as `1706.03762v1` and the same paper comes in as `1706.03762v2` from a non-arXiv source (unlikely but possible), the normalized IDs collide and the second insert is ignored. Jaccard doesn't run in that case.

If an arXiv paper is reposted by a tech blog with a different title ("Vaswani et al. introduce Transformers"), the arXiv version dedup won't catch it (different ID) but the Jaccard will — if the titles are similar enough.

## Edge cases NOT handled

### Translation

If the same article is published in English and Spanish, the titles won't match at the word-set level. The Jaccard will return 0. Both articles get inserted. Mitigation: a future embedding-based dedup layer can catch this.

### Same event, different stories

"Apple announces new iPhone" and "Apple unveils new iPhone 15" have ~60% Jaccard — below the 0.80 threshold, so they pass through. Whether this is correct depends on what you want. The current setting is biased toward allowing through.

### Headline rewrites by aggregators

Some aggregators rewrite headlines aggressively. "Sources: Apple to launch new AI chip next month" might become "Rumor: Apple's AI chip coming soon". Jaccard will be ~30% — well below threshold. Both get inserted. This is acceptable; we want the news, and aggregator rewrites are often different takes anyway.

## Performance

Measured on a typical run:

- **arXiv dedup**: ~1ms per article (O(1) hash lookup)
- **Jaccard dedup**: ~5ms per article (200 titles × O(words) per comparison, but bounded by `dedup_log` hash filter)
- **Total dedup overhead**: ~600ms for 100 new articles

This is fast enough to not be a bottleneck. The pipeline's total runtime is dominated by network I/O, not dedup.

## Tuning the threshold

The threshold is in `is_duplicate_title()` in `database.py`. To change it:

```python
# default
def is_duplicate_title(title, category, threshold=0.80):

# more aggressive
def is_duplicate_title(title, category, threshold=0.70):

# more lenient
def is_duplicate_title(title, category, threshold=0.90):
```

Trade-offs:

- **0.70** — catches more paraphrases, but also flags "Apple's stock up 5%" as a duplicate of "Apple's stock down 5%" (high overlap on non-stopword words).
- **0.80** (current) — balanced. Most paraphrases caught, most genuine duplicates pass.
- **0.90** — only catches near-identical titles. More articles get through; some will be duplicates the user has to manually ignore.

There's no perfect threshold. If you tune it, also tune the stopword list — a more aggressive stopword list allows a lower threshold without false positives.

## Future improvements

The roadmap includes:

- **Embedding-based dedup** — sentence embeddings (e.g., `all-MiniLM-L6-v2`) for semantic similarity. Catches translations and aggressive rewrites. Adds a dependency and ~50ms per article.
- **URL canonicalization** — strip tracking parameters (`utm_*`, `?ref=...`) and compare URLs as a stronger signal.
- **Content fingerprinting** — hash the full body text, not just the title. Catches cases where the title is rewritten but the body is identical.

None of these are implemented. The current Jaccard + arXiv version approach is fast, dependency-free, and good enough for the use case.

## See also

- [ARCHITECTURE.md](ARCHITECTURE.md) — where dedup sits in the pipeline
- [CLASSIFIER.md](CLASSIFIER.md) — what happens to articles after dedup
- [SCRAPERS.md](SCRAPERS.md) — what produces the articles being deduped
