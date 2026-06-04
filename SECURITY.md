# Security policy

## Supported versions

| Version | Supported          |
| ------- | ------------------ |
| 1.0.x   | :white_check_mark: |
| < 1.0   | :x:                |

Only the latest minor release receives security fixes. Older versions are
end-of-life.

## Reporting a vulnerability

**Please do not file a public GitHub issue for security bugs.**

Use one of these private channels:

1. **GitHub Security Advisories** (preferred):
   <https://github.com/OWNER/bloomy-news/security/advisories/new>
2. **Email**: open a draft security advisory on GitHub first, and the
   maintainers will share a private contact address in the advisory thread.

You should receive an acknowledgement within **72 hours**. If you do not,
please follow up by mentioning `@maintainers` on the advisory.

### What to include

A good report contains:

- A clear, reproducible description of the issue
- The affected version(s) and commit hash(es) if known
- Steps to reproduce (ideally a minimal `news_tool.py` / `serve.py` snippet
  or a `curl` invocation)
- The impact you believe it has (data leak, RCE, denial of service, etc.)
- Any known workarounds

### What to expect

- **72 hours**: acknowledgement and triage
- **7 days**: initial assessment, severity rating, and a plan for a fix
- **30 days**: target for a fix and a public advisory, coordinated with the
  reporter on disclosure timing

We follow [coordinated disclosure](https://en.wikipedia.org/wiki/Coordinated_vulnerability_disclosure):
please give us a reasonable window to patch before publishing details.

## Threat model (what this project is and is not designed to defend against)

### In scope

- Defense against malicious article content (XSS, embedded iframes,
  script tags) — the dashboard escapes HTML via `escapeHtml()` and
  validates URLs via `safeUrl()`.
- Defense against bookmark API abuse — body size capped at 1 KB,
  bookmark list capped at 5,000, ID pattern enforced, single thread
  per write.
- Defense against configuration leakage — all secrets live in `.env`
  (gitignored); tracked JSON uses `${VAR}` placeholders.
- Defense against race conditions on file writes — all writes are
  atomic (`tempfile.mkstemp` + `os.replace`); bookmark writes hold a
  `threading.Lock`.

### Out of scope (by design)

- **Multi-user authentication.** The dashboard binds `127.0.0.1` only
  and has no login. It is designed to be reachable from a single
  browser on the same machine. Exposing it to a network is unsupported
  and at your own risk — front it with a reverse proxy + TLS + auth
  if you must.
- **API-key leakage from a misconfigured `secrets.py` consumer.**
  Keys that start with `YOUR_` are treated as unset, but a typo
  (e.g., `YOUR_KEY_HERE_PLEASE`) will be treated as a real value.
  Verify your config after editing.
- **Compromise of the upstream APIs** (Telegram, NewsAPI, Finnhub,
  arXiv, the various RSS feeds). If any of those return malicious
  content, this project will faithfully store and render it. Run
  behind a network egress filter if that concerns you.

## Security-related configuration

- `dashboard/serve.py` binds `127.0.0.1:8080` (not `0.0.0.0`).
  Override with `HOST=0.0.0.0` only if you understand the implications.
- HTTP responses carry `X-Content-Type-Options: nosniff`,
  `X-Frame-Options: DENY`, `Referrer-Policy: no-referrer`, and
  `Cache-Control: no-store` on API endpoints.
- CORS is restricted to `http://localhost:8080`.
- SQLite uses WAL mode for crash safety.

## Acknowledgements

Reporters who follow the process above and respect the disclosure
window will be credited in the release notes of the fix (unless they
prefer to remain anonymous).
