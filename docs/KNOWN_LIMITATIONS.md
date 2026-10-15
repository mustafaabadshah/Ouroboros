# PROJECT OUROBOROS — KNOWN LIMITATIONS & OPERATIONAL BOUNDARIES
**Document Reference:** `docs/KNOWN_LIMITATIONS.md`  
**Release:** `v0.9.0-rc1`  
**Status:** ACTIVE  
**Last Updated:** October 15, 2026  

---

## 1. HARDWARE & CONTAINER RUNTIME LIMITATIONS

### 1.1 Host Docker Daemon Offline (Isolation: BLOCKED)
- **Status:** **BLOCKED**
- **Impact:** Live container isolation cannot be executed because Docker Desktop / Docker daemon is offline on the development host.
- **Safety Enforcement:** The system enforces strict fail-closed security. When `REQUIRE_CONTAINER_SANDBOX=True`, `PytestRunner` immediately returns `command="BLOCKED", exit_code=1` without executing candidate code on the host.
- **Remediation:** Start Docker Desktop and verify with `docker info` before enabling strict container isolation in `.env`.

### 1.2 Memory Limits (8 GB RAM Host)
- **Status:** **BOUNDED**
- **Impact:** The development machine operates with 8.0 GB RAM. Running simultaneous local LLM inference alongside multi-worker test runners risks memory exhaustion.
- **Enforcement:**
  - `RAM Warning Threshold` is set to 1,500 MB in `backend/app/core/config.py`.
  - Max test process concurrency is capped at 1 via `_lock` in `PytestRunner`.
  - Context windows for local models are capped at 4,096 tokens.

---

## 2. REPOSITORY & WORKTREE BOUNDARIES

### 2.1 Single-Tenant Worktree Concurrency
- **Status:** **BOUNDED**
- **Impact:** SQLite enforces single-writer locking. To prevent conflicting merges and race conditions, `backend/app/api/runs.py` serializes approvals using an asynchronous lock (`_merge_lock`).
- **Remediation:** For enterprise multi-tenant deployments, migrate SQLite to PostgreSQL with row-level locking.

### 2.2 Worktree Pruning on Abrupt Power Loss
- **Status:** **PARTIAL**
- **Impact:** If the host process is forcefully terminated (e.g. power severed) while a candidate worktree exists, `.git/worktrees/<ticket-id>` remains on disk.
- **Remediation:** Run `git worktree prune` from the target repository root to safely prune orphaned references. Primary repository commit history is never corrupted.

---

## 3. STATIC AST ANALYSIS BOUNDARY

- **Status:** **DEFENSE-IN-DEPTH**
- **Impact:** The `ASTSecurityVisitor` inspects Python syntax trees for prohibited calls (`os.system`, `eval`, `exec`, `__import__`) and modules (`socket`, `ctypes`, `pty`).
- **Boundary:** Static AST screening cannot inspect compiled native C-extensions or dynamic runtime strings disguised as obfuscated attributes. It is designed as an early filter before container execution, not as a replacement for OS-level container isolation.
