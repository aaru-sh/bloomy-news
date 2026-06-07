# Roadmap

High-level plan for the News aggregator. Timelines are aspirational — contributions welcome to accelerate any item.

---

## Short-term (next 1-2 months)

- **Tighten keyword classifier gate** — raise precision above 0.80 (currently 63.3% at the hard gate).
- **Expand mypy scope** — add `scripts/` and `dashboard/` to the checked paths.
- **GitHub Discussions** — enable Q&A and Ideas categories for community support.
- **Good-first-issue labels** — tag 3-5 starter tasks to onboard new contributors.
- **Test coverage to 75 %+** — backfill missing edge-case and integration tests.

## Medium-term (next 3-6 months)

- **Discord / Slack digest** — push daily digests via webhooks or bot tokens.
- **WebSocket live updates** — real-time feed on the dashboard without manual refresh.
- **Semantic dedup** — add sentence-embedding similarity alongside existing Jaccard dedup.
- **RSS aggregator mode** — ingest arbitrary feeds; accept OPML import/export.
- **Configurable classifier training** — let users label articles and retrain the classifier from feedback.
- **9th source** — expand the scraper ecosystem with one community-requested provider.

## Long-term (6+ months)

- **Multi-user support** — authentication, per-user preferences, and isolated digests.
- **Plugin system** — let users write and register custom scrapers without touching core code.
- **Mobile app** — React Native companion for browsing and digest delivery.
- **Hosted SaaS option** — managed deployment for users who prefer not to self-host.
- **Custom ML model training pipeline** — fine-tune classifiers on domain-specific data.

---

## How to contribute

1. Read **[CONTRIBUTING.md](CONTRIBUTING.md)** for setup, coding standards, and PR guidelines.
2. Browse **[good first issues](../../labels/good%20first%20issue)** for tasks tagged for newcomers.
3. Want to suggest a feature or report a problem? Open a thread in **GitHub Discussions → [Ideas](../../discussions/categories/ideas)**.
4. For quick questions or setup help, use **GitHub Discussions → [Q&A](../../discussions/categories/q-a)**.

All contributions — code, docs, bug reports, feature ideas — are appreciated.
