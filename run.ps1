# ==============================================================================
# Discovery Engine - PowerShell Launcher
# Launches FastAPI Backend (port 8000) and Next.js Frontend (port 3000)
# in two separate terminal windows.
# ==============================================================================

[CmdletBinding()]
param(
    [switch]$Prod,
    [switch]$Stop,
    [switch]$Help
)

if ($Help) {
    Write-Host "Usage: .\run.ps1 [-Prod] [-Stop] [-Help]"
    Write-Host "  -Prod   Run frontend in production mode ('npm run start')"
    Write-Host "  -Stop   Stop any running servers on ports 8000 and 3000"
    exit 0
}

$RootDir = Split-Path -Parent $MyInvocation.MyCommand.Path

# Helper to stop servers on ports 8000 and 3000
function Stop-DiscoveryServers {
    Write-Host "Clearing servers on ports 8000 and 3000..." -ForegroundColor Cyan
    Get-NetTCPConnection -State Listen -ErrorAction SilentlyContinue |
        Where-Object { $_.LocalPort -eq 8000 -or $_.LocalPort -eq 3000 } |
        ForEach-Object {
            Write-Host "Stopping PID $($_.OwningProcess) on port $($_.LocalPort)..." -ForegroundColor Yellow
            Stop-Process -Id $_.OwningProcess -Force -ErrorAction SilentlyContinue
        }
    Write-Host "Ports 8000 and 3000 cleared." -ForegroundColor Green
}

if ($Stop) {
    Stop-DiscoveryServers
    exit 0
}

Stop-DiscoveryServers

# Locate Python
$PythonExe = "$RootDir\.venv\Scripts\python.exe"
if (-not (Test-Path $PythonExe)) {
    $PythonExe = "$RootDir\backend\.venv\Scripts\python.exe"
}
if (-not (Test-Path $PythonExe)) {
    $PythonExe = "python.exe"
}

# Ensure frontend dependencies
if (-not (Test-Path "$RootDir\frontend\node_modules")) {
    Write-Host "Installing frontend dependencies..." -ForegroundColor Cyan
    npm --prefix "$RootDir\frontend" install
}

$FrontendScript = if ($Prod) { "npm run start" } else { "npm run dev" }

Write-Host "========================================================================" -ForegroundColor Green
Write-Host " Starting Discovery Engine in Separate Windows" -ForegroundColor Green
Write-Host "========================================================================" -ForegroundColor Green

# Launch Backend in new window
$BackendCmd = "cd /d `"$RootDir`" && title Discovery Engine - Backend (FastAPI) && set PYTHONPATH=backend && `"$PythonExe`" -m uvicorn api.main:app --host 127.0.0.1 --port 8000 --reload"
Start-Process cmd.exe -ArgumentList "/k `"$BackendCmd`""

# Launch Frontend in new window
$FrontendCmd = "cd /d `"$RootDir\frontend`" && title Discovery Engine - Frontend (Next.js) && $FrontendScript"
Start-Process cmd.exe -ArgumentList "/k `"$FrontendCmd`""

Write-Host ""
Write-Host "========================================================================" -ForegroundColor Cyan
Write-Host " Discovery Engine launched!" -ForegroundColor Cyan
Write-Host "------------------------------------------------------------------------"
Write-Host "  Backend API:      http://127.0.0.1:8000"
Write-Host "  API Health:       http://127.0.0.1:8000/v1/health"
Write-Host "  Swagger Docs:     http://127.0.0.1:8000/docs"
Write-Host "  Frontend UI:      http://localhost:3000"
Write-Host "------------------------------------------------------------------------"
Write-Host " To stop servers at any time, run: .\run.ps1 -Stop"
Write-Host "========================================================================" -ForegroundColor Cyan
