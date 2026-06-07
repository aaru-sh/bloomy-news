# Contributing to Bloomy News

Welcome! We're thrilled you're interested in contributing. Whether you're fixing a typo, adding a feature, or reporting a bug, every contribution matters. This guide will walk you through everything you need to get started.

New to the project? Check out [docs/NEWCOMERS.md](docs/NEWCOMERS.md) for a full project overview.

---

## Code of conduct

Be kind. Be specific. Disagree on substance, not on style. We are all here to make a better news aggregator. Please read our [Code of Conduct](CODE_OF_CONDUCT.md) before participating.

---

## Getting started

### 1. Fork the repository

Click the **Fork** button in the top-right corner of the [repo page](https://github.com/aaru-sh/bloomy-news) to create your own copy.

### 2. Clone your fork

```bash
git clone https://github.com/<your-username>/bloomy-news.git
cd bloomy-news
```

### 3. Create a virtual environment

```bash
python -m venv .venv
source .venv/bin/activate   # Linux/macOS
.venv\Scripts\activate      # Windows
```

### 4. Install dependencies

```bash
pip install -r requirements.txt -r requirements-dev.txt
```

### 5. Run the tests

```bash
python -m unittest discover -s tests
```

All 131 tests should pass. Current coverage is 68%.

### 6. Run the linter

```bash
python -m mypy news_tool.py database.py
```

mypy must pass before submitting any changes.

---

## Development workflow

### 1. Create a branch from `main`

```bash
git checkout main
git pull origin main
git checkout -b feat/my-feature
```

Use a descriptive branch name with a prefix:

- `feat/` for new features
- `fix/` for bug fixes
- `docs/` for documentation changes
- `test/` for test additions or corrections
- `chore/` for maintenance tasks

### 2. Make your changes

Write clean, readable code. Follow the code standards below.

### 3. Write or update tests

Every new feature must have tests. Every bug fix must have a regression test. Tests live in the `tests/` directory.

### 4. Run the full test suite

```bash
python -m unittest discover -s tests
```

All tests must pass before you commit.

### 5. Commit your changes

Use [Conventional Commits](https://www.conventionalcommits.org/):

```
feat: add reddit scraper
fix: handle empty summary in telegram digest
docs: clarify scheduler catch-up logic
test: add coverage for scheduler catch-up at 11:59
chore: bump requests to 2.32.0
```

- Subject line: 50 chars or less, imperative mood, no trailing period
- Body wraps at 72 chars and explains *why*, not *what*
- One logical change per commit (atomic commits)

### 6. Push and create a PR

```bash
git push origin feat/my-feature
```

Then open a pull request against `main` on the upstream repo.

---

## Code standards

### Python

- **Python 3.8+ compatible.** Do not use `X | None` union syntax — use `Optional[X]` from `typing`.
- **Type hints** on all public functions and methods.
- **mypy must pass.** Run `python -m mypy news_tool.py database.py` before committing.
- **Docstrings** on all public functions in Google style:

```python
def fetch_articles(source: str, limit: int = 10) -> List[Article]:
    """Fetch articles from a given source.

    Args:
        source: The source identifier to fetch from.
        limit: Maximum number of articles to return.

    Returns:
        A list of Article objects.

    Raises:
        ValueError: If the source is not recognized.
    """
```

- **No comments in code** unless explicitly requested in a review.
- **Atomic commits.** Each commit should be a single logical change.
- **f-strings** for string formatting. No `%` or `.format()`.
- **No `print()` for normal-flow output.** Use the `logging` module.

---

## Testing requirements

- **All new features** must include unit tests.
- **Bug fixes** must include a regression test that would have caught the bug.
- Tests go in the `tests/` directory.
- Use `unittest.TestCase` and `unittest.mock` (no external test dependencies).
- Run the full suite before submitting:

```bash
python -m unittest discover -s tests
```

- Follow existing test naming conventions and patterns in the codebase.

---

## Pull request guidelines

- **One feature or fix per PR.** Keep PRs focused and reviewable.
- **Clear PR title and description.** Explain what changed and why.
- **Link related issues.** Use `Closes #N` or `Refs #N` in the description.
- **Ensure CI passes.** All GitHub Actions checks must be green.
- **Be responsive to review feedback.** Iteration is part of the process.
- **Update documentation** if your change affects user-facing behavior.

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

## Questions

Have a question? The best places to ask are:

- **GitHub Discussions** — for general questions, architecture decisions, or brainstorming.
- **Issues with the "question" label** — for specific, scoped questions about behavior or implementation.

---

## Areas that need help

- **More scrapers** — Reddit, Hacker News (the comment site, not the security feed), Lobsters, Dev.to, specific Substack blogs
- **Classifier improvements** — better keyword weighting, support for multi-language content, embedding-based classification
- **Dashboard polish** — better mobile layout, virtualized scrolling for large article lists, a "loading" state for `generate_data.py`
- **Telegram improvements** — per-user subscriptions, digests on demand via inline buttons, "save to bookmarks" callback
- **Tests** — end-to-end test of the full pipeline, integration test of the dashboard API, scheduler test for 60s startup delay
- **Documentation** — translations of the README, more `docs/*.md` files (e.g., `docs/DEPLOYMENT.md` for production-style deployments)

---

## Release process

1. Bump version in any place it's referenced.
2. Update `CHANGELOG.md` — move `[Unreleased]` changes to a new dated version block.
3. Tag the release: `git tag -a v1.0.0 -m "Release 1.0.0"`.
4. Push the tag: `git push origin v1.0.0`.
5. The GitHub release is auto-generated from the tag, with the CHANGELOG section as the body.

Releases happen when there's something worth shipping. There's no fixed cadence.

---

Thank you for contributing to Bloomy News!
