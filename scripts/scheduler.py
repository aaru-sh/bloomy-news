#!/usr/bin/env python3
"""
Bloomy News - Twice-daily scheduler.

Runs the news pipeline + dashboard regeneration at 12:00 AM and 12:00 PM
local time. On startup, performs a catch-up run if the last scheduled
checkpoint was missed (e.g., laptop was off).

State is persisted to .last_run so restarts are safe.

Run modes:
  python scripts/scheduler.py            # run in foreground
  python scripts/scheduler.py --install  # install as Windows autostart
  python scripts/scheduler.py --uninstall
  python scripts/scheduler.py --run-now  # run pipeline once and exit
  python scripts/scheduler.py --verify   # read-only diagnostic (6 checks)

--verify is a read-only diagnostic. It reads the registered autostart
entry from the Windows registry and confirms:
  1. the registered python.exe path exists and is launchable
  2. the registered repo path (cwd at install time) is reachable
  3. the database file is writable
  4. the .env file is present (only if .env.example exists in the repo)
  5. the autostart entry is registered
Prints one pass/fail line per check and exits 0 if all pass, 1 otherwise.
--install runs --verify automatically after registering, so silent
failures (e.g. a moved venv, broken path encoding) surface at install
time instead of at the first scheduled run.
"""
import argparse
import json
import logging
import os
import subprocess
import sys
import time
from datetime import datetime, timedelta
from pathlib import Path

BASE = Path(__file__).parent.parent.resolve()
LOG_DIR = BASE / "logs"
STATE_FILE = BASE / ".last_run"
PIPELINE = BASE / "news_tool.py"
REGEN = BASE / "dashboard" / "generate_data.py"
PYTHON = sys.executable

CHECKPOINT_HOURS = (0, 12)
CACHE_HOURS = 12
STARTUP_DELAY_SEC = 60
PIPELINE_TIMEOUT = 1800
REGEN_TIMEOUT = 300
SLEEP_CHUNK = 30

REG_RUN_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"
REG_VALUE_NAME = "BloomyScheduler"
REG_CWD_VALUE = "BloomySchedulerCwd"

LOG_DIR.mkdir(exist_ok=True)

logging.basicConfig(
    filename=LOG_DIR / "scheduler.log",
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger("scheduler")


def load_state():
    if not STATE_FILE.exists():
        return {"last_run": None, "last_status": None}
    try:
        return json.loads(STATE_FILE.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as e:
        logger.warning("State file unreadable (%s); starting fresh", e)
        return {"last_run": None, "last_status": None}


def save_state(state):
    tmp = STATE_FILE.with_suffix(".tmp")
    try:
        tmp.write_text(json.dumps(state, indent=2), encoding="utf-8")
        os.replace(tmp, STATE_FILE)
    except OSError as e:
        logger.error("Failed to save state: %s", e)


def run_pipeline():
    started = datetime.now()
    logger.info("=" * 50)
    logger.info("PIPELINE START at %s", started.isoformat(timespec="seconds"))
    logger.info("=" * 50)

    steps = [
        ("news_tool.py", [PYTHON, str(PIPELINE)], PIPELINE_TIMEOUT),
        ("generate_data.py", [PYTHON, str(REGEN)], REGEN_TIMEOUT),
    ]

    for label, cmd, timeout in steps:
        logger.info("Running %s", label)
        try:
            result = subprocess.run(
                cmd,
                cwd=str(BASE),
                capture_output=True,
                text=True,
                timeout=timeout,
            )
        except subprocess.TimeoutExpired:
            logger.error("%s timed out after %ds", label, timeout)
            return False
        except Exception as e:
            logger.error("%s failed to launch: %s", label, e)
            return False

        if result.returncode != 0:
            logger.error(
                "%s exited %d\nstdout: %s\nstderr: %s",
                label,
                result.returncode,
                result.stdout[-2000:],
                result.stderr[-2000:],
            )
            return False
        logger.info("%s ok", label)

    elapsed = (datetime.now() - started).total_seconds()
    logger.info("Pipeline finished in %.0fs", elapsed)
    return True


def should_catch_up(state, now):
    last = state.get("last_run")
    if not last:
        return True
    try:
        last_dt = datetime.fromisoformat(last)
    except ValueError:
        return True
    hours = (now - last_dt).total_seconds() / 3600
    if hours > CACHE_HOURS:
        logger.info("Catch-up needed: %.1fh since last run", hours)
        return True
    logger.info("Skipping catch-up: only %.1fh since last run", hours)
    return False


def next_checkpoint(now):
    for h in CHECKPOINT_HOURS:
        candidate = now.replace(hour=h, minute=0, second=0, microsecond=0)
        if candidate > now:
            return candidate
    tomorrow = (now + timedelta(days=1)).replace(
        hour=CHECKPOINT_HOURS[0], minute=0, second=0, microsecond=0
    )
    return tomorrow


def sleep_until(target_dt):
    while True:
        now = datetime.now()
        wait = (target_dt - now).total_seconds()
        if wait <= 0:
            return
        time.sleep(min(SLEEP_CHUNK, wait))


def run_loop():
    logger.info("Scheduler starting (checkpoints: %s)", CHECKPOINT_HOURS)
    state = load_state()
    now = datetime.now()

    if should_catch_up(state, now):
        logger.info("Waiting %ds before catch-up run", STARTUP_DELAY_SEC)
        time.sleep(STARTUP_DELAY_SEC)
        ok = run_pipeline()
        save_state({"last_run": datetime.now().isoformat(), "last_status": "ok" if ok else "failed"})

    while True:
        now = datetime.now()
        target = next_checkpoint(now)
        wait_min = (target - now).total_seconds() / 60
        logger.info("Next run at %s (in %.0f min)", target.isoformat(timespec="seconds"), wait_min)
        sleep_until(target)
        ok = run_pipeline()
        save_state({"last_run": datetime.now().isoformat(), "last_status": "ok" if ok else "failed"})


def get_pythonw_path():
    """Locate pythonw.exe reliably. Falls back to python.exe with a warning.

    Tries in this order:
    1. Sibling of sys.executable (e.g. venv/Scripts/pythonw.exe)
    2. Sibling named pythonw.exe in the same parent dir as sys.executable
    3. Asks `py -c "import sys; print(sys.executable)"` (Windows Python Launcher)
    4. Falls back to sys.executable (python.exe) and prints a warning
    """
    import sys
    candidates = []
    base = Path(sys.executable).parent
    candidates.append(base / "pythonw.exe")
    for ancestor in [base, *base.parents]:
        candidates.append(ancestor / "pythonw.exe")
    for c in candidates:
        if c.exists():
            return c, None
    if os.name == "nt":
        try:
            result = subprocess.run(
                ["py", "-c", "import sys; print(sys.executable)"],
                capture_output=True, text=True, timeout=5
            )
            if result.returncode == 0 and result.stdout.strip():
                py = Path(result.stdout.strip()).parent / "pythonw.exe"
                if py.exists():
                    return py, None
        except (subprocess.TimeoutExpired, FileNotFoundError, OSError):
            pass
    return Path(sys.executable), "pythonw.exe not found, falling back to python.exe (a console window will appear at login)"


def install_autostart():
    """Install the scheduler as a Windows autostart entry.

    Writes HKCU\\Software\\Microsoft\\Windows\\CurrentVersion\\Run\\BloomyScheduler
    plus a companion BloomySchedulerCwd value that records the project root
    at install time (used by --verify to detect a moved repo).

    After registering, runs --verify so silent failures (moved venv, broken
    path encoding) surface at install time instead of at first scheduled run.
    Returns 0 only if the registry write AND the post-install verify both
    succeed; returns 1 otherwise.
    """
    if os.name != "nt":
        print("Auto-install only supported on Windows.")
        return 1
    import winreg
    pythonw, warn = get_pythonw_path()
    if warn:
        print(f"[WARN] {warn}")
    script = BASE / "scripts" / "scheduler.py"
    cmd = f'"{pythonw}" "{script}"'
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, REG_RUN_KEY, 0, winreg.KEY_SET_VALUE) as key:
            winreg.SetValueEx(key, REG_VALUE_NAME, 0, winreg.REG_SZ, cmd)
            winreg.SetValueEx(key, REG_CWD_VALUE, 0, winreg.REG_SZ, str(BASE))
    except OSError as e:
        print(f"Install failed: {e}")
        return 1

    print(f"Installed: HKCU\\{REG_RUN_KEY}\\{REG_VALUE_NAME} = {cmd}")
    print()
    verify_rc = verify_install()
    if verify_rc != 0:
        print()
        print("Install succeeded but verification reported issues. Re-run --install after fixing the cause above.")
    return verify_rc


def collect_verify_results():
    """Read-only diagnostic. Returns a list of (name, ok, message) tuples.

    Reads the registered autostart value (HKCU\\...\\Run\\BloomyScheduler)
    and the companion BloomySchedulerCwd value (recorded at install time),
    parses the python and script paths, and reports on:
      1. python path exists
      2. python is launchable and reports a version
      3. repo path (recorded at install time) is reachable
      4. database file is writable
      5. .env exists (only if .env.example is present in the repo)
      6. autostart entry is registered
    """
    if os.name != "nt":
        return [("platform", False, "verify is Windows-only")]

    import winreg
    import shlex

    value = None
    cwd_value = None
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, REG_RUN_KEY, 0, winreg.KEY_READ) as key:
            try:
                value, _ = winreg.QueryValueEx(key, REG_VALUE_NAME)
            except FileNotFoundError:
                value = None
            try:
                cwd_value, _ = winreg.QueryValueEx(key, REG_CWD_VALUE)
            except FileNotFoundError:
                cwd_value = None
    except OSError as e:
        return [("autostart entry", False, f"registry open failed: {e}")]

    if value is None:
        return [(
            "autostart entry",
            False,
            f"not registered at HKCU\\{REG_RUN_KEY}\\{REG_VALUE_NAME} (run --install)",
        )]

    try:
        parts = shlex.split(value)
    except ValueError as e:
        return [("autostart command", False, f"could not parse: {e}")]

    python_path = Path(parts[0]) if parts and parts[0] else None
    script_path = Path(parts[1]) if len(parts) > 1 and parts[1] else None

    results = []

    # 1. Python path exists
    if python_path:
        if python_path.is_file():
            results.append(("python path exists", True, str(python_path)))
        else:
            results.append(("python path exists", False, f"{python_path} not found"))
    else:
        results.append(("python path exists", False, "no python path in registry value"))

    # 2. Python launchable and reports a version
    if python_path and python_path.is_file():
        try:
            r = subprocess.run(
                [str(python_path), "--version"],
                capture_output=True, text=True, timeout=10,
            )
            if r.returncode == 0:
                out = (r.stdout or "").strip()
                err = (r.stderr or "").strip()
                ver = out or err or "ok"
                results.append(("python launchable", True, ver))
            else:
                results.append(("python launchable", False, f"exit {r.returncode}"))
        except subprocess.TimeoutExpired:
            results.append(("python launchable", False, "timed out after 10s"))
        except (FileNotFoundError, OSError) as e:
            results.append(("python launchable", False, str(e)))
    else:
        results.append(("python launchable", False, "skipped: python path missing"))

    # 3. Repo path reachable. Prefer the cwd captured at install time;
    # fall back to the parent of the registered script (which is always at
    # <repo>/scripts/scheduler.py per the BASE constant).
    if cwd_value:
        repo_path = Path(cwd_value)
    elif script_path:
        repo_path = script_path.parent.parent
    else:
        repo_path = None

    if repo_path:
        if repo_path.is_dir():
            results.append(("repo path reachable", True, str(repo_path)))
        else:
            results.append(("repo path reachable", False, f"{repo_path} not a directory"))
    else:
        results.append(("repo path reachable", False, "no repo path captured at install time"))

    # 4. Database writable
    if repo_path and repo_path.is_dir():
        db_path = repo_path / "news.db"
        try:
            with open(str(db_path), "a"):
                pass
            results.append(("database writable", True, str(db_path)))
        except OSError as e:
            results.append(("database writable", False, f"{db_path}: {e}"))
    else:
        results.append(("database writable", False, "skipped: repo path missing"))

    # 5. .env present (only if .env.example exists)
    if repo_path and repo_path.is_dir():
        env_example = repo_path / ".env.example"
        env_file = repo_path / ".env"
        if env_example.is_file():
            if env_file.is_file():
                results.append((".env file present", True, str(env_file)))
            else:
                results.append((
                    ".env file present",
                    False,
                    f"{env_file} not found (copy from .env.example)",
                ))
        # else: not all installs use .env, so this check is intentionally skipped
    else:
        results.append((".env file present", False, "skipped: repo path missing"))

    # 6. Autostart registered (this codebase uses HKCU Run key, not Task Scheduler)
    results.append((
        "autostart registered",
        True,
        f"HKCU\\{REG_RUN_KEY}\\{REG_VALUE_NAME}",
    ))

    return results


def render_verify_results(results):
    """Print one pass/fail line per tuple. Returns True if all pass."""
    all_ok = True
    for name, ok, message in results:
        marker = "PASS" if ok else "FAIL"
        print(f"  [{marker}] {name}: {message}")
        if not ok:
            all_ok = False
    return all_ok


def verify_install():
    """Read-only diagnostic. Exits 0 if all checks pass, 1 otherwise.

    Reads the registered autostart value from the registry, parses the
    python and script paths, and runs 6 checks (python path, python
    launchable, repo path, database writable, .env present, autostart
    registered). On failure, prints a one-line remediation hint.
    """
    print("Scheduler verification:")
    results = collect_verify_results()
    all_ok = render_verify_results(results)
    if not all_ok:
        print()
        print("Action: python scripts/scheduler.py --uninstall && python scripts/scheduler.py --install")
    return 0 if all_ok else 1


def uninstall_autostart():
    if os.name != "nt":
        print("Auto-install only supported on Windows.")
        return 1
    import winreg
    try:
        with winreg.OpenKey(
            winreg.HKEY_CURRENT_USER, REG_RUN_KEY, 0, winreg.KEY_SET_VALUE
        ) as key:
            for name in (REG_VALUE_NAME, REG_CWD_VALUE):
                try:
                    winreg.DeleteValue(key, name)
                except FileNotFoundError:
                    pass
        print("Uninstalled.")
        return 0
    except FileNotFoundError:
        print("Not installed.")
        return 0
    except OSError as e:
        print(f"Uninstall failed: {e}")
        return 1


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--install", action="store_true", help="Install as Windows autostart")
    parser.add_argument("--uninstall", action="store_true", help="Remove autostart")
    parser.add_argument("--run-now", action="store_true", help="Run pipeline once and exit")
    parser.add_argument("--status", action="store_true", help="Print state and exit")
    parser.add_argument("--verify", action="store_true", help="Read-only diagnostic: 6 checks (python, repo, db, .env, autostart). Exits 1 on any failure.")
    args = parser.parse_args()

    if args.install:
        return install_autostart()
    if args.uninstall:
        return uninstall_autostart()
    if args.verify:
        return verify_install()
    if args.run_now:
        ok = run_pipeline()
        save_state({"last_run": datetime.now().isoformat(), "last_status": "ok" if ok else "failed"})
        return 0 if ok else 1
    if args.status:
        state = load_state()
        print(json.dumps(state, indent=2))
        return 0

    run_loop()
    return 0


if __name__ == "__main__":
    sys.exit(main())
