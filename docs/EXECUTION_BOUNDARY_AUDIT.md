# PROJECT OUROBOROS: EXECUTION BOUNDARY & ENTRY-POINT AUDIT

**Document Version:** 1.0.0 (Release Candidate Audit)  
**Classification:** Defensive Security & Systems Architecture Specification  
**Audit Target:** All backend paths that execute code, spawn subprocesses, or invoke test/build harnesses.  
**Status:** COMPLETED & INDEPENDENTLY ENFORCED  

---

## 1. Executive Summary

In automated code generation and repair platforms, relying exclusively on a single high-level controller check creates privilege escalation risks. Non-workflow callers, test fixtures, background jobs, evaluation endpoints, or fallback routines can inadvertently bypass higher-level gates.

This audit inventories **every path in the Project Ouroboros backend** that can execute repository-controlled code, invoke shell binaries, or touch disk structures. Every entry point is verified to enforce its own security boundary independently.

---

## 2. Complete Execution-Entry-Point Inventory

```
+---------------------------------------------------------------------------------------------------+
|                                  ENTRY POINT INVENTORY TAXONOMY                                    |
+------------------------------------+--------------------------------+-----------------------------+
| Category                           | Component / Function           | Primary Security Gate       |
+------------------------------------+--------------------------------+-----------------------------+
| 1. Test & Harness Execution        | PytestRunner.run_tests         | Fail-Closed Sandbox Gate    |
| 2. Multi-Agent Lifecycle Engine    | WorkflowController.execute_run | State Machine & Frozen Hash |
| 3. Ephemeral Git Worktree Manager  | GitWorktreeManager.*           | Path & Process Isolation    |
| 4. Static Patch Boundary Inspector | UnifiedDiffParser.parse_patch  | Diff Header Regex Guard     |
| 5. Static AST Threat Screen        | ASTSecurityVisitor.visit_*     | Prohibited Primitives Set   |
| 6. Subprocess Wrapper              | run_safe_subprocess            | Process-Tree Timeout / Args |
| 7. Dependency & Environment Policy | Environment Isolation          | Zero Dynamic Pip Install    |
+------------------------------------+--------------------------------+-----------------------------+
```

---

## 3. Detailed Boundary Audits

### 3.1 PytestRunner (`backend/app/evaluation/runner.py`)
* **Callers:**
  - `workflow.py` (Stage 1: Baseline validation, Stage 6: Candidate acceptance & regression)
  - `judge.py` (`evaluate_candidate`)
  - Test suites and evaluation lab harnesses (`test_e2e_fixture.py`, `test_adversarial_validation.py`)
* **Trust Boundary:** Candidate worktree code and tests (UNTRUSTED).
* **Sandbox Enforcement:**
  - **Intrinsic Check:** Directly calls `sandbox_detector.detect_capabilities()`.
  - **Fail-Closed Gate:** If `fail_closed_required` is `True` and Docker is offline, execution is immediately halted, returning `{exit_code: 1, passed: False, command: "BLOCKED"}` without spawning any host subprocess.
  - **Container Isolation (when Docker active):** Dispatches rootless container: `docker run --rm --network none --user 1000:1000 --memory 1500m --cpus 1.0 --pids-limit 100 -v <worktree>:/workspace:rw -w /workspace python:3.12-slim pytest`.
  - **Restricted Local Mode (local dev fallback only):** Executes localized venv python interpreter with global concurrency mutex (`asyncio.Lock()`).
* **Timeout:** Bounded by `SUBPROCESS_TIMEOUT_SECONDS` (default: 45s, max: 60s).
* **Cancellation Behavior:** If parent task cancels or times out, Windows `taskkill /F /T /PID` terminates the entire process tree.
* **Failure Mode:** Structured JSON dictionary with exit codes, passed/failed counts, and parsed tracebacks. No unhandled exceptions leak to callers.

---

### 3.2 WorkflowController (`backend/app/orchestration/workflow.py`)
* **Callers:**
  - `runs.py` (`start_run`) via FastAPI `BackgroundTasks`
* **Trust Boundary:** Run initiation requests, ticket parameters, LLM patches (UNTRUSTED).
* **Sandbox Enforcement:**
  - Pre-execution validation: ticket status must be `APPROVED` (checked in `runs.py`).
  - Pre-flight sandbox check: aborts if `sandbox_status.can_execute` is `False`.
  - Cryptographic criteria freezing: computes SHA-256 fingerprint of `acceptance_criteria_json` and candidate scope before generating code.
  - State machine transitions validated via `WorkflowStateMachine.validate_transition()`.
* **Timeout:** Per-stage timeouts; overall run capped by `SUBPROCESS_TIMEOUT_SECONDS * max_retries`.
* **Cancellation Behavior:** Polled before each stage (`self.is_cancelled(run_id)`). If cancelled, transitions run state to `CANCELLED`, halts background execution, and cleans up worktree.
* **Failure Mode:** Transitions run to `FAILED` or `BLOCKED` with diagnostic error message persisted in SQLite and emitted via Server-Sent Events (SSE).

---

### 3.3 Git Worktree Subprocesses (`backend/app/integrations/git/worktree.py`)
* **Callers:**
  - `WorkflowController` (Stages 3, 5, 7)
  - `runs.py` (`approve_merge`, `reject_merge`)
  - Integration and fixture tests
* **Subprocess Operations:**
  1. `create_worktree`: `git worktree add -b <branch> <path> <base_commit>`
  2. `apply_patch`: `git apply --check`, `git apply -v`, `git apply --3way`, fallback to `_apply_hunks_directly`
  3. `commit_candidate`: `git add -A`, `git commit -m <msg>`
  4. `merge_candidate`: `git merge <branch> --no-ff -m <msg>`
  5. `remove_worktree`: `git worktree remove --force <path>`, `git worktree prune`, `git branch -D <branch>`
* **Trust Boundary:** Developer's primary working tree (TRUSTED) vs. Candidate worktrees under `worktrees/` (ISOLATED / DISPOSABLE).
* **Sandbox Enforcement:**
  - Worktrees created strictly under `worktrees/ouro-...`.
  - In `_apply_hunks_directly`, `validate_safe_path(worktree_path, target_file_rel)` blocks path traversal (`../../`) and secret files (`.env`, `.pem`, `id_rsa`).
  - In `merge_candidate`, if `git merge` returns non-zero, `git merge --abort` is executed immediately to restore clean repository state.
* **Timeout:** Process timeout bounded by `run_safe_subprocess`.
* **Cancellation Behavior:** Ephemeral worktrees pruned on termination.
* **Failure Mode:** Returns `(False, error_message)` tuple; handles git conflicts safely without dirtying main branch.

---

### 3.4 Static Patch Boundary Guard (`backend/app/integrations/git/diff_parser.py`)
* **Callers:**
  - `judge.py` (`evaluate_patch_static`)
  - `runs.py` (`approve_merge` pre-merge verification)
  - `workflow.py` (Stage 5)
* **Trust Boundary:** LLM-generated unified diff text (UNTRUSTED).
* **Sandbox Enforcement:**
  - Non-executing regex parsing.
  - Matches `diff --git`, `--- a/...`, and `+++ b/...`.
  - Deletions to `+++ /dev/null` are tracked under source file path and checked against `is_protected_path()`.
  - Renamed or multi-file diffs validate all touched paths.
  - Rejects out-of-scope files (`candidate_files_json`) and line additions exceeding `max_lines` (500).
* **Timeout:** In-memory string processing (< 5ms).
* **Cancellation Behavior:** N/A (synchronous).
* **Failure Mode:** Returns `{is_valid: False, error: "..."}`.

---

### 3.5 Static AST Security Visitor (`backend/app/sandbox/security.py`)
* **Callers:**
  - `judge.py` (`evaluate_patch_static`)
  - Test suites
* **Trust Boundary:** Python source files within candidate worktree (UNTRUSTED).
* **Sandbox Enforcement:**
  - In-memory AST parsing via `ast.parse` (no bytecode or runtime execution).
  - Detects prohibited calls: `os.system`, `os.popen`, `os.spawn*`, `os.posix_spawn*`, `os.exec*`, `subprocess.*`, `asyncio.create_subprocess_*`, `importlib.*`, `eval`, `exec`, `__import__`, `compile`.
  - Detects prohibited modules: `socket`, `ctypes`, `pty`, `importlib`, `multiprocessing`.
* **Timeout:** In-memory AST traversal (< 10ms).
* **Cancellation Behavior:** N/A (synchronous).
* **Failure Mode:** Returns `{is_safe: False, violations: [...]}`.

---

### 3.6 Subprocess Execution Wrapper (`backend/app/core/security.py`)
* **Callers:**
  - `runner.py`, `worktree.py`, `detector.py`, `security.py`
* **Trust Boundary:** System shell and process boundaries.
* **Sandbox Enforcement:**
  - Explicit argument arrays only: **`shell=True` is strictly forbidden**.
  - Environment sanitization: strips cloud provider keys, passes PATH and venv variables.
  - Working directory strictly validated via `cwd`.
  - Output bounded by `MAX_OUTPUT_CAPTURE_BYTES` (64 KB).
* **Timeout:** `asyncio.wait_for()` wraps `proc.communicate()`.
* **Cancellation Behavior:** On timeout, Windows `taskkill /F /T /PID {proc.pid}` terminates parent and all spawned child/worker processes.
* **Failure Mode:** Returns `(-1, "", "Execution timed out...")` or `(exit_code, stdout, stderr)`.

---

### 3.7 Dependency Installation & Build Policy
* **Policy:** **Zero dynamic package installation**.
* **Audit Finding:**
  - Project Ouroboros candidates and repair loops are **strictly prohibited** from invoking `pip install`, `npm install`, or downloading wheels.
  - All test executions utilize the pre-existing, vetted virtual environment or base container image (`python:3.12-slim`).
  - Patches attempting to modify `requirements.txt`, `pyproject.toml`, or `package.json` are rejected unless explicitly listed in `candidate_files` and subject to human review.

---

## 4. Architectural Summary

| Entry Point | Independently Sandboxed? | Bypass Possible via Non-Workflow Caller? |
| :--- | :---: | :---: |
| `PytestRunner.run_tests` | **YES** (Intrinsic capability check) | **NO** |
| `UnifiedDiffParser.validate_patch_boundaries` | **YES** (Header & protected path regex) | **NO** |
| `GitWorktreeManager._apply_hunks_directly` | **YES** (`validate_safe_path` check) | **NO** |
| `GitWorktreeManager.merge_candidate` | **YES** (`git merge --abort` on conflict) | **NO** |
| `runs.py (start_run)` | **YES** (`ticket.status == APPROVED` check) | **NO** |
| `runs.py (approve_merge)` | **YES** (verdict check + diff hash verify + lock) | **NO** |
| `ASTSecurityVisitor` | **YES** (Comprehensive prohibited sets) | **NO** |
