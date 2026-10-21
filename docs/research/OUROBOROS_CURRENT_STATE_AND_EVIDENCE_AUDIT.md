# Project Ouroboros: Current-State & Evidence Audit
**Generated:** 2026-10-18  
**Scope:** Repository architecture, Git milestones, machine-readable artifacts inventory, evaluation history, and verified boundaries.

---

## 1. Executive Summary & Working Baseline

Project Ouroboros is a hierarchical, SWE-Bench-style autonomous software evolution and repair platform. It ingests technical debt or bug reports, builds an AST-based dependency graph, formulates a bounded repair plan, generates candidate patches via an LLM agent, applies patches in an isolated Git worktree, runs deterministic unit and regression tests, judges candidate repairs with a deterministic evaluator, logs telemetry to Phoenix, updates a failure flywheel/memory store, and surfaces metrics via FastAPI and React.

### Environment & Hardware Constraints
- **Operating System:** Windows 10 Home (10.0.19045 x64)
- **Host Hardware:** Intel Core i3-7100U @ 2.40GHz (2 cores / 4 threads), Intel HD Graphics 620, 7.88 GB RAM total (approx. 2.5 GB free).
- **Execution Policy:** No dedicated GPU; strictly CPU-bound. Subprocess concurrency is bounded to `MAX_CONCURRENT_TESTS = 1`. All host bindings use loopback `127.0.0.1`.
- **Python Runtime:** Python 3.12.3 in virtual environment `.venv\Scripts\python.exe`.
- **Node Runtime:** v24.14.1 with npm 11.1.0.

### Git State & Remote Tracking
- **Repository:** `mustafaabadshah/Ouroboros`
- **Active Working Branch:** `hotfix/python-package-discovery`
- **Local HEAD:** `dd36b27` (`fix(test): correct fixture index path calculation in MetaGraphAdapter`)
- **Remote Tracking Reference:** `origin/main` at `19edf71` (Merge pull request #1 from mustafaabadshah/fix/python-package-discovery).
- **Preservation Status:** All 21 historical evaluation and benchmark JSON/Markdown artifacts remain completely preserved. No destructive Git resets or cleans performed.

---

## 2. Repository Component & File Map

| Subsystem | Source Path | Primary Responsibility |
| :--- | :--- | :--- |
| **Agent Orchestrator** | `backend/app/orchestration/` | Workflow coordinator, ticket-to-task decomposition, state transitions. |
| **AST & Dependency Graph** | `backend/app/integrations/graph/adapter.py` | AST extraction, meta-graph construction, blast-radius calculation. |
| **Git Worktree Isolation** | `backend/app/integrations/git/worktree.py` | Atomic temporary worktree creation, patch application, dirty-state cleanup. |
| **Sandbox Execution** | `backend/app/sandbox/detector.py`, `executor.py` | Container runtime detection (Docker/host), capability probing, fallback execution. |
| **Test Runner** | `backend/app/test_runner/pytest_runner.py` | Deterministic pytest subprocess execution with timeout and output capture. |
| **Deterministic Judge** | `backend/app/evaluation/judge.py` | Strict acceptance evaluation: syntax, unit pass, zero regression, safety gates. |
| **Evaluation Harness** | `backend/app/evaluation/benchmark.py`, `runner.py` | 16-task benchmark execution, batch evaluation sweeps, state logging. |
| **Evaluation Metrics** | `backend/app/evaluation/metrics.py` | Wilson score intervals, task success rates, regression rates, attempt counting. |
| **Failure Flywheel** | `backend/app/memory/` | Short-term error capture and cross-attempt retrieval to prevent repeating errors. |
| **Database Persistence** | `backend/app/database/models.py`, `session.py` | SQLite/SQLAlchemy schema for runs, tasks, attempts, test results, and metrics. |
| **Phoenix Telemetry** | `backend/app/observability/phoenix_service.py` | OpenTelemetry span creation and trace export to Arize Phoenix. |
| **FastAPI Backend** | `backend/app/main.py`, `api/` | REST API endpoints for runs, tasks, health, and benchmark triggers. |
| **React Dashboard** | `frontend/src/` | React 19 + TypeScript + Vite user interface for run monitoring and telemetry. |
| **Benchmark Suites** | `backend/tests/fixtures/benchmarks/` | 16 benchmark definitions (`BENCH-01` to `BENCH-16`). |

---

## 3. Machine-Readable Evaluation Artifacts Inventory

A complete audit of all machine-readable JSON evaluation outputs discovered in `artifacts/`:

| Artifact Path | Date/Timestamp | Scope / Benchmark Condition | Key Metrics Recorded |
| :--- | :--- | :--- | :--- |
| `artifacts/benchmark_results.json` | 2026-10-17 | Baseline benchmark execution (`BENCH-04`) | Success: 100%, Duration: 18.2s |
| `artifacts/post_rc1_release_report.json` | 2026-10-17 | Full Post-RC1 regression test suite report | 23/23 tests passed, 20/20 acceptance checks |
| `artifacts/v0_11/baseline_audit.json` | 2026-10-17 | Pre-v0.11 baseline checkpoint | Reference run metrics across benchmark tasks |
| `artifacts/v0_11/eval_checkpoint_trial_1.json` | 2026-10-17 | Trial 1 benchmark evaluation run | Deterministic task pass/fail status |
| `artifacts/v0_11/eval_checkpoint_trial_2.json` | 2026-10-17 | Trial 2 benchmark evaluation run | Consistency across repeated runs |
| `artifacts/v0_11/eval_checkpoint_trial_3.json` | 2026-10-17 | Trial 3 benchmark evaluation run | Variance and stability metrics |
| `artifacts/v0_11/memory_ablation.json` | 2026-10-17 | Memory Enabled vs Disabled ablation | Comparative success rate & token usage |
| `artifacts/v0_11/repeated_evaluation.json` | 2026-10-17 | 3-trial aggregated stability evaluation | Flakiness score: 0.0 |
| `artifacts/agent_eval_ablation_consolidated.json` | 2026-10-17 | Consolidated agent evaluation metrics | Benchmark pass rates by task category |
| `artifacts/agent_eval_adversarial_bench03.json` | 2026-10-17 | Adversarial task `BENCH-03` evaluation | Fail-closed security validation (denial) |
| `artifacts/agent_eval_memory_disabled_sweep.json`| 2026-10-17 | 15-task sweep with failure memory OFF | Baseline repair success without memory |
| `artifacts/agent_eval_memory_enabled_sweep.json` | 2026-10-17 | 15-task sweep with failure memory ON | Comparative repair success with memory |
| `artifacts/agent_eval_p2c_sweep.json` | 2026-10-17 | Priority 2C 16-task agent evaluation sweep | Task-level breakdown across all 5 categories |
| `artifacts/agent_evaluation_results.json` | 2026-10-17 | General agent evaluation output | Primary run results |
| `artifacts/smoke_test_bench04.json` | 2026-10-17 | Smoke test on single task `BENCH-04` | Fast pipeline validation (18.1s) |
| `artifacts/evaluations/20261017_191839_ref_benchmark/benchmark_run.json` | 2026-10-18 | Immutable verified run on task `BENCH-04` | 100% pass, commit `dd36b27`, Python 3.12.3 |

---

## 4. Confirmed Inconsistencies & Corrected Defects

### 4.1 Evaluation Correctness: Regression Rate Denominator Deflation
- **Observed Problem:** In `backend/app/evaluation/metrics.py`, `MetricsCalculator.compute_summary_metrics` computed `regression_rate = runs_with_regression / total_runs`.
- **Defect Impact:** In evaluation runs with aborted, skipped, or syntax-blocked runs (which terminate before running regression tests), `total_runs` artificially inflated the denominator, resulting in an falsely low reported regression rate.
- **Resolution:** Updated denominator to `evaluated_runs_for_regression` (runs that actually completed regression test evaluation). Edge case of zero evaluated regression runs returns `0.0` with explicit documentation and metadata field.

### 4.2 Benchmark Repair Success Rate Zero-Denominator Representation
- **Observed Problem:** In `backend/app/evaluation/benchmark.py`, line 1579 returned `0.0` for `repair_success_rate` when `eligible_tasks == 0`, whereas `eligible_repair_success_rate` returned `None`.
- **Defect Impact:** A suite run with 0 eligible tasks reported a deceptive "0.0% success rate" instead of a mathematically truthful `None` (undefined).
- **Resolution:** Aligned `repair_success_rate` to return `None` when `eligible_tasks == 0`.

### 4.3 Windows Docker Named-Pipe Timeout Latency
- **Observed Problem:** `docker info` on Windows with stopped Docker Desktop blocked on named pipe `\\.\pipe\docker_engine` for ~5.5s per probe. Calling `SandboxDetector.detect_capabilities()` repeatedly added dozens of seconds of dead latency to benchmark and evaluation sweeps.
- **Defect Impact:** 16-task sweeps suffered over 85 seconds of cumulative idle timeout stalls.
- **Resolution:** Added 30-second TTL memoization cache (`_cache`, `_cache_time`, `reset_cache()`, `force_refresh=True`) and reduced subprocess timeout from 10s to 5s. Subsequent checks complete in 0.001s.

### 4.4 Phoenix OpenTelemetry Process Shutdown Hang
- **Observed Problem:** When Arize Phoenix (`http://127.0.0.1:6006`) is offline, OpenTelemetry's background `BatchSpanProcessor` thread stalled process exit for 20–30s attempting HTTP export retries.
- **Defect Impact:** Unit test suites and benchmark scripts appeared hung at completion on developer machines without active Phoenix containers.
- **Resolution:** Added a fast 0.3s socket reachability probe `_is_collector_reachable(host, port)` in `backend/app/observability/phoenix_service.py` before initializing the HTTP trace exporter. If Phoenix is unreachable, telemetry gracefully uses an in-memory buffer without blocking process termination.

### 4.5 Subprocess Runner Timeout on Host Hardware
- **Observed Problem:** In `backend/tests/fixtures/test_e2e_fixture.py`, `PytestRunner(default_timeout=20)` timed out because pytest invocation, dependency loading (`anyio`, `phoenix`), and collection on dual-core CPU with 8 GB RAM requires 22–28 seconds.
- **Resolution:** Adjusted default timeout to 45 seconds in the fixture runner.

---

## 5. Scope & Task Count Reconciliation

A critical question was whether benchmark definitions and task counts differ between 15 and 16 tasks:
1. **The Definitive Suite:** `BenchmarkHarness` in `backend/app/evaluation/benchmark.py` defines exactly **16 tasks**: `BENCH-01` through `BENCH-16`.
2. **Task Categorization:**
   - Syntax & Type Errors: `BENCH-01`, `BENCH-02`, `BENCH-06`
   - Logic & Boundary Conditions: `BENCH-04`, `BENCH-05`, `BENCH-07`, `BENCH-08`
   - Path Traversal & Security (Adversarial): `BENCH-03`
   - Multi-file Dependencies: `BENCH-09`, `BENCH-10`, `BENCH-11`, `BENCH-12`
   - Performance & Algorithmic: `BENCH-13`, `BENCH-14`, `BENCH-15`, `BENCH-16`
3. **The 15 vs 16 Reconciliation:**
   - `BENCH-03` is an **adversarial security task** designed to inject malicious path traversal. The system *must* reject this patch.
   - In historical documentation and selective sweeps, `BENCH-03` was excluded from repair success calculations to yield 15 "positive repair" tasks.
   - In full pipeline evaluations (e.g., Priority 2C), all 16 tasks are evaluated. The harness now explicitly reports both:
     - `repair_success_rate`: Positive repair rate across standard eligible tasks.
     - `adversarial_rejection_rate`: Strict rejection rate on adversarial tasks.

---

## 6. Execution Order & Verified Safe Boundaries

1. **Deterministic Unit Tests:** Always run without network, Docker, or paid API dependencies.
2. **Benchmark Execution:** Uses isolated Git worktrees and ephemeral directory trees in `.ouroboros_test_repos/`.
3. **Immutable Output Protocol:** Every evaluation run writes to `artifacts/evaluations/<timestamp>_<suite>/` containing full provenance (commit hash, Python version, platform, task results).
