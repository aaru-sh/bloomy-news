"""Article classifier: embedding-based (primary) with keyword fallback.

Architecture: the embedding classifier (sentence-transformers +
centroid-based similarity over CATEGORY_EXAMPLES) is the primary
path. On any failure (model load error, network, OOM) the failure is
cached in _embedding_load_failed and the keyword classifier takes
over permanently for the rest of the process - we never want a
single transient error to drop the whole pipeline.

The keyword classifier uses the pre-filtered keyword sets defined
in scrapers._keywords. The unfiltered constants (CATEGORY_KEYWORDS,
SUBCATEGORY_KEYWORDS) are kept around for tests that want to inspect
the canonical keyword sets.
"""
import sys
from typing import Any, Dict, List, Optional, Tuple

from scrapers._http import Article, ArticleList
from scrapers._keywords import (
    _FILTERED_CATEGORY_KEYWORDS,
    _FILTERED_SUBCATEGORY_KEYWORDS,
    _tokenize,
    _keyword_tokens,
)

ArticleDict = Article
ArticleListType = ArticleList
ClassifyResult = Tuple[str, float, List[str], str, Any]

KEYWORD_MINIMUM_ACCURACY = 0.80
EMBEDDING_MINIMUM_ACCURACY = 0.95
COMBINED_MINIMUM_ACCURACY = 0.90

try:
    from sentence_transformers import SentenceTransformer
    import numpy as np
    EMBEDDING_AVAILABLE = True
except ImportError:
    EMBEDDING_AVAILABLE = False

_embedding_model: Optional[Any] = None
_category_embeddings: Optional[Dict[str, Any]] = None
_embedding_load_failed: bool = False
_embedding_load_error: Optional[str] = None

CATEGORY_EXAMPLES: Dict[str, List[str]] = {
    'LLM': [
        'GPT-5 rumored to launch in Q3 with multimodal capabilities',
        'Claude 4 introduces 1M token context window',
        'OpenAI releases fine-tuning API for GPT-4o',
        'Llama 3.1 405B matches GPT-4 on reasoning benchmarks',
        'Mistral releases Mixtral 8x22B mixture-of-experts model',
        'Gemini Pro 1.5 handles hour-long video prompts',
        'RLHF training improves alignment in instruction-following models',
        'Chain-of-thought prompting boosts math reasoning on GSM8K',
        'Researchers probe hallucination rates in retrieval-augmented LLMs',
        'Anthropic publishes constitutional AI methods paper',
        'Anthropic releases Claude API with extended context for developers',
        'New transformer architecture for large language models achieves SOTA on benchmarks',
        'In-context learning lets small models match fine-tuned baselines',
        'Tokenization choices affect downstream multilingual performance',
    ],
    'Neural-Nets': [
        'Vision Transformers outperform CNNs on ImageNet at scale',
        'Diffusion models achieve state-of-the-art image synthesis',
        'New attention mechanism reduces transformer memory 4x',
        'GANs generate realistic medical images for training augmentation',
        'LSTM networks revisited for long-range sequence modeling',
        'Batch normalization alternatives: GroupNorm and LayerNorm compared',
        'Recurrent neural networks for time-series forecasting',
        'Convolutional layers replaced by MLPs in vision backbones',
        'Embedding layers analyzed for knowledge representation',
        'Encoder-decoder architectures for machine translation',
        'Training stability improved via gradient clipping heuristics',
        'Activation functions surveyed: GELU, SiLU, Mish, ReLU',
    ],
    'ML-Research': [
        'New benchmark MMLU-Pro tests multi-step reasoning across subjects',
        'Reinforcement learning beats humans at Diplomacy',
        'Self-supervised learning on ImageNet closes gap to supervised',
        'Few-shot classification via prototypical networks',
        'Unsupervised clustering methods compared on real-world datasets',
        'Statistical learning theory bounds generalization for deep nets',
        'Convergence guarantees proven for stochastic gradient descent variants',
        'Precision-recall tradeoffs analyzed for imbalanced classification',
        'Active learning reduces labeling cost by 10x on NLP tasks',
        'Curriculum learning improves training efficiency on vision tasks',
        'Meta-learning enables quick adaptation to new tasks',
        'Robustness benchmarks reveal out-of-distribution failures',
    ],
    'AI-Applications': [
        'GitHub Copilot launches agent mode for autonomous refactoring',
        'Notion AI rolls out Q&A across team workspaces',
        'Salesforce Einstein Copilot automates sales pipeline workflows',
        'Adobe Firefly Video generates clips from text prompts',
        'Midjourney v6 introduces style reference and character consistency',
        'OpenAI launches Operator agent for browser automation',
        'Anthropic Claude debuts computer use API for desktop control',
        'Enterprise customers deploy retrieval-augmented chat for support',
        'Startup ships AI code reviewer that catches 40% of production bugs',
        'Healthcare startup gets FDA clearance for AI radiology assistant',
        'AI video editor Descript adds multi-track generation',
        'Productivity tools integrate AI assistants for meeting summaries',
    ],
    'Finance': [
        'S&P 500 closes at record high on cooling inflation data',
        'Apple reports record quarterly earnings beating estimates',
        'Federal Reserve holds interest rates steady at 5.25-5.50%',
        'Bitcoin surges past $100K on ETF inflows',
        'Ethereum spot ETF approved by SEC',
        'Tesla cuts prices again amid weak demand in China',
        'Nvidia market cap briefly tops $3 trillion on AI chip demand',
        'Goldman Sachs upgrades Microsoft to buy on Azure growth',
        'Treasury yields fall as jobs report signals slowdown',
        'Oil prices drop on OPEC+ production cut disagreement',
        'Hedge fund returns 40% betting on regional bank recovery',
        'IPO market reopens as Reddit and Astera Labs price above range',
    ],
    'Cybersecurity': [
        'Critical CVE-2024-3094 in xz-utils enables SSH backdoor',
        'Ransomware group LockBit disrupted by international law enforcement',
        'Microsoft patches actively exploited zero-day in Windows kernel',
        'MoveIt Transfer breach affects hundreds of organizations',
        'Phishing campaign targets Microsoft 365 admins with OAuth abuse',
        'APT29 linked to Russian SVR uses new GraphicalProton malware',
        'Snowflake customer breaches traced to credential reuse attacks',
        'CISA warns of nation-state attacks on critical infrastructure',
        'LastPass breach update reveals encrypted vaults were stolen',
        'Firefox and Chrome patch high-severity use-after-free bugs',
        'Penetration testing frameworks compared: Metasploit vs Cobalt Strike',
        'Forensic analysis of supply chain attack on 3CX desktop app',
    ],
}


def _get_embedding_model() -> Tuple[Optional[Any], Optional[Dict[str, Any]]]:
    """Load the sentence-transformer model and pre-compute category centroids.

    Centroids are the mean of embeddings over a curated list of example
    article titles per category (CATEGORY_EXAMPLES). Centroid-based
    classification consistently outperforms single-description similarity
    on this codebase: a single 12-word description is essentially an
    arbitrary point in embedding space, while the centroid of 10-12
    representative titles is a stable class prototype.

    This is called from _classify_embedding() and is cached on first
    successful load. On any failure (network, HF rate limit, OOM, etc.)
    the failure is cached in _embedding_load_failed and the keyword
    classifier takes over permanently for the rest of the process.
    """
    global _embedding_model, _category_embeddings, _embedding_load_failed, _embedding_load_error
    if _embedding_model is None and _embedding_load_failed is False:
        try:
            _embedding_model = SentenceTransformer('all-MiniLM-L6-v2')
            _category_embeddings = {}
            for cat, examples in CATEGORY_EXAMPLES.items():
                vecs = _embedding_model.encode(examples, convert_to_numpy=True)
                _category_embeddings[cat] = vecs.mean(axis=0)
        except Exception as exc:
            _embedding_load_failed = True
            _embedding_load_error = str(exc)
            sys.stderr.write(
                "warning: sentence-transformers model load failed, "
                f"falling back to keyword classifier: {exc}\n"
            )
    return _embedding_model, _category_embeddings


def _classify_embedding(article: Article) -> ClassifyResult:
    global EMBEDDING_AVAILABLE
    title = article.get('title', '') or ''
    summary = article.get('summary', '') or ''
    text = f"{title}. {summary}".strip()
    if not text or text == '.':
        return 'Uncategorized', 0.0, [], 'news', None

    model, cat_embs = _get_embedding_model()
    if model is None:
        EMBEDDING_AVAILABLE = False
        return _classify_keywords(article)
    text_emb = model.encode(text, convert_to_numpy=True)
    text_norm = np.linalg.norm(text_emb)
    if text_norm == 0:
        return 'Uncategorized', 0.0, [], 'news', None

    if cat_embs is None:
        return 'Uncategorized', 0.0, [], 'news', None

    scores: Dict[str, float] = {}
    for cat, cat_emb in cat_embs.items():
        cat_norm = np.linalg.norm(cat_emb)
        if cat_norm == 0:
            scores[cat] = 0.0
        else:
            scores[cat] = float(np.dot(text_emb, cat_emb) / (text_norm * cat_norm))

    best_cat = max(scores, key=lambda c: scores[c])
    best_score = scores[best_cat]

    if best_score < 0.15:
        return 'Uncategorized', 0.0, [], 'news', None

    return best_cat, round(best_score, 4), [best_cat], 'news', text_emb


def _classify_keywords(article: Article) -> ClassifyResult:
    # Multi-word keywords require ALL of their tokens to appear in the text
    # (in any order); single-word keywords require exact token membership.
    # This eliminates substring false positives (e.g. "social security" ->
    # Cybersecurity via the bare word "security", "small" -> ML via the
    # substring "ml" inside "small").
    text_tokens = _tokenize(f"{article.get('title', '')} {article.get('summary', '')}")

    def keyword_matches(kw: str) -> bool:
        kw_tokens = _keyword_tokens(kw)
        if not kw_tokens:
            return False
        if len(kw_tokens) == 1:
            return next(iter(kw_tokens)) in text_tokens
        return kw_tokens.issubset(text_tokens)

    scores: Dict[str, int] = {}
    for cat, keywords in _FILTERED_CATEGORY_KEYWORDS.items():
        scores[cat] = sum(1 for kw in keywords if keyword_matches(kw))

    max_score = max(scores.values(), default=0)

    if max_score == 0:
        return "Uncategorized", 0.0, [], "news", None

    primary = max(scores, key=lambda c: scores[c])
    confidence = min(max_score / 5.0, 1.0)

    threshold = max_score * 0.5
    tags = [cat for cat, score in scores.items() if cat != primary and score >= threshold]

    # Determine subcategory
    subcategory = "news"
    if primary in _FILTERED_SUBCATEGORY_KEYWORDS:
        subcats = _FILTERED_SUBCATEGORY_KEYWORDS[primary]
        best_subcat = "news"
        best_score = 0
        for subcat_name, subcat_keywords in subcats.items():
            subcat_score = sum(1 for kw in subcat_keywords if keyword_matches(kw))
            if subcat_score > best_score:
                best_score = subcat_score
                best_subcat = subcat_name
        if best_score > 0:
            subcategory = best_subcat

    return primary, confidence, tags, subcategory, None


def classify_article(article: Article) -> ClassifyResult:
    if EMBEDDING_AVAILABLE:
        return _classify_embedding(article)
    return _classify_keywords(article)
