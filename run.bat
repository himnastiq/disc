@echo off
setlocal enabledelayedexpansion

:: Resolve directory without trailing backslash
set "SCRIPT_DIR=%~dp0"
if "%SCRIPT_DIR:~-1%"=="\" set "SCRIPT_DIR=%SCRIPT_DIR:~0,-1%"
cd /d "%SCRIPT_DIR%"

set "PYTHON_EXE="
if exist "%SCRIPT_DIR%\.venv\Scripts\python.exe" (
    set "PYTHON_EXE=%SCRIPT_DIR%\.venv\Scripts\python.exe"
) else if exist "%SCRIPT_DIR%\backend\.venv\Scripts\python.exe" (
    set "PYTHON_EXE=%SCRIPT_DIR%\backend\.venv\Scripts\python.exe"
) else (
    set "PYTHON_EXE=python.exe"
)

"%PYTHON_EXE%" "%SCRIPT_DIR%\tools\demo.py" %*
set "EXIT_CODE=%ERRORLEVEL%"

if %EXIT_CODE% neq 0 (
    echo.
    echo [ERROR] Demo process exited with code %EXIT_CODE%.
    echo Press any key to exit...
    pause >nul
)

exit /b %EXIT_CODE%
