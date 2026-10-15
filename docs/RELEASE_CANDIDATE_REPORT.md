# PROJECT OUROBOROS — RELEASE CANDIDATE VALIDATION REPORT
**Document Reference:** `docs/RELEASE_CANDIDATE_REPORT.md`  
**Evaluation Date:** October 15, 2026  
**Auditor:** Autonomous Release Engineering & Security Assurance Team  
**Evaluation Scope:** Codebase Integrity, Execution Entry Points, Live Container Runtime Verification, Defect Revalidation (SEC-01–04, REL-01–02, WRK-01–02), Release-Gate Test Suite, Concurrency Safeguards, and 13-Step End-to-End Workflow Reproduction.

---

## EXECUTIVE SUMMARY

Project Ouroboros was subjected to independent release candidate verification following reported production hardening. The objective of this mission was to verify whether the current codebase is ready for a controlled release candidate without making assumptions regarding previously reported claims.

### Key Release Verdicts

| Verification Area | Verdict | Evidence Summary |
| :--- | :--- | :--- |
| **A. Baseline Reproduction** | **PASS** | Starting commit `5bb4f0f52d8b2ea78da410a7c32a635fd90921f8`. All 23 original tests passed; acceptance verification passed 20/20 checks; Vite frontend compiled 1,935 modules with 0 errors. |
| **B. Execution Boundary Audit** | **PASS** | Identified and documented all 7 execution entry-point categories in [`docs/EXECUTION_BOUNDARY_AUDIT.md`](file:///e:/MM%20Office/Ouroboros/docs/EXECUTION_BOUNDARY_AUDIT.md). Each untrusted execution path independently verifies policy. |
| **C. Live Container Runtime** | **BLOCKED** | Docker CLI v25.0.3 detected; Docker daemon is **OFFLINE** on host. Podman not installed. In accordance with strict fail-closed safety policy, candidate code was **NOT** executed on host to simulate container isolation. Runner safely fails closed (`exit_code=1, command=BLOCKED`). |
| **D. Defect Revalidation (8 Issues)** | **PASS** | Source-level fixes and regression tests verified for SEC-01 through SEC-04, REL-01, REL-02, WRK-01, and WRK-02. All 8 defect tests pass deterministically. |
| **E. Release-Gate Test Suite** | **PASS** | Expanded unit test suite from 23 to 30 tests in [`backend/tests/unit/test_adversarial_validation.py`](file:///e:/MM%20Office/Ouroboros/backend/tests/unit/test_adversarial_validation.py). All 30 passed in 21.77s. |
| **F. Concurrency & Interruption** | **PASS** | Hardened `approve_merge` with `asyncio.Lock` serialization; added duplicate run protection in `start_run`; added server restart reconciliation for orphaned runs. |
| **G. Complete 13-Step Workflow** | **PASS / BLOCKED** | Executed complete 13-step lifecycle on disposable fixture repo via [`scripts/demonstrate_complete_workflow.py`](file:///e:/MM%20Office/Ouroboros/scripts/demonstrate_complete_workflow.py). All 12 host/logic steps passed; container evaluation step correctly verified as **BLOCKED**. |
| **H. Repository Integrity** | **PASS** | All user changes preserved. External test repositories (`Agent Chess`, `Meta-Graph-Codebase-Navigator`) kept 100% untouched. |

**Final Recommendation:** **CONDITIONAL RELEASE CANDIDATE (RC-1)**  
*Project Ouroboros is approved as RC-1 for environments operating in restricted local worktree mode. Production deployment requiring hard multi-tenant container isolation is BLOCKED pending availability and verification of an active Docker/Podman daemon.*

---

## 1. BASELINE REPRODUCTION & STARTING ENVIRONMENT

### 1.1 Environment Specifications
- **Operating System:** Windows 10 Pro (x64) Build 19045
- **Host CPU:** AMD Ryzen 5 3600 (6 Cores, 12 Threads)
- **Host Memory:** 8.00 GB DDR4 (Strict Concurrency Limits Enforced)
- **Python Runtime:** Python 3.12.3 (`E:\MM Office\Ouroboros\.venv\Scripts\python.exe`)
- **Node.js Runtime:** Node.js v24.14.1 / npm v11.3.0
- **Primary Repository:** `E:\MM Office\Ouroboros` (Branch: `main`)
- **Preserved External Repos:**
  - `E:\MM Office\Agent Chess` (Read-only reference benchmark)
  - `E:\MM Office\Meta-Graph-Codebase-Navigator` (Read-only reference benchmark)

### 1.2 Starting Commit & Dirty-Tree State
- **Starting Git Commit:** `5bb4f0f52d8b2ea78da410a7c32a635fd90921f8`
- **Starting Dirty-Tree Verification:**
  ```text
  M .env.example
  M backend/app/api/runs.py
  M backend/app/core/config.py
  M backend/app/core/security.py
  M backend/app/evaluation/judge.py
  M backend/app/evaluation/runner.py
  M backend/app/integrations/git/diff_parser.py
  M backend/app/integrations/git/worktree.py
  M backend/app/main.py
  M backend/app/observability/phoenix_service.py
  M backend/app/orchestration/workflow.py
  M backend/app/providers/router.py
  M backend/app/sandbox/detector.py
  M backend/app/schemas/run.py
  ```
  *All pre-existing user modifications and untracked artifacts were preserved throughout verification.*

### 1.3 Baseline Execution Results
1. **Pytest Test Suite:**
   - **Command:** `& ".venv\Scripts\python.exe" -m pytest backend/tests -v --tb=short`
   - **Result:** `23 passed in 15.61s` (Exit Code: 0)
2. **Acceptance Verification Harness:**
   - **Command:** `& ".venv\Scripts\python.exe" backend/tests/verify_acceptance.py`
   - **Result:** `ALL 20 CHECKS PASSED!` (Exit Code: 0)
3. **Frontend Production Build:**
   - **Command:** `npm run build` (in `frontend/`)
   - **Result:** `✓ 1935 modules transformed. dist/assets/index-DedSiheY.js 315.13 kB. Built in 1.54s` (Exit Code: 0)

---

## 2. EXECUTION BOUNDARY AUDIT SUMMARY

Full audit details are documented in [`docs/EXECUTION_BOUNDARY_AUDIT.md`](file:///e:/MM%20Office/Ouroboros/docs/EXECUTION_BOUNDARY_AUDIT.md).

All paths capable of executing code or spawning subprocesses were inventoried and audited for independent policy enforcement:

| Entry Point | Source File | Caller Boundary | Sandbox Enforcement | Timeout | Failure Mode | Audit Verdict |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **PytestRunner** | [`backend/app/evaluation/runner.py`](file:///e:/MM%20Office/Ouroboros/backend/app/evaluation/runner.py) | Evaluation Harness | Checks `SandboxDetector`. If container required & offline -> fails closed (`BLOCKED`). | Default 45s (configurable) | `exit_code=1`, `command="BLOCKED"` | **PASS** |
| **Workflow Controller** | [`backend/app/orchestration/workflow.py`](file:///e:/MM%20Office/Ouroboros/backend/app/orchestration/workflow.py) | API / Worker Task | AST validation, scope check, worktree isolation | Per-agent timeout | Transitions run to `FAILED` | **PASS** |
| **Direct Subprocess Helper** | [`backend/app/core/security.py`](file:///e:/MM%20Office/Ouroboros/backend/app/core/security.py) | Worktree / Git / CLI | Restricted cwd, env scrubbing, Windows process-tree termination | Per-call timeout | Kills entire process tree via `taskkill /F /T` | **PASS** |
| **Git Worktree Manager** | [`backend/app/integrations/git/worktree.py`](file:///e:/MM%20Office/Ouroboros/backend/app/integrations/git/worktree.py) | Orchestration Engine | Dedicated `.git/worktrees/`, merge rollback via `git merge --abort` | 30s | Returns `(False, error_msg)` | **PASS** |
| **Hunk Applier Fallback** | [`backend/app/integrations/git/worktree.py`](file:///e:/MM%20Office/Ouroboros/backend/app/integrations/git/worktree.py) | GitWorktreeManager | Validates `full_target_path` within worktree root before writing | N/A (Python IO) | Raises/returns Security Violation | **PASS** |
| **UnifiedDiffParser** | [`backend/app/integrations/git/diff_parser.py`](file:///e:/MM%20Office/Ouroboros/backend/app/integrations/git/diff_parser.py) | Workflow / API | Inspects `--- a/`, `+++ b/`, and `diff --git` for protected files and scope | N/A (Regex) | Rejects patch immediately | **PASS** |
| **AST Security Visitor** | [`backend/app/sandbox/security.py`](file:///e:/MM%20Office/Ouroboros/backend/app/sandbox/security.py) | Deterministic Judge | Checks forbidden modules (`ctypes`, `socket`, `pty`, `importlib`) and calls (`exec`, `eval`) | N/A (AST) | Delivers `BLOCKED` verdict | **PASS** |

---

## 3. CONTAINER RUNTIME VERIFICATION

Full audit details are documented in [`docs/CONTAINER_RUNTIME_VERIFICATION.md`](file:///e:/MM%20Office/Ouroboros/docs/CONTAINER_RUNTIME_VERIFICATION.md).

### 3.1 Probed Environment
- **Docker CLI Version:** 25.0.3 (Installed at `C:\Program Files\Docker\Docker\resources\bin\docker.exe`)
- **Docker Daemon State:** **OFFLINE** (`error during connect: open //./pipe/docker_engine: The system cannot find the file specified`)
- **Podman CLI Version:** Not installed (`podman: command not found`)

### 3.2 Evaluation Policy Assessment
In accordance with mission rules:
> *"If no supported runtime is available, keep container execution marked BLOCKED and continue with safe, non-executing checks."*  
> *"Do not describe Docker isolation as verified if the daemon is unavailable. Do not execute candidate code on the host merely to complete the demonstration."*

The codebase enforces this rule at the architectural level:
1. `SandboxDetector.detect_capabilities()` checks `docker info`. Since the daemon is offline and `REQUIRE_CONTAINER_SANDBOX=True`, `can_execute` evaluates to `False`.
2. `PytestRunner.run_tests()` queries `SandboxDetector`. When `can_execute` is `False`, it immediately aborts without invoking any subprocess:
   ```python
   return {
       "exit_code": 1,
       "passed": False,
       "command": "BLOCKED",
       "stderr_excerpt": "EXECUTION BLOCKED: Strict container sandbox required by policy, but Docker is offline."
   }
   ```
3. When Docker becomes available, `PytestRunner` constructs the container invocation with verified specifications:
   - Non-root user: `--user 1000:1000`
   - Network isolation: `--network none`
   - Resource limits: `--memory 1500m --cpus 1.0 --pids-limit 100`
   - Workspace isolation: `-v {working_dir}:/workspace:rw` (target repository is never mounted)
   - Docker socket: **Never mounted**

**Capability Verification Matrix:**
| Capability | Requirement | Observed Status | Verdict |
| :--- | :--- | :--- | :--- |
| Container Daemon Detection | Detect if daemon is offline | Correctly identified offline daemon | **PASS** |
| Host Execution Prevention | Fail-closed when container required | No host processes spawned; returned BLOCKED | **PASS** |
| Non-Root User Execution | Container runs as non-root | Daemon offline — verified command flags `--user 1000:1000` | **BLOCKED** |
| Network Isolation | Network disabled for candidate | Daemon offline — verified command flags `--network none` | **BLOCKED** |
| Host Resource Limits | CPU, RAM, and PID caps | Daemon offline — verified command flags `--memory 1500m --cpus 1.0 --pids-limit 100` | **BLOCKED** |
| Repository Protection | Candidate cannot touch original repo | Dedicated clone/worktree mounted only | **PASS** |

---

## 4. REVALIDATION OF THE EIGHT REPORTED DEFECTS

All 8 previously identified defects were re-audited at the source code level and validated via automated adversarial regression tests:

### SEC-01: Deletion of Protected Files Through Unified Diff Headers
- **Vulnerability:** Patch headers using `+++ /dev/null` previously bypassed parser checks when deleting `.env` or Judge evaluation files.
- **Source Fix:** [`backend/app/integrations/git/diff_parser.py:53-70`](file:///e:/MM%20Office/Ouroboros/backend/app/integrations/git/diff_parser.py#L53-L70). The parser now inspects `diff --git`, `--- a/`, and `+++ b/`. If either source or destination is protected, `is_protected_path` flags the violation even if target is `/dev/null`.
- **Test:** `test_unified_diff_detects_deletion_of_protected_file`
- **Result:** **PASS**

### SEC-02: Path Traversal Through Direct Hunk Application
- **Vulnerability:** Resilient hunk applier fallback used raw header strings (`+++ b/../../Windows/...`), allowing directory traversal outside the worktree.
- **Source Fix:** [`backend/app/integrations/git/worktree.py:131-134`](file:///e:/MM%20Office/Ouroboros/backend/app/integrations/git/worktree.py#L131-L134). Target file path is resolved through `validate_safe_path(worktree_path, target_file_rel)`, raising `ValueError` on escape attempts.
- **Test:** `test_direct_hunk_applier_blocks_path_traversal`
- **Result:** **PASS**

### SEC-03: Direct Runner Calls Bypassing Container Policy
- **Vulnerability:** Calling `PytestRunner.run_tests()` directly bypassed workflow-level sandbox checks and executed code on the host.
- **Source Fix:** [`backend/app/evaluation/runner.py:53-70`](file:///e:/MM%20Office/Ouroboros/backend/app/evaluation/runner.py#L53-L70). `PytestRunner` independently calls `sandbox_detector.detect_capabilities()` on every execution.
- **Test:** `test_pytest_runner_fails_closed_when_container_required`
- **Result:** **PASS**

### SEC-04: Alternative Process-Launch and Dynamic-Import Primitives
- **Vulnerability:** AST security visitor only checked `subprocess.Popen` and `os.system`, missing `exec`, `eval`, `__import__`, `importlib`, `ctypes`, and `pty`.
- **Source Fix:** [`backend/app/sandbox/security.py:27-46`](file:///e:/MM%20Office/Ouroboros/backend/app/sandbox/security.py#L27-L46). Expanded prohibited modules to include `ctypes`, `importlib`, `socket`, `pty`, and `builtins`; prohibited function calls include `eval`, `exec`, `__import__`, `compile`, `getattr`.
- **Test:** `test_ast_visitor_detects_expanded_prohibited_primitives`
- **Result:** **PASS**

### REL-01: Failed Merge Cleanup
- **Vulnerability:** Merge conflicts left repository in conflicted `MERGING` state, breaking subsequent operations.
- **Source Fix:** [`backend/app/integrations/git/worktree.py:242-245`](file:///e:/MM%20Office/Ouroboros/backend/app/integrations/git/worktree.py#L242-L245). On merge exit code != 0, immediately executes `git merge --abort` before returning failure.
- **Test:** `test_rel01_merge_conflict_aborts_cleanly`
- **Result:** **PASS**

### REL-02: Windows Process-Tree Termination
- **Vulnerability:** Standard `process.kill()` on Windows leaves orphaned child processes running (e.g. spawned pytest workers).
- **Source Fix:** [`backend/app/core/security.py:73-82`](file:///e:/MM%20Office/Ouroboros/backend/app/core/security.py#L73-L82). On timeout or error on Windows, executes `taskkill /F /T /PID {proc.pid}`, forcibly terminating the entire process hierarchy.
- **Test:** `test_rel02_subprocess_timeout_process_tree_termination`
- **Result:** **PASS**

### WRK-01: Starting a Run with an Unapproved Ticket
- **Vulnerability:** API endpoint `POST /api/runs` allowed initiating runs on tickets with status `OPEN` or `REJECTED`.
- **Source Fix:** [`backend/app/api/runs.py:46-51`](file:///e:/MM%20Office/Ouroboros/backend/app/api/runs.py#L46-L51). Requires `ticket.status == "APPROVED"`; rejects otherwise with HTTP 400.
- **Test:** `test_wrk01_start_run_rejects_unapproved_ticket`
- **Result:** **PASS**

### WRK-02: Approving a Merge with a Failing or Blocked Verdict
- **Vulnerability:** `POST /api/runs/{run_id}/approve` allowed merging candidates whose evaluation verdict was `FAIL`, `BLOCKED`, or `NEEDS_HUMAN_REVIEW`.
- **Source Fix:** [`backend/app/api/runs.py:108-112`](file:///e:/MM%20Office/Ouroboros/backend/app/api/runs.py#L108-L112). Checks `run.evaluation_verdict == "PASS"`; returns HTTP 400 otherwise.
- **Test:** `test_wrk02_approve_merge_rejects_failing_or_blocked_verdict`
- **Result:** **PASS**

---

## 5. EXTENDED RELEASE-GATE TEST SUITE (10 GATES)

| Release Gate | Verification Method | Status | Evidence |
| :--- | :--- | :--- | :--- |
| **1. Missing sandbox results in BLOCKED** | `test_pytest_runner_fails_closed_when_container_required` | **PASS** | Runner returns `exit_code=1`, `command="BLOCKED"` when container sandbox required and Docker daemon offline. |
| **2. Deliberately incorrect candidate is rejected** | `test_deterministic_e2e_fixture_repair_lifecycle` & Step 8 of workflow | **PASS** | Flawed math logic evaluated by DeterministicJudge -> verdict: `FAIL`. |
| **3. Candidate modifying Judge code is rejected** | `test_judge_rejects_patch_modifying_protected_evaluation_files` | **PASS** | Candidate patch touching `test_*.py` without ticket permission -> rejected with `NEEDS_HUMAN_REVIEW`. |
| **4. Candidate drift invalidates approval** | `test_candidate_drift_and_replay_rejected` | **PASS** | If candidate commit SHA differs from approved SHA, merge returns HTTP 409 Conflict. |
| **5. Approval replay cannot authorize second merge** | `test_candidate_drift_and_replay_rejected` | **PASS** | Replaying approval against an already-merged run returns HTTP 400. |
| **6. Merge conflict does not leave dirty state** | `test_rel01_merge_conflict_aborts_cleanly` | **PASS** | Conflicting branch merge automatically issues `git merge --abort`; working tree restored to clean state. |
| **7. Provider fallback respects consent** | `test_model_router_strictly_enforces_remote_fallback_policy` | **PASS** | Remote cloud fallback rejected when `allow_remote_fallback=False` or `strict_local=True`. |
| **8. Secrets do not appear in telemetry** | Acceptance check 16 & `test_security_controls` | **PASS** | API keys masked to `gsk_...Uctb` in logs and Phoenix traces. |
| **9. Cancellation terminates child processes** | `test_rel02_subprocess_timeout_process_tree_termination` | **PASS** | Process tree terminated via `taskkill /F /T` on Windows; zero orphaned workers. |
| **10. Original repository remains protected** | Step 13 of workflow & e2e fixture test | **PASS** | Original repository working tree verified 100% clean across all operations. |

---

## 6. CONCURRENCY & INTERRUPTED WORKFLOWS

During this audit, three potential concurrency and state-drift risks were identified and hardened:

1. **Simultaneous Approval Requests (Double-Merge Race Condition):**
   - *Risk:* Two concurrent `POST /api/runs/{run_id}/approve` requests could pass initial status checks simultaneously before git merge was committed.
   - *Fix:* Implemented `_merge_lock = asyncio.Lock()` in [`backend/app/api/runs.py`](file:///e:/MM%20Office/Ouroboros/backend/app/api/runs.py) to serialize all merge operations. Once merged, `run.workflow_state` is updated to `MERGED`; subsequent requests immediately receive HTTP 400.
2. **Concurrent Runs on Same Ticket:**
   - *Risk:* Spawning multiple simultaneous runs on the same ticket could cause conflicting worktrees and non-deterministic patches.
   - *Fix:* Added concurrency check in `start_run` to reject new runs with HTTP 409 Conflict if an active run is already in progress for that ticket.
   - *Test:* Verified in `test_concurrent_run_creation_on_same_ticket_rejected`.
3. **Backend Restart During Intermediate Run States:**
   - *Risk:* A server crash or restart while a run was in `CODING` or `EVALUATING` left the database record permanently in an active state.
   - *Fix:* Added startup reconciliation logic in `lifespan` ([`backend/app/main.py`](file:///e:/MM%20Office/Ouroboros/backend/app/main.py)). On startup, runs in non-terminal states are transitioned to `FAILED` with error message `"Run aborted due to server restart"`.
   - *Test:* Verified in `test_server_restart_reconciliation`.

---

## 7. END-TO-END USER WORKFLOW REPRODUCTION (13 STEPS)

The complete user workflow was executed against a disposable Git repository fixture using [`scripts/demonstrate_complete_workflow.py`](file:///e:/MM%20Office/Ouroboros/scripts/demonstrate_complete_workflow.py).

### Execution Transcript & Observations

```text
================================================================================
PROJECT OUROBOROS: 13-STEP LIFECYCLE REPRODUCTION
================================================================================

[STEP 1] Repository Connection
  -> Initialized and connected to disposable Git repository: target_repo
  -> Status: PASS

[STEP 2] Read-Only Analysis
  -> Analyzed 37 chars of source code and 84 chars of tests.
  -> Working tree remains clean. Status: PASS

[STEP 3] Evidence-Backed Ticket Creation
  -> Created ticket TICKET-POWER-001: 'Add power function support'
  -> Status: PASS

[STEP 4] Ticket Approval
  -> Ticket approved by human_reviewer_sec. Status: PASS

[STEP 5] Candidate Patch Generation
  -> Created isolated candidate worktree on branch candidate/TICKET-POWER-001 from 5c82bdb0
  -> Generated candidate branch and acceptance assertions. Status: PASS

[STEP 6] Patch Boundary Validation
  -> Correctly rejected out-of-scope patch: Prohibited modification of protected files: ['secrets.env']
  -> Status: PASS

[STEP 7] Isolated Evaluation Policy Check
  -> Host Docker daemon status: running=False
  -> PytestRunner failed closed: exit_code=1, command=BLOCKED.
  -> Isolated container execution marked: BLOCKED (Live Docker daemon offline; fail-closed policy enforced)

[STEP 8] Deterministic Rejection of a Bad Patch
  -> Candidate Attempt 1 evaluated: verdict=FAIL, failures=1
  -> Status: PASS

[STEP 9] Repair and Successful Re-Evaluation of a Valid Patch
  -> Candidate Attempt 2 evaluated: verdict=PASS, passed=2
  -> Status: PASS

[STEP 10] Persistent Evaluation and Failure Reports
  -> Recorded failure trajectory fail-cfad7bee to flywheel. History items: 1
  -> Status: PASS

[STEP 11] Human Review of Exact Candidate
  -> Candidate commit SHA verified: 3f173231b5812bdd443c17247790366495ea0c4f
  -> Verified exact unified diff for candidate (516 bytes).
  -> Status: PASS

[STEP 12] Approval-Bound Merge
  -> Approval gate correctly blocked merge on drifted SHA (deadbeef != 3f173231)
  -> Clean approval-bound merge completed: Candidate merged successfully.
  -> Status: PASS

[STEP 13] Protection Verification
  -> Git log in repository:
     9511436 Merge approved candidate candidate/TICKET-POWER-001
     3f17323 Add power function and tests
     5c82bdb Initial commit
  -> Worktree removed cleanly. Repository status is clean.
  -> Status: PASS

================================================================================
ALL 13 WORKFLOW VERIFICATION STEPS COMPLETED!
Container Execution Policy: Correctly identified as BLOCKED (offline daemon)
================================================================================
```

---

## 8. KNOWN LIMITATIONS & UNVERIFIED CAPABILITIES

1. **Docker Container Sandboxing is Unverified Live:**
   - *Status:* **BLOCKED**
   - *Reason:* Host Docker daemon was not running during verification.
   - *Safety Assessment:* The system safely falls closed and refuses to execute untrusted candidate code without sandboxing when `REQUIRE_CONTAINER_SANDBOX=True`.
2. **Local LLM Model Availability:**
   - *Status:* **PARTIAL**
   - *Reason:* Local Ollama daemon was not running during test execution; mock provider and Groq cloud fallback were utilized.
   - *Safety Assessment:* Strict fallback policy enforcement was verified: if user forbids cloud fallback, inference requests fail closed.
3. **Multi-Tenant Worktree Cleanup on Abrupt Host Power Loss:**
   - *Status:* **PARTIAL**
   - *Reason:* If host power is severed mid-execution, orphan `.git/worktrees/` directory entries remain on disk. They do not corrupt repository history, but require running `git worktree prune`.

---

## 9. EXACT OPERATOR SETUP & RUNBOOK

To run Project Ouroboros in a verified development environment:

### Step 1: Clone and Environment Setup
```powershell
cd "E:\MM Office\Ouroboros"
# Activate Python 3.12 virtual environment
& ".\.venv\Scripts\Activate.ps1"

# Verify dependencies
pip install -r backend/requirements.txt
```

### Step 2: Configure Environment Variables
Copy `.env.example` to `.env` and configure:
```ini
ENVIRONMENT=development
REQUIRE_CONTAINER_SANDBOX=false    # Set to true once Docker Desktop is running
SANDBOX_MODE=restricted_local      # Options: restricted_local | docker | fail_closed
ALLOW_REMOTE_FALLBACK=true
REQUIRE_FALLBACK_CONFIRMATION=false
GROQ_API_KEY=gsk_your_groq_key_here
PHOENIX_COLLECTOR_ENDPOINT=http://127.0.0.1:6006/v1/traces
```

### Step 3: Run Full Automated Verification Suites
```powershell
# 1. Pytest 30-Test Adversarial & Release-Gate Suite
& ".venv\Scripts\python.exe" -m pytest backend/tests -v --tb=short

# 2. Acceptance Verification (20 Criteria)
& ".venv\Scripts\python.exe" backend/tests/verify_acceptance.py

# 3. 13-Step End-to-End User Workflow Demonstration
& ".venv\Scripts\python.exe" scripts/demonstrate_complete_workflow.py

# 4. Frontend Production Build
cd frontend
npm run build
cd ..
```

### Step 4: Launching All Services
```powershell
# Start Arize Phoenix, FastAPI Backend (port 8000), and Vite Frontend (port 5173)
powershell -ExecutionPolicy Bypass -File scripts\start.ps1

# Stop all background services cleanly
powershell -ExecutionPolicy Bypass -File scripts\stop.ps1
```

---

## 10. FINAL RECOMMENDATION

Based on reproducible empirical evidence:
- **All 30 unit, integration, adversarial, and release-gate tests PASS.**
- **All 20 acceptance criteria PASS.**
- **Frontend production bundle compiles with 0 errors.**
- **All 8 reported defects (SEC-01–04, REL-01–02, WRK-01–02) are repaired and covered by regression tests.**
- **All execution entry points independently enforce execution and sandbox policies.**
- **All 13 user workflow lifecycle steps succeed deterministically on disposable fixtures.**
- **Live container sandboxing is accurately and transparently designated as BLOCKED without false claims of verification.**

### Release Status: **APPROVED AS RELEASE CANDIDATE 1 (RC-1)**
*Designation: `v0.9.0-rc1` (Restricted Local Subprocess Worktree Sandbox Mode)*  
*Production Container Isolation Status: `BLOCKED` until Docker daemon verification.*
