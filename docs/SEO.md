# SEO Considerations for Bloomy News

This document covers search engine optimization and discoverability for the Bloomy News project across GitHub, documentation, and external search engines.

## 1. GitHub Repository SEO

### What's already strong
- **Descriptive repo name**: `bloomy-news` clearly communicates the product
- **Topics/tags**: `news`, `aggregator`, `rss`, `ai`, `machine-learning`, `cybersecurity`, `finance`, `dashboard`, `telegram`, `arxiv`
- **Clear description** in `pyproject.toml`: "Self-hosted AI/ML/finance/cybersecurity news aggregator with a local dashboard and Telegram digest."
- **CITATION.cff**: Enables "Cite this repository" on GitHub, improving academic discoverability
- **Badges in README**: CI, CodeQL, tests, coverage — signals active maintenance

### Recommendations
- Keep topics updated as the project evolves (e.g., add `self-hosted`, `llm`, `privacy`)
- Ensure the GitHub repo description field is: "Self-hosted AI news aggregator — Python, RSS, local dashboard, Telegram digest"
- Enable GitHub Pages if a project website is desired (not currently used)

## 2. Documentation SEO

### README structure
The README is the primary landing page for search engines crawling the repo. Key elements:

- **First paragraph** contains the core value proposition and primary keywords
- **Heading hierarchy** follows H1 (`Bloomy News`) → H2 sections → H3 subsections
- **Code blocks** use language tags (`bash`, `powershell`, `json`) for syntax highlighting and crawlability
- **Internal links** point to `docs/` files, keeping readers (and crawlers) within the repo

### Keywords present in README
- AI news aggregator, self-hosted, Python, RSS, machine learning, cybersecurity, finance
- arXiv, Telegram, SQLite, dashboard, deduplication, classifier
- Related terms: NLP, LLM, deep learning, fintech, threat intelligence

### docs/ files
Each doc targets a specific technical topic and uses descriptive filenames:
- `CLASSIFIER.md` — ranks for "news article classifier python"
- `DEDUP.md` — ranks for "article deduplication"
- `SCRAPERS.md` — ranks for "arXiv RSS scraper python"
- `DEPLOYMENT.md` — ranks for "self-hosted news dashboard setup"
- `ARCHITECTURE.md` — ranks for "news aggregator architecture"

### Recommendations
- Add a `docs/index.md` as a documentation landing page if the file count grows
- Cross-link between docs files using relative paths
- Use descriptive H1/H2 headings in every doc file (avoid generic titles)

## 3. External Visibility

### Search engine optimization for blog posts and landing pages
If promoting Bloomy News externally (blog posts, Product Hunt, Hacker News):

- **Title tag**: "Bloomy News — Self-Hosted AI News Aggregator in Python"
- **Meta description**: "Pull fresh articles from 8 sources, classify into AI/ML/cybersecurity/finance categories, and view on a local dashboard. No cloud, no accounts, no telemetry."
- **Primary keywords**: self-hosted news aggregator, AI news aggregator, Python RSS reader
- **Long-tail keywords**: "self-hosted alternative to Google News for AI research", "local news aggregator with machine learning classification"

### Open Graph / Social
- Repository description and README first paragraph will be used by GitHub for OG tags
- Ensure `pyproject.toml` description stays concise (under 160 chars for Twitter cards)

### Discoverability signals
- **GitHub stars**: organic discovery driver — mention on HN, Reddit r/selfhosted, r/Python
- **PyPI**: Not published as a package (by design) — but `pip install -e .` works
- **arXiv integration**: Papers linking to or mentioning Bloomy News would boost authority
- **Telegram channel**: Public channels are indexed by Telegram search

### Recommended external channels
| Channel | URL | Purpose |
|---------|-----|---------|
| GitHub Discussions | repo/Discussions | Q&A, ideas |
| Reddit r/selfhosted | reddit.com/r/selfhosted | Self-hosted community |
| Reddit r/Python | reddit.com/r/Python | Python community |
| Hacker News | news.ycombinator.com | Tech audience |
| Product Hunt | producthunt.com | Launch visibility |
| Dev.to / Hashnode | dev.to | Technical blog posts |

## 4. Technical SEO Notes

- **HTTPS**: GitHub serves all content over HTTPS — no mixed content issues
- **Canonical URLs**: GitHub handles canonical tags automatically
- **Sitemap**: Not applicable (no GitHub Pages)
- **Robots.txt**: GitHub provides a default that allows crawling
- **Page speed**: README loads fast (static markdown, no heavy assets)
- **Mobile**: GitHub's responsive design handles mobile rendering

## 5. Monitoring

To track external visibility:
- Set up Google Search Console for any project website
- Monitor GitHub traffic in repo Insights → Traffic
- Track inbound links via GitHub's Referring Sites report
- Use `site:github.com/aaru-sh/bloomy-news` on Google to check indexing
