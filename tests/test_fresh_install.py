"""Smoke test that simulates a fresh install.

Verifies that on a clean checkout (no .env, no news.db, no dashboard data,
no .last_run) the system can:
  1. Resolve all paths relative to the project root (no hardcoded E:\\ paths).
  2. Initialize the SQLite database and create the schema.
  3. Generate dashboard data even when the DB is empty.
  4. Serve a valid /api/articles response (empty articles list) from serve.py.
  5. Reject invalid bookmark IDs.

The TestFreshInstallFlow cases run in a subprocess so the real `database`
module is never imported into the test's process. Previously these tests
copied modules into a temp dir and used importlib to load them, which
polluted `sys.modules` for the rest of the suite (e.g. TestServerSmoke
would see a database module bound to the wrong DB_PATH).
"""
import json
import os
import subprocess
import sys
import tempfile
import threading
import time
import unittest
import urllib.error
import urllib.request
from pathlib import Path
from unittest.mock import MagicMock, patch

BASE = Path(__file__).parent.parent
sys.path.insert(0, str(BASE))
sys.path.insert(0, str(BASE / "dashboard"))


def _run_in_subprocess(root: Path, script: str) -> str:
    """Run a Python snippet in a fresh interpreter with `root` on sys.path
    AND as CWD, so relative `sqlite3.connect('news.db')` opens the temp DB
    and not the test runner's project-root DB.
    """
    full = (
        f"import sys, os; sys.path.insert(0, r'{root.as_posix()}'); "
        f"os.chdir(r'{root.as_posix()}')\n" + script
    )
    result = subprocess.run(
        [sys.executable, "-c", full],
        capture_output=True,
        text=True,
        timeout=30,
    )
    if result.returncode != 0:
        raise AssertionError(
            f"subprocess failed (exit {result.returncode}):\n"
            f"STDOUT:\n{result.stdout}\nSTDERR:\n{result.stderr}"
        )
    return result.stdout + result.stderr


class TestPathResolution(unittest.TestCase):
    """All scripts must resolve paths relative to their __file__, not hardcoded Windows paths."""

    def _project_root(self):
        return Path(__file__).parent.parent.resolve()

    def test_database_paths_derive_from_module(self):
        import database
        root = self._project_root()
        self.assertEqual(database.DB_PATH, root / "news.db")
        self.assertEqual(
            database.BOOKMARKS_FILE,
            root / "dashboard" / "data" / "bookmarks.json"
        )

    def test_telegram_bot_paths_derive_from_module(self):
        import scripts.telegram_bot as telegram_bot
        root = self._project_root()
        self.assertEqual(telegram_bot.BASE, root)
        import database
        self.assertEqual(database.DB_PATH, root / "news.db")

    def test_serve_paths_derive_from_module(self):
        import serve
        dashboard_dir = self._project_root() / "dashboard"
        self.assertEqual(serve.DASHBOARD_DIR, dashboard_dir)
        self.assertEqual(
            serve.DATA_FILE, dashboard_dir / "data" / "dashboard_data.json"
        )
        self.assertEqual(
            serve.BOOKMARKS_FILE, dashboard_dir / "data" / "bookmarks.json"
        )

    def test_generate_data_paths_derive_from_module(self):
        import generate_data
        self.assertEqual(generate_data.BASE, self._project_root())

    def test_scheduler_paths_derive_from_module(self):
        import scripts.scheduler as scheduler
        self.assertEqual(scheduler.BASE, self._project_root())


class TestFreshInstallFlow(unittest.TestCase):
    """End-to-end smoke test: simulate a clean checkout in a temp dir.

    Each test runs in a subprocess so the parent test process's
    sys.modules stays clean. This is the fix for the historical
    TestFreshInstallFlow sys.modules pollution that blocked v1.5.0
    work on the in-memory bookmark store.
    """

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)

        for sub in ("config", "logs", "dashboard", "dashboard/data",
                    "scripts", "tests"):
            (self.root / sub).mkdir(parents=True, exist_ok=True)

        for cfg in ("categories.json", "sources.json", "telegram.json"):
            (self.root / "config" / cfg).write_text(
                (BASE / "config" / cfg).read_text(encoding="utf-8"),
                encoding="utf-8",
            )

        for src in ("database.py", "config.py", "news_tool.py"):
            (self.root / src).write_text(
                (BASE / src).read_text(encoding="utf-8"), encoding="utf-8"
            )

        (self.root / "dashboard" / "generate_data.py").write_text(
            (BASE / "dashboard" / "generate_data.py").read_text(encoding="utf-8"),
            encoding="utf-8",
        )
        (self.root / "dashboard" / "serve.py").write_text(
            (BASE / "dashboard" / "serve.py").read_text(encoding="utf-8"),
            encoding="utf-8",
        )

        for src in ("scheduler.py", "check_system.py", "telegram_bot.py"):
            (self.root / "scripts" / src).write_text(
                (BASE / "scripts" / src).read_text(encoding="utf-8"),
                encoding="utf-8",
            )

    def tearDown(self):
        self.tmp.cleanup()

    def test_init_db_creates_db_at_project_root(self):
        """importing database and calling init_db() should create news.db inside the project root."""
        self.assertFalse((self.root / "news.db").exists())
        _run_in_subprocess(self.root, """
import database
database.init_db()
import os, sqlite3
assert os.path.exists('news.db'), 'no db'
conn = sqlite3.connect('news.db')
row = conn.execute(
    "SELECT name FROM sqlite_master WHERE type='table' AND name='articles'"
).fetchone()
assert row is not None, 'no articles table'
# v1.4.2: verify the new bookmarked column is created
cols = [r[1] for r in conn.execute('PRAGMA table_info(articles)').fetchall()]
assert 'bookmarked' in cols, f'no bookmarked column; have {cols}'
conn.close()
""")

    def test_serve_api_handles_missing_data_file(self):
        """serve.py must return valid JSON when dashboard_data.json is missing."""
        tmp_data = self.root / "dashboard" / "data"
        _run_in_subprocess(self.root, f"""
import importlib.util
from pathlib import Path
spec = importlib.util.spec_from_file_location('serve', r'{(self.root / 'dashboard' / 'serve.py').as_posix()}')
serve = importlib.util.module_from_spec(spec)
spec.loader.exec_module(serve)
serve.DATA_FILE = Path(r'{tmp_data.as_posix()}/dashboard_data.json')
serve.BOOKMARKS_FILE = Path(r'{tmp_data.as_posix()}/bookmarks.json')
payload = serve.load_data()
assert 'articles' in payload, f'no articles key in {{payload}}'
assert payload['articles'] == [], f'expected empty list, got {{payload["articles"]}}'
bookmarks = serve.load_bookmarks()
assert bookmarks == {{'bookmarks': []}}, f'expected empty bookmarks, got {{bookmarks}}'
""")

    def test_generate_data_creates_file_on_empty_db(self):
        """generate_data.build_dashboard_data() must not crash on an empty DB."""
        _run_in_subprocess(self.root, f"""
import importlib.util
from pathlib import Path
spec = importlib.util.spec_from_file_location('generate_data', r'{(self.root / 'dashboard' / 'generate_data.py').as_posix()}')
gd = importlib.util.module_from_spec(spec)
spec.loader.exec_module(gd)
gd.BASE = Path(r'{self.root.as_posix()}')
try:
    import database
    database.init_db()
except Exception:
    pass
data = gd.build_dashboard_data()
assert 'articles' in data, f'no articles key in {{data}}'
assert 'stats' in data, f'no stats key in {{data}}'
assert isinstance(data['articles'], list)
assert isinstance(data['stats'], dict)
""")


class TestServerSmoke(unittest.TestCase):
    """Spin up serve.py on a free port and hit the API endpoints."""

    def setUp(self):
        import serve
        self.serve = serve
        self._db_mock_patcher = patch.object(serve, 'database', MagicMock())
        self._db_mock_patcher.start()

        import socket
        s = socket.socket()
        s.bind(("127.0.0.1", 0))
        self.port = s.getsockname()[1]
        s.close()

        self.tmp = tempfile.TemporaryDirectory()
        self.tmp_data = Path(self.tmp.name)
        self.serve.DATA_DIR = self.tmp_data
        self.serve.DATA_FILE = self.tmp_data / "dashboard_data.json"
        self.serve.BOOKMARKS_FILE = self.tmp_data / "bookmarks.json"

        from http.server import ThreadingHTTPServer
        self.httpd = ThreadingHTTPServer(("127.0.0.1", self.port), self.serve.DashboardHandler)
        self.thread = threading.Thread(target=self.httpd.serve_forever, daemon=True)
        self.thread.start()
        time.sleep(0.3)

    def tearDown(self):
        self.httpd.shutdown()
        self.httpd.server_close()
        self.tmp.cleanup()
        self._db_mock_patcher.stop()

    def _get(self, path):
        url = f"http://127.0.0.1:{self.port}{path}"
        with urllib.request.urlopen(url, timeout=3) as resp:
            return resp.status, json.loads(resp.read().decode("utf-8"))

    def _post(self, path, body):
        url = f"http://127.0.0.1:{self.port}{path}"
        data = json.dumps(body).encode("utf-8")
        req = urllib.request.Request(url, data=data, method="POST",
                                     headers={"Content-Type": "application/json"})
        try:
            with urllib.request.urlopen(req, timeout=3) as resp:
                return resp.status, json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            return e.code, json.loads(e.read().decode("utf-8"))

    def test_articles_endpoint_empty(self):
        status, payload = self._get("/api/articles")
        self.assertEqual(status, 200)
        self.assertIn("articles", payload)
        self.assertEqual(payload["articles"], [])

    def test_bookmarks_endpoint_empty(self):
        status, payload = self._get("/api/bookmarks")
        self.assertEqual(status, 200)
        self.assertEqual(payload, {"bookmarks": []})

    def test_bookmark_toggle_round_trip(self):
        status, payload = self._post("/api/bookmarks/toggle", {"id": "abc123"})
        self.assertEqual(status, 200)
        self.assertTrue(payload["starred"])
        self.assertIn("abc123", payload["bookmarks"])

        status, payload = self._post("/api/bookmarks/toggle", {"id": "abc123"})
        self.assertEqual(status, 200)
        self.assertFalse(payload["starred"])
        self.assertNotIn("abc123", payload["bookmarks"])

    def test_bookmark_toggle_mirrors_to_db(self):
        """v1.4.2: toggling a bookmark must also call set_bookmarked_by_hash_prefix."""
        self._post("/api/bookmarks/toggle", {"id": "deadbeefcafe1234"})
        self.serve.database.set_bookmarked_by_hash_prefix.assert_called_with(
            "deadbeefcafe1234", True,
        )

        self._post("/api/bookmarks/toggle", {"id": "deadbeefcafe1234"})
        self.serve.database.set_bookmarked_by_hash_prefix.assert_called_with(
            "deadbeefcafe1234", False,
        )

    def test_bookmark_id_rejected(self):
        status, payload = self._post("/api/bookmarks/toggle", {"id": "has spaces!"})
        self.assertEqual(status, 400)
        self.assertIn("error", payload)
        # v1.4.2: an invalid id must not reach the DB mirror
        self.serve.database.set_bookmarked_by_hash_prefix.assert_not_called()


if __name__ == "__main__":
    unittest.main()
