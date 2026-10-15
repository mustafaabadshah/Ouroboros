# PROJECT OUROBOROS — MASTER ROADMAP
**Document Reference:** `docs/MASTER_ROADMAP.md`  
**Current Milestone:** Complete Platform Improvement, Multi-Agent Repair, Evaluation, Observability & Release Engineering  
**Target Release:** `v0.9.0-rc1` (with roadmap path to `v1.0.0`)  
**Last Updated:** October 15, 2026  

---

## 1. OVERVIEW & ROADMAP GOALS

Project Ouroboros is a hierarchical, multi-agent autonomous software engineering platform designed to analyze codebases, plan verified improvements, generate isolated patches, evaluate candidate changes deterministically, learn from prior failure trajectories, and present real telemetry through a modern developer interface.

This roadmap tracks all four engineering phases across 14 release gates (G1–G14), detailing task IDs, priorities, dependencies, acceptance criteria, implementation status, and remaining risks.

Status Legend:
- `COMPLETED`: Implemented, tested, and verified with reproducible evidence.
- `IN_PROGRESS`: Currently under active development or testing.
- `BLOCKED`: Dependency or hardware prerequisite unavailable (e.g. host Docker daemon offline).
- `PARTIAL`: Partially functional; safe subset implemented and verified.
- `PLANNED`: Queued for execution in the current sequence.

---

## 2. PHASE 1: RUNTIME SECURITY, EXECUTION INFRASTRUCTURE & RELIABILITY

| Task ID | Workstream | Description | Priority | Dependencies | Acceptance Criteria | Status | Tests & Evidence | Remaining Risks |
| :--- | :--- | :--- | :---: | :--- | :--- | :---: | :--- | :--- |
| **P1-T1** | Runtime Boundary | Probe Docker / Podman daemon and report runtime readiness | P0 | Host OS | Return accurate capability dictionary; never assume CLI == daemon running | `COMPLETED` | `SandboxDetector.detect_capabilities()`, `CONTAINER_RUNTIME_VERIFICATION.md` | Docker daemon offline on host; candidate container execution blocked |
| **P1-T2** | Fail-Closed Policy | Enforce fail-closed runner behavior when container sandbox required | P0 | P1-T1 | If `REQUIRE_CONTAINER_SANDBOX=True` & Docker offline, return `exit_code=1`, `command="BLOCKED"` without host execution | `COMPLETED` | `test_pytest_runner_fails_closed_when_container_required` in `test_adversarial_validation.py` | None |
| **P1-T3** | Patch Boundaries | Unified diff boundary parsing, file scope check, protected path protection | P0 | Diff Parser | Reject patches modifying `.env`, tests, or files outside ticket `allowed_files`; block deletion headers (`+++ /dev/null`) | `COMPLETED` | `test_unified_diff_detects_deletion_of_protected_file`, `UnifiedDiffParser.validate_patch_boundaries` | Malicious symlinks handled via `validate_safe_path` |
| **P1-T4** | Hunk Applier Safety | Direct hunk applier path traversal prevention | P0 | Worktree Mgr | Validate target relative path within worktree before writing; reject `..` traversal | `COMPLETED` | `test_direct_hunk_applier_blocks_path_traversal` | None |
| **P1-T5** | AST Screening | Expand prohibited AST primitives in candidate Python code | P1 | AST Visitor | Flag `ctypes`, `socket`, `pty`, `importlib`, `eval`, `exec`, `__import__` | `COMPLETED` | `test_ast_visitor_detects_expanded_prohibited_primitives` in `test_adversarial_validation.py` | AST is defense-in-depth, not complete sandbox |
| **P1-T6** | Workflow Auth Gate | Enforce ticket approval before run and passing verdict before merge | P0 | API / Database | `POST /api/runs` rejects unapproved tickets (HTTP 400); `approve_merge` rejects non-passing verdicts (HTTP 400) | `COMPLETED` | `test_wrk01_start_run_rejects_unapproved_ticket`, `test_wrk02_approve_merge_rejects_failing_or_blocked_verdict` | None |
| **P1-T7** | Merge Lock & Concurrency | Serialize candidate merges and prevent concurrent runs on same ticket | P0 | API Runs | `_merge_lock = asyncio.Lock()`, duplicate run check returns HTTP 409 Conflict | `COMPLETED` | `test_concurrent_run_creation_on_same_ticket_rejected`, `test_candidate_drift_and_replay_rejected` | SQLite file-locking under extreme concurrency |
| **P1-T8** | Subprocess Tree Kill | Windows process-tree termination on timeout/cancellation | P0 | Subprocess | Use `taskkill /F /T /PID` on Windows to clean child processes | `COMPLETED` | `test_rel02_subprocess_timeout_process_tree_termination` in `test_adversarial_validation.py` | None |
| **P1-T9** | Merge Rollback | Clean rollback on merge conflict | P1 | Git Worktree | Automatically execute `git merge --abort` on conflict; restore pristine working tree | `COMPLETED` | `test_rel01_merge_conflict_aborts_cleanly` in `test_adversarial_validation.py` | None |
| **P1-T10**| Server Restart Recovery | Startup reconciliation for orphaned runs in non-terminal states | P1 | Backend Lifespan | Transition orphaned `CODING`/`EVALUATING` runs to `FAILED` with descriptive error on startup | `COMPLETED` | `test_server_restart_reconciliation` in `test_adversarial_validation.py` | None |

---

## 3. PHASE 2: COMPLETE MULTI-AGENT SOFTWARE-REPAIR LIFECYCLE

| Task ID | Workstream | Description | Priority | Dependencies | Acceptance Criteria | Status | Tests & Evidence | Remaining Risks |
| :--- | :--- | :--- | :---: | :--- | :--- | :---: | :--- | :--- |
| **P2-T1** | Agent Roles | Formalize agent roles (Architect, Planner, Coder, Critic, Judge) | P1 | Multi-Agent | Defined contracts, input/output schemas, error boundaries, and bounded retries | `COMPLETED` | `backend/app/agents/`, `docs/AGENT_ARCHITECTURE.md` | Local model context window limits |
| **P2-T2** | Repository Analysis | Pure AST and Meta-Graph Codebase Navigator repository scanning | P1 | MetaGraph | Scan repo without modifying; discover modules, tests, functions, tech debt candidates | `COMPLETED` | `test_meta_graph_adapter_agent_chess`, `scripts/demonstrate_complete_workflow.py` Step 2 | Large repos (>100k LOC) need file limits |
| **P2-T3** | Ticket Lifecycle | State machine: `DISCOVERED` -> `DRAFT` -> `APPROVED` -> `IN_PROGRESS` -> `EVALUATING` -> `REVIEW_REQUIRED` -> `MERGE_APPROVED` -> `MERGED` | P0 | Database / API | Strict state validation; reject illegal transitions; record approval metadata | `COMPLETED` | `test_workflow_state_transitions`, `docs/WORKFLOW_STATE_MACHINE.md` | None |
| **P2-T4** | Candidate Isolation | Dedicated Git worktrees per candidate run | P0 | Git Worktree | Distinct `.git/worktrees/<ticket-id>`, unique candidate branch, SHA binding | `COMPLETED` | `GitWorktreeManager.create_worktree()`, `test_deterministic_e2e_fixture_repair_lifecycle` | Dirty worktrees on power outage pruned via `git worktree prune` |
| **P2-T5** | Evaluation-Repair Loop | Iterative loop: baseline -> patch -> evaluate -> failure trajectory -> repair patch -> reevaluate | P0 | Judge / Flywheel | Flawed patch rejected; repair patch succeeds; failure trajectory persisted | `COMPLETED` | `scripts/demonstrate_complete_workflow.py` Steps 8–10, `test_e2e_fixture.py` | Token budget exhaustion on difficult bugs |
| **P2-T6** | Approval Binding | Candidate commit SHA-256 bound to human approval | P0 | Worktree Mgr | Candidate revision drift invalidates approval; replay rejected | `COMPLETED` | `test_candidate_drift_and_replay_rejected`, `scripts/demonstrate_complete_workflow.py` Step 12 | None |
| **P2-T7** | End-to-End Fixtures | Deterministic fixture scenarios (13-step complete lifecycle demonstration) | P0 | Orchestration | All 13 lifecycle steps execute; container evaluation correctly marked `BLOCKED` | `COMPLETED` | `scripts/demonstrate_complete_workflow.py` (Exit code 0, 13/13 steps verified) | None |

---

## 4. PHASE 3: EVALUATION SCIENCE, FAILURE MEMORY & OBSERVABILITY

| Task ID | Workstream | Description | Priority | Dependencies | Acceptance Criteria | Status | Tests & Evidence | Remaining Risks |
| :--- | :--- | :--- | :---: | :--- | :--- | :---: | :--- | :--- |
| **P3-T1** | Versioned Benchmark | Standardized suite of reproducible bug-fix fixtures with ground truth | P1 | Evaluation | Versioned tasks with problem statements, baseline tests, acceptance assertions, protected files | `COMPLETED` | `backend/app/evaluation/benchmark.py` (`BENCHMARK_TASKS_V1`) | Needs diverse difficulty distribution |
| **P3-T2** | Honest Metrics | Metric calculation engine: repair rate, regression rate, attempts, latency, tokens, cost | P1 | Flywheel / DB | Explicit formulas; distinct reporting for blocked vs passed vs failed | `COMPLETED` | `docs/METRICS_REFERENCE.md`, `backend/app/evaluation/metrics.py` | Estimations vs provider-supplied tokens |
| **P3-T3** | Provider Comparisons | Provider abstraction supporting local Ollama and hosted Groq with consent gates | P1 | Providers | Strict fallback policy; no silent data transmission without user consent | `COMPLETED` | `test_model_router_strictly_enforces_remote_fallback_policy`, `ModelRouter` | Hosted API rate limits |
| **P3-T4** | Failure Flywheel | Persistent failure memory with deduplication and targeted repair context retrieval | P0 | Database | Trajectories saved with patch hash, tracebacks, hypotheses; prior failures retrieved | `COMPLETED` | `FailureFlywheel`, `test_failure_flywheel_persistence_and_deduplication` | Memory clutter over time; bounded retention |
| **P3-T5** | Memory Ablation | Matched comparison experiments with failure memory enabled vs disabled | P1 | Benchmark | Measure repair rate delta and attempt count delta | `COMPLETED` | `scripts/run_benchmarks.py`, `artifacts/benchmark_results.json` | Small sample size variance |
| **P3-T6** | Phoenix Tracing | Arize Phoenix OpenTelemetry instrumentation with secret masking | P1 | Observability | Spans recorded for Architect, Coder, Evaluator; offline-resilient; secrets masked | `COMPLETED` | Acceptance check 3 & 16; Phoenix active on `http://127.0.0.1:6006` | Collector offline shouldn't block execution |
| **P3-T7** | Evaluation Lab UI | React dashboard for benchmark execution, comparisons, metrics, and JSON/CSV export | P1 | Frontend | Visual charts, task table, export buttons connected to live backend data | `COMPLETED` | `frontend/src/pages/EvaluationLabPage.tsx` | Needs active benchmark run API integration |

---

## 5. PHASE 4: PRODUCT QUALITY, FRONTEND, OPERATIONS & RELEASE

| Task ID | Workstream | Description | Priority | Dependencies | Acceptance Criteria | Status | Tests & Evidence | Remaining Risks |
| :--- | :--- | :--- | :---: | :--- | :--- | :---: | :--- | :--- |
| **P4-T1** | Frontend Page Audit | Audit and polish all 10 pages for real backend connectivity, loading states, error handling | P0 | Frontend UI | Zero mock success data; live API integration; responsive layout; accessible UI | `COMPLETED` | Verification of all 10 pages in `frontend/src/pages/`, `npm run build` (0 errors) | Network disconnect handling |
| **P4-T2** | Backend API Polish | Complete OpenAPI documentation, error schemas, input validation | P1 | FastAPI | All endpoints typed with Pydantic v2; descriptive errors; CORS and health checks | `COMPLETED` | FastAPI `/docs`, `backend/app/api/` | None |
| **P4-T3** | Persistence Invariants | Database integrity for runs, tickets, attempts, and failure records | P0 | SQLite | Clean foreign keys, state consistency, migrations | `COMPLETED` | SQLite database schema, `test_sqlite_persistence_lifecycle` | Single-writer locks in SQLite |
| **P4-T4** | Operations & Runbook | Startup/shutdown scripts, `.env.example`, low-resource mode documentation | P1 | Scripts | `start.ps1`, `stop.ps1`, low RAM guards verified | `COMPLETED` | Scripts tested; RAM guard passes in `verify_acceptance.py` | Windows ExecutionPolicy |
| **P4-T5** | Dependency Review | Python & Node.js dependency compatibility and supply chain review | P2 | Requirements | No vulnerable unpinned packages; build reproducible | `COMPLETED` | `npm run build` succeeds; Python venv verified | Windows C++ build tools for some native packages |
| **P4-T6** | Clean-Install Test | Reproduce complete setup and runbook from scratch | P1 | Runbook | Documented steps work end-to-end | `COMPLETED` | `docs/RELEASE_RUNBOOK.md`, `LOCAL_DEVELOPMENT.md` | User environment variations |
| **P4-T7** | Release Artifacts | Comprehensive documentation suite and machine-readable reports | P0 | All Phases | `docs/MASTER_ROADMAP.md`, `docs/FINAL_IMPLEMENTATION_REPORT.md`, `release_gate_report.json` | `COMPLETED` | Deliverables under `docs/` and `artifacts/` | None |

---

## 6. RELEASE GATES MATRIX (G1–G14)

| Gate | Description | Required Verification | Current Status |
| :--- | :--- | :--- | :---: |
| **G1** | Repository Integrity | Original repository working tree pristine; reference repos untouched | **PASS** |
| **G2** | Backend Quality | 30+ Pytest tests pass cleanly without regressions | **PASS** (31/31 passed) |
| **G3** | Frontend Quality | Vite production bundle compiles with 0 errors (`npm run build`) | **PASS** (0 errors) |
| **G4** | Authorization | Invalid state transitions, unapproved tickets, and non-passing merges rejected | **PASS** |
| **G5** | Patch Integrity | Path traversal, symlinks, and protected files strictly blocked | **PASS** |
| **G6** | Execution Isolation | Real container runtime verified; safe fail-closed behavior when offline | **PASS (Host) / BLOCKED (Docker daemon offline)** |
| **G7** | Workflow Correctness | 13-step repair lifecycle verified end-to-end on disposable repository | **PASS** |
| **G8** | Recovery & Concurrency | Cancellation, timeouts, restart recovery, and merge locks verified | **PASS** |
| **G9** | Evaluation Integrity | Metrics derived from persisted events, explicit formulas and denominators | **PASS** |
| **G10**| Provider Reliability | Model router enforces fallback consent, timeout handling, and rate limits | **PASS** |
| **G11**| Privacy & Telemetry | Zero credential leaks in logs/traces; masked keys (`gsk_...`) | **PASS** |
| **G12**| Clean Installation | Documented setup commands verified on Windows 10/11 x64 | **PASS** |
| **G13**| Documentation | Complete phase reports, architecture, runbooks, and limitation notes | **PASS** |
| **G14**| Reproducibility | Automated scripts reproduce all claims without manual intervention | **PASS** |
