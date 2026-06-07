@echo off
setlocal

REM Bloomy News - On-demand dashboard launcher
REM Starts the dashboard server in the background and opens the browser.
REM Use this when you want to view the dashboard right now (without
REM restarting Windows to trigger the autostart). Server keeps running
REM until Windows shutdown or you kill the pythonw.exe process.
REM
REM For always-on: run scripts\install_dashboard.py --install

title Bloomy News - Dashboard Launcher

cd /d "%~dp0"

echo ==========================================
echo   Bloomy News - Starting Dashboard
echo ==========================================
echo.

REM Check if server is already running on port 8080
netstat -an | findstr ":8080" | findstr /R ".*LISTENING" >nul 2>&1
if %ERRORLEVEL% EQU 0 (
    echo   Dashboard already running on port 8080 - skipping start.
    echo.
    goto :open_browser
)

echo   Starting dashboard server...
REM pythonw.exe (not python.exe) so no console window appears.
REM start "" /B detaches the process from this batch so it survives
REM after the batch window closes.
start "" /B pythonw "%~dp0dashboard\serve.py"

REM Poll for up to 10s for the server to bind port 8080
set /a ATTEMPT=0
:wait_for_server
set /a ATTEMPT+=1
if !ATTEMPT! GTR 10 (
    echo   ERROR: Server failed to start within 10s. Check logs\server.log
    goto :end
)
timeout /t 1 /nobreak >nul
netstat -an | findstr ":8080" | findstr /R ".*LISTENING" >nul 2>&1
if %ERRORLEVEL% NEQ 0 goto :wait_for_server
echo   Server started at http://localhost:8080

:open_browser
echo.
echo   Opening browser...
start "" http://localhost:8080
echo.
echo ==========================================
echo   Dashboard: http://localhost:8080
echo   Server keeps running until Windows shutdown.
echo   To stop: kill pythonw.exe in Task Manager.
echo ==========================================
echo.

:end
endlocal
exit /b 0
