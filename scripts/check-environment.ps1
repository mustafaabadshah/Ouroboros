# ==============================================================================
# PROJECT OUROBOROS: ENVIRONMENT & CAPABILITY DIAGNOSTIC SCRIPT
# ==============================================================================

Write-Host "==========================================================" -ForegroundColor Cyan
Write-Host "   PROJECT OUROBOROS: HOST ENVIRONMENT DIAGNOSTIC" -ForegroundColor Cyan
Write-Host "==========================================================" -ForegroundColor Cyan

# 1. Python Check
$pyExe = Get-Command python -ErrorAction SilentlyContinue
if ($pyExe) {
    $pyVer = python --version
    Write-Host "[OK] Python Detected: $pyVer" -ForegroundColor Green
} else {
    Write-Host "[FAIL] Python not found in system PATH." -ForegroundColor Red
}

# 2. Node.js & npm Check
$nodeExe = Get-Command node -ErrorAction SilentlyContinue
if ($nodeExe) {
    $nodeVer = node --version
    $npmVer = npm --version
    Write-Host "[OK] Node.js Detected: $nodeVer (npm: $npmVer)" -ForegroundColor Green
} else {
    Write-Host "[FAIL] Node.js not found in system PATH." -ForegroundColor Red
}

# 3. Git Check
$gitExe = Get-Command git -ErrorAction SilentlyContinue
if ($gitExe) {
    $gitVer = git --version
    Write-Host "[OK] Git Detected: $gitVer" -ForegroundColor Green
} else {
    Write-Host "[FAIL] Git not found in system PATH." -ForegroundColor Red
}

# 4. RAM Check (Strict 8 GB Guardrail)
$os = Get-CimInstance Win32_OperatingSystem
$totalMb = [math]::Round($os.TotalVisibleMemorySize / 1024, 0)
$freeMb = [math]::Round($os.FreePhysicalMemory / 1024, 0)
Write-Host "[INFO] Total System RAM: $totalMb MB" -ForegroundColor Gray
if ($freeMb -lt 1500) {
    Write-Host "[WARN] Available RAM: $freeMb MB (< 1500 MB threshold). Strict single-model policy enforced." -ForegroundColor Yellow
} else {
    Write-Host "[OK] Available RAM: $freeMb MB" -ForegroundColor Green
}

# 5. Optional Ollama Check
$ollamaExe = Get-Command ollama -ErrorAction SilentlyContinue
if ($ollamaExe) {
    Write-Host "[OK] Ollama CLI Detected." -ForegroundColor Green
} else {
    Write-Host "[OPTIONAL] Ollama not detected. (App will use Groq or Mock fallback)." -ForegroundColor Yellow
}

# 6. Optional Docker Check
$dockerExe = Get-Command docker -ErrorAction SilentlyContinue
if ($dockerExe) {
    Write-Host "[OK] Docker CLI Detected." -ForegroundColor Green
} else {
    Write-Host "[OPTIONAL] Docker not detected. (App will use restricted local worktree sandbox)." -ForegroundColor Yellow
}

Write-Host "==========================================================" -ForegroundColor Cyan
