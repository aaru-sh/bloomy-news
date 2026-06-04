# Classifier

This document explains how `classify_article()` decides which of the 6 categories an article belongs to, how the keyword table is structured, and how to tune it.

## The 6 categories

| Category          | What it covers                                           |
| ----------------- | -------------------------------------------------------- |
| `LLM`             | Large language models, prompt engineering, fine-tuning, instruction tuning, RLHF |
| `Neural-Nets`     | Novel neural network architectures, training methods, theoretical results |
| `ML-Research`     | General ML research: computer vision, NLP, RL, optimization, benchmarks |
| `AI-Applications` | Production AI products, AI in industry, AI tools, generative AI for non-research use cases |
| `Finance`         | Stock market, trading, fintech, Fed policy, macroeconomics (only as it relates to markets) |
| `Cybersecurity`   | Vulnerabilities, breaches, malware, threat actors, security research |
| `Uncategorized`   | Fallback when no keyword matches above the threshold     |

The first 6 are mutually exclusive. `Uncategorized` is the default when nothing else fits.

## The classification algorithm

`classify_article(title, summary, source=None, arxiv_category=None)` returns `(category, confidence, tags, subcategory)`.

### Step 1: arXiv prior (if applicable)

If `source` starts with `arXiv` and `arxiv_category` is set, the arXiv subject category is mapped to one of the 6 categories with high confidence (≥0.9) and used as the primary signal.

```python
ARXIV_CATEGORY_MAP = {
    "cs.CL":  "LLM",              # Computation and Language
    "cs.AI":  "AI-Applications",  # Artificial Intelligence (general)
    "cs.LG":  "ML-Research",      # Machine Learning
    "cs.NE":  "Neural-Nets",      # Neural and Evolutionary Computing
    "cs.CR":  "Cybersecurity",    # Cryptography and Security
    "cs.CV":  "ML-Research",      # Computer Vision
    "cs.RO":  "AI-Applications",  # Robotics
    "stat.ML": "ML-Research",     # Machine Learning (stat)
    "q-fin.CP": "Finance",        # Computational Finance
    "q-fin.TR": "Finance",        # Trading and Market Microstructure
    "q-fin.PM": "Finance",        # Portfolio Management
    "q-fin.RM": "Finance",        # Risk Management
    "q-fin.ST": "Finance",        # Statistical Finance
}
```

The mapping is intentionally opinionated. arXiv's `cs.AI` is a broad bucket; we map it to `AI-Applications` because most cs.AI papers are about deploying AI, not novel AI research (which goes in `cs.LG` or `cs.NE`).

If the arXiv category isn't in the map, we fall through to the keyword scoring.

### Step 2: keyword scoring

The article's title and summary are concatenated, lowercased, and tokenized on word boundaries. Each token is matched against `CATEGORY_KEYWORDS`:

```python
CATEGORY_KEYWORDS = {
    "LLM": [
        ("llm", 3.0), ("large language model", 3.0), ("gpt", 2.0), ("claude", 2.0),
        ("gemini", 2.0), ("llama", 2.0), ("prompt", 1.5), ("fine-tun", 2.0),
        # ... ~50 keywords
    ],
    "Neural-Nets": [
        ("transformer", 1.5), ("attention", 1.0), ("neural network", 2.0),
        ("backprop", 2.0), ("gradient descent", 1.5),
        # ...
    ],
    # ... etc
}
```

Each keyword has a weight. Title matches get 1.5x the weight, summary matches get 1.0x. The scores are summed per category, and the highest-scoring category wins.

### Step 3: confidence calculation

Confidence is the top score divided by the sum of all scores. This is a 0-1 ratio:

- `1.0` — one category scored all the keywords; unambiguous
- `0.5` — top category has half the total mass; the article could go either way
- `0.0` — no keyword matched anything; falls into `Uncategorized`

### Step 4: tags

All keywords that matched (across all categories, not just the winner) are returned as a `tags` list, capped at 5. The original keyword strings are used, not the canonical forms.

For example, an article about "GPT-4 fine-tuning with LoRA" might be tagged:
- `["gpt", "fine-tun", "lora"]`

These tags are used by the dashboard for client-side filtering and by the Telegram poster for inline buttons.

### Step 5: subcategory

The subcategory is the first matched keyword in the winning category, lowercased and cleaned up. This gives a more specific label than the top-level category — e.g., `LLM / fine-tuning` or `Finance / trading`.

If no keyword matched in the winning category, the subcategory is `None`.

### Step 6: fallback

If the top score is 0 (no keywords matched), the function returns:

```python
("Uncategorized", 0.0, [], None)
```

This is the "I don't know" answer. It's better to admit uncertainty than to force an article into a category it doesn't belong in.

The previous version of the classifier forced any 0.5-confidence article into `AI-Applications`. This was a bug — `AI-Applications` became a junk drawer for anything the classifier was unsure about. The "Uncategorized" fallback fixes this.

## Threshold tuning

The current threshold is implicit: any non-zero top score wins. There is no minimum confidence cutoff.

If you want to require higher confidence, edit `classify_article()`:

```python
# before
return primary, confidence, tags, subcategory

# after
if confidence < 0.3:
    return "Uncategorized", 0.0, [], None
return primary, confidence, tags, subcategory
```

A threshold of 0.3 means "if the top category doesn't have at least 30% of the keyword mass, admit defeat". A threshold of 0.0 (current) means "any non-zero match wins".

The trade-off:

- **Lower threshold (current)** — more articles categorized, more chance of misclassification
- **Higher threshold** — fewer articles categorized, more "Uncategorized" articles, fewer misclassifications

There's no objectively correct answer. The current default is biased toward categorization (better UX in the dashboard) at the cost of some accuracy.

## Adding a new keyword

If you find a category is consistently misclassifying an article, add a keyword:

1. Find the category in `CATEGORY_KEYWORDS` in `news_tool.py`.
2. Add a `(keyword, weight)` tuple. Use a lowercase substring (so "gpt" matches "GPT-4", "Llama-3-70b" matches "llama", etc.).
3. If the keyword is multi-word, use it as a phrase ("large language model") — it will match the phrase as a whole.
4. Choose a weight between 0.5 (very general) and 3.0 (very specific). A weight of 1.0 is neutral.

Example:

```python
"LLM": [
    # ... existing keywords ...
    ("mixture of experts", 2.5),   # MoE papers are clearly LLM
    ("moe", 1.0),                  # matches "MoE", "moe", "mixture of experts" via substring
],
```

Be cautious with short keywords. `"ai"` matches too much (any paper mentioning "AI" gets a 1.0 boost to `LLM`). Prefer specific terms.

## Adding a new category

1. Add the category to the `CATEGORIES` list near the top of `news_tool.py`.
2. Add a `CATEGORY_KEYWORDS[<category>]` block with at least 5 keywords.
3. Add a color in `dashboard/app.js`, `dashboard/app-filters.js`, and `dashboard/app-bookmarks.js`:
   ```javascript
   var catColor = {
       // ... existing ...
       "Robotics": "#ff6b35",
   };
   ```
4. Add an icon and label in the same three files (`catIcons`, `catLabels`).
5. Add CSS color rules in `dashboard/style.css` under `panel-category[data-cat="..."]`.
6. Add a sub-channel ID to `config/telegram.json`.
7. Update the README's categories list.
8. Add a test in `tests/test_fixes.py` verifying that a sample article in the new category is classified correctly.

## Test coverage

The classifier is tested in `tests/test_fixes.py::TestClassifierFallback`:

- `test_llm_match` — a clearly-LLM article returns `LLM` as the category
- `test_no_match_returns_uncategorized` — a clearly-uncategorizable article returns `Uncategorized`
- `test_no_fallback_to_ai_applications` — a low-confidence article does NOT get forced into `AI-Applications`

To run just the classifier tests:

```bash
python -m unittest tests.test_fixes.TestClassifierFallback -v
```

## Known limitations

- **No semantic understanding** — the classifier can't tell that "transformer" and "self-attention" refer to the same concept, unless you add both as keywords.
- **No multi-language support** — keywords are English-only. A French AI paper will likely be `Uncategorized`.
- **No context** — "Apple's stock is up 5%" gets the same treatment as "Apple's new AI model is up 5%". The first is `Finance`, the second is `LLM`. The classifier sees the word "Apple" in both and shrugs.
- **Hand-tuned** — adding keywords is a code change, not a config change. The roadmap includes a config-driven keyword system and a feedback-trained classifier.

## See also

- [ARCHITECTURE.md](ARCHITECTURE.md) — where the classifier sits in the pipeline
- [DEDUP.md](DEDUP.md) — what happens before classification (deduplication)
- [SCRAPERS.md](SCRAPERS.md) — what produces the articles being classified
