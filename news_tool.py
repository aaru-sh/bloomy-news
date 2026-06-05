#!/usr/bin/env python3
"""
Bloomy News Excavator - Pure Python News Scraper & Distributor.
"""
import json
import re
import urllib.request
import time
import html
import shutil
import logging
import sys
from pathlib import Path
from datetime import datetime, date
from collections import defaultdict

import database
from config import get_telegram_token, get_newsapi_key, get_finnhub_key

BASE = Path(__file__).parent.resolve()

KEYWORD_MINIMUM_ACCURACY = 0.80
EMBEDDING_MINIMUM_ACCURACY = 0.95
COMBINED_MINIMUM_ACCURACY = 0.90

LOG_DIR = BASE / "logs"
LOG_DIR.mkdir(exist_ok=True)

logging.basicConfig(
    filename=LOG_DIR / "pipeline.log",
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

CATEGORY_KEYWORDS = {
    "LLM": ["llm", "large language model", "gpt", "claude", "gemini", "chatgpt",
            "transformer", "bert", "llama", "mistral", "nlp", "text generation",
            "language model", "prompt", "fine-tuning", "rlhf"],
    "Neural-Nets": ["neural network", "deep learning", "cnn", "rnn", "lstm", "gan",
                    "diffusion", "attention mechanism", "backpropagation"],
    "ML-Research": ["machine learning", "reinforcement learning", "supervised",
                   "unsupervised", "clustering", "regression", "benchmark"],
    "AI-Applications": ["artificial intelligence", "ai application", "computer vision",
                       "speech recognition", "robotics", "autonomous", "ai tool"],
    "Finance": ["stock", "trading", "market", "investor", "portfolio", "dividend",
               "earnings", "financial", "economy", "fed", "interest rate"],
    "Cybersecurity": ["security", "cyber", "hack", "breach", "vulnerability", "malware",
                     "ransomware", "phishing", "firewall", "encryption", "zero-day"],
}

SUBCATEGORY_KEYWORDS = {
    "Finance": {
        "stocks": ["stock", "equity", "share", "nasdaq", "s&p", "dow", "ticker", "ipo",
                   "earnings", "dividend", "market cap", "shares"],
        "trading": ["trading", "trade", "options", "futures", "forex", "commodity", "day trading",
                   "volatility", "market move", "rally", "sell-off"],
        "key-figures": ["trump", "elon musk", "powell", "yellen", "buffett", "jensen huang",
                       "sam altman", "ceo", "cfo", "founder", "chairman", "congress",
                       "insider trading", "leadership", "executive"],
        "quant": ["quant", "quantitative", "algorithm", "hedge fund", "citadel", "renaissance",
                 "mathematical", "statistical", "model", "algo trading"],
    },
    "Cybersecurity": {
        "vulnerabilities": ["vulnerability", "exploit", "cve", "zero-day", "patch", "buffer overflow",
                           "security flaw", "security bug", "rce"],
        "threat-intel": ["apt", "threat", "attack", "campaign", "actor", "malware", "ransomware",
                        "threat report", "malware campaign", "threat actor"],
        "web-security": ["xss", "sqli", "injection", "csrf", "owasp", "web", "api security",
                        "web application", "web app"],
        "cloud-security": ["cloud", "aws", "azure", "gcp", "container", "kubernetes", "docker",
                          "cloud misconfig", "cloud security"],
    },
    "LLM": {
        "papers": ["arxiv", "paper", "research", "study", "benchmark", "evaluation",
                  "llm paper", "language model paper"],
        "releases": ["release", "launch", "announce", "update", "new model", "gpt", "claude",
                    "llama", "mistral", "gemini", "model release", "open source model"],
        "industry": ["funding", "acquisition", "partnership", "company", "startup", "investment",
                    "valuation", "ipo", "enterprise", "product launch"],
    },
    "Neural-Nets": {
        "architectures": ["architecture", "transformer", "cnn", "rnn", "lstm", "gan", "diffusion",
                         "attention mechanism", "neural architecture", "backbone"],
        "training": ["training", "optimization", "fine-tuning", "rlhf", "gradient", "loss function",
                    "learning rate", "batch size", "convergence"],
        "applications": ["application", "deploy", "inference", "real-world", "production",
                        "computer vision", "nlp", "speech", "recommendation"],
    },
    "ML-Research": {
        "papers": ["arxiv", "paper", "research", "study", "theorem", "proof",
                  "ml paper", "machine learning paper"],
        "benchmarks": ["benchmark", "leaderboard", "sota", "evaluation", "comparison",
                      "dataset", "metric", "accuracy", "performance"],
        "methods": ["method", "algorithm", "technique", "approach", "framework",
                   "novel", "proposed", "introduce"],
    },
    "AI-Applications": {
        "tools": ["tool", "api", "developer", "platform", "sdk", "library", "framework",
                 "open source", "github", "developer tool"],
        "agents": ["agent", "autonomous", "agentic", "tool use", "function calling",
                  "mcp", "multi-agent", "agent framework"],
        "creative": ["art", "music", "writing", "content creation", "image generation",
                    "video generation", "creative ai", "generative art", "design"],
    },
}

STOPWORDS = frozenset({
    "the", "a", "an", "is", "are", "of", "to", "in", "for", "on", "with", "and", "or",
})

_TOKEN_RE = re.compile(r"\b[\w'-]+\b")


def _tokenize(text):
    """Lowercase + tokenize text into a frozenset of word tokens."""
    if not text:
        return frozenset()
    return frozenset(_TOKEN_RE.findall(text.lower()))


def _keyword_tokens(keyword):
    """Lowercase + tokenize a keyword into a frozenset of word tokens."""
    if not keyword:
        return frozenset()
    return frozenset(_TOKEN_RE.findall(keyword.lower()))


def _filter_keywords(keywords):
    """Drop keywords that are < 3 chars or composed entirely of stopwords."""
    result = []
    for kw in keywords:
        if len(kw) < 3:
            continue
        toks = _keyword_tokens(kw)
        if not toks or toks.issubset(STOPWORDS):
            continue
        result.append(kw)
    return result


_FILTERED_CATEGORY_KEYWORDS = {
    cat: _filter_keywords(keywords) for cat, keywords in CATEGORY_KEYWORDS.items()
}
_FILTERED_SUBCATEGORY_KEYWORDS = {
    cat: {
        sub: _filter_keywords(sub_keywords)
        for sub, sub_keywords in subcats.items()
    }
    for cat, subcats in SUBCATEGORY_KEYWORDS.items()
}

SOURCE_NAMES = {
    "arxiv": "arXiv",
    "github": "GitHub",
    "newsapi": "NewsAPI",
    "google-news": "Google News",
    "bleepingcomputer": "BleepingComputer",
    "thehackersnews": "TheHackersNews",
    "finnhub": "Finnhub",
    "techcrunch": "TechCrunch",
    "reuters": "Reuters",
}

def fetch_url(url, timeout=20, retries=3):
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "Accept": "application/rss+xml, application/xml, text/xml, */*",
    }
    
    for attempt in range(retries):
        try:
            req = urllib.request.Request(url, headers=headers)
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                return resp.read().decode("utf-8", errors="replace")
        except Exception as e:
            logger.warning(f"Attempt {attempt + 1}/{retries} failed for {url}: {e}")
            if attempt < retries - 1:
                time.sleep(2 ** attempt)
    
    logger.error(f"All {retries} attempts failed for {url}")
    return None

def fetch_json(url, timeout=20):
    content = fetch_url(url, timeout)
    if content:
        try:
            return json.loads(content)
        except json.JSONDecodeError:
            return None
    return None

def parse_rss(xml_text, source_key):
    articles = []
    source_name = SOURCE_NAMES.get(source_key, source_key)

    items = re.findall(r'<item>(.*?)</item>', xml_text, re.DOTALL)
    if not items:
        items = re.findall(r'<entry>(.*?)</entry>', xml_text, re.DOTALL)

    for item in items[:20]:
        title = url = summary = published = ""
        author = ""

        t = re.search(r'<title[^>]*>(.*?)</title>', item, re.DOTALL)
        if t:
            title = re.sub(r'<!\[CDATA\[(.*?)\]\]>', r'\1', t.group(1)).strip()
            title = re.sub(r'<[^>]+>', '', title).strip()

        u = re.search(r'<link[^>]*>(.*?)</link>', item, re.DOTALL)
        if not u:
            u = re.search(r'<link[^>]*href="([^"]*)"', item)
        if u:
            url = re.sub(r'<[^>]+>', '', u.group(1)).strip()

        for tag in ['description', 'summary', 'content', 'content:encoded']:
            s = re.search(rf'<{tag}[^>]*>(.*?)</{tag}>', item, re.DOTALL)
            if s:
                summary = re.sub(r'<!\[CDATA\[(.*?)\]\]>', r'\1', s.group(1)).strip()
                summary = re.sub(r'<[^>]+>', '', summary).strip()
                break

        for tag in ['pubDate', 'published', 'updated', 'dc:date', 'atom:updated']:
            p = re.search(rf'<{tag}[^>]*>(.*?)</{tag}>', item, re.DOTALL)
            if p:
                published = p.group(1).strip()
                break

        a = re.search(r'<author[^>]*>(.*?)</author>', item, re.DOTALL)
        if a:
            author = re.sub(r'<[^>]+>', '', a.group(1)).strip()

        title = html.unescape(title)
        url = html.unescape(url)
        summary = html.unescape(summary)
        summary = re.sub(r'<[^>]+>', '', summary)

        if title and url:
            articles.append({
                "title": title,
                "url": url,
                "summary": summary[:600] if summary else "",
                "source": source_name,
                "source_key": source_key,
                "published": published,
                "author": author,
            })

    return articles

def scrape_arxiv():
    print("  [1/8] arXiv ML/AI papers...")
    feeds = [
        ("https://rss.arxiv.org/rss/cs.AI", "cs.AI"),
        ("https://rss.arxiv.org/rss/cs.LG", "cs.LG"),
        ("https://rss.arxiv.org/rss/cs.CL", "cs.CL"),
        ("https://rss.arxiv.org/rss/cs.CV", "cs.CV"),
    ]
    articles = []
    for url, cat in feeds:
        content = fetch_url(url)
        if content:
            arts = parse_rss(content, "arxiv")
            for a in arts:
                a["subcategory"] = cat
            articles.extend(arts)
    print(f"    Found {len(articles)} papers")
    return articles

def scrape_github():
    print("  [2/8] GitHub trending...")
    articles = []
    for lang in ["python", "jupyter-notebook", "rust"]:
        url = f"https://github.com/trending/{lang}?since=daily"
        content = fetch_url(url)
        if not content:
            continue
        repo_pattern = re.compile(
            r'<h2[^>]*>\s*<a href="(/[^"]*)"[^>]*>\s*([^<]*?)\s*/\s*([^<]*?)\s*</a>'
            r'(.*?)(?=<h2|</article)',
            re.DOTALL
        )
        desc_pattern = re.compile(r'<p class="col-9[^"]*">(.*?)</p>', re.DOTALL)
        for m in repo_pattern.finditer(content):
            path = m.group(1)
            owner = m.group(2)
            name = m.group(3).strip()
            rest = m.group(4)
            if not name:
                name = path.split("/")[-1]
            desc_m = desc_pattern.search(rest)
            if desc_m:
                desc = re.sub(r'<[^>]+>', '', desc_m.group(1)).strip()
            else:
                desc = ""
            if not desc:
                desc = f"Trending {lang} repository on GitHub"
            articles.append({
                "title": f"{owner.strip()}/{name.strip()}",
                "url": f"https://github.com{path}",
                "summary": desc,
                "source": "GitHub",
                "source_key": "github",
                "published": datetime.now().isoformat(),
            })
            if len([a for a in articles if a.get('source_key') == 'github']) >= 10:
                break
    print(f"    Found {len(articles)} repos")
    return articles

def scrape_newsapi():
    print("  [3/8] NewsAPI...")
    api_key = get_newsapi_key()

    if not api_key or api_key.startswith("YOUR_"):
        print("    Skipped - no API key")
        return []

    articles = []
    for cat in ["technology", "science", "business"]:
        url = f"https://newsapi.org/v2/top-headlines?country=us&category={cat}&pageSize=15&apiKey={api_key}"
        data = fetch_json(url)
        if data and data.get("status") == "ok":
            for item in data.get("articles", [])[:10]:
                articles.append({
                    "title": item.get("title", ""),
                    "url": item.get("url", ""),
                    "summary": item.get("description", "") or "",
                    "source": item.get("source", {}).get("name", "NewsAPI"),
                    "source_key": "newsapi",
                    "published": item.get("publishedAt", ""),
                })
    print(f"    Found {len(articles)} articles")
    return articles

def scrape_cybersec():
    print("  [4/8] Cybersecurity feeds...")
    feeds = [
        ("https://feeds.feedburner.com/TheHackersNews", "thehackersnews"),
        ("https://www.bleepingcomputer.com/feed/", "bleepingcomputer"),
        ("https://krebsonsecurity.com/feed/", "KrebsOnSecurity"),
    ]
    articles = []
    for url, key in feeds:
        content = fetch_url(url)
        if content:
            articles.extend(parse_rss(content, key))
    print(f"    Found {len(articles)} articles")
    return articles

def scrape_finance():
    print("  [5/8] Finance news...")
    api_key = get_finnhub_key()

    articles = []

    if api_key and not api_key.startswith("YOUR_"):
        url = f"https://finnhub.io/api/v1/news?category=general&token={api_key}"
        data = fetch_json(url)
        if data:
            for item in data[:15]:
                articles.append({
                    "title": item.get("headline", ""),
                    "url": item.get("url", ""),
                    "summary": item.get("summary", "") or "",
                    "source": "Finnhub",
                    "source_key": "finnhub",
                    "published": datetime.fromtimestamp(item.get("datetime", 0)).isoformat(),
                })

    rss_feeds = [
        ("https://feeds.finance.yahoo.com/rss/2.0/headline?s=^GSPC&region=US&lang=en-US", "YahooFinance"),
        ("https://www.investing.com/rss/news.rss", "Investing.com"),
    ]
    for url, key in rss_feeds:
        content = fetch_url(url)
        if content:
            articles.extend(parse_rss(content, key))

    print(f"    Found {len(articles)} articles")
    return articles

def scrape_tech():
    print("  [6/8] Tech news...")
    feeds = [
        ("https://techcrunch.com/feed/", "techcrunch"),
        ("https://www.theverge.com/rss/index.xml", "theverge"),
        ("https://arstechnica.com/feed/", "arstechnica"),
    ]
    articles = []
    for url, key in feeds:
        content = fetch_url(url)
        if content:
            articles.extend(parse_rss(content, key))
    print(f"    Found {len(articles)} articles")
    return articles

def resolve_google_news_redirect(url, timeout=10):
    """Resolve a Google News redirect URL to the actual article URL.

    Google News RSS emits URLs like
        https://news.google.com/articles/CAIiE...
        https://news.google.com/rss/articles/CAIiE...
    These are click-tracking redirects that bounce through several
    Google properties before landing on the real publisher. Storing
    the redirect URL means users click a Google tracker instead of
    the article.

    For non-Google URLs this is a no-op (cheap string check first,
    no network call). For Google News URLs we try HEAD with redirect
    following; if that doesn't escape the news.google.com domain
    (which it usually doesn't, because Google renders a JS page),
    we fall back to a GET and look for <link rel="canonical"> or
    <meta property="og:url">. Returns the original URL on any
    failure so we never break the pipeline.
    """
    if 'news.google.com/articles/' not in url:
        return url
    try:
        req = urllib.request.Request(url, method='HEAD', headers={
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
        })
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            final = resp.url
            if final and final != url and 'news.google.com' not in final:
                return final
    except Exception:
        pass
    try:
        content = fetch_url(url, timeout=timeout, retries=1)
        if content:
            canonical = re.search(r'<link rel="canonical" href="([^"]+)"', content)
            if canonical:
                return canonical.group(1)
            og = re.search(r'<meta property="og:url" content="([^"]+)"', content)
            if og:
                return og.group(1)
    except Exception:
        pass
    return url


def scrape_google_news():
    print("  [7/8] Google News AI/ML...")
    queries = [
        "artificial+intelligence+machine+learning",
        "cybersecurity+news",
        "stock+market+trading",
    ]
    articles = []
    for q in queries:
        url = f"https://news.google.com/rss/search?q={q}&hl=en-US&gl=US&ceid=US:en"
        content = fetch_url(url)
        if content:
            arts = parse_rss(content, "google-news")
            for a in arts:
                if 'news.google.com/articles/' in a.get('url', ''):
                    a['url'] = resolve_google_news_redirect(a['url'])
            articles.extend(arts)
    print(f"    Found {len(articles)} articles")
    return articles

def scrape_markets():
    print("  [8/8] Market data...")
    feeds = [
        ("https://www.cnbc.com/id/100003114/device/rss/rss.html", "CNBC"),
        ("https://feeds.marketwatch.com/marketwatch/topstories/", "MarketWatch"),
    ]
    articles = []
    for url, key in feeds:
        content = fetch_url(url)
        if content:
            articles.extend(parse_rss(content, key))
    print(f"    Found {len(articles)} articles")
    return articles

try:
    from sentence_transformers import SentenceTransformer
    import numpy as np
    EMBEDDING_AVAILABLE = True
except ImportError:
    EMBEDDING_AVAILABLE = False

_embedding_model = None
_category_embeddings = None
_embedding_load_failed = False
_embedding_load_error = None

CATEGORY_EXAMPLES = {
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


def _get_embedding_model():
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


def _classify_embedding(article):
    global EMBEDDING_AVAILABLE
    title = article.get('title', '') or ''
    summary = article.get('summary', '') or ''
    text = f"{title}. {summary}".strip()
    if not text or text == '.':
        return 'Uncategorized', 0.0, [], 'news'

    model, cat_embs = _get_embedding_model()
    if model is None:
        EMBEDDING_AVAILABLE = False
        return _classify_keywords(article)
    text_emb = model.encode(text, convert_to_numpy=True)
    text_norm = np.linalg.norm(text_emb)
    if text_norm == 0:
        return 'Uncategorized', 0.0, [], 'news'

    scores = {}
    for cat, cat_emb in cat_embs.items():
        cat_norm = np.linalg.norm(cat_emb)
        if cat_norm == 0:
            scores[cat] = 0.0
        else:
            scores[cat] = float(np.dot(text_emb, cat_emb) / (text_norm * cat_norm))

    best_cat = max(scores, key=scores.get)
    best_score = scores[best_cat]

    if best_score < 0.15:
        return 'Uncategorized', 0.0, [], 'news'

    return best_cat, round(best_score, 4), [best_cat], 'news'


def _classify_keywords(article):
    # Multi-word keywords require ALL of their tokens to appear in the text
    # (in any order); single-word keywords require exact token membership.
    # This eliminates substring false positives (e.g. "social security" ->
    # Cybersecurity via the bare word "security", "small" -> ML via the
    # substring "ml" inside "small").
    text_tokens = _tokenize(f"{article.get('title', '')} {article.get('summary', '')}")

    def keyword_matches(kw):
        kw_tokens = _keyword_tokens(kw)
        if not kw_tokens:
            return False
        if len(kw_tokens) == 1:
            return next(iter(kw_tokens)) in text_tokens
        return kw_tokens.issubset(text_tokens)

    scores = {}
    for cat, keywords in _FILTERED_CATEGORY_KEYWORDS.items():
        scores[cat] = sum(1 for kw in keywords if keyword_matches(kw))

    max_score = max(scores.values(), default=0)

    if max_score == 0:
        return "Uncategorized", 0.0, [], "news"

    primary = max(scores, key=scores.get)
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

    return primary, confidence, tags, subcategory


def classify_article(article):
    if EMBEDDING_AVAILABLE:
        return _classify_embedding(article)
    return _classify_keywords(article)

def post_to_telegram(categorized):
    tg_path = BASE / "config" / "telegram.json"
    if not tg_path.exists():
        print("  Skipping Telegram - not configured")
        return

    with open(tg_path, encoding="utf-8-sig") as f:
        tg_config = json.load(f)

    token = get_telegram_token()
    main_channel = tg_config.get("main_channel_id", "")

    if not token or not main_channel:
        print("  Skipping Telegram - not configured")
        return
    
    today_top = database.get_today_top_per_category(limit_per_cat=3)
    
    emojis = {"LLM": "🧠", "Neural-Nets": "🔬", "ML-Research": "📊",
              "AI-Applications": "🤖", "Finance": "💰", "Cybersecurity": "🔒"}
    
    msg = f"📰 *Bloomy Daily Digest*\n"
    msg += f"📅 {date.today()}\n"
    msg += f"{'═' * 30}\n\n"
    
    total = 0
    for cat in ["LLM", "Neural-Nets", "ML-Research", "AI-Applications", "Finance", "Cybersecurity"]:
        articles = today_top.get(cat, [])
        if not articles:
            continue
        
        emoji = emojis.get(cat, "📰")
        msg += f"{emoji} *{cat}* ({len(articles)})\n"
        
        for i, art in enumerate(articles, 1):
            title = art.get('title', 'Untitled')[:80]
            summary = art.get('summary', '')[:100]
            url = art.get('url', '')
            
            msg += f"{i}\\. *{title}*\n"
            if summary:
                msg += f"   {summary}...\n"
            if url:
                msg += f"   [Read more]({url})\n"
            msg += "\n"
        
        total += len(articles)
    
    msg += f"{'─' * 30}\n"
    msg += f"*Total: {total} articles*\n"
    
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    data = json.dumps({
        "chat_id": main_channel,
        "text": msg,
        "parse_mode": "Markdown",
        "disable_web_page_preview": True,
    }).encode("utf-8")
    
    req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            result = json.loads(resp.read())
            if result.get("ok"):
                print("  Telegram digest sent!")
                logger.info("Telegram digest sent successfully")
            else:
                print(f"  Telegram error: {result.get('description')}")
                logger.error(f"Telegram error: {result.get('description')}")
    except Exception as e:
        print(f"  Telegram request failed: {e}")
        logger.error(f"Telegram request failed: {e}")

def main():
    logger.info("=" * 60)
    logger.info("Bloomy NEWS EXCAVATOR - Starting")
    logger.info("=" * 60)
    
    database.init_db()
    
    print("\nPHASE 1: SCRAPING")
    print("-" * 40)
    
    all_articles = []
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

    categorized = defaultdict(list)
    new_count = dup_count = 0

    conn = database.get_connection()
    try:
        for article in all_articles:
            category, confidence, tags, subcategory = classify_article(article)
            article['category'] = category
            article['confidence'] = confidence
            article['tags'] = tags
            article['subcategory'] = subcategory

            is_new, article_id = database.store_article(article, conn=conn)
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
    
    print("\nPHASE 4: CLEANUP")
    print("-" * 40)
    
    raw_dir = BASE / "raw"
    if raw_dir.exists():
        shutil.rmtree(raw_dir, ignore_errors=True)
        logger.info("Cleaned up raw data directory")
        print("  Raw files cleaned")
    
    print("\n" + "=" * 60)
    print("  DONE!")
    print(f"  Scraped: {len(all_articles)} | New: {new_count} | Duplicates: {dup_count} | Errors: {error_count}")
    print(f"  Database: {database.DB_PATH}")
    print("=" * 60)
    
    logger.info(f"Pipeline complete: {len(all_articles)} scraped, {new_count} new, {dup_count} duplicates, {error_count} errors")

def _load_labeled_samples():
    """Load LABELED_SAMPLES from tests/test_classifier.py.

    Importing the test module gives a single source of truth: when the
    labeled set is updated for a new release, the accuracy eval picks
    it up automatically.
    """
    import importlib.util
    test_path = BASE / "tests" / "test_classifier.py"
    spec = importlib.util.spec_from_file_location("_classifier_tests_eval", test_path)
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
    by_category = {}

    for title, summary, expected in samples:
        article = {"title": title, "summary": summary}

        kw_cat, _, _, _ = _classify_keywords(article)
        kw_match = (kw_cat == expected)
        if kw_match:
            keyword_correct += 1

        emb_cat, _, _, _ = _classify_embedding(article)
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


if __name__ == "__main__":
    import json
    import sys
    if len(sys.argv) > 1 and sys.argv[1] == "evaluate":
        print(json.dumps(evaluate_classifier_accuracy(), indent=2))
    else:
        main()
