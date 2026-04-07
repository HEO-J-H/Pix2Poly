# Pix2Poly local dev server (FastAPI + static UI)
# Usage: .\scripts\start-local.ps1
# Optional: $env:PORT = "8080"

$ErrorActionPreference = "Stop"

$ScriptDir = $PSScriptRoot
if (-not $ScriptDir) {
    $ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
}
$ProjectRoot = Split-Path -Parent $ScriptDir
$Backend = Join-Path $ProjectRoot "backend"

if (-not (Test-Path (Join-Path $Backend "app\main.py"))) {
    Write-Error "backend\app\main.py not found. Run from Pix2Poly repo root."
}

Set-Location $Backend

$Port = if ($env:PORT) { $env:PORT } else { "8000" }
$VenvPy = Join-Path $Backend ".venv\Scripts\python.exe"

if (-not (Test-Path $VenvPy)) {
    Write-Host "Creating .venv..."
    python -m venv .venv
}

$Activate = Join-Path $Backend ".venv\Scripts\Activate.ps1"
. $Activate

pip install -r requirements.txt -q

Write-Host ""
Write-Host "Pix2Poly (local)" -ForegroundColor Cyan
Write-Host "  UI:    http://127.0.0.1:${Port}/ui/"
Write-Host "  API:   http://127.0.0.1:${Port}/docs"
Write-Host "  Hot reload: app/*.py, static/* (see backend/run_dev.py)"
Write-Host "  Press Ctrl+C to stop."
Write-Host ""

$env:PORT = $Port
python run_dev.py
