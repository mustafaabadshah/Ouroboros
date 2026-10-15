# Project Ouroboros — Release Runbook
**Version:** `v0.9.0-rc1`  
**Target Environment:** Local Workstation / Single-tenant Developer Host (Windows / Linux / macOS)  
**Hardware Profile:** 8 GB RAM, Python 3.12+, Node.js 20+

---

## 1. System Overview & Architecture

Project Ouroboros is an autonomous, multi-agent AI software-repair and codebase-refactoring platform. It integrates:
- **FastAPI Backend (`http://127.0.0.1:8000`)**: Handles repository analysis, ticket lifecycles, worktree creation, diff parsing, judge evaluation, failure memory, and benchmark execution.
- **Vite/React 19 Frontend (`http://localhost:5173`)**: Developer dashboard for repository inspection, ticket review, candidate patch diffs, live agent logs, and the Evaluation Lab.
- **SQLite Persistence (`ouroboros.db`)**: Local ACID-compliant database tracking tickets, runs, candidate revisions, evaluation results, and failure trajectories.
- **Arize Phoenix Observability (`http://127.0.0.1:6006`)**: OpenInference tracing capturing spans for planner, coder, critic, and judge operations.
- **Git Worktree Manager**: Isolated branches and directories preventing candidate patches from touching the main working tree.
- **Sandbox Boundary**: Strict fail-closed execution boundary requiring container isolation for untrusted candidate code execution.

---

## 2. Prerequisites & Environment Setup

### 2.1 Host Requirements
| Component | Minimum Version | Verified Version | Notes |
|---|---|---|---|
| OS | Windows 10/11 64-bit / Linux / macOS | Windows 10 x64 | Windows PowerShell or bash supported |
| Python | 3.10+ | 3.12.3 | Installed with venv support |
| Node.js | 20.0+ | 24.14.1 | Installed with npm 11+ |
| Git | 2.40+ | 2.45+ | Required for worktree isolation |
| Container Runtime | Docker 20.10+ / Podman 4.0+ | Docker CLI 25.0.3 | Daemon optional for planning; mandatory for untrusted execution |
| Memory | 8 GB | 8 GB | Enable `LOW_RESOURCE_MODE=true` on <=8GB machines |

### 2.2 Clean Installation Procedure

1. **Clone and Navigate to Workspace**:
   ```powershell
   cd "E:\MM Office\Ouroboros"
   ```

2. **Initialize Python Virtual Environment**:
   ```powershell
   python -m venv .venv
   .\.venv\Scripts\Activate.ps1
   python -m pip install --upgrade pip
   pip install -r backend/requirements.txt
   ```

3. **Install Frontend Dependencies**:
   ```powershell
   cd frontend
   npm install
   cd ..
   ```

4. **Configure Environment**:
   Copy `.env.example` to `.env`:
   ```powershell
   Copy-Item .env.example .env
   ```

   Key configuration variables in `.env`:
   ```ini
   # Server Configuration
   HOST=127.0.0.1
   PORT=8000
   DEBUG=false

   # Hardware & Concurrency
   LOW_RESOURCE_MODE=true
   MAX_INFERENCE_CONCURRENCY=1
   CONTEXT_WINDOW_LIMIT=8192

   # Model Providers
   PRIMARY_PROVIDER=ollama
   OLLAMA_BASE_URL=http://127.0.0.1:11434
   ALLOW_HOSTED_FALLBACK=false
   GROQ_API_KEY=

   # Container Sandbox
   CONTAINER_ISOLATION_REQUIRED=true
   EXECUTION_POLICY=fail_closed
   CONTAINER_MEMORY_LIMIT=1g
   CONTAINER_CPU_LIMIT=1.0
   CONTAINER_TIMEOUT_SECONDS=60

   # Observability
   ENABLE_PHOENIX=true
   PHOENIX_PORT=6006
   REDACT_SECRETS=true
   ```

---

## 3. Operations & Service Lifecycle

### 3.1 Starting Services

#### Automated Startup (Recommended)
Run the PowerShell startup script:
```powershell
.\scripts\start.ps1
```
This script:
1. Validates Python and Node.js environments.
2. Launches Arize Phoenix on port 6006.
3. Launches FastAPI backend with Uvicorn on port 8000.
4. Launches Vite frontend dev server on port 5173.
5. Saves process IDs in `.ouroboros_pids.json` for reliable shutdown.

#### Manual Startup
In separate terminal windows:
```powershell
# Terminal 1: Backend
.\.venv\Scripts\Activate.ps1
python -m uvicorn app.main:app --app-dir backend --host 127.0.0.1 --port 8000

# Terminal 2: Frontend
cd frontend
npm run dev -- --host 127.0.0.1 --port 5173

# Terminal 3: Phoenix Observability (optional)
.\.venv\Scripts\Activate.ps1
python -c "import phoenix as px; px.launch_app(port=6006)"
```

### 3.2 Health Check & Service Verification

Verify that all endpoints respond:
```powershell
# 1. Backend Health
Invoke-RestMethod -Uri "http://127.0.0.1:8000/api/health"

# 2. Evaluation Health & Metrics
Invoke-RestMethod -Uri "http://127.0.0.1:8000/api/evaluation/metrics"

# 3. Sandbox Capability Diagnostic
Invoke-RestMethod -Uri "http://127.0.0.1:8000/api/system/sandbox-status"
```

Expected response from `/api/health`:
```json
{
  "status": "healthy",
  "version": "0.9.0-rc1",
  "components": {
    "database": "connected",
    "git": "available",
    "sandbox": "offline_fail_closed"
  }
}
```

### 3.3 Stopping Services

#### Automated Shutdown
```powershell
.\scripts\stop.ps1
```
This script reads `.ouroboros_pids.json` and terminates the entire process tree for Uvicorn, Vite, and Phoenix on Windows using `taskkill /F /T /PID`.

#### Manual Shutdown
Kill tasks listening on ports 8000, 5173, and 6006:
```powershell
Get-NetTCPConnection -LocalPort 8000, 5173, 6006 -ErrorAction SilentlyContinue | 
  Select-Object -ExpandProperty OwningProcess -Unique | 
  ForEach-Object { Stop-Process -Id $_ -Force }
```

---

## 4. Verification Suites & Testing

Run verification commands to confirm system integrity before conducting operations:

### 4.1 Pytest Core Suite (31 Tests)
```powershell
.\.venv\Scripts\python.exe -m pytest backend/tests -v
```
*Expected: 31 passed in ~60 seconds.*

### 4.2 Acceptance Test Suite (20 Checks)
```powershell
.\.venv\Scripts\python.exe backend/tests/verify_acceptance.py
```
*Expected: 20/20 checks passed.*

### 4.3 End-to-End Workflow Demonstration (13 Steps)
```powershell
.\.venv\Scripts\python.exe scripts/demonstrate_complete_workflow.py
```
*Expected: 12 logic steps pass, Step 8 isolated container execution returns `BLOCKED` (fail-closed).*

### 4.4 Evaluation Benchmark Suite & Memory Ablation
```powershell
.\.venv\Scripts\python.exe scripts/run_benchmarks.py
```
*Expected: BENCH-01 and BENCH-02 pass; BENCH-03 fails closed with security block; results saved to `artifacts/benchmark_results.json`.*

### 4.5 Frontend Production Build
```powershell
cd frontend
npm run build
cd ..
```
*Expected: Vite builds successfully with 0 TypeScript/compilation errors.*

---

## 5. Troubleshooting & Edge Cases

### 5.1 Docker Daemon Offline
- **Symptom**: Step 8 in workflow returns `BLOCKED`, or run status indicates `RUNTIME_UNAVAILABLE`.
- **Cause**: Docker Desktop is not running or socket is not accessible.
- **Handling**: This is intentional. Project Ouroboros operates under a strict **fail-closed** policy. Untrusted code is never run on the host. Planning, AST analysis, ticket review, and patch generation remain 100% functional.
- **Resolution**: To enable candidate testing, start Docker Desktop and ensure Linux container mode is selected.

### 5.2 SQLite Database Locks
- **Symptom**: `sqlite3.OperationalError: database is locked`.
- **Mitigation**: The backend utilizes `StaticPool` for integration test clients and explicit transaction commits with WAL (Write-Ahead Logging) enabled. Ensure no external SQLite viewers lock `ouroboros.db`.

### 5.3 Low Memory (<8 GB RAM)
- **Symptom**: Memory pressure or system thrashing.
- **Resolution**:
  - Keep `LOW_RESOURCE_MODE=true` in `.env`.
  - Set `MAX_INFERENCE_CONCURRENCY=1`.
  - Use smaller quantized models (e.g., `qwen2.5-coder:1.5b` or `qwen2.5-coder:7b-q4_K_M`).
  - Disable Phoenix tracing if not needed (`ENABLE_PHOENIX=false`).

### 5.4 Orphaned Worktrees
- **Symptom**: Git errors stating branch or worktree directory already exists in `.ouroboros/worktrees/`.
- **Resolution**: Run worktree prune:
  ```powershell
  git worktree prune
  Remove-Item -Recurse -Force .ouroboros/worktrees/*
  ```

### 5.5 Interrupted Runs
- **Behavior**: Upon backend restart, the `lifespan` handler automatically scans for runs in `RUNNING` or `EVALUATING` states and transitions them to `FAILED` with failure category `ORPHANED_RUN_INTERRUPTED`.

---

## 6. Release Verification Checklist

- [x] G1: Repository integrity preserved; external reference repositories untouched.
- [x] G2: Backend suite passing (31/31 unit, integration, adversarial tests).
- [x] G3: Frontend build clean (0 errors, 1,935 modules compiled).
- [x] G4: Authorization and state machines verified (replayed/stale merges rejected).
- [x] G5: Unified diff boundary enforcement verified (path traversal, protected paths blocked).
- [x] G6: Execution isolation verified as fail-closed (`BLOCKED` when daemon offline).
- [x] G7: Closed-loop multi-agent repair verified across 13 workflow steps.
- [x] G8: Concurrency serialization (`_merge_lock`), orphan cleanup, and recovery tested.
- [x] G9: Metric formulas, benchmarks, and memory ablation tested and documented.
- [x] G10: Provider timeouts, errors, and fallbacks configured without silent data exfiltration.
- [x] G11: Secret redaction in logs and Phoenix traces validated.
- [x] G12: Clean installation procedures validated.
- [x] G13: Release documentation and runbooks updated.
- [x] G14: Reproducible scripts present in `scripts/`.
