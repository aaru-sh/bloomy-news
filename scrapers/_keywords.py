"""Keyword tokenization for the rule-based classifier.

The keyword classifier (in classifier.py) needs to:
1. Lowercase + tokenize article text into a frozenset of word tokens.
2. Lowercase + tokenize individual keywords the same way.
3. Pre-filter the keyword list to drop keywords that are < 3 chars or
   composed entirely of stopwords — this prevents substring false
   positives like "small" matching "ml" or "social" matching "security"
   via the bare word "security".

`_FILTERED_CATEGORY_KEYWORDS` and `_FILTERED_SUBCATEGORY_KEYWORDS` are
the pre-computed views the classifier actually reads at runtime. The
unfiltered constants (CATEGORY_KEYWORDS, SUBCATEGORY_KEYWORDS) are
kept around for reference and for tests that want to inspect the
canonical keyword sets.
"""
import re
from typing import Dict, FrozenSet, List

_TOKEN_RE = re.compile(r"\b[\w'-]+\b")

STOPWORDS: FrozenSet[str] = frozenset({
    "the", "a", "an", "is", "are", "of", "to", "in", "for", "on", "with", "and", "or",
})

CATEGORY_KEYWORDS: Dict[str, List[str]] = {
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

SUBCATEGORY_KEYWORDS: Dict[str, Dict[str, List[str]]] = {
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


def _tokenize(text: str) -> FrozenSet[str]:
    """Lowercase + tokenize text into a frozenset of word tokens."""
    if not text:
        return frozenset()
    return frozenset(_TOKEN_RE.findall(text.lower()))


def _keyword_tokens(keyword: str) -> FrozenSet[str]:
    """Lowercase + tokenize a keyword into a frozenset of word tokens."""
    if not keyword:
        return frozenset()
    return frozenset(_TOKEN_RE.findall(keyword.lower()))


def _filter_keywords(keywords: List[str]) -> List[str]:
    """Drop keywords that are < 3 chars or composed entirely of stopwords."""
    result: List[str] = []
    for kw in keywords:
        if len(kw) < 3:
            continue
        toks = _keyword_tokens(kw)
        if not toks or toks.issubset(STOPWORDS):
            continue
        result.append(kw)
    return result


_FILTERED_CATEGORY_KEYWORDS: Dict[str, List[str]] = {
    cat: _filter_keywords(keywords) for cat, keywords in CATEGORY_KEYWORDS.items()
}
_FILTERED_SUBCATEGORY_KEYWORDS: Dict[str, Dict[str, List[str]]] = {
    cat: {
        sub: _filter_keywords(sub_keywords)
        for sub, sub_keywords in subcats.items()
    }
    for cat, subcats in SUBCATEGORY_KEYWORDS.items()
}
