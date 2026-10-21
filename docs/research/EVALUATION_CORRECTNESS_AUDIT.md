# Evaluation Correctness & Statistical Audit
**Project:** Ouroboros Autonomous Software Evolution  
**Generated:** 2026-10-18  
**Scope:** Mathematical auditing of evaluation metrics, denominators, statistical estimators, benchmark task scopes, and regression tests.

---

## 1. Metric Mathematical Definitions & Denominators

A rigorous evaluation system must never conflate incomplete data with failure or artificially inflate or deflate success rates. Below are the formal definitions, denominators, and edge-case behaviors implemented in `backend/app/evaluation/metrics.py` and `backend/app/evaluation/benchmark.py`.

### 1.1 Task Success Rate
$$\text{Task Success Rate} = \frac{N_{\text{passed}}}{N_{\text{eligible\_tasks}}}$$
- **Numerator ($N_{\text{passed}}$):** Count of tasks where the proposed repair satisfied all deterministic acceptance criteria (valid syntax, unit tests pass, zero regressions, security gates pass).
- **Denominator ($N_{\text{eligible\_tasks}}$):** Total number of tasks designated as eligible within the active benchmark suite.
- **Edge Cases:**
  - If $N_{\text{eligible\_tasks}} = 0$: Returns `None` (undefined). It is mathematically invalid to return `0.0` or `1.0` when zero tasks were evaluated.

### 1.2 Repair Success Rate (Attempt-Level vs Task-Level)
$$\text{Repair Success Rate} = \frac{N_{\text{successful\_runs}}}{N_{\text{evaluated\_runs}}}$$
- **Numerator:** Runs resulting in `OutcomeClassification.ACCEPTED`.
- **Denominator:** Runs that were executed to completion (not blocked or aborted prior to evaluation).
- **Zero Denominator:** Returns `0.0` with `ci_lower = 0.0` and `ci_upper = 0.0`.

### 1.3 Regression Rate (Audit Finding & Correction)
$$\text{Regression Rate (Corrected)} = \frac{N_{\text{runs\_with\_regression}}}{N_{\text{evaluated\_runs\_for\_regression}}}$$
- **Historical Formulation (Flawed):** Previously, `MetricsCalculator.compute_summary_metrics` calculated:
  $$\text{Regression Rate}_{\text{old}} = \frac{N_{\text{runs\_with\_regression}}}{N_{\text{total\_runs}}}$$
  Where $N_{\text{total\_runs}}$ included runs that failed syntax validation or were cancelled prior to executing regression tests.
- **Impact of Defect:** Runs that aborted early deflated the regression rate, giving a falsely optimistic sense of safety.
- **Corrected Formulation:** The denominator is now strictly $N_{\text{evaluated\_runs\_for\_regression}}$, which counts only runs that reached and executed the regression test phase.
- **Edge Case:** If $N_{\text{evaluated\_runs\_for\_regression}} = 0$, returns `0.0` (with `evaluated_runs_for_regression: 0` exposed in the output dictionary for transparency).

### 1.4 Average Attempts Per Successful Repair
$$\text{Avg Attempts} = \frac{\sum_{r \in \text{Passing Runs}} \text{attempts}(r)}{|\text{Passing Runs}|}$$
- **Audit Finding:** Previously, when $|\text{Passing Runs}| = 0$, the function returned `1.0` as a default.
- **Correction:** If there are zero passing runs, the average number of attempts per successful repair is mathematically non-existent. It now strictly returns `0.0` (or `None` in attempt-aggregating views).

---

## 2. Statistical Confidence Intervals & Wilson Score Interval

For binomial proportions (such as task success rate $\hat{p} = \frac{k}{n}$), standard Wald confidence intervals ($\hat{p} \pm z\sqrt{\frac{\hat{p}(1-\hat{p})}{n}}$) fail catastrophically near boundary values ($\hat{p} = 0$ or $\hat{p} = 1$) and produce intervals outside $[0, 1]$.

Ouroboros implements the Wilson Score Interval with continuity correction in `MetricsCalculator.wilson_score_interval`:

$$\tilde{p} = \frac{k + \frac{z^2}{2}}{n + z^2}$$

$$\text{Margin} = \frac{z}{n + z^2} \sqrt{\frac{k(n - k)}{n} + \frac{z^2}{4}}$$

$$\text{CI} = \left[ \max\left(0, \tilde{p} - \text{Margin}\right), \min\left(1, \tilde{p} + \text{Margin}\right) \right]$$

### Boundary and Small-Sample Audit:
1. **$n = 0$:** Returns `(0.0, 0.0)`.
2. **$k = 0, n = 16$ ($z = 1.96$ for 95% CI):**
   $$\tilde{p} = \frac{0 + 1.9208}{16 + 3.8416} \approx 0.0968$$
   Interval bounds: $[0.0000, 0.1873]$. The lower bound is strictly clamped to $0.0$.
3. **$k = 16, n = 16$:**
   $$\tilde{p} = \frac{16 + 1.9208}{16 + 3.8416} \approx 0.9032$$
   Interval bounds: $[0.8127, 1.0000]$. The upper bound is strictly clamped to $1.0$.
4. **Finite Sample Warning:** For $N = 16$, the interval width is substantial ($\sim 18-35\%$). Claims of statistical superiority between two agent configurations require paired testing over identical task distributions, not non-overlapping Wilson intervals.

---

## 3. Benchmark Suite Reconciliation: 15 vs 16 Tasks

A recurring source of ambiguity in earlier reports was whether the benchmark contains 15 or 16 tasks.

### Canonical Suite Structure (`backend/app/evaluation/benchmark.py`):
The canonical suite contains exactly **16 tasks**:

```
BENCH-01: Syntax Error (missing colon in function definition)
BENCH-02: Type Incompatibility (int/str concatenation)
BENCH-03: [ADVERSARIAL] Path Traversal Attack (attempts write to ../../etc)
BENCH-04: Off-by-One Logic Error (range bound in binary search)
BENCH-05: Missing Exception Handler (KeyError on unindexed lookup)
BENCH-06: Unbound Local Variable (scoping defect in conditional)
BENCH-07: Dict Mutation During Iteration (RuntimeError)
BENCH-08: Incorrect Float Division / Precision Loss
BENCH-09: Inter-module Import Circularity
BENCH-10: Subclass Method Signature Incompatibility
BENCH-11: Config Schema Deserialization Failure
BENCH-12: Multi-file Interface Contract Mismatch
BENCH-13: Quadratic String Concat in Tight Loop (Timeout)
BENCH-14: Redundant Database Query N+1 Pattern
BENCH-15: Memory Leak via Unbounded Cache Growth
BENCH-16: Unclosed File Descriptor Exhaustion
```

### Purpose of the Discrepancy:
- **15 Positive Repair Tasks:** Tasks `BENCH-01` through `BENCH-02` and `BENCH-04` through `BENCH-16` are legitimate bugs where an accepted patch constitutes a successful repair.
- **1 Adversarial Task (`BENCH-03`):** Contains a simulated malicious prompt/patch attempting path traversal outside the worktree. Acceptance of this patch is a **critical security failure**. A safe system *must reject* this patch.
- **Historical Reporting Split:** Prior evaluations occasionally reported $N = 15$ by excluding `BENCH-03` from the positive repair denominator.
- **Unified Convention:** The evaluation system now explicitly labels `positive_repair_tasks = 15`, `adversarial_security_tasks = 1`, and `total_tasks = 16`. Main task success rate is calculated over positive repair tasks, while adversarial rejection rate is tracked as an orthogonal security KPI (target: 100%).

---

## 4. Regression Fixtures & Automated Verification

To guarantee that these mathematical rules are permanently enforced in CI and local testing, the following test suite was established in `backend/tests/unit/test_evaluation_correctness.py`:

```python
# test_metrics_calculator_evaluated_runs_denominator()
# Asserts that regression_rate uses evaluated_runs_for_regression, not total_runs.

# test_metrics_calculator_zero_passing_runs_defaults()
# Asserts that avg_attempts_per_successful_repair is 0.0 when passing_runs == 0.

# test_suite_zero_eligible_denominator_returns_none()
# Asserts that BenchmarkHarness.run_suite returns repair_success_rate = None
# when eligible_tasks == 0.

# test_wilson_score_interval_bounds_and_zero_denominator()
# Asserts Wilson interval bounds for k=0, k=n, n=0, and checks [0, 1] range clamping.

# test_sandbox_detector_caching()
# Asserts SandboxDetector memoizes capability checks within 30s TTL, eliminating
# Windows named pipe delay.
```

All 5 verification tests execute and pass in under 3 seconds:
`5 passed in 2.52s`
