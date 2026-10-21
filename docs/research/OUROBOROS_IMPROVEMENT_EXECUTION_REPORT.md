# Project Ouroboros: Improvement Execution Report
**Date:** 2026-10-18  
**Author:** Lead Architecture & MLOps Engineer  
**Scope:** Engineering upgrades, bug fixes, observability hardening, immutable evaluation provenance, and baseline benchmark verification.

---

## 1. Implemented Improvements & Rationale

| # | Improvement | Files Modified | Why It Was Needed |
| :--- | :--- | :--- | :--- |
| **1** | **Sandbox Capability Memoization** | `backend/app/sandbox/detector.py` | On Windows, probing Docker Desktop when stopped blocks for ~5.5s on the named pipe `\\.\pipe\docker_engine`. Repeated checks during a 16-task sweep added over 80 seconds of idle latency. Added a 30s TTL cache so subsequent checks take <0.001s. |
| **2** | **Evaluation Metrics Denominator Fix** | `backend/app/evaluation/metrics.py` | `regression_rate` previously used `total_runs` as denominator, deflating regression rates when runs were cancelled or blocked before regression tests ran. Changed denominator to `evaluated_runs_for_regression`. Fixed `avg_attempts_per_successful_repair` to return `0.0` (not `1.0`) when passing runs count is zero. |
| **3** | **Zero-Eligible Task Truthful Metric** | `backend/app/evaluation/benchmark.py` | Line 1579 returned `0.0` for `repair_success_rate` when `eligible_tasks == 0`, conflicting with `eligible_repair_success_rate` which returned `None`. Now both return `None` to prevent misleading 0% claims when no tasks were evaluated. |
| **4** | **Subprocess Runner Hardware Resilience** | `backend/tests/fixtures/test_e2e_fixture.py` | The test fixture had a hardcoded 20s timeout in `PytestRunner`. On an Intel Core i3 with 8 GB RAM, pytest bootstrap, plugin registration, and test collection require 22–28s. Increased timeout to 45s. |
| **5** | **Fast Phoenix Socket Reachability Probe** | `backend/app/observability/phoenix_service.py` | When Arize Phoenix is not running locally, OpenTelemetry's `BatchSpanProcessor` thread stalled process exit for 20–30s on retry loops. Added a fast 0.3s socket probe before initializing the HTTP exporter, preventing hangs on developer environments. |
| **6** | **Immutable Evaluation Provenance** | `scripts/run_benchmarks.py`, `scripts/run_agent_eval.py` | Evaluation runs previously wrote to static paths (`artifacts/benchmark_results.json`), risking overwriting historical evidence. Added automatic timestamped archival to `artifacts/evaluations/<timestamp>_<suite>/` containing Git commit hash, Python version, platform, and full task results, while preserving static paths for CI backward compatibility. |
| **7** | **Evaluation Correctness Test Suite** | `backend/tests/unit/test_evaluation_correctness.py` | Built a dedicated 5-test suite validating caching, regression denominator calculation, zero-passing defaults, zero-eligible `None` return, and Wilson score interval boundary conditions. |

---

## 2. Before vs After Performance & Correctness Comparison

| Subsystem / Metric | Historical / Before | Post-Upgrade / After | Verification Evidence |
| :--- | :--- | :--- | :--- |
| **Sandbox Detection Latency (Docker Stopped)** | ~5.5 seconds per task check | 0.001 seconds (after initial probe) | `test_sandbox_detector_caching` PASSED |
| **Evaluation Regression Rate Calculation** | Deflated by `total_runs` including un-evaluated runs | Strictly divided by `evaluated_runs_for_regression` | `test_metrics_calculator_evaluated_runs_denominator` PASSED |
| **Zero Passing Runs Average Attempts** | Defaulted deceptively to `1.0` | Accurately returns `0.0` | `test_metrics_calculator_zero_passing_runs_defaults` PASSED |
| **Zero Eligible Tasks Repair Rate** | Returned `0.0` (misleading 0% claim) | Returns `None` (mathematically undefined) | `test_suite_zero_eligible_denominator_returns_none` PASSED |
| **Process Exit Time (Phoenix Offline)** | 20–30s OpenTelemetry thread block | Immediate exit (<0.05s) | Fast socket probe active in `_init_tracer()` |
| **Deterministic E2E Test Fixture** | Timed out at 20s on dual-core host | 100% PASS with 45s timeout | `test_deterministic_e2e_fixture_repair_lifecycle` PASSED |
| **Evaluation Run Storage** | Static overwritable file | Dual storage: static file + immutable timestamped folder | `artifacts/evaluations/20261017_191839_ref_benchmark/` created |

---

## 3. Controlled Benchmark Run Details

To validate the end-to-end pipeline under real execution conditions without requiring paid APIs or remote models, a reference benchmark was executed:

- **Command:** `.venv\Scripts\python scripts/run_benchmarks.py --task-id BENCH-04 --memory-enabled`
- **Benchmark Task:** `BENCH-04` (Off-by-one logic defect in binary search)
- **Git Commit Fingerprint:** `dd36b27`
- **Python Version:** 3.12.3 (win32)
- **Isolated Worktree:** Clean ephemeral worktree created in `.ouroboros_test_repos/`
- **Outcome:** ACCEPTED
- **Task Duration:** 18.23 seconds
- **Unit Tests:** Passed
- **Regression Tests:** Passed (zero regressions)
- **Security Check:** Passed
- **Immutable Run Artifact:** `artifacts/evaluations/20261017_191839_ref_benchmark/benchmark_run.json`

---

## 4. Test Verification Summary

The changes were validated across multiple test suites:

```powershell
.venv\Scripts\python -m pytest backend/tests/unit/test_evaluation_correctness.py -v
```
**Result:** 5 passed in 2.52s.

```powershell
.venv\Scripts\python -m pytest backend/tests/fixtures/test_e2e_fixture.py -v
```
**Result:** 1 passed in 24.89s (full end-to-end fixture lifecycle).

---

## 5. Remaining Limitations & Recommended Next Steps

1. **Docker Sandbox Execution:** On Windows developer workstations where Docker Desktop is not actively running, execution safely falls back to host execution. For untrusted public repositories, a running Docker daemon is mandatory for complete boundary isolation.
2. **Arize Phoenix Integration:** When Phoenix (`http://127.0.0.1:6006`) is offline, telemetry traces are stored in an in-memory buffer. When Phoenix is launched via Docker or local uvicorn, full span streaming to the Phoenix UI is automatically enabled.
3. **External Model APIs:** Baseline deterministic evaluations run entirely locally with zero cost. When live model evaluation is triggered (e.g., Groq Llama-3.3-70b), `GROQ_API_KEY` must be provisioned in `.env`.
4. **Recommended Next Step:** Launch Arize Phoenix (`docker compose up phoenix` or `phoenix.server.main`) and execute a paired 16-task memory ablation sweep (`scripts/run_benchmarks.py --memory-enabled` vs `--memory-disabled`) into the new `artifacts/evaluations/` directory to record comparative telemetry and Wilson score confidence intervals.
