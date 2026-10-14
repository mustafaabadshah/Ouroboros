# ==============================================================================
# PROJECT OUROBOROS: AUTOMATED TEST SUITE RUNNER
# ==============================================================================
$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$projectRoot = Split-Path -Parent $scriptDir
$venvPython = Join-Path $projectRoot ".venv\Scripts\python.exe"

Write-Host "==========================================================" -ForegroundColor Cyan
Write-Host "   RUNNING PROJECT OUROBOROS TEST SUITE" -ForegroundColor Cyan
Write-Host "==========================================================" -ForegroundColor Cyan

Push-Location $projectRoot
try {
    $env:PYTHONPATH = "backend"
    & $venvPython -m pytest backend/tests -v --tb=short
} finally {
    Pop-Location
}
