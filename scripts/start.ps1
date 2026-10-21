# ==============================================================================
# PROJECT OUROBOROS: START SERVICES SCRIPT
# ==============================================================================
$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$projectRoot = Split-Path -Parent $scriptDir

$venvPython = Join-Path $projectRoot ".venv\Scripts\python.exe"
$frontendDir = Join-Path $projectRoot "frontend"
$pidFile = Join-Path $projectRoot ".ouroboros_pids.json"

Write-Host "==========================================================" -ForegroundColor Cyan
Write-Host "   STARTING PROJECT OUROBOROS (Backend + Frontend)" -ForegroundColor Cyan
Write-Host "==========================================================" -ForegroundColor Cyan

# 1. Start Arize Phoenix in Background
Write-Host "Starting Arize Phoenix on http://127.0.0.1:6006..." -ForegroundColor Yellow
$phoenixScript = Join-Path $projectRoot "scripts\run_phoenix.py"
$phoenixProcess = Start-Process -FilePath $venvPython -ArgumentList $phoenixScript -WorkingDirectory $projectRoot -PassThru
Start-Sleep -Seconds 2

# 2. Start Backend in Background
Write-Host "Starting FastAPI Backend on http://127.0.0.1:8000..." -ForegroundColor Yellow
$backendProcess = Start-Process -FilePath $venvPython -ArgumentList "-m", "uvicorn", "app.main:app", "--app-dir", "backend", "--host", "127.0.0.1", "--port", "8000", "--reload" -WorkingDirectory $projectRoot -PassThru

# 3. Start Frontend in Background
Write-Host "Starting React + Vite Frontend on http://localhost:5173..." -ForegroundColor Yellow
$frontendProcess = Start-Process -FilePath "npm.cmd" -ArgumentList "run", "dev" -WorkingDirectory $frontendDir -PassThru

# Save PIDs for stop script
$pids = @{
    phoenix_pid = $phoenixProcess.Id
    backend_pid = $backendProcess.Id
    frontend_pid = $frontendProcess.Id
}
$pids | ConvertTo-Json | Out-File -FilePath $pidFile -Encoding utf8

Write-Host "`n[OK] Services launched successfully!" -ForegroundColor Green
Write-Host "  - React Dashboard:      http://localhost:5173" -ForegroundColor Cyan
Write-Host "  - Backend REST API:     http://127.0.0.1:8000/docs" -ForegroundColor Cyan
Write-Host "  - Arize Phoenix UI:     http://127.0.0.1:6006" -ForegroundColor Cyan
Write-Host "  - SSE Event Stream:     http://127.0.0.1:8000/api/runs/{id}/events" -ForegroundColor Cyan
Write-Host "`nTo stop all services safely, run:" -ForegroundColor Gray
Write-Host "  powershell -ExecutionPolicy Bypass scripts/stop.ps1`n" -ForegroundColor Gray
