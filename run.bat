@echo off
setlocal
set SCRIPT_DIR=%~dp0
cd /d "%SCRIPT_DIR%"

set PYTHON_EXE=
if exist "%SCRIPT_DIR%\.venv\Scripts\python.exe" (
    set "PYTHON_EXE=%SCRIPT_DIR%\.venv\Scripts\python.exe"
) else if exist "%SCRIPT_DIR%\backend\.venv\Scripts\python.exe" (
    set "PYTHON_EXE=%SCRIPT_DIR%\backend\.venv\Scripts\python.exe"
) else (
    set "PYTHON_EXE=python.exe"
)

"%PYTHON_EXE%" "%SCRIPT_DIR%\tools\demo.py" %*
exit /b %ERRORLEVEL%
