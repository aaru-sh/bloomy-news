# Contributing to Bloomy News

Thanks for your interest in contributing. This document explains how to report bugs, request features, and submit code changes.

## Code of conduct

Be kind. Be specific. Disagree on substance, not on style. We are all here to make a better news aggregator.

---

## Reporting bugs

Open a [bug report](../../issues/new?template=bug_report.md). Please include:

1. **What you did** — exact command(s) run, or exact dashboard URL with the relevant filter state.
2. **What you expected** — one sentence.
3. **What happened** — actual behavior, including any error messages, exit codes, or log lines.
4. **Environment** — Python version (`python --version`), OS, commit hash (`git rev-parse HEAD`).
5. **Logs** — attach the relevant `logs/*.log` file or paste the relevant lines. Do not paste your real `.env`.

If the bug is a security issue, **do not** open a public issue — see the security section in the README.

---

## Requesting features

Open a [feature request](../../issues/new?template=feature_request.md). Please include:

1. **The problem you're trying to solve** — what are you trying to do that the current project doesn't support?
2. **Your proposed solution** — one paragraph. It's fine if this is a sketch; the implementation details can come later.
3. **Alternatives you've considered** — what other approaches did you look at, and why is this one better?
4. **A small example** — what would the user-facing change look like? A CLI command, a config snippet, or a screenshot of a similar tool.

---

## Contributing code

### Setting up a development environment

```bash
git clone https://github.com/aaru-sh/bloomy-news.git
cd bloomy-news
python -m venv .venv
source .venv/bin/activate   # or .venv\Scripts\activate on Windows
pip install -r requirements.txt
cp .env.example .env        # fill in any API keys you have
```

### Running the test suite

```bash
python -m unittest tests.test_fixes -v
```

All 18 tests should pass. If you add a new test, add it to the appropriate class in `tests/test_fixes.py` and follow the existing naming convention.

### Pull request process

1. **Open an issue first** for non-trivial changes. We can save each other a lot of time by aligning on the approach before code is written.
2. **Create a branch** off `main` with a descriptive name: `fix/issue-42-bookmark-race` or `feat/reddit-scraper`.
3. **Make your changes.** Follow the code style below.
4. **Add tests** for any new logic. The existing tests are the template.
5. **Run the full test suite** — all tests must pass.
6. **Update CHANGELOG.md** under the `[Unreleased]` section. Use the same sub-headings as the rest of the file (`Added`, `Changed`, `Fixed`, `Removed`).
7. **Open a pull request** using the [PR template](../../pulls). The PR description should reference any related issues with `Closes #N` or `Refs #N`.
8. **Wait for review.** Expect comments and revision requests. This is normal.

### Code style

#### Python

- **PEP 8** with 4-space indents. No external linter is configured; the existing code is the style guide.
- **Type hints** on all new public functions. Internal helpers can skip hints.
- **f-strings** for string formatting. No `%` or `.format()`.
- **Docstrings** for modules and public functions, but not for one-liners. Use the existing tone — terse, factual, no marketing language.
- **No `print()` for normal-flow output.** Use the `logging` module or a module-level helper. The pipeline's `print()` calls are for user-facing CLI feedback; that's the exception.
- **No silent failures.** Catch exceptions only when you can do something with them, and log the context. Re-raising is fine.

#### JavaScript

- **ES5-compatible syntax** — `var`, no arrow functions, no template literals, no `const`/`let`. This is intentional for maximum browser compatibility.
- **`escapeHtml()` for any user-controlled string** before `innerHTML` assignment. Look at `app.js` for the helper.
- **`safeUrl()` for any URL field** — only allows `http://` and `https://` schemes.
- **Event delegation** is preferred over per-element listeners when the parent container is stable.
- **No external dependencies.** The dashboard must work offline with no `<script src="https://...">` references.

#### HTML / CSS

- **Semantic tags first** — `<main>`, `<nav>`, `<article>`, `<section>`, `<button>`. Use ARIA only when semantics fail.
- **CSS custom properties** for theme values. Light/dark switching is via `[data-theme="..."]` selectors, not media queries.
- **All interactive elements** get a `:focus-visible` style. The browser default is not enough.

#### Config

- **No new top-level env vars without updating `.env.example`.** Add a comment explaining what the var is for and whether it's required.
- **Placeholder syntax in JSON** is `${VAR_NAME}`. The `secrets.py` loader expands it. Do not put real keys in tracked JSON.

### Commit messages

Follow [Conventional Commits](https://www.conventionalcommits.org/):

```
feat: add reddit scraper
fix: handle empty summary in telegram digest
docs: clarify scheduler catch-up logic
refactor: extract Jaccard similarity to its own module
test: add coverage for scheduler catch-up at 11:59
chore: bump requests to 2.32.0
```

The subject line is 50 chars or less, imperative mood, no trailing period. The body wraps at 72 chars and explains *why*, not *what* (the diff shows the what).

### Areas that need help

- **More scrapers** — Reddit, Hacker News (the comment site, not the security feed), Lobsters, Dev.to, specific Substack blogs
- **Classifier improvements** — better keyword weighting, support for multi-language content, embedding-based classification
- **Dashboard polish** — better mobile layout, virtualized scrolling for large article lists, a "loading" state for `generate_data.py`
- **Telegram improvements** — per-user subscriptions, digests on demand via inline buttons, "save to bookmarks" callback
- **Tests** — end-to-end test of the full pipeline, integration test of the dashboard API, scheduler test for 60s startup delay
- **Documentation** — translations of the README, more `docs/*.md` files (e.g., `docs/DEPLOYMENT.md` for production-style deployments)

---

## Release process

1. Bump version in any place it's referenced (currently no `__version__` constant; the version is in the README and the commit history).
2. Update `CHANGELOG.md` — move `[Unreleased]` changes to a new dated version block.
3. Tag the release: `git tag -a v1.0.0 -m "Release 1.0.0"`.
4. Push the tag: `git push origin v1.0.0`.
5. The GitHub release is auto-generated from the tag, with the CHANGELOG section as the body.

Releases happen when there's something worth shipping. There's no fixed cadence.
