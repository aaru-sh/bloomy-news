#!/usr/bin/env python3
"""HTTP server with API endpoints for the Bloomsberg News dashboard."""
import http.server
import json
import os
import sys
import threading
import re
import tempfile
from pathlib import Path
from urllib.parse import urlparse

PORT = 8080
HOST = '127.0.0.1'
DASHBOARD_DIR = Path(__file__).parent
DATA_DIR = DASHBOARD_DIR / 'data'
DATA_FILE = DATA_DIR / 'dashboard_data.json'
BOOKMARKS_FILE = DATA_DIR / 'bookmarks.json'

MAX_BODY_SIZE = 1024
MAX_BOOKMARKS = 5000
ID_PATTERN = re.compile(r'^[a-zA-Z0-9_-]{1,64}$')

_bookmarks_lock = threading.Lock()


def load_data():
    if DATA_FILE.exists():
        try:
            with open(DATA_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except (json.JSONDecodeError, OSError) as e:
            print(f"Warning: failed to load {DATA_FILE}: {e}", file=sys.stderr)
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
            print(f"Warning: failed to load {BOOKMARKS_FILE}: {e}", file=sys.stderr)
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
    os.chdir(DASHBOARD_DIR)
    print(f"Dashboard server: http://{HOST}:{PORT}")

    with http.server.ThreadingHTTPServer((HOST, PORT), DashboardHandler) as httpd:
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            print("\nStopped.")
