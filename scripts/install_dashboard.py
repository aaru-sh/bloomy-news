#!/usr/bin/env python3
"""Bloomy News - Dashboard autostart installer.

Installs the dashboard server (dashboard/serve.py) as a Windows autostart
entry so it's running on http://127.0.0.1:8080 any time the user is logged
in, without requiring a terminal. The server binds 127.0.0.1 only and uses
~30-50 MB RAM; the dashboard is on only while the user is logged in, so
the cost is zero outside an active session.

Uses HKCU (not HKLM) so no admin elevation is required. Mirrors the
pattern in scripts/scheduler.py for consistency.

Usage:
    python scripts/install_dashboard.py --install     # register
    python scripts/install_dashboard.py --uninstall   # remove
    python scripts/install_dashboard.py --verify      # 5-check read-only diag

After --install, the next user logon will auto-start the server. To start
it in the current session, run BROWSE_DASHBOARD.bat (one-click launcher).
"""
import argparse
import os
import shlex
import subprocess
import sys
from pathlib import Path

BASE = Path(__file__).parent.parent.resolve()
SERVE_SCRIPT = BASE / "dashboard" / "serve.py"
REG_RUN_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"
REG_VALUE_NAME = "BloomyDashboard"
REG_CWD_VALUE = "BloomyDashboardCwd"


def get_pythonw_path():
    """Locate pythonw.exe reliably. Falls back to python.exe with a warning.

    Same resolution order as scripts/scheduler.py: sibling of sys.executable,
    then walk up parents, then Windows Python Launcher `py`. The fallback to
    python.exe is acceptable for an installer script (which already runs in
    a terminal); the dashboard server is launched by the autostart entry,
    which uses whichever exe this function returns.
    """
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
                capture_output=True, text=True, timeout=5,
            )
            if result.returncode == 0 and result.stdout.strip():
                py = Path(result.stdout.strip()).parent / "pythonw.exe"
                if py.exists():
                    return py, None
        except (subprocess.TimeoutExpired, FileNotFoundError, OSError):
            pass
    return Path(sys.executable), "pythonw.exe not found, falling back to python.exe (a console window will appear at logon)"


def install_autostart():
    """Register the dashboard server in HKCU\\...\\Run.

    Returns 0 on success and 1 on any failure (Windows-only, registry write,
    or post-install verify). Run --verify automatically after registering
    so silent failures surface at install time.
    """
    if os.name != "nt":
        print("Auto-install is Windows-only.")
        return 1
    if not SERVE_SCRIPT.is_file():
        print(f"Install failed: {SERVE_SCRIPT} not found.")
        return 1
    import winreg
    pythonw, warn = get_pythonw_path()
    if warn:
        print(f"[WARN] {warn}")
    cmd = f'"{pythonw}" "{SERVE_SCRIPT}"'
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, REG_RUN_KEY, 0, winreg.KEY_SET_VALUE) as key:
            winreg.SetValueEx(key, REG_VALUE_NAME, 0, winreg.REG_SZ, cmd)
            winreg.SetValueEx(key, REG_CWD_VALUE, 0, winreg.REG_SZ, str(BASE))
    except OSError as e:
        print(f"Install failed: {e}")
        return 1

    print(f"Installed: HKCU\\{REG_RUN_KEY}\\{REG_VALUE_NAME} = {cmd}")
    print(f"  CWD:     {BASE}")
    print()
    verify_rc = verify_install()
    if verify_rc != 0:
        print()
        print("Install succeeded but verification reported issues. Re-run --install after fixing the cause above.")
    return verify_rc


def collect_verify_results():
    """Read-only diagnostic. Returns a list of (name, ok, message) tuples."""
    if os.name != "nt":
        return [("platform", False, "verify is Windows-only")]

    import winreg

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

    if python_path:
        if python_path.is_file():
            results.append(("python path exists", True, str(python_path)))
        else:
            results.append(("python path exists", False, f"{python_path} not found"))
    else:
        results.append(("python path exists", False, "no python path in registry value"))

    if python_path and python_path.is_file():
        try:
            r = subprocess.run(
                [str(python_path), "--version"],
                capture_output=True, text=True, timeout=10,
            )
            if r.returncode == 0:
                ver = (r.stdout or r.stderr or "").strip() or "ok"
                results.append(("python launchable", True, ver))
            else:
                results.append(("python launchable", False, f"exit {r.returncode}"))
        except subprocess.TimeoutExpired:
            results.append(("python launchable", False, "timed out after 10s"))
        except (FileNotFoundError, OSError) as e:
            results.append(("python launchable", False, str(e)))
    else:
        results.append(("python launchable", False, "skipped: python path missing"))

    if script_path:
        if script_path.is_file():
            results.append(("serve.py exists", True, str(script_path)))
        else:
            results.append(("serve.py exists", False, f"{script_path} not found"))
    else:
        results.append(("serve.py exists", False, "no script path in registry value"))

    if cwd_value:
        repo_path = Path(cwd_value)
        if repo_path.is_dir():
            results.append(("repo path reachable", True, str(repo_path)))
        else:
            results.append(("repo path reachable", False, f"{repo_path} not a directory"))
    else:
        results.append(("repo path reachable", False, "no repo path captured at install time"))

    port_listening = False
    try:
        r = subprocess.run(
            ["netstat", "-an"],
            capture_output=True, text=True, timeout=5,
        )
        for line in r.stdout.splitlines():
            if "127.0.0.1:8080" in line and "LISTENING" in line:
                port_listening = True
                break
    except (subprocess.TimeoutExpired, FileNotFoundError, OSError):
        pass
    if port_listening:
        results.append(("port 8080 listening", True, "server is running"))
    else:
        results.append(("port 8080 listening", False, "not bound (server may not be started yet - normal before next logon)"))

    return results


def render_verify_results(results):
    all_ok = True
    for name, ok, message in results:
        marker = "PASS" if ok else "FAIL"
        print(f"  [{marker}] {name}: {message}")
        if not ok:
            all_ok = False
    return all_ok


def verify_install():
    print("Dashboard autostart verification:")
    results = collect_verify_results()
    all_ok = render_verify_results(results)
    if not all_ok:
        print()
        print("Action: python scripts/install_dashboard.py --uninstall && python scripts/install_dashboard.py --install")
    return 0 if all_ok else 1


def uninstall_autostart():
    if os.name != "nt":
        print("Auto-install is Windows-only.")
        return 1
    import winreg
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, REG_RUN_KEY, 0, winreg.KEY_SET_VALUE) as key:
            for name in (REG_VALUE_NAME, REG_CWD_VALUE):
                try:
                    winreg.DeleteValue(key, name)
                except FileNotFoundError:
                    pass
        print("Uninstalled.")
        return 0
    except OSError as e:
        print(f"Uninstall failed: {e}")
        return 1


def main():
    parser = argparse.ArgumentParser(description="Dashboard autostart installer")
    parser.add_argument("--install", action="store_true", help="Register dashboard as Windows autostart")
    parser.add_argument("--uninstall", action="store_true", help="Remove autostart")
    parser.add_argument("--verify", action="store_true", help="Read-only diagnostic (5 checks)")
    args = parser.parse_args()

    if args.install:
        return install_autostart()
    if args.uninstall:
        return uninstall_autostart()
    if args.verify:
        return verify_install()

    parser.print_help()
    return 1


if __name__ == "__main__":
    sys.exit(main())
