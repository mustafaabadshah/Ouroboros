# Project Ouroboros — Implementation Backlog
**Document Reference:** `docs/IMPLEMENTATION_BACKLOG.md`  
**Current Milestone:** Release Candidate `v0.9.0-rc1` to General Availability `v0.9.0`  
**Last Updated:** October 15, 2026  

---

## 1. Prioritization Schema

- **P0 (Critical / Mandatory)**: Security boundaries, workflow authorization, data integrity, deterministic evaluation, and release gates.
- **P1 (High)**: Observability, failure memory ablation, benchmark expansions, performance optimizations.
- **P2 (Medium / Nice-to-Have)**: UI polish, extended provider options, multi-tenant database migrations.

---

## 2. Phase 0 — Baseline & Codebase Audit

| Task ID | Priority | Description | Acceptance Criteria | Status | Evidence |
|---|:---:|---|---|:---:|---|
| **BKLG-001** | P0 | Reconcile Git history and remote status | Local `main` synchronized with `origin/main` without uncommitted loss | `COMPLETED` | Commit `9f0e95d` live on GitHub |
| **BKLG-002** | P0 | Document complete architectural audit | Map all backend routers, DB models, agents, sandboxes, UI pages | `COMPLETED` | `docs/CODEBASE_AUDIT.md` |
| **BKLG-003** | P0 | Establish baseline test and build results | Record 31 pytest tests, 20 acceptance checks, 0 build errors | `COMPLETED` | `artifacts/baseline/baseline_report.json` |

---

## 3. Phase 1 — Platform Foundation & Runtime Security

| Task ID | Priority | Description | Acceptance Criteria | Status | Evidence |
|---|:---:|---|---|:---:|---|
| **BKLG-101** | P0 | Fail-closed execution boundary | If Docker offline, untrusted code evaluation returns `BLOCKED` without host execution | `COMPLETED` | `backend/app/sandbox/security.py`, `test_adversarial_validation.py` |
| **BKLG-102** | P0 | Unified diff traversal & protected files | Reject `../`, symlinks, `.env`, and test modifications | `COMPLETED` | `UnifiedDiffParser.validate_patch_boundaries` |
| **BKLG-103** | P0 | Concurrent merge serialization | Serialize merges with `_merge_lock = asyncio.Lock()` | `COMPLETED` | `backend/app/api/runs.py` |
| **BKLG-104** | P0 | Startup orphan run reconciliation | Interrupted runs transitioned to `FAILED` with category `ORPHANED_RUN_INTERRUPTED` | `COMPLETED` | `backend/app/main.py` lifespan |
| **BKLG-105** | P0 | Subprocess process-tree termination | Windows `taskkill /F /T /PID` terminates spawned processes | `COMPLETED` | `run_safe_subprocess` in `backend/app/core/security.py` |
| **BKLG-106** | P1 | Sandbox detector timeout tuning | Detection timeout increased from 3s to 10s for Windows pipe initialization | `COMPLETED` | `backend/app/sandbox/detector.py` |

---

## 4. Phase 2 — Multi-Agent Repair Lifecycle & Product

| Task ID | Priority | Description | Acceptance Criteria | Status | Evidence |
|---|:---:|---|---|:---:|---|
| **BKLG-201** | P0 | Formal agent roles & contracts | Typed contracts for Architect, Planner, Coder, Critic, Judge, Repair | `COMPLETED` | `docs/AGENT_ARCHITECTURE.md` |
| **BKLG-202** | P0 | State machine enforcement | Valid transitions: `DISCOVERED` -> `DRAFT` -> `APPROVED` -> `IN_PROGRESS` -> `EVALUATING` -> `REVIEW_REQUIRED` -> `MERGE_APPROVED` -> `MERGED` | `COMPLETED` | `docs/WORKFLOW_STATE_MACHINE.md` |
| **BKLG-203** | P0 | Isolated Git worktrees | Dedicated `.git/worktrees/<ticket-id>` created for candidate code | `COMPLETED` | `GitWorktreeManager.create_worktree` |
| **BKLG-204** | P0 | Diff-hash binding on merge | Approval bound to exact candidate SHA-256 diff hash | `COMPLETED` | `test_candidate_drift_and_replay_rejected` |
| **BKLG-205** | P0 | 13-step workflow demonstrator | Deterministic demonstration executes 13 lifecycle steps | `COMPLETED` | `scripts/demonstrate_complete_workflow.py` |

---

## 5. Phase 3 — Evaluation Science, Memory & Observability

| Task ID | Priority | Description | Acceptance Criteria | Status | Evidence |
|---|:---:|---|---|:---:|---|
| **BKLG-301** | P0 | Metrics calculation engine | Compute honest repair rates, pass rates, latency, and costs from DB | `COMPLETED` | `backend/app/evaluation/metrics.py` |
| **BKLG-302** | P0 | Versioned benchmark suite | Standardized suite of tasks (`BENCH-01`, `BENCH-02`, `BENCH-03`) | `COMPLETED` | `backend/app/evaluation/benchmark.py` |
| **BKLG-303** | P1 | Failure memory ablation study | Matched runs with memory enabled vs disabled | `COMPLETED` | `artifacts/benchmark_results.json` |
| **BKLG-304** | P1 | Arize Phoenix tracing & secret masking | Trace spans recorded on port 6006 with API keys masked | `COMPLETED` | `docs/PHOENIX_OBSERVABILITY.md` |
| **BKLG-305** | P1 | Interactive Evaluation Lab UI | Benchmark execution, ablation toggle, honest metrics cards, JSON export | `COMPLETED` | `frontend/src/pages/EvaluationLabPage.tsx` |

---

## 6. Phase 4 — Product Quality, Documentation & Release

| Task ID | Priority | Description | Acceptance Criteria | Status | Evidence |
|---|:---:|---|---|:---:|---|
| **BKLG-401** | P0 | Frontend production build | Clean Vite compilation with 0 errors | `COMPLETED` | `npm run build` (1,935 modules) |
| **BKLG-402** | P0 | Operational automation scripts | Automated `start.ps1` and `stop.ps1` with PID tracking | `COMPLETED` | `scripts/start.ps1`, `scripts/stop.ps1` |
| **BKLG-403** | P0 | Release runbook & operational guide | Comprehensive operator documentation | `COMPLETED` | `docs/RELEASE_RUNBOOK.md` |
| **BKLG-404** | P0 | Documented limitations & security model | Document threat boundaries and known hardware constraints | `COMPLETED` | `docs/KNOWN_LIMITATIONS.md` |
| **BKLG-405** | P0 | Final implementation report | 15-section report covering all empirical outcomes | `COMPLETED` | `docs/FINAL_IMPLEMENTATION_REPORT.md` |
| **BKLG-406** | P0 | Update README and CHANGELOG | Reconcile test counts, documentation links, and changelog | `COMPLETED` | `README.md`, `CHANGELOG.md` |
| **BKLG-407** | P0 | Release gate audit report | Machine-readable release gate report covering G1–G14 | `COMPLETED` | `artifacts/release_gate_report.json` |
| **BKLG-408** | P1 | Live container isolation execution | Run live Linux container execution when Docker Desktop daemon online | `IN_PROGRESS` | Docker Desktop integration online |
