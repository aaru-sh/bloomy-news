#!/usr/bin/env bash
# Bloomy News - Daily Launcher (Linux / macOS)
#
# Mirrors LAUNCH_DAILY.bat for non-Windows systems.
# - Runs health check
# - Starts dashboard server on 127.0.0.1:8080 if not already running
# - Runs the news pipeline (news_tool.py)
# - Regenerates dashboard data
#
# Usage:
#   ./launch_daily.sh
set -u
# Don't `set -e`: we want to continue past non-fatal steps.

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

PYTHON="${PYTHON:-python3}"
HOST="127.0.0.1"
PORT=8080
URL="http://${HOST}:${PORT}"

mkdir -p logs

echo "=========================================="
echo "  Bloomy News - Starting Up"
echo "=========================================="
echo

# --- 1. Health check ---
echo "[1/5] Running system health check..."
"$PYTHON" scripts/check_system.py || echo "  WARNING: Some checks failed. Continuing anyway..."
echo

# --- 2. Check / start dashboard server ---
echo "[2/5] Checking dashboard server..."
if (echo > /dev/tcp/${HOST}/${PORT}) >/dev/null 2>&1; then
    echo "  Server already running on port ${PORT} - skipping start."
else
    echo "  Starting dashboard server..."
    nohup "$PYTHON" dashboard/serve.py > logs/server.log 2>&1 &
    SERVER_PID=$!
    sleep 2
    if (echo > /dev/tcp/${HOST}/${PORT}) >/dev/null 2>&1; then
        echo "  Server started at ${URL} (pid ${SERVER_PID})"
    else
        echo "  ERROR: Server failed to start. Check logs/server.log"
    fi
fi
echo

# --- 3. Verify server reachable ---
echo "[3/5] Verifying server reachable..."
if command -v curl >/dev/null 2>&1; then
    if curl -fsS --max-time 3 "${URL}/api/stats" >/dev/null 2>&1; then
        echo "  Server reachable. Open ${URL} in your browser."
    else
        echo "  WARNING: Server not reachable. Skipping browser launch."
    fi
elif command -v wget >/dev/null 2>&1; then
    if wget -q -T 3 -O /dev/null "${URL}/api/stats"; then
        echo "  Server reachable. Open ${URL} in your browser."
    else
        echo "  WARNING: Server not reachable. Skipping browser launch."
    fi
else
    echo "  (Neither curl nor wget available - skipping reachability check.)"
fi
echo

# --- 4. Run pipeline ---
echo "[4/5] Running news pipeline..."
echo "  Started at $(date '+%Y-%m-%d %H:%M:%S')"
if "$PYTHON" news_tool.py > logs/pipeline_stdout.log 2>&1; then
    PIPELINE_RC=0
else
    PIPELINE_RC=$?
fi
echo "  Pipeline finished at $(date '+%Y-%m-%d %H:%M:%S')"
echo "  Exit code: ${PIPELINE_RC}"
echo

if [ "${PIPELINE_RC}" -ne 0 ]; then
    echo "  ERROR: Pipeline failed. Skipping dashboard regeneration."
    echo "  See logs/pipeline.log and logs/pipeline_stdout.log"
    exit 1
fi

# --- 5. Regenerate dashboard data ---
echo "[5/5] Regenerating dashboard data..."
"$PYTHON" dashboard/generate_data.py
RC=$?
if [ $RC -ne 0 ]; then
    echo "  ERROR: Dashboard data regeneration failed."
    exit $RC
fi

echo
echo "=========================================="
echo "  All done! Dashboard: ${URL}"
echo "=========================================="
exit 0
