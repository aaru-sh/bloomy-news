# Coding Standards

Python 3.8+ coding standards for the News project.

---

## Python Style

- **PEP 8** with a **120-character line length** (not 79).
- **Black** for auto-formatting.
- **isort** for import sorting using the `black` profile.
- Use **f-strings** over `.format()` or `%` formatting.
- No `print()` for control flow — use the `logging` module instead.
- No bare `except:` — use `except Exception:` at minimum.

## Type Hints

- All **public functions** must have complete type hints.
- Use `Optional[X]` (not `X | None`) for Python 3.8 compatibility.
- Use `List`, `Dict`, `Tuple` from `typing` (not lowercase builtins) for Python 3.8 compatibility.
- `mypy` must pass with **zero errors**.

## Docstrings

- **Google-style** docstrings on all public functions.
- Include `Args`, `Returns`, and `Raises` sections where applicable.
- Keep docstrings concise — 1–3 sentences for simple functions.

```python
def fetch_article(url: str, timeout: int = 30) -> Optional[Article]:
    """Fetch and parse a news article from a URL.

    Args:
        url: The article URL to fetch.
        timeout: Request timeout in seconds.

    Returns:
        Parsed Article or None if the fetch failed.

    Raises:
        ValueError: If the URL is malformed.
    """
```

## Testing

- All **new features** must have tests.
- All **bug fixes** must have regression tests.
- Use `unittest.TestCase` and `unittest.mock`.
- Test file naming: `test_<module>.py`
- Test class naming: `Test<Feature>`
- Test method naming: `test_<behavior>`
- Aim for **80%+ coverage** on new code.

```python
class TestArticleFetcher(unittest.TestCase):
    def test_fetch_returns_article_on_success(self):
        ...

    def test_fetch_returns_none_on_timeout(self):
        ...
```

## Git

- **Conventional Commits** for all messages:
  - `feat:` new feature
  - `fix:` bug fix
  - `docs:` documentation only
  - `test:` adding or updating tests
  - `chore:` maintenance tasks
  - `refactor:` code change that neither fixes a bug nor adds a feature
  - `perf:` performance improvement
- One feature or fix per commit.
- Atomic commits — no "fix stuff" or "wip" commits.
- **No secrets** in commits — verify before pushing.

## Error Handling

- Use **specific exception types**, never bare `except:`.
- Log errors with **context** (file, line, function name).
- **Fail gracefully** — a single scraper failure should not crash the entire pipeline.

```python
try:
    article = fetch_article(url)
except ConnectionError as e:
    logger.error("Failed to fetch %s: %s", url, e)
    return None
```

## Security

- No hardcoded secrets — use environment variables or a secrets manager.
- **Input validation** on all API endpoints.
- **Atomic file writes** — write to a temp file, then `os.replace()` to the final path.
- No `eval()` or `exec()` on user input.

## Code Organization

- One class per file for larger classes.
- Related functions grouped in the same module.
- Import order: **stdlib → third-party → local** (enforced by isort).
- No circular imports.
