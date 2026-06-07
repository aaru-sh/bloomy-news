# Partnerships and Integrations

This document covers built-in integrations, planned work, and potential community contributions.

## Current Integrations

### Telegram Bot (Built-in)

The Telegram bot sends categorized digests every 12 hours via the scheduler. It reads the most recent articles, picks the top 3 per category (18 max), and sends them with inline "Read" and "Save" buttons. The save callback calls `toggle_bookmark()` on the dashboard server.

See [ARCHITECTURE.md](ARCHITECTURE.md#scriptstelegram_bot--digest-poster) for implementation details.

### GitHub Actions (CI/CD)

Automated testing and linting on every push and pull request. Runs the test suite and code quality checks defined in the workflow configuration.

### Dependabot (Dependency Updates)

Automated dependency update PRs. Keeps Python packages current and flags security vulnerabilities in transitive dependencies.

### CodeQL (Security Scanning)

Static analysis for code security vulnerabilities. Runs on a schedule and on pull requests.

---

## Planned Integrations

These are on the project roadmap. Contributions welcome.

### Discord / Slack Digest

Send daily or weekly digests to a Discord channel (via webhook) or Slack workspace (via bot). Similar to the Telegram bot but targeting different chat platforms.

**Approach:** A new function in the pipeline that posts formatted messages to a webhook URL or bot token, configured via `config/discord.json` or `config/slack.json`.

### RSS Aggregator Mode (OPML Import)

Import feed lists from OPML files exported by other RSS readers. Allows migrating subscriptions from Miniflux, FreshRSS, or any OPML-compatible tool.

**Approach:** Parse OPML XML, add feeds to `config/sources.json`, and scrape them via the existing `_rss.py` base scraper.

### WebSocket Live Updates

Push new articles to connected dashboard clients in real time instead of requiring a page refresh. Useful for active monitoring setups.

**Approach:** Add a WebSocket endpoint to `dashboard/serve.py` that publishes on `run_pipeline()` completion.

### Semantic Dedup (Sentence Embeddings)

Replace the current Jaccard title dedup with embedding-based similarity for better cross-source duplicate detection. Catches articles with different titles but the same content.

**Approach:** Use a local sentence-transformers model to compute embeddings, store them in the DB, and use cosine similarity for dedup.

---

## Potential Integrations

Community suggestions welcome. Open an issue or PR to discuss.

### 1. Nextcloud News

Import and export subscriptions via OPML. Bidirectional sync lets you manage feeds from Nextcloud News and keep Bloomy News in sync.

- **Type:** RSS feed import/export
- **Config:** Nextcloud instance URL + credentials
- **Status:** Community suggestion

### 2. Miniflux / FreshRSS

Connect to a running Miniflux or FreshRSS instance. Pull articles directly from their API instead of re-scraping the same feeds.

- **Type:** Article source
- **Config:** Instance URL + API token
- **Status:** Community suggestion

### 3. Discord

Webhook-based digest. Post daily or weekly summaries to a Discord channel using a Discord webhook URL.

- **Type:** Digest target
- **Config:** `DISCORD_WEBHOOK_URL` env var
- **Status:** Community suggestion

### 4. Slack

Bot-based digest. Send digests to a Slack channel via an incoming webhook or a Slack bot token with `chat:write` scope.

- **Type:** Digest target
- **Config:** `SLACK_WEBHOOK_URL` or `SLACK_BOT_TOKEN` + `SLACK_CHANNEL_ID`
- **Status:** Community suggestion

### 5. Matrix

Bridge-based digest. Use a Matrix bot or webhook bridge to send digests to Matrix rooms.

- **Type:** Digest target
- **Config:** Matrix homeserver URL + access token
- **Status:** Community suggestion

### 6. Grafana

Export dashboard metrics to Grafana. Feed article counts, category breakdowns, and scraper stats into a Grafana panel for monitoring.

- **Type:** Metrics export
- **Config:** Grafana instance URL + API key
- **Status:** Community suggestion

### 7. Prometheus

Expose a `/metrics` endpoint with article counts, scraper run durations, and classification stats. Prometheus scrapes this endpoint for alerting and dashboards.

- **Type:** Metrics endpoint
- **Config:** `PROMETHEUS_ENABLED` env var, listen port
- **Status:** Community suggestion

### 8. Uptime Kuma

Health check endpoint at `/healthz` that returns 200 if the dashboard server is running and the database is accessible. Uptime Kuma monitors this for uptime tracking.

- **Type:** Health check
- **Config:** None beyond the dashboard URL
- **Status:** Community suggestion

### 9. OpenAI / Anthropic

Enhanced article classification via API. Send article title + summary to a cloud LLM for more accurate categorization than keyword matching, at the cost of latency and API fees.

- **Type:** Classification upgrade
- **Config:** `OPENAI_API_KEY` or `ANTHROPIC_API_KEY`
- **Status:** Community suggestion

### 10. Local LLMs (Ollama)

Enhanced classification without cloud APIs. Run a local model via Ollama for better classification accuracy while keeping everything self-hosted.

- **Type:** Classification upgrade
- **Config:** `OLLAMA_BASE_URL` (default `http://localhost:11434`)
- **Status:** Community suggestion

---

## How to Add an Integration

### 1. Create a new scraper (for source integrations)

If the integration is a new article source, add a scraper in `scrapers/` following the contract in [SCRAPERS.md](SCRAPERS.md).

### 2. Add configuration

Add any required config to `config/sources.json` or create a new config file in `config/`. Document required env vars in `.env.example`.

### 3. Write tests

Add tests in `tests/` covering the integration's happy path and error cases.

### 4. Document

Update [SCRAPERS.md](SCRAPERS.md) if it's a new scraper, or add a section here in [INTEGRATIONS.md](INTEGRATIONS.md).

### 5. Submit a PR

Follow the project's [CODING_STANDARDS.md](CODING_STANDARDS.md) and include test coverage.

---

## API Endpoints

The dashboard server exposes these endpoints for external integrations. All responses are JSON.

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/articles` | GET | List all articles (supports pagination via `?limit=` and `?offset=`) |
| `/api/articles?q=search` | GET | Search articles by title or summary |
| `/api/bookmarks` | GET | List bookmarked article IDs |
| `/api/categories` | GET | List all categories |
| `/api/stats` | GET | Get per-category counts and total |
| `/api/bookmark` | POST | Toggle bookmark for an article (send `{"id": "article_id"}`) |

**Base URL:** `http://localhost:8080`

**Rate limits:** None configured. The server binds to `127.0.0.1:8080` only (local access).

**CORS:** Restricted to `http://localhost:8080`.

---

## See also

- [ARCHITECTURE.md](ARCHITECTURE.md) — system components and data flow
- [SCRAPERS.md](SCRAPERS.md) — how to add a new scraper
- [CONFIGURATION.md](CONFIGURATION.md) — config files and env vars
- [DEPLOYMENT.md](DEPLOYMENT.md) — self-hosting setup
