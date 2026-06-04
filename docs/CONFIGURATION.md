# Configuration

Every config option in Bloomy News, in one place. For the friendly
quick start, see the [README](../README.md). For the deep architecture
overview, see [ARCHITECTURE.md](../README.md#learn-more).

---

## Precedence

Config values are resolved in this order (highest wins):

1. Real environment variables (e.g. `TELEGRAM_BOT_TOKEN=...` in the
   shell)
2. `.env` file in the project root
3. `config/*.json` files with `${VAR}` placeholder expansion
4. Built-in defaults (lowest)

This means a key in `.env` overrides a key in `config/telegram.json`,
and a real env var overrides `.env`.

---

## Environment variables

| Variable               | Required | Default       | Used by                                |
| ---------------------- | -------- | ------------- | -------------------------------------- |
| `TELEGRAM_BOT_TOKEN`   | no       | _placeholder_ | `scripts/telegram_bot.py`              |
| `TELEGRAM_CHAT_ID`     | no       | _placeholder_ | `scripts/telegram_bot.py`              |
| `NEWS_API_KEY`         | no       | _placeholder_ | `news_tool.py` (NewsAPI scraper)       |
| `FINNHUB_API_KEY`      | no       | _placeholder_ | `news_tool.py` (Finnhub finance scraper) |
| `ARXIV_RATE_LIMIT`     | no       | `3.0`         | `news_tool.py` (seconds between requests) |
| `LOG_LEVEL`            | no       | `INFO`        | All scripts                            |
| `HTTP_PROXY`           | no       | _none_        | All `urllib` / `requests` calls        |
| `HTTPS_PROXY`          | no       | _none_        | All `urllib` / `requests` calls        |

If a key is missing, the corresponding scraper is skipped silently —
the pipeline never crashes on a missing config.

---

## `.env` example

```bash
# Copy this file to .env and fill in the keys you have.
# None of these are required for the pipeline to work.

TELEGRAM_BOT_TOKEN=123456789:ABCdef-GHIjkl_MNOpqrSTUvwxYZ
TELEGRAM_CHAT_ID=-1001234567890

NEWS_API_KEY=your_newsapi_key_here
FINNHUB_API_KEY=your_finnhub_key_here
```

No trailing whitespace after `=`. The loader is strict about that.

---

## Config files

Three JSON files in `config/` carry the per-source and per-channel
settings that don't belong in env vars:

| File                     | What it holds                                              |
| ------------------------ | ---------------------------------------------------------- |
| `config/sources.json`    | All feed URLs, API endpoints, and any per-source tuning   |
| `config/categories.json` | The category keyword tables used by the classifier         |
| `config/telegram.json`   | Bot token placeholder + channel IDs (main + 6 sub-channels) |

Any string value in these files can use `${VAR}` placeholder syntax,
which is expanded at load time by `config.py`. For example,
`config/telegram.json` might have:

```json
{
  "bot_token": "${TELEGRAM_BOT_TOKEN}",
  "main_channel_id": "${TELEGRAM_MAIN_CHANNEL_ID}",
  "sub_channels": {
    "LLM":   "${TELEGRAM_LLM_CHANNEL_ID}",
    "Finance": "${TELEGRAM_FINANCE_CHANNEL_ID}"
  }
}
```

The `TELEGRAM_BOT_TOKEN` placeholder is never resolved with a real
value into a tracked file — only `.env` (gitignored) carries the real
value.

---

## Adding new feeds

For RSS / Atom feeds, edit `config/sources.json` and add the URL to
the right category. For full custom scrapers (e.g. a JSON API that
needs parsing), see [SCRAPERS.md](SCRAPERS.md).

For Telegram sub-channels, add a new `TELEGRAM_<NAME>_CHANNEL_ID`
entry to `.env` and reference it in `config/telegram.json`.

For new classification keywords, edit `config/categories.json`. The
keyword format and scoring rules are in [CLASSIFIER.md](CLASSIFIER.md).
