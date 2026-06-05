"""GitHub trending scraper: parses 3 language trending pages via HTML."""
import re
from datetime import datetime

from ._http import fetch_url, ArticleList


def scrape_github() -> ArticleList:
    print("  [2/8] GitHub trending...")
    articles: ArticleList = []
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
