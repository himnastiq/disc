@echo off
setlocal enabledelayedexpansion

title Discovery Engine Launcher
echo ========================================================================
echo  Discovery Engine - Windows Launcher
echo ========================================================================

set SCRIPT_DIR=%~dp0
cd /d "%SCRIPT_DIR%"

if "%1"=="--stop" goto do_stop
if "%1"=="-k" goto do_stop
if "%1"=="--kill" goto do_stop
if "%1"=="--help" goto do_help
if "%1"=="-h" goto do_help

:: Find Python
set PYTHON_EXE=
if exist "%SCRIPT_DIR%\.venv\Scripts\python.exe" (
    set "PYTHON_EXE=%SCRIPT_DIR%\.venv\Scripts\python.exe"
) else if exist "%SCRIPT_DIR%\backend\.venv\Scripts\python.exe" (
    set "PYTHON_EXE=%SCRIPT_DIR%\backend\.venv\Scripts\python.exe"
) else (
    set "PYTHON_EXE=python.exe"
)

:: Clear old processes on 8000 and 3000
echo Clearing previous servers on ports 8000 and 3000...
for /f "tokens=5" %%a in ('netstat -aon 2^>nul ^| findstr ":8000.*LISTENING"') do (
    echo Stopping PID %%a on port 8000...
    taskkill /f /pid %%a >nul 2>&1
)
for /f "tokens=5" %%a in ('netstat -aon 2^>nul ^| findstr ":3000.*LISTENING"') do (
    echo Stopping PID %%a on port 3000...
    taskkill /f /pid %%a >nul 2>&1
)

:: Check frontend node_modules
if not exist "%SCRIPT_DIR%\frontend\node_modules\" (
    echo Installing frontend dependencies...
    cd /d "%SCRIPT_DIR%\frontend" && npm install && cd /d "%SCRIPT_DIR%"
)

set FRONTEND_MODE=npm run dev
if "%1"=="--prod" (
    set FRONTEND_MODE=npm run start
)

echo Starting Backend in separate terminal...
start "Discovery Engine - Backend" cmd /k "cd /d "%SCRIPT_DIR%" && title Discovery Engine - Backend (FastAPI) && set PYTHONPATH=backend && "%PYTHON_EXE%" -m uvicorn api.main:app --host 127.0.0.1 --port 8000 --reload"

echo Starting Frontend in separate terminal...
start "Discovery Engine - Frontend" cmd /k "cd /d "%SCRIPT_DIR%\frontend" && title Discovery Engine - Frontend (Next.js) && %FRONTEND_MODE%"

echo.
echo ========================================================================
echo  Discovery Engine is launching in two separate terminals!
echo ------------------------------------------------------------------------
echo   Backend API:      http://127.0.0.1:8000
echo   API Health:       http://127.0.0.1:8000/v1/health
echo   Swagger Docs:     http://127.0.0.1:8000/docs
echo   Frontend UI:      http://localhost:3000
echo ------------------------------------------------------------------------
echo  To stop servers at any time, run: run.bat --stop
echo ========================================================================
exit /b 0

:do_stop
echo Terminating running servers on ports 8000 and 3000...
for /f "tokens=5" %%a in ('netstat -aon 2^>nul ^| findstr ":8000.*LISTENING"') do (
    taskkill /f /pid %%a >nul 2>&1
)
for /f "tokens=5" %%a in ('netstat -aon 2^>nul ^| findstr ":3000.*LISTENING"') do (
    taskkill /f /pid %%a >nul 2>&1
)
echo Ports cleared.
exit /b 0

:do_help
echo Usage: run.bat [--prod ^| --stop ^| --help]
echo   (no args)    Start Backend and Frontend in separate terminals
echo   --prod       Run frontend in production mode
echo   --stop, -k   Stop servers running on ports 8000 and 3000
exit /b 0
