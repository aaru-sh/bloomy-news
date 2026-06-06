#!/usr/bin/env python3
"""HTTP server with API endpoints for the Bloomy News dashboard."""
import http.server
import json
import logging
import os
import sys
import threading
import re
import tempfile
from logging.handlers import RotatingFileHandler
from pathlib import Path
from urllib.parse import urlparse

# Make the project root importable so we can reach the `database` module
# (which lives next to news_tool.py at the repo root, not inside dashboard/).
_PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))
import database  # noqa: E402

PORT = 8080
HOST = '127.0.0.1'
DASHBOARD_DIR = Path(__file__).parent
DATA_DIR = DASHBOARD_DIR / 'data'
DATA_FILE = DATA_DIR / 'dashboard_data.json'
BOOKMARKS_FILE = DATA_DIR / 'bookmarks.json'
LOG_FILE = DASHBOARD_DIR.parent / 'logs' / 'server.log'

MAX_BODY_SIZE = 1024
MAX_BOOKMARKS = 5000
ID_PATTERN = re.compile(r'^[a-zA-Z0-9_-]{1,64}$')

_bookmarks_lock = threading.Lock()
logger = logging.getLogger('bloomy_news.dashboard')


def setup_logging():
    """Configure root logger to write to logs/server.log with size-based rotation.

    Replaces the previous LAUNCH_DAILY.bat `start /B python ... > log 2>&1`
    pattern, which was broken on Windows: cmd.exe's `>` redirect goes to
    `start`, not to the spawned python process, so the log file was always
    empty even when the server failed. Now serve.py owns its own log file
    and rotates at 1 MB with one generation kept.
    """
    LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
    root = logging.getLogger()
    root.setLevel(logging.INFO)
    for handler in list(root.handlers):
        root.removeHandler(handler)
    file_handler = RotatingFileHandler(
        LOG_FILE, maxBytes=1_000_000, backupCount=1, encoding='utf-8'
    )
    file_handler.setFormatter(logging.Formatter(
        '%(asctime)s [%(levelname)s] %(name)s: %(message)s'
    ))
    root.addHandler(file_handler)
    root.addHandler(logging.StreamHandler(sys.stderr))


def load_data():
    if DATA_FILE.exists():
        try:
            with open(DATA_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except (json.JSONDecodeError, OSError) as e:
            logger.warning("failed to load %s: %s", DATA_FILE, e)
    return {"generated": "", "stats": {}, "articles": []}


def load_bookmarks():
    if BOOKMARKS_FILE.exists():
        try:
            with open(BOOKMARKS_FILE, 'r', encoding='utf-8') as f:
                data = json.load(f)
                if isinstance(data, list):
                    return {"bookmarks": data}
                if isinstance(data, dict) and isinstance(data.get("bookmarks"), list):
                    return data
        except (json.JSONDecodeError, OSError) as e:
            logger.warning("failed to load %s: %s", BOOKMARKS_FILE, e)
    return {"bookmarks": []}


def save_bookmarks_atomic(data):
    """Write bookmarks atomically via temp file + rename to avoid corruption."""
    DATA_DIR.mkdir(exist_ok=True)
    fd, tmp_path = tempfile.mkstemp(
        dir=DATA_DIR,
        prefix='.bookmarks_',
        suffix='.tmp'
    )
    try:
        with os.fdopen(fd, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        os.replace(tmp_path, BOOKMARKS_FILE)
    except Exception:
        if os.path.exists(tmp_path):
            os.unlink(tmp_path)
        raise


class DashboardHandler(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(DASHBOARD_DIR), **kwargs)

    def do_GET(self):
        parsed = urlparse(self.path)
        path = parsed.path.rstrip('/')

        if path == '/api/articles':
            self._send_json(load_data(), cache_max_age=10)
        elif path == '/api/bookmarks':
            self._send_json(load_bookmarks(), cache_max_age=0)
        elif path == '/api/stats':
            data = load_data()
            self._send_json(
                {"stats": data.get("stats", {}), "generated": data.get("generated", "")},
                cache_max_age=10
            )
        else:
            super().do_GET()

    def end_headers(self):
        """Force no-cache on all non-API responses so the dashboard
        (HTML / JS / CSS) refetches on every page load. Without this,
        SimpleHTTPRequestHandler doesn't set Cache-Control on static
        files and the browser caches stale HTML, requiring a hard
        refresh after each pipeline run. API endpoints keep their
        per-endpoint Cache-Control set by _send_json."""
        if hasattr(self, 'path'):
            path = urlparse(self.path).path.rstrip('/')
            if not path.startswith('/api/'):
                self.send_header('Cache-Control', 'no-store, must-revalidate')
                self.send_header('Pragma', 'no-cache')
        super().end_headers()

    def do_POST(self):
        parsed = urlparse(self.path)
        path = parsed.path.rstrip('/')

        if path == '/api/bookmarks/toggle':
            self._handle_bookmark_toggle()
        else:
            self._send_json({"error": "Not found"}, 404)

    def _handle_bookmark_toggle(self):
        try:
            length = int(self.headers.get('Content-Length', 0))
        except (TypeError, ValueError):
            self._send_json({"error": "Invalid Content-Length"}, 400)
            return

        if length <= 0 or length > MAX_BODY_SIZE:
            self._send_json({"error": f"Body size must be 1-{MAX_BODY_SIZE} bytes"}, 413)
            return

        try:
            body = self.rfile.read(length)
            payload = json.loads(body)
        except (json.JSONDecodeError, OSError) as e:
            self._send_json({"error": f"Invalid JSON: {e}"}, 400)
            return

        article_id = payload.get('id', '')
        if not isinstance(article_id, str):
            self._send_json({"error": "id must be a string"}, 400)
            return
        if not ID_PATTERN.match(article_id):
            self._send_json({"error": "id must be 1-64 chars of [a-zA-Z0-9_-]"}, 400)
            return

        with _bookmarks_lock:
            bookmarks = load_bookmarks()
            bm_list = bookmarks.get("bookmarks", [])

            if len(bm_list) >= MAX_BOOKMARKS and article_id not in bm_list:
                self._send_json({"error": f"Bookmark limit reached ({MAX_BOOKMARKS})"}, 429)
                return

            if article_id in bm_list:
                bm_list.remove(article_id)
                starred = False
            else:
                bm_list.append(article_id)
                starred = True
            bookmarks["bookmarks"] = bm_list

            try:
                save_bookmarks_atomic(bookmarks)
            except OSError as e:
                self._send_json({"error": f"Failed to save: {e}"}, 500)
                return

        try:
            database.set_bookmarked_by_hash_prefix(article_id, starred)
        except Exception as e:
            logger.warning("Failed to mirror bookmark %s to DB: %s", article_id, e)

        self._send_json({"starred": starred, "bookmarks": bm_list}, cache_max_age=0)

    def do_OPTIONS(self):
        self.send_response(200)
        self._set_cors_headers()
        self.end_headers()

    def _send_json(self, data, code=200, cache_max_age=None):
        content = json.dumps(data, ensure_ascii=False).encode('utf-8')
        self.send_response(code)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Content-Length', len(content))
        self.send_header('X-Content-Type-Options', 'nosniff')
        self.send_header('X-Frame-Options', 'DENY')
        self.send_header('Referrer-Policy', 'no-referrer')
        if cache_max_age is not None:
            self.send_header('Cache-Control', f'public, max-age={cache_max_age}')
        self._set_cors_headers()
        self.end_headers()
        self.wfile.write(content)

    def _set_cors_headers(self):
        self.send_header('Access-Control-Allow-Origin', 'http://localhost:8080')
        self.send_header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')

    def log_message(self, format, *args):
        if args and len(args) >= 1 and isinstance(args[0], str):
            status = str(args[0])
            if ' 4' in status or ' 5' in status:
                super().log_message(format, *args)
        else:
            super().log_message(format, *args)


if __name__ == '__main__':
    setup_logging()
    os.chdir(DASHBOARD_DIR)
    logger.info("Dashboard server starting on http://%s:%d", HOST, PORT)

    with http.server.ThreadingHTTPServer((HOST, PORT), DashboardHandler) as httpd:
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            logger.info("Dashboard server stopped by user")
        except OSError as e:
            logger.error("Dashboard server failed: %s", e)
            raise
