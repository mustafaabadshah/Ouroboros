# ==============================================================================
# PROJECT OUROBOROS: AUTOMATED WINDOWS SETUP SCRIPT
# ==============================================================================
$ErrorActionPreference = "Stop"

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$projectRoot = Split-Path -Parent $scriptDir

Write-Host "==========================================================" -ForegroundColor Cyan
Write-Host "   PROJECT OUROBOROS: LOCAL ENVIRONMENT SETUP" -ForegroundColor Cyan
Write-Host "==========================================================" -ForegroundColor Cyan
Write-Host "Project Root: $projectRoot" -ForegroundColor Gray

# 1. Check Python and Node
Write-Host "`n[1/5] Checking System Prerequisites..." -ForegroundColor Yellow
& "$scriptDir\check-environment.ps1"

# 2. Setup Configuration
Write-Host "`n[2/5] Setting Up Configuration..." -ForegroundColor Yellow
$envPath = Join-Path $projectRoot ".env"
$envExamplePath = Join-Path $projectRoot ".env.example"

if (-not (Test-Path $envPath)) {
    Write-Host "Creating .env from .env.example..." -ForegroundColor Gray
    Copy-Item $envExamplePath $envPath
    Write-Host "[OK] .env initialized." -ForegroundColor Green
} else {
    Write-Host "[OK] .env already exists. Preserving existing credentials." -ForegroundColor Green
}

# 3. Create & Populate Python Virtual Environment
Write-Host "`n[3/5] Setting Up Python Virtual Environment..." -ForegroundColor Yellow
$venvDir = Join-Path $projectRoot ".venv"
$venvPython = Join-Path $venvDir "Scripts\python.exe"

if (-not (Test-Path $venvPython)) {
    Write-Host "Creating Python virtual environment in .venv..." -ForegroundColor Gray
    python -m venv $venvDir
}

Write-Host "Installing/Upgrading Python dependencies via pip..." -ForegroundColor Gray
$uvExe = Get-Command uv -ErrorAction SilentlyContinue
if ($uvExe) {
    Write-Host "Using uv for fast dependency synchronization..." -ForegroundColor Gray
    & uv pip install --python $venvPython -r (Join-Path $projectRoot "pyproject.toml")
} else {
    & $venvPython -m pip install --upgrade pip
    & $venvPython -m pip install -e $projectRoot
}
Write-Host "[OK] Python dependencies installed." -ForegroundColor Green

# 4. Install Frontend Dependencies
Write-Host "`n[4/5] Setting Up Frontend Dependencies..." -ForegroundColor Yellow
$frontendDir = Join-Path $projectRoot "frontend"
Push-Location $frontendDir
try {
    npm install
    Write-Host "[OK] Frontend packages installed." -ForegroundColor Green
} finally {
    Pop-Location
}

# 5. Initialize SQLite Database Schema
Write-Host "`n[5/5] Initializing Database Schema..." -ForegroundColor Yellow
Push-Location $projectRoot
try {
    & $venvPython -c "import sys; sys.path.insert(0, 'backend'); from app.database.session import init_db; init_db()"
    Write-Host "[OK] SQLite database schema initialized." -ForegroundColor Green
} finally {
    Pop-Location
}

Write-Host "`n==========================================================" -ForegroundColor Green
Write-Host "   SETUP COMPLETE! To start Ouroboros, run:" -ForegroundColor Green
Write-Host "   powershell -ExecutionPolicy Bypass scripts/start.ps1" -ForegroundColor Cyan
Write-Host "==========================================================" -ForegroundColor Green
