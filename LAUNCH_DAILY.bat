@echo off
title Bloomy News - Daily Launcher
setlocal EnableDelayedExpansion

:: Rotate log files larger than 1 MB (keep 1 generation: .1)
:: serve.py handles its own log rotation via RotatingFileHandler so
:: logs\server.log doesn't need to be rotated here. The batch file
:: only needs to rotate the pipeline stdout/stderr capture.
if exist "%~dp0logs\pipeline_stdout.log" (
    for %%A in ("%~dp0logs\pipeline_stdout.log") do (
        if %%~zA gtr 1048576 (
            if exist "%~dp0logs\pipeline_stdout.log.1" del "%~dp0logs\pipeline_stdout.log.1" >nul 2>&1
            move /y "%~dp0logs\pipeline_stdout.log" "%~dp0logs\pipeline_stdout.log.1" >nul 2>&1
        )
    )
)

echo ==========================================
echo   Bloomy News - Starting Up
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
    :: No `> log 2>&1` here — serve.py writes its own log to logs\server.log
    :: via Python's logging + RotatingFileHandler. The previous `start /B
    :: python ... > log` was broken: cmd.exe's redirect went to `start`,
    :: not to the spawned python, so the log was always 0 bytes.
    start "" /B python -u "%~dp0dashboard\serve.py"

    :: Poll for up to 10s for the server to bind port 8080.
    :: The original 2s wait was too eager on slow first runs and
    :: produced a misleading "Server failed to start" message
    :: even when the server was binding successfully.
    set /a ATTEMPT=0
    :wait_for_server
    set /a ATTEMPT+=1
    if !ATTEMPT! GTR 10 (
        echo   ERROR: Server failed to start within 10s. Check logs\server.log
    ) else (
        timeout /t 1 /nobreak >nul
        netstat -an | findstr ":8080" | findstr /R ".*LISTENING" >nul 2>&1
        if %ERRORLEVEL% NEQ 0 goto :wait_for_server
        echo   Server started at http://localhost:8080
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
python -u "%~dp0news_tool.py" > "%~dp0logs\pipeline_stdout.log" 2>&1
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
echo.
echo Press any key to close this window...
pause >nul
goto :eof

:end
echo.
echo ==========================================
echo   Launch completed with errors. See logs above.
echo ==========================================
echo.
echo Press any key to close this window...
pause >nul
exit /b 1
