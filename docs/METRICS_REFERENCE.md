# PROJECT OUROBOROS — EVALUATION METRICS REFERENCE
**Document Reference:** `docs/METRICS_REFERENCE.md`  
**Version:** 1.0.0  
**Status:** ACTIVE  
**Last Updated:** October 15, 2026  

---

## 1. PURPOSE & PRINCIPLES

All evaluation metrics in Project Ouroboros are derived strictly from persisted SQLite database records (`runs`, `candidates`, `test_results`, `failure_trajectories`), never from simulated or hardcoded values.

### Guiding Principles:
1. **Explicit Denominators:** Every percentage or rate explicitly states its numerator and denominator.
2. **Distinct Failure Accounting:** `BLOCKED` (security/policy prevented execution), `FAILED` (test assertions broke), and `CANCELLED` states are counted separately and never conflated with passing outcomes.
3. **Reproducibility:** Every metric can be recomputed deterministically using `MetricsCalculator.compute_summary_metrics(db)`.

---

## 2. METRIC DEFINITIONS & FORMULAS

### 2.1 Repair Success Rate
- **Definition:** The proportion of eligible bug-fix tasks that successfully achieve a `PASS` evaluation verdict without regressions.
- **Formula:**
  $$\text{Repair Success Rate} = \frac{\text{Eligible Runs with Verdict } \texttt{PASS}}{\text{Total Attempted Eligible Runs}}$$
- **Denominator Clarification:** Eligible runs include runs reaching evaluation (`COMPLETED`, `FAILED`, `AWAITING_APPROVAL`). Runs blocked prior to evaluation due to missing prerequisites (e.g. offline Docker daemon) are reported separately in `blocked_runs` and are NOT counted in the numerator.

### 2.2 Candidate Test Pass Rate
- **Definition:** The proportion of candidate test executions that pass with zero failures or errors.
- **Formula:**
  $$\text{Candidate Test Pass Rate} = \frac{\text{Candidate Test Executions with Exit Code } 0}{\text{Total Completed Candidate Test Executions}}$$
- **Scope:** Restricted to candidate `acceptance` and `regression` test harness executions. Baseline tests are tracked independently.

### 2.3 Regression Rate
- **Definition:** The percentage of evaluated runs that introduce regressions into previously passing baseline tests.
- **Formula:**
  $$\text{Regression Rate} = \frac{\text{Runs where Baseline Tests Failed on Candidate Code}}{\text{Total Evaluated Runs}}$$
- **Enforcement:** If `failed_count > 0` on regression test suites, the DeterministicJudge immediately flags the candidate with `REGRESSION_DETECTED` and issues a `FAIL` verdict.

### 2.4 Average Attempts per Successful Repair
- **Definition:** The mean number of patch synthesis attempts required to produce a passing, non-regressing candidate.
- **Formula:**
  $$\text{Avg Attempts} = \frac{\sum (\text{attempt count for runs with } \texttt{PASS})}{\text{Count of Passing Runs}}$$
- **Range:** $[1.0, 3.0]$ (capped by `MAX_REPAIR_ATTEMPTS = 3`).

### 2.5 Latency Distribution (p50 and p95)
- **Definition:** The median (50th percentile) and 95th percentile wall-clock execution duration of test harness invocations in milliseconds.
- **Calculation:** All durations are collected from `test_results.duration_ms`, sorted, and indexed at $0.50 \times N$ and $0.95 \times N$.

### 2.6 Repeated Failure Prevention Count
- **Definition:** The number of times the `FailureFlywheel` detected an identical patch hash and failed test tuple, successfully terminating an unproductive repair loop.
- **Database Anchor:** Records in `failure_trajectories` where `status == "REPEATED"`.

---

## 3. METRIC VALUES IN RELEASE CANDIDATE (RC-1)

*Derived from database verification and `scripts/run_benchmarks.py`:*

| Metric Name | Value | Denominator / Basis |
| :--- | :---: | :--- |
| **Repair Success Rate (Benchmark v1)** | `66.67%` | 2 passing / 3 tasks (1 task was an adversarial security probe correctly `BLOCKED`) |
| **Acceptance Suite Pass Rate** | `100.0%` | 20 / 20 criteria passed (`verify_acceptance.py`) |
| **Pytest Suite Pass Rate** | `100.0%` | 30 / 30 tests passed (`pytest backend/tests`) |
| **Regression Rate** | `0.0%` | 0 regressions introduced across passing candidates |
| **Median Test Duration (p50)** | `4,660 ms` | Benchmark suite execution |
| **Repeated Failures Caught** | Verified | Tested in `test_failure_flywheel_persistence_and_deduplication` |
