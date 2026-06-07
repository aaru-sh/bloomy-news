# Security Policy

## Supported Versions

| Version | Supported          |
| ------- | ------------------ |
| 1.2.x   | :white_check_mark: |
| < 1.2   | :x:                |

Only the latest minor release receives security fixes. Older versions are
end-of-life and will not receive patches. Ensure you are running the
most recent release to benefit from security updates.

## Reporting a Vulnerability

**Please do not file a public GitHub issue for security bugs.**

Use one of these private channels:

1. **GitHub Security Advisories** (preferred):
   <https://github.com/aaru-sh/bloomy-news/security/advisories/new>
   This creates a private, encrypted channel between you and the
   maintainers.

2. **Email**: open a draft security advisory on GitHub first, and the
   maintainers will share a private contact address in the advisory
   thread.

### What to Include

A good report contains:

- A clear, reproducible description of the issue
- The affected version(s) and commit hash(es) if known
- Steps to reproduce (ideally a minimal `news_tool.py` / `serve.py`
  snippet or a `curl` invocation)
- The impact you believe it has (data leak, RCE, denial of service,
  etc.)
- Any known workarounds

### Response Timeline

| Milestone         | Target                        |
| ----------------- | ----------------------------- |
| Acknowledgement   | Within **48 hours**           |
| Initial assessment| Within **7 days**             |
| Fix and advisory  | Coordinated with reporter     |

We follow [coordinated disclosure](https://en.wikipedia.org/wiki/Coordinated_vulnerability_disclosure):
please give us a reasonable window to patch before publishing details.

## Security Measures

This project has been designed with the following security measures:

### Network Isolation

- **Localhost binding only** — The dashboard (`dashboard/serve.py`)
  binds to `127.0.0.1:8080`, never `0.0.0.0`. It is unreachable from
  the network by default.
- **CORS restricted** — Cross-origin requests are allowed only from
  `http://localhost:8080`.

### Secrets Management

- **Environment variables via `.env`** — All API keys and secrets
  live in `.env`, which is gitignored. Tracked JSON files use
  `${VAR}` placeholder expansion instead of embedding real values.

### Input Validation and XSS Prevention

- **Bookmark API input validation** — Request body capped at 1 KB,
  bookmark list capped at 5,000 entries, ID pattern enforced, single
  thread per write.
- **HTML escaping** — All rendered content passes through `escapeHtml()`.
- **URL validation** — URLs are validated via `safeUrl()` before
  rendering or redirecting.

### Security Headers

The following headers are set on HTTP responses:

- `X-Content-Type-Options: nosniff`
- `X-Frame-Options: DENY`
- `Referrer-Policy: no-referrer`
- `Cache-Control: no-store` on API endpoints

### Data Integrity

- **Atomic file writes** — Bookmark writes use the
  `tempfile.mkstemp` + `os.replace` pattern, serialized by a
  module-level `threading.Lock`. The same pattern is used by
  `dashboard/generate_data.py` (writes `dashboard_data.json`) and
  `scripts/scheduler.py` (writes `.last_run`).
- **SQLite WAL mode** — Write-Ahead Logging provides crash safety
  and allows concurrent reads without blocking writes.

### Authentication (By Design)

- **No external authentication** — The dashboard is designed for
  single-user, localhost-only access. No login is required because
  the service is only reachable from the same machine. This is an
  intentional design decision, not an oversight.

## Known Limitations

The following are acknowledged trade-offs of the current design:

- **No authentication** — By design, the dashboard has no login
  screen. If you expose it beyond `127.0.0.1` (e.g., via a reverse
  proxy), you must add your own authentication layer.
- **Single-user dashboard** — The application is designed for a
  single operator. Running it multi-user is unsupported and may
  introduce data-race or privilege-separation issues.
- **API keys in `.env`** — If your `.env` file is compromised,
  all connected services (Telegram, NewsAPI, Finnhub, arXiv) are
  exposed. Protect `.env` with appropriate filesystem permissions.
- **SQLite is not a multi-user database** — SQLite with WAL mode is
  suitable for single-writer workloads. Concurrent multi-user access
  is not a supported use case.
- **Upstream content is trusted as-is** — Malicious content returned
  by upstream APIs (Telegram, NewsAPI, RSS feeds) will be stored and
  rendered. The dashboard escapes HTML to prevent XSS, but it does
  not perform content sanitization beyond that.

## Dependency Security

- **Dependabot** is enabled to automatically open PRs when
  dependencies with known vulnerabilities are detected.
- **CodeQL scanning** runs on pushes and pull requests to identify
  code-level vulnerabilities.

Review and merge Dependabot PRs promptly to stay current with
security patches.

## Security Update Process

1. A vulnerability is reported via GitHub Security Advisories.
2. The maintainers acknowledge within 48 hours and triage the issue.
3. A fix is developed and tested on the latest release branch.
4. A new patch version is released (e.g., `1.2.2`).
5. A GitHub Security Advisory is published with credit to the reporter
   (unless they prefer anonymity).
6. Users are encouraged to update by pulling the latest version.

## Acknowledgements

Reporters who follow the process above and respect the disclosure
window will be credited in the release notes of the fix (unless they
prefer to remain anonymous).
