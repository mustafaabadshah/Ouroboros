# ==============================================================================
# PROJECT OUROBOROS: STOP SERVICES SCRIPT
# ==============================================================================
$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$projectRoot = Split-Path -Parent $scriptDir
$pidFile = Join-Path $projectRoot ".ouroboros_pids.json"

Write-Host "Stopping Project Ouroboros services..." -ForegroundColor Yellow

if (Test-Path $pidFile) {
    try {
        $pids = Get-Content $pidFile | ConvertFrom-Json
        if ($pids.backend_pid) {
            Write-Host "Stopping Backend (PID: $($pids.backend_pid))..." -ForegroundColor Gray
            Stop-Process -Id $pids.backend_pid -Force -ErrorAction SilentlyContinue
        }
        if ($pids.frontend_pid) {
            Write-Host "Stopping Frontend (PID: $($pids.frontend_pid))..." -ForegroundColor Gray
            Stop-Process -Id $pids.frontend_pid -Force -ErrorAction SilentlyContinue
        }
        if ($pids.phoenix_pid) {
            Write-Host "Stopping Arize Phoenix (PID: $($pids.phoenix_pid))..." -ForegroundColor Gray
            Stop-Process -Id $pids.phoenix_pid -Force -ErrorAction SilentlyContinue
        }
        Remove-Item $pidFile -Force -ErrorAction SilentlyContinue
        Write-Host "[OK] All services stopped." -ForegroundColor Green
    } catch {
        Write-Host "Error reading PID file: $_" -ForegroundColor Red
    }
} else {
    Write-Host "No active PID file found. Terminating any lingering processes on ports 8000 and 5173..." -ForegroundColor Gray
    Get-Process -Name "python", "node" -ErrorAction SilentlyContinue | Where-Object {
        $_.Path -like "*Ouroboros*"
    } | Stop-Process -Force -ErrorAction SilentlyContinue
    Write-Host "[OK] Cleanup completed." -ForegroundColor Green
}
