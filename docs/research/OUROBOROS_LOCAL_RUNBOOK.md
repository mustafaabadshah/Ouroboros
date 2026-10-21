# Project Ouroboros — Local Operations Runbook

**Purpose:** Authoritative reference for starting, operating, testing, and shutting down Project Ouroboros on local workstations (Windows 10 x64 / 8 GB RAM).

---

## 1. Quick Start (Unified Scripting)

### 1.1 Launch All Services
To start Arize Phoenix, FastAPI Backend, and React Frontend together in background processes:
```powershell
powershell -ExecutionPolicy Bypass -File scripts/start.ps1
```

**Service Endpoints:**
- **React Web Dashboard:** `http://localhost:5173`
- **Backend REST API Docs:** `http://127.0.0.1:8000/docs`
- **Backend Health Check:** `http://127.0.0.1:8000/api/health`
- **Arize Phoenix Web UI:** `http://127.0.0.1:6006`
- **Arize Phoenix OTLP Ingestion:** `http://127.0.0.1:6006/v1/traces`

### 1.2 Stop All Services Safely
To terminate all background processes and remove `.ouroboros_pids.json`:
```powershell
powershell -ExecutionPolicy Bypass -File scripts/stop.ps1
```

---

## 2. Manual Service Orchestration (Individual Terminals)

If developing or debugging individual components:

### 2.1 Terminal 1: Arize Phoenix AI Observability
```powershell
# From project root in active virtualenv
python scripts/run_phoenix.py
```
*Note: Serves UI on port 6006 and receives OTLP traces at `http://127.0.0.1:6006/v1/traces`.*

### 2.2 Terminal 2: FastAPI Backend Engine
```powershell
python -m uvicorn app.main:app --app-dir backend --host 127.0.0.1 --port 8000 --reload
```

### 2.3 Terminal 3: Vite React Frontend
```powershell
cd frontend
npm run dev
```

---

## 3. Running Workflows & Evaluations

### 3.1 Controlled Live-Provider RC1 Workflow
Executes the full 7-stage pipeline (AST discovery, ticket generation, schema freezing, planning, worktree isolation, patch synthesis, deterministic judging, merge gating, Phoenix trace ingestion, and budget auditing) under live Groq inference:
```powershell
# Ensure GROQ_API_KEY is present in environment
$env:GROQ_API_KEY = "gsk_..."

# Execute bounded live run
python scripts/run_rc1_live_workflow.py
```
*Safety Controls Enforced:*
- Single task (`BENCH-01: Input Validation Boundary Guard`).
- Concurrency capped at 1.
- Max 8 remote provider requests.
- 12,000 token ceiling.
- $0.01 USD cost ceiling.
- Minimum 3.0s inter-request pacing.
- Fail-closed routing (zero fallback to mock).
- Auto-merge to `main` strictly blocked by policy.

### 3.2 Offline Mock Evaluation (Default Safe Mode)
Run a deterministic mock evaluation on a selected benchmark task without internet access or API keys:
```powershell
python scripts/run_agent_eval.py --mock-agents --task-id BENCH-01 --output artifacts/scratch/my_mock_run.json
```

### 3.3 Live Multi-Task Benchmark (Interactive Authorization)
To run with live Groq remote inference:
```powershell
python scripts/run_agent_eval.py --live --task-id BENCH-04 --output artifacts/scratch/live_eval_bench04.json
```
**Interactive Banner Prompt:**
1. Displays model, task count, token limit (60,000), cost limit ($0.10 USD), and pacing (3.0s).
2. Type `yes` when prompted to authorize execution.
3. Typing anything else terminates the run with code 2 before any remote call is dispatched.

---

## 4. Test Suite Execution Runbook

Run test suites sequentially to respect the 8 GB system RAM limit:

### 4.1 Safety & Integrity Remediation Suite (18 tests)
```powershell
pytest backend/tests/unit/test_phase5_1_2_safety_remediation.py -v
```

### 4.2 Git Worktree Isolation Security Suite (7 tests)
```powershell
pytest backend/tests/unit/test_worktree_isolation_security.py -v
```

### 4.3 Phoenix Observability & Hierarchy Ingestion Suite (5 tests)
```powershell
pytest backend/tests/unit/test_phoenix_observability.py -v
```

### 4.4 End-to-End Scenarios Suite (Scenarios A through J)
```powershell
pytest backend/tests/integration/test_e2e_scenarios_suite.py -v
```

### 4.5 Comprehensive Acceptance Verification Checklist (20 checks)
```powershell
python backend/tests/verify_acceptance.py
```

### 4.5 Frontend Production Build & TypeScript Verification
```powershell
cd frontend
npm run build
cd ..
```

---

## 5. Troubleshooting & Maintenance

### 5.1 Port Already in Use (8000, 5173, 6006)
If a previous session crashed without running `stop.ps1`:
```powershell
# Terminate lingering Python and Node processes tied to Ouroboros
Get-Process -Name "python", "node" -ErrorAction SilentlyContinue | Where-Object { $_.Path -like "*Ouroboros*" } | Stop-Process -Force
```

### 5.2 Orphaned Git Worktrees
If a test or run was killed mid-execution, prune abandoned worktrees:
```powershell
git worktree prune
```

### 5.3 Database Crash Reconciliation
On backend startup, `app/main.py` automatically queries `ouroboros.db` and reconciles any runs that were left in intermediate states (`CODING`, `PLANNING`, `PATCH_VALIDATION`) due to an unexpected power loss or server crash, marking them `FAILED` with a clear explanation: `"Process interrupted by server restart. Run halted safely."`.
