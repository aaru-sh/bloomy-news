#!/usr/bin/env python3
"""System health check for Bloomy News."""
import os
import sys
import sqlite3
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from secrets import get_telegram_token

BASE = Path(__file__).parent.parent

def check_database():
    """Check SQLite database is accessible and has data."""
    db_path = BASE / "news.db"
    if not db_path.exists():
        return {"status": "error", "message": "news.db not found"}
    try:
        conn = sqlite3.connect(str(db_path))
        cursor = conn.execute("SELECT COUNT(*) FROM articles")
        count = cursor.fetchone()[0]
        cursor = conn.execute("SELECT COUNT(*) FROM articles WHERE date(published) = date('now')")
        today = cursor.fetchone()[0]
        conn.close()
        return {"status": "ok", "total": count, "today": today}
    except Exception as e:
        return {"status": "error", "message": str(e)}

def check_config():
    """Check config files exist."""
    configs = ["sources.json", "categories.json", "telegram.json"]
    missing = []
    for c in configs:
        if not (BASE / "config" / c).exists():
            missing.append(c)
    return {"status": "ok" if not missing else "warning", "missing": missing}

def check_dashboard():
    """Check dashboard data exists and is recent."""
    data_file = BASE / "dashboard" / "data" / "dashboard_data.json"
    if not data_file.exists():
        return {"status": "warning", "message": "No dashboard data (run generate_data.py)"}
    import time
    age_hours = (time.time() - data_file.stat().st_mtime) / 3600
    return {"status": "ok" if age_hours < 24 else "warning", "age_hours": round(age_hours, 1)}

def check_telegram():
    """Check Telegram bot connectivity."""
    try:
        import requests
        token = get_telegram_token()
        if not token:
            return {"status": "warning", "message": "TELEGRAM_BOT_TOKEN not set"}
        r = requests.get(f"https://api.telegram.org/bot{token}/getMe", timeout=5)
        data = r.json()
        if data.get("ok"):
            return {"status": "ok", "bot": data["result"].get("username")}
        return {"status": "error", "message": "Bot token invalid"}
    except Exception as e:
        return {"status": "error", "message": str(e)}

def check_disk():
    """Check available disk space."""
    import shutil
    total, used, free = shutil.disk_usage(str(BASE))
    free_gb = free / (1024**3)
    return {"status": "ok" if free_gb > 1 else "warning", "free_gb": round(free_gb, 1)}

def main():
    print("=" * 50)
    print("Bloomy News - System Health Check")
    print("=" * 50)
    
    checks = {
        "Database": check_database(),
        "Config": check_config(),
        "Dashboard": check_dashboard(),
        "Telegram": check_telegram(),
        "Disk": check_disk(),
    }
    
    all_ok = True
    for name, result in checks.items():
        status = result["status"]
        icon = "[OK]" if status == "ok" else "[!!]" if status == "warning" else "[ERR]"
        if status == "error":
            all_ok = False
        
        details = {k: v for k, v in result.items() if k != "status"}
        detail_str = f" — {details}" if details else ""
        print(f"  {icon} {name}{detail_str}")
    
    print("=" * 50)
    if all_ok:
        print("All systems operational.")
    else:
        print("Some issues detected. Check errors above.")
    
    return 0 if all_ok else 1

if __name__ == "__main__":
    sys.exit(main())
