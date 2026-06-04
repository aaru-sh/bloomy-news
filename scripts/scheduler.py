#!/usr/bin/env python3
"""
Bloomsberg News - Twice-daily scheduler.

Runs the news pipeline + dashboard regeneration at 12:00 AM and 12:00 PM
local time. On startup, performs a catch-up run if the last scheduled
checkpoint was missed (e.g., laptop was off).

State is persisted to .last_run so restarts are safe.

Run modes:
  python scripts/scheduler.py            # run in foreground
  python scripts/scheduler.py --install  # install as Windows autostart
  python scripts/scheduler.py --uninstall
  python scripts.scheduler.py --run-now  # run pipeline once and exit
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
REG_VALUE_NAME = "BloomsbergScheduler"

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


def install_autostart():
    if os.name != "nt":
        print("Auto-install only supported on Windows.")
        return 1
    import winreg
    script = BASE / "scripts" / "scheduler.py"
    pythonw = Path(PYTHON).parent / "pythonw.exe"
    runner = pythonw if pythonw.exists() else PYTHON
    cmd = f'"{runner}" "{script}"'
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, REG_RUN_KEY, 0, winreg.KEY_SET_VALUE) as key:
            winreg.SetValueEx(key, REG_VALUE_NAME, 0, winreg.REG_SZ, cmd)
        print(f"Installed: HKCU\\{REG_RUN_KEY}\\{REG_VALUE_NAME} = {cmd}")
        return 0
    except OSError as e:
        print(f"Install failed: {e}")
        return 1


def uninstall_autostart():
    if os.name != "nt":
        print("Auto-install only supported on Windows.")
        return 1
    import winreg
    try:
        with winreg.OpenKey(
            winreg.HKEY_CURRENT_USER, REG_RUN_KEY, 0, winreg.KEY_SET_VALUE
        ) as key:
            winreg.DeleteValue(key, REG_VALUE_NAME)
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
    args = parser.parse_args()

    if args.install:
        return install_autostart()
    if args.uninstall:
        return uninstall_autostart()
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
