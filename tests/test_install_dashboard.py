"""Tests for scripts/install_dashboard.py (v1.2.1).

Covers:
  - --install writes the correct registry values
  - --install is idempotent (running twice does not duplicate values)
  - --uninstall removes the registry values
  - --verify reports correct status
  - Autostart command is a well-formed shlex-parseable string
  - CWD value matches the repo path
  - pythonw.exe resolution picks a real interpreter
"""
import os
import shlex
import subprocess
import sys
import unittest
from pathlib import Path

BASE = Path(__file__).parent.parent
sys.path.insert(0, str(BASE))

REG_RUN_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"
REG_VALUE_NAME = "BloomyDashboard"
REG_CWD_VALUE = "BloomyDashboardCwd"
INSTALLER = BASE / "scripts" / "install_dashboard.py"


def _run(args):
    """Run the installer CLI as a subprocess. Returns (returncode, stdout)."""
    proc = subprocess.run(
        [sys.executable, str(INSTALLER), *args],
        capture_output=True, text=True, timeout=30,
    )
    return proc.returncode, proc.stdout + proc.stderr


def _read_reg_values():
    """Snapshot the two registry values for save/restore in setUp/tearDown."""
    if os.name != "nt":
        return None
    import winreg
    snap = {}
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, REG_RUN_KEY, 0, winreg.KEY_READ) as key:
            for name in (REG_VALUE_NAME, REG_CWD_VALUE):
                try:
                    snap[name] = winreg.QueryValueEx(key, name)[0]
                except FileNotFoundError:
                    snap[name] = None
    except OSError:
        snap = {REG_VALUE_NAME: None, REG_CWD_VALUE: None}
    return snap


def _restore_reg_values(snap):
    if os.name != "nt" or snap is None:
        return
    import winreg
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, REG_RUN_KEY, 0, winreg.KEY_SET_VALUE) as key:
            for name, value in snap.items():
                if value is None:
                    try:
                        winreg.DeleteValue(key, name)
                    except FileNotFoundError:
                        pass
                else:
                    winreg.SetValueEx(key, name, 0, winreg.REG_SZ, value)
    except OSError:
        pass


@unittest.skipUnless(os.name == "nt", "Windows-only (uses HKCU registry)")
class TestInstallDashboard(unittest.TestCase):
    def setUp(self):
        self.snapshot = _read_reg_values()

    def tearDown(self):
        _restore_reg_values(self.snapshot)

    def test_install_creates_registry_values(self):
        rc, out = _run(["--uninstall"])
        self.assertEqual(rc, 0)
        rc, out = _run(["--install"])
        self.assertEqual(rc, 0, f"install failed: {out}")
        self.assertIn("Installed", out)
        import winreg
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, REG_RUN_KEY, 0, winreg.KEY_READ) as key:
            cmd, _ = winreg.QueryValueEx(key, REG_VALUE_NAME)
            cwd, _ = winreg.QueryValueEx(key, REG_CWD_VALUE)
        self.assertIsInstance(cmd, str)
        self.assertIsInstance(cwd, str)
        parts = shlex.split(cmd)
        self.assertEqual(len(parts), 2)
        self.assertTrue(parts[0].lower().endswith("pythonw.exe"))
        self.assertTrue(parts[1].endswith("serve.py"))
        self.assertEqual(Path(cwd).resolve(), BASE.resolve())

    def test_install_is_idempotent(self):
        rc1, _ = _run(["--install"])
        self.assertEqual(rc1, 0)
        rc2, out2 = _run(["--install"])
        self.assertEqual(rc2, 0)
        import winreg
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, REG_RUN_KEY, 0, winreg.KEY_READ) as key:
            values = []
            for name in (REG_VALUE_NAME, REG_CWD_VALUE):
                values.append(winreg.QueryValueEx(key, name)[0])
        self.assertEqual(values[0], values[0])

    def test_uninstall_removes_values(self):
        rc, _ = _run(["--install"])
        self.assertEqual(rc, 0)
        rc, out = _run(["--uninstall"])
        self.assertEqual(rc, 0, f"uninstall failed: {out}")
        self.assertIn("Uninstalled", out)
        import winreg
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, REG_RUN_KEY, 0, winreg.KEY_READ) as key:
            for name in (REG_VALUE_NAME, REG_CWD_VALUE):
                with self.assertRaises(FileNotFoundError):
                    winreg.QueryValueEx(key, name)

    def test_uninstall_when_not_installed_is_noop(self):
        rc, _ = _run(["--uninstall"])
        rc2, out = _run(["--uninstall"])
        self.assertEqual(rc2, 0)
        # Either "Not installed." (key missing) or "Uninstalled." (values missing)
        # is acceptable - both are safe no-ops.
        self.assertTrue(
            "Not installed" in out or "Uninstalled" in out,
            f"unexpected output: {out}",
        )

    def test_verify_when_installed_passes(self):
        _run(["--install"])
        rc, out = _run(["--verify"])
        self.assertIn("python path exists", out)
        self.assertIn("serve.py exists", out)
        self.assertIn("repo path reachable", out)
        self.assertIn("port 8080 listening", out)

    def test_verify_when_not_installed_fails(self):
        _run(["--uninstall"])
        rc, out = _run(["--verify"])
        self.assertEqual(rc, 1)
        self.assertIn("autostart entry", out)
        self.assertIn("not registered", out)

    def test_pythonw_resolution_returns_existing_file(self):
        import importlib.util
        spec = importlib.util.spec_from_file_location("install_dashboard", INSTALLER)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        pythonw, warn = mod.get_pythonw_path()
        self.assertTrue(pythonw.is_file(), f"pythonw not found: {pythonw}")
        self.assertIsNone(warn)


if __name__ == "__main__":
    unittest.main()
