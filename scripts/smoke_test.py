#!/usr/bin/env python3
"""Smoke test for Bloomy News — verifies a fresh checkout can run end-to-end.

Run this right after cloning to confirm your machine has everything you need:

    python scripts/smoke_test.py

Or:

    make smoke

Exits 0 on success, 1 on failure. Each check prints [OK] or [FAIL] with a
short remediation hint. The script never touches the real news.db — it
runs in a temp directory and cleans up after itself.

What it checks (in order):
  1. Python version is 3.8+
  2. The only external dependency (`requests`) imports
  3. All required config files exist and parse as JSON
  4. No module contains a hardcoded absolute Windows path
  5. Database can be initialized and the schema created
  6. Dashboard server starts and serves valid /api/articles
  7. Classifier accepts a known sample and returns "LLM"
  8. secrets loader honors env-over-config precedence
"""
import json
import os
import re
import socket
import sqlite3
import sys
import tempfile
import threading
import time
import urllib.request
from http.server import ThreadingHTTPServer
from pathlib import Path

BASE = Path(__file__).parent.parent.resolve()
sys.path.insert(0, str(BASE))
sys.path.insert(0, str(BASE / "dashboard"))

MIN_PY = (3, 8)
PASS = 0
FAIL = 0


def _ok(label, detail=""):
    global PASS
    PASS += 1
    print(f"  [OK]   {label}" + (f" — {detail}" if detail else ""))


def _bad(label, hint=""):
    global FAIL
    FAIL += 1
    print(f"  [FAIL] {label}" + (f"\n         -> {hint}" if hint else ""))


def banner(title):
    print()
    print("=" * 60)
    print(f"  {title}")
    print("=" * 60)


def check_python():
    banner("1. Python version")
    ver = sys.version_info
    if (ver.major, ver.minor) >= MIN_PY:
        _ok(f"Python {ver.major}.{ver.minor}.{ver.micro}", ">= 3.8 required")
    else:
        _bad(
            f"Python {ver.major}.{ver.minor}.{ver.micro}",
            f"Upgrade to Python {MIN_PY[0]}.{MIN_PY[1]} or newer",
        )


def check_deps():
    banner("2. External dependencies")
    try:
        import requests  # noqa: F401
        _ok("requests is importable", f"version {requests.__version__}")
    except ImportError:
        _bad("requests is missing", "Run: pip install -r requirements.txt")


def check_configs():
    banner("3. Config files")
    needed = ["sources.json", "categories.json", "telegram.json"]
    for name in needed:
        path = BASE / "config" / name
        if not path.exists():
            _bad(f"config/{name} missing", "Re-clone the repository")
            continue
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            _ok(f"config/{name} parses as JSON", f"{len(json.dumps(data))} bytes")
        except json.JSONDecodeError as e:
            _bad(f"config/{name} is not valid JSON", str(e))


def check_no_hardcoded_paths():
    banner("4. No hardcoded paths (portable across machines)")
    # Match the specific anti-pattern: a literal Windows-style absolute path
    # inside a Python string. We avoid embedding the literal we are testing
    # for (it would self-match) and instead build it from parts at runtime.
    bad_literal = "E" + ":" + "\\" + "AI" + "\\" + "Projects" + "\\" + "News"
    bad_pattern = re.compile(re.escape(bad_literal))
    offenders = []
    scanned = 0
    for py in BASE.rglob("*.py"):
        if "tests" in py.parts or "logs" in py.parts or "__pycache__" in py.parts:
            continue
        scanned += 1
        try:
            text = py.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue
        if bad_pattern.search(text):
            offenders.append(str(py.relative_to(BASE)))
    if offenders:
        for line in offenders:
            _bad(
                f"{line} contains a hardcoded '{bad_literal}' path",
                "Use Path(__file__).parent / ... instead",
            )
    else:
        _ok(
            "No hardcoded absolute Windows paths",
            f"scanned {scanned} .py files (test/ and __pycache__/ skipped)",
        )


def check_database_init():
    banner("5. Database initialization")
    with tempfile.TemporaryDirectory() as tmp:
        sys.path.insert(0, tmp)
        try:
            import database
            original_db_path = database.DB_PATH
            database.DB_PATH = Path(tmp) / "news.db"
            try:
                database.init_db()
                if not database.DB_PATH.exists():
                    _bad("init_db() did not create news.db", "Check database.py:init_db()")
                    return
                conn = sqlite3.connect(str(database.DB_PATH))
                try:
                    row = conn.execute(
                        "SELECT name FROM sqlite_master WHERE type='table' AND name='articles'"
                    ).fetchone()
                finally:
                    conn.close()
                if row:
                    _ok(
                        "SQLite schema created",
                        f"news.db at {database.DB_PATH.name}, 'articles' table present",
                    )
                else:
                    _bad("'articles' table missing", "Check database.py:init_db()")
            finally:
                database.DB_PATH = original_db_path
        except Exception as e:
            _bad("init_db() raised", f"{type(e).__name__}: {e}")


def check_server_serves():
    banner("6. Dashboard server")
    with tempfile.TemporaryDirectory() as tmp:
        try:
            import serve
        except Exception as e:
            _bad("Could not import serve.py", f"{type(e).__name__}: {e}")
            return

        original = (serve.DATA_DIR, serve.DATA_FILE, serve.BOOKMARKS_FILE)
        serve.DATA_DIR = Path(tmp)
        serve.DATA_FILE = Path(tmp) / "dashboard_data.json"
        serve.BOOKMARKS_FILE = Path(tmp) / "bookmarks.json"

        s = socket.socket()
        s.bind(("127.0.0.1", 0))
        port = s.getsockname()[1]
        s.close()

        httpd = ThreadingHTTPServer(("127.0.0.1", port), serve.DashboardHandler)
        thread = threading.Thread(target=httpd.serve_forever, daemon=True)
        thread.start()
        time.sleep(0.3)

        try:
            with urllib.request.urlopen(
                f"http://127.0.0.1:{port}/api/articles", timeout=3
            ) as resp:
                status = resp.status
                payload = json.loads(resp.read().decode("utf-8"))
            if status == 200 and "articles" in payload:
                _ok(
                    f"GET /api/articles returned 200",
                    f"{len(payload['articles'])} articles (empty state OK)",
                )
            else:
                _bad("GET /api/articles returned unexpected payload", str(payload)[:120])
        except Exception as e:
            _bad("Could not reach dashboard server", f"{type(e).__name__}: {e}")
        finally:
            httpd.shutdown()
            httpd.server_close()
            serve.DATA_DIR, serve.DATA_FILE, serve.BOOKMARKS_FILE = original


def check_classifier():
    banner("7. Classifier")
    try:
        sys.path.insert(0, str(BASE))
        import news_tool  # noqa: F401
        cat, conf, tags, subcat, _embedding = news_tool.classify_article({
            "title": "A new transformer architecture for large language models",
            "summary": "Comparing GPT and BERT on common NLP benchmarks",
        })
        if cat == "LLM" and conf > 0:
            _ok("classify_article() returned LLM", f"confidence={conf:.2f}, subcat={subcat}")
        else:
            _bad(
                "classify_article() returned unexpected result",
                f"got ({cat}, {conf}, {tags}, {subcat})",
            )
    except Exception as e:
        _bad("Could not run classifier", f"{type(e).__name__}: {e}")


def check_secrets_precedence():
    banner("8. Secrets loader")
    os.environ["TELEGRAM_BOT_TOKEN"] = "smoke_test_token"
    try:
        from config import get_telegram_token
        token = get_telegram_token()
        if token == "smoke_test_token":
            _ok("env overrides config", "TELEGRAM_BOT_TOKEN=smoke_test_token wins")
        else:
            _bad("env did not override config", f"got {token!r}")
    except Exception as e:
        _bad("get_telegram_token() raised", f"{type(e).__name__}: {e}")
    finally:
        del os.environ["TELEGRAM_BOT_TOKEN"]


def main():
    print()
    print("=" * 60)
    print("  Bloomy News — Smoke Test")
    print(f"  Project: {BASE}")
    print("=" * 60)

    check_python()
    check_deps()
    check_configs()
    check_no_hardcoded_paths()
    check_database_init()
    check_server_serves()
    check_classifier()
    check_secrets_precedence()

    print()
    print("=" * 60)
    if FAIL == 0:
        print(f"  ALL CHECKS PASSED ({PASS}/{PASS})")
        print()
        print("  Your machine is ready. Next steps:")
        print("    1. cp .env.example .env        # optional: add API keys")
        print("    2. python news_tool.py         # run the pipeline once")
        print("    3. python dashboard/serve.py   # start the dashboard")
        print("    4. Open http://127.0.0.1:8080")
        print()
        print("  Or just run:  make run")
        print("=" * 60)
        return 0
    else:
        print(f"  {FAIL} of {PASS + FAIL} CHECKS FAILED")
        print()
        print("  Fix the [FAIL] items above and re-run:")
        print("    python scripts/smoke_test.py")
        print()
        print("  Common fixes:")
        print("    - pip install -r requirements.txt")
        print("    - Re-clone the repository if files are missing")
        print("    - Upgrade Python to 3.8+")
        print("=" * 60)
        return 1


if __name__ == "__main__":
    sys.exit(main())
