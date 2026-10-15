# PROJECT OUROBOROS — WINDOWS OPERATIONS & RUNTIME GUIDE
**Document Reference:** `docs/WINDOWS_OPERATIONS.md`
**Classification:** SRE & Windows System Operations Guide
**Host Target:** Windows 10 x64 / Windows 11 x64
**Status:** ACTIVE
**Last Updated:** October 15, 2026

---

## 1. Host Profile & Resource Architecture

Project Ouroboros is engineered to operate efficiently on resource-constrained commodity developer machines without requiring dedicated server infrastructure, cloud GPU instances, or paid databases.

### Target Host Specifications:
* **Operating System:** Windows 10 x64 (Version 22H2 / Build 19045+)
* **Python Runtime:** Python 3.12.3 in virtual environment (`.venv`)
* **Node.js Runtime:** Node.js 24.14.1 with npm
* **Memory Ceiling:** 8 GB Total Visible RAM (available RAM ~ 800 MB to 3,500 MB)
* **Graphics / Acceleration:** Intel HD Graphics 620 (Integrated; No CUDA GPU)
* **Container Runtime:** Docker Desktop 25.0+ on WSL2 (Optional / Fail-Closed)

---

## 2. Service Architecture & Port Bindings

For security, all local development services bind strictly to loopback (`127.0.0.1`), preventing unwanted exposure across shared local area networks:

| Service | Port | Host Binding | Process Owner | Purpose |
| :--- | :---: | :---: | :--- | :--- |
| **FastAPI Backend** | `8000` | `127.0.0.1` | `.venv\Scripts\python.exe` | Core API, orchestrator, state machine |
| **Vite / React UI** | `5173` | `127.0.0.1` | `npm.cmd run dev` | Real-time human review dashboard |
| **Arize Phoenix** | `6006` | `127.0.0.1` | Phoenix background daemon | OpenTelemetry multi-agent traces |
| **Ollama (Optional)**| `11434`| `127.0.0.1` | `ollama.exe` | Local quantized CPU model inference |
| **MetaGraph (Opt.)**| `8001` | `127.0.0.1` | Navigator daemon | Live codebase graph probe |

---

## 3. Operational PowerShell Scripts

The `scripts/` directory provides standardized, non-destructive automation for Windows:

### 3.1 Pre-Flight Capability Diagnostic
```powershell
powershell -ExecutionPolicy Bypass scripts/check-environment.ps1
```
* Audits Python, Node.js, Git, system RAM, Ollama, and Docker.
* Checks if free physical memory is below the 1,500 MB safety threshold.

### 3.2 Automated Idempotent Setup
```powershell
powershell -ExecutionPolicy Bypass scripts/setup.ps1
```
1. Verifies prerequisites.
2. Initializes `.env` from `.env.example` if absent (preserves existing `.env` without overwriting).
3. Creates `.venv` and installs dependencies via `uv` or `pip`.
4. Runs `npm install` inside `frontend/`.
5. Initializes SQLite database tables via `init_db()`.

### 3.3 Service Startup
```powershell
powershell -ExecutionPolicy Bypass scripts/start.ps1
```
* Launches FastAPI with `--reload` in background.
* Launches Vite dev server in background.
* Records process IDs to `.ouroboros_pids.json` for deterministic tracking.

### 3.4 Service Teardown & Process Cleanup
```powershell
powershell -ExecutionPolicy Bypass scripts/stop.ps1
```
* Reads `.ouroboros_pids.json` and gracefully terminates backend and frontend processes.
* Filters strictly by process path matching `*Ouroboros*` to ensure **unrelated user processes are never killed**.
* Removes `.ouroboros_pids.json`.

---

## 4. Docker Desktop on Windows & WSL2 Engine

### 4.1 Engine Architecture
Docker Desktop on Windows exposes its daemon via the Windows named pipe:
`\\.\pipe\docker_engine`
The underlying container engine runs within the `docker-desktop` WSL2 Linux distribution (Linux kernel 6.6+).

### 4.2 Fail-Closed Handling When Docker Is Stopped
* If Docker Desktop is closed, `SandboxDetector.detect_capabilities()` detects that Docker is offline.
* When `REQUIRE_CONTAINER_SANDBOX=True`, all candidate test executions are halted with:
  `verdict = "BLOCKED"` and `reason_code = "RUNTIME_UNAVAILABLE"`.
* **Zero Host Fallback:** Candidate code is **never** executed directly on the host machine.

### 4.3 Container Security Hardening
When Docker is active, containers are dispatched with strict flags:
```bash
docker run --rm \
  --network none \
  --user 1000:1000 \
  --security-opt no-new-privileges \
  --cap-drop ALL \
  --memory 1500m \
  --cpus 1.0 \
  --pids-limit 100 \
  --tmpfs /tmp:rw,noexec,nosuid,size=64m \
  -v <worktree>:/workspace:rw \
  -w /workspace \
  python:3.12-slim pytest
```

---

## 5. SQLite Database Maintenance & Crash Recovery

### 5.1 Storage Location
All run history, audit logs, candidates, and failure trajectories are stored in:
`ouroboros.db` (SQLite 3 WAL mode enabled).

### 5.2 Server Restart Reconciliation
If the backend process is interrupted during an active run (e.g. power loss or manual kill):
* On subsequent startup, `app.main:app` startup handler executes reconciliation.
* Any run stuck in intermediate non-terminal states (`IDLE`, `CODING`, `PATCH_VALIDATION`, `BASELINE_VALIDATION`) is transitioned safely to `FAILED` with:
  `error_message = "Process interrupted by server restart. Run halted safely."`

### 5.3 Backup & Pruning
```powershell
# Create timestamped snapshot
Copy-Item ouroboros.db "ouroboros_backup_$(Get-Date -Format 'yyyyMMdd_HHmmss').db"
```
To purge ephemeral disposable worktrees without affecting the database:
```powershell
Get-ChildItem -Path "worktrees" -Directory | Remove-Item -Recurse -Force
```
