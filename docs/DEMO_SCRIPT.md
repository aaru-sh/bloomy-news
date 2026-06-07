# Bloomy News — 5-Minute Demo Video Script

**Total duration:** 5:00  
**Format:** Screen recording with voiceover  
**Tools:** OBS, screen recorder, or similar  
**Resolution:** 1920×1080 (or 1440p)

---

## 1. Opening (0:00–0:30)

**What to show:** GitHub repo page (`https://github.com/aaru-sh/bloomy-news`)

**Talking points:**
- "This is Bloomy News — a self-hosted news aggregator for AI, ML, cybersecurity, and finance."
- "8 scrapers, 6 categories, 131 tests, MIT licensed."
- "No cloud, no accounts, no telemetry. Everything runs on your machine."

**Screenshot suggestion:** Full GitHub repo page with badges visible (CI, Python 3.8+, MIT, tests, coverage).

**Duration:** 30 seconds

---

## 2. Installation (0:30–1:00)

**What to show:** Terminal with clone, install, and smoke test

```bash
git clone https://github.com/aaru-sh/bloomy-news.git
cd bloomy-news
pip install -r requirements.txt
python scripts/smoke_test.py
```

**Talking points:**
- "Clone it, install one dependency, run the smoke test."
- "If it says ALL CHECKS PASSED, you're ready. Takes about 10 seconds."
- "Zero API keys required to get started — the arXiv, GitHub, and cybersecurity scrapers work out of the box."

**Screenshot suggestion:** Terminal showing the smoke test output with all 10 checks passing.

**Duration:** 30 seconds

---

## 3. Dashboard (1:00–2:00)

**What to show:** Launch the pipeline and dashboard

```bash
python news_tool.py
python dashboard/generate_data.py
python dashboard/serve.py
```

Then open `http://127.0.0.1:8080`.

**Show these pages:**
1. **Landing page** (index.html) — hero section, category grid with article counts, recent articles
2. **Filters page** (filters.html) — calendar date picker, search bar, multi-select dropdowns
3. **Bookmarks page** (bookmarks.html) — starred articles, empty state

**Talking points:**
- "Three pages — landing, filters, and bookmarks."
- "Category grid shows article counts at a glance. Click any category to filter."
- "Calendar picker lets you browse by date. Full-text search across all articles."
- "Star any article to bookmark it. Bookmarks persist in SQLite."
- "Dark and light theme — toggle in the header. WCAG-AA contrast ratios."

**Screenshot suggestion:** Dashboard landing page with category grid and recent articles visible. Show the dark/light toggle in action.

**Duration:** 60 seconds

---

## 4. Pipeline in Action (2:00–3:00)

**What to show:** Run `python news_tool.py` in the terminal, show the output scrolling

**Talking points:**
- "Watch the pipeline run. It goes through 8 scrapers sequentially."
- "arXiv with 13 feeds, GitHub trending, cybersecurity RSS, Google News with redirect resolution..."
- "Articles are classified into 6 categories and deduplicated automatically."
- "If you have Telegram set up, the digest posts to your channel at the end."

**What to highlight in the output:**
- The scraper progress (`[1/8] arXiv (13 feeds)...`)
- Article counts per scraper
- Classification summary (`Classification: N articles, M Uncategorized`)
- Dedup count (`N duplicates suppressed`)
- Telegram confirmation (if enabled)

**Screenshot suggestion:** Terminal output showing a complete pipeline run with all scrapers and counts.

**Duration:** 60 seconds

---

## 5. Dual-Mode Classifier (3:00–3:30)

**What to show:** Two terminal runs — one with keyword mode, one with embedding mode

```bash
# Keyword mode (default)
python news_tool.py
# Shows: Classifier: keyword (install sentence-transformers for better accuracy)

# Embedding mode (with sentence-transformers installed)
python news_tool.py
# Shows: Classifier: embedding
```

**Talking points:**
- "The classifier has two modes. Keyword mode works offline with zero extra deps — fast, deterministic."
- "Install sentence-transformers and you get the embedding mode — semantic similarity using all-MiniLM-L6-v2."
- "The dispatcher picks automatically based on what's installed. Falls back gracefully if the model can't load."

**Screenshot suggestion:** Side-by-side or sequential terminal output showing both classifier modes.

**Duration:** 30 seconds

---

## 6. Telegram Digest (3:30–4:00)

**What to show:** Telegram channel with the digest message

**Talking points:**
- "The Telegram digest sends the top 3 articles per category — up to 18 articles total."
- "Each article gets a title, source, and direct link. Sub-channels per category for targeted feeds."
- "Inline buttons to open the source and save to bookmarks."
- "Set it up in 5 minutes with BotFather — bot token goes in .env, channel IDs in config/telegram.json."

**Screenshot suggestion:** Telegram channel showing a digest message with category headings and article links.

**Duration:** 30 seconds

---

## 7. 30-Day Retention (4:00–4:30)

**What to show:** Database before and after cleanup

```python
# Show the database size
import os
print(f"Database size: {os.path.getsize('news.db') / 1024 / 1024:.2f} MB")

# Show article count
import sqlite3
conn = sqlite3.connect('news.db')
print(f"Articles: {conn.execute('SELECT COUNT(*) FROM articles').fetchone()[0]}")
```

**Talking points:**
- "The pipeline prunes articles older than 30 days at the end of each run."
- "A live DB with 1,794 articles shrank to 264 — from 4.93 MB to 0.6 MB."
- "Set MAX_ARTICLE_AGE_DAYS to 0 in database.py to disable. That's the only knob."
- "Dedup_log entries older than 7 days are also pruned."

**Screenshot suggestion:** Terminal showing database size before and after, or the `cleanup_old_articles` call in action.

**Duration:** 30 seconds

---

## 8. Closing (4:30–5:00)

**What to show:** GitHub repo page again

**Talking points:**
- "That's Bloomy News. MIT licensed, 131 tests, self-hosted."
- "Star it on GitHub if you find it useful."
- "Contributions welcome — code, docs, bug reports, feature ideas."
- "Check the docs for the full architecture, classifier details, and deployment guide."

**Screenshot suggestion:** GitHub repo page with the Star button prominent. Show the docs folder structure.

**Duration:** 30 seconds

---

## Post-Production Notes

### Editing checklist
- [ ] Trim dead air between sections
- [ ] Add section titles as lower-third text overlays (e.g., "Installation", "Dashboard", "Pipeline")
- [ ] Speed up the pipeline run section if it takes more than 60 seconds (2x speed with voiceover is fine)
- [ ] Add a progress bar or timestamp overlay in the corner
- [ ] Normalize audio levels across sections
- [ ] Add background music at low volume (optional)

### Thumbnail
- Show the dashboard landing page with category grid
- Text overlay: "Bloomy News — Self-Hosted AI News Aggregator"
- GitHub star count if > 10

### Upload checklist
- [ ] YouTube: title "Bloomy News — Self-Hosted AI News Aggregator (5-Min Demo)"
- [ ] Description includes GitHub link, quickstart commands, and feature list
- [ ] Tags: news aggregator, AI news, self-hosted, open source, Python, RSS
- [ ] Pin a comment with the 3-step quickstart
- [ ] Cross-post to Reddit (r/selfhosted, r/Python, r/MachineLearning)

### B-roll suggestions (optional)
- Terminal scrolling through a full pipeline run (use for background during voiceover)
- Browser showing the dashboard loading for the first time
- Telegram notification popping up with the digest
- GitHub Actions CI passing on the repo

### Key metrics to mention
| Stat | Value |
|------|-------|
| Scrapers | 8 |
| Categories | 6 |
| arXiv feeds | 13 |
| Tests | 131 passed |
| Coverage | 68% |
| Python versions | 3.8 – 3.12 |
| External deps | 1 (`requests`) |
| License | MIT |
| Database size (after retention) | ~0.6 MB |
| Project size | ~15 MB |
