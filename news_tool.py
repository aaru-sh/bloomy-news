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
            articles.extend(parse_rss(content, "google-news"))
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

CATEGORY_DESCRIPTIONS = {
    'LLM':             'large language model LLM generative AI chatbot assistant GPT Claude Llama Mistral Gemini PaLM '
                       'transformer decoder prompt fine-tuning RLHF instruction tuning chain-of-thought reasoning '
                       'tokenization few-shot in-context learning alignment hallucination',
    'Neural-Nets':     'neural network deep learning architecture layer activation backpropagation gradient convolutional '
                       'recurrent LSTM GRU GAN diffusion transformer attention mechanism encoder decoder embedding '
                       'training optimization loss function epoch batch normalization',
    'ML-Research':     'machine learning research paper arXiv benchmark dataset supervised unsupervised reinforcement '
                       'classification regression clustering evaluation metric accuracy F1 precision recall '
                       'theoretical analysis proof convergence statistical learning generalization',
    'AI-Applications': 'artificial intelligence product launch tool application platform software deployment API SDK '
                       'enterprise customer user company startup agent automation copilot assistant code generation '
                       'image generation video generation creative content production workflow productivity',
    'Finance':         'stock market finance investment trading cryptocurrency bitcoin ethereum price earnings revenue '
                       'profit quarterly report IPO merger acquisition dividend yield inflation interest rate Fed '
                       'central bank economy GDP recession bull bear rally sector index S&P 500 Nasdaq Dow Jones '
                       'Wall Street hedge fund portfolio asset management',
    'Cybersecurity':   'security cybersecurity vulnerability exploit breach malware ransomware phishing attack threat '
                       'CVE zero-day patch firewall encryption authentication data leak incident response forensics '
                       'penetration testing APT nation-state espionage',
}


def _get_embedding_model():
    global _embedding_model, _category_embeddings
    if _embedding_model is None:
        _embedding_model = SentenceTransformer('all-MiniLM-L6-v2')
        _category_embeddings = {
            cat: _embedding_model.encode(desc, convert_to_numpy=True)
            for cat, desc in CATEGORY_DESCRIPTIONS.items()
        }
    return _embedding_model, _category_embeddings


def _classify_embedding(article):
    title = article.get('title', '')
    summary = article.get('summary', '')
    text = f"{title}. {summary}"

    model, cat_embs = _get_embedding_model()
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
    text = f"{article.get('title', '')} {article.get('summary', '')}".lower()

    scores = {}
    for cat, keywords in CATEGORY_KEYWORDS.items():
        score = sum(1 for kw in keywords if kw in text)
        scores[cat] = score

    max_score = max(scores.values(), default=0)

    if max_score == 0:
        return "Uncategorized", 0.0, [], "news"

    primary = max(scores, key=scores.get)
    confidence = min(max_score / 5.0, 1.0)

    threshold = max_score * 0.5
    tags = [cat for cat, score in scores.items() if cat != primary and score >= threshold]

    # Determine subcategory
    subcategory = "news"
    if primary in SUBCATEGORY_KEYWORDS:
        subcats = SUBCATEGORY_KEYWORDS[primary]
        best_subcat = "news"
        best_score = 0
        for subcat_name, subcat_keywords in subcats.items():
            subcat_score = sum(1 for kw in subcat_keywords if kw in text)
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
    
    for article in all_articles:
        category, confidence, tags, subcategory = classify_article(article)
        article['category'] = category
        article['confidence'] = confidence
        article['tags'] = tags
        article['subcategory'] = subcategory
        
        is_new, article_id = database.store_article(article)
        if is_new:
            new_count += 1
            categorized[category].append(article)
            logger.info(f"Stored: {article['title'][:60]} -> {category} (conf={confidence:.2f})")
        else:
            dup_count += 1
            logger.info(f"Duplicate: {article['title'][:60]}")
    
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

if __name__ == "__main__":
    main()
