@echo off
title Bloomsberg News - Daily Launcher
setlocal

echo ==========================================
echo   Bloomsberg News - Starting Up
echo ==========================================
echo.

:: Ensure logs directory exists
if not exist "%~dp0logs" mkdir "%~dp0logs"

:: Step 1: Run health check
echo [1/5] Running system health check...
python "%~dp0scripts\check_system.py"
if %ERRORLEVEL% NEQ 0 (
    echo.
    echo WARNING: Some checks failed. Continuing anyway...
)
echo.

:: Step 2: Start dashboard server (background) if not already running
echo [2/5] Checking dashboard server...
netstat -an | findstr ":8080" | findstr /R ".*LISTENING" >nul 2>&1
if %ERRORLEVEL% EQU 0 (
    echo   Server already running on port 8080 - skipping start.
) else (
    echo   Starting dashboard server...
    start "" /B python "%~dp0dashboard\serve.py" > "%~dp0logs\server.log" 2>&1
    timeout /t 2 /nobreak >nul

    :: Verify server actually started
    netstat -an | findstr ":8080" | findstr /R ".*LISTENING" >nul 2>&1
    if %ERRORLEVEL% EQU 0 (
        echo   Server started at http://localhost:8080
    ) else (
        echo   ERROR: Server failed to start. Check logs\server.log
    )
)
echo.

:: Step 3: Verify server is reachable before opening browser
echo [3/5] Verifying server reachable...
powershell -NoProfile -Command "try { (Invoke-WebRequest -Uri http://localhost:8080/api/stats -UseBasicParsing -TimeoutSec 3).StatusCode } catch { exit 1 }" >nul 2>&1
if %ERRORLEVEL% EQU 0 (
    echo   Opening browser...
    start http://localhost:8080
) else (
    echo   WARNING: Server not reachable. Skipping browser launch.
)
echo.

:: Step 4: Run pipeline
echo [4/5] Running news pipeline...
echo   Started at %DATE% %TIME%
python "%~dp0news_tool.py" > "%~dp0logs\pipeline_stdout.log" 2>&1
set PIPELINE_RC=%ERRORLEVEL%
echo.
echo   Pipeline finished at %DATE% %TIME%
echo   Exit code: %PIPELINE_RC%

if %PIPELINE_RC% NEQ 0 (
    echo.
    echo   ERROR: Pipeline failed. Skipping dashboard regeneration.
    echo   See logs\pipeline.log and logs\pipeline_stdout.log
    goto :end
)

:: Step 5: Regenerate dashboard data
echo.
echo [5/5] Regenerating dashboard data...
python "%~dp0dashboard\generate_data.py"
if %ERRORLEVEL% NEQ 0 (
    echo   ERROR: Dashboard data regeneration failed.
    goto :end
)

echo.
echo ==========================================
echo   All done! Dashboard: http://localhost:8080
echo ==========================================
goto :eof

:end
echo.
echo ==========================================
echo   Launch completed with errors. See logs above.
echo ==========================================
exit /b 1
