# Changelog

All notable changes to Project Ouroboros will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

---

## [0.9.0-rc1] - 2026-10-15

### Added
- **Evaluation Science & Benchmark Suite (Phase 3)**:
  - Added `backend/app/evaluation/benchmark.py` (`BenchmarkHarness`) with versioned benchmark tasks (`BENCH-01`, `BENCH-02`, and adversarial security probe `BENCH-03`).
  - Added `backend/app/evaluation/metrics.py` (`MetricsCalculator`) computing honest repair success rates, candidate test pass rates, regression rates, attempt distributions, and median/P95 latencies with explicit formulas and denominators.
  - Added evaluation REST endpoints (`GET /api/evaluation/metrics`, `GET /api/evaluation/benchmark/tasks`, `POST /api/evaluation/benchmark/run`, `GET /api/evaluation/benchmark/export`) mounted in `backend/app/main.py`.
  - Added interactive Evaluation Lab in React dashboard (`frontend/src/pages/EvaluationLabPage.tsx`) supporting real-time benchmark execution, memory ablation toggles, and JSON export.
- **Runtime Security & Adversarial Hardening (Phase 1)**:
  - Universal fail-closed container execution boundary in `backend/app/sandbox/security.py` and `backend/app/sandbox/detector.py`.
  - Detection and reporting of container isolation capabilities (daemon status, isolation features, non-root user, memory limits).
  - Extended adversarial test suite (`backend/tests/unit/test_adversarial_validation.py`) covering path traversal (`SEC-01`), symlink escapes (`SEC-02`), test file tampering (`SEC-03`), protected file blocks (`SEC-04`), merge authorization bypasses (`WRK-01`), and replay attacks (`WRK-02`).
  - Concurrent merge serialization lock (`_merge_lock = asyncio.Lock()`) in `backend/app/api/runs.py`.
  - Duplicate run prevention returning `HTTP 409 Conflict`.
- **Closed-Loop Repair Lifecycle (Phase 2)**:
  - 13-step software repair lifecycle demonstrator (`scripts/demonstrate_complete_workflow.py`).
  - Failure memory integration (`FailureFlywheel`) storing structured tracebacks, AST diffs, and repair actions.
  - Agent roles specification (`docs/AGENT_ARCHITECTURE.md`) covering Architect, Planner, Coder, Critic, Judge, and Repair Agent.
- **Operational Automation & Reliability (Phase 4)**:
  - Startup reconciliation in `backend/app/main.py` transitioning orphaned runs to `FAILED` with category `ORPHANED_RUN_INTERRUPTED`.
  - Process-tree termination scripts (`scripts/start.ps1`, `scripts/stop.ps1`) managing Uvicorn, Vite, and Phoenix via `.ouroboros_pids.json`.
  - Standalone benchmark runner (`scripts/run_benchmarks.py`) generating `artifacts/benchmark_results.json`.
  - Automated release-gate auditing script and report (`artifacts/release_gate_report.json`).

### Changed
- Refactored `UnifiedDiffParser` to strictly validate old and new file paths against allowed scopes and reject traversals.
- Upgraded `frontend/src/services/api.ts` with typed evaluation API methods (`getMetrics`, `getBenchmarkTasks`, `runBenchmark`, `exportBenchmark`).
- Configured SQLite connection pool with `StaticPool` and WAL mode for reliable test transactions and zero database locks.

### Fixed
- Fixed race condition where concurrent merge requests could create conflicting Git merges on the same candidate worktree.
- Fixed vulnerability where untrusted candidate code could execute on the host if Docker was offline; now universally fails closed with structured `BLOCKED` status.
- Fixed startup hang when previous runs were interrupted mid-evaluation without proper database status cleanup.

### Security
- Gated candidate code execution exclusively to verified container sandboxes.
- Implemented automatic redaction for credentials, API tokens, and authorization headers in all logs and Phoenix traces.
- Enforced strict diff-hash binding on merge approvals to prevent patch alteration between evaluation and merge.

---

## [0.8.0] - 2026-10-14
### Added
- Initial multi-agent orchestration architecture using AutoGen.
- Git worktree manager for isolated candidate branches.
- Deterministic Judge enforcing zero-regression pytest gates.
- React 19 dashboard with overview, tickets, runs, and unified diff viewer.
- Ollama local model provider (`qwen2.5-coder:1.5b`) and Groq API integration.
- Meta-Graph Codebase Navigator AST graph ingestion.
