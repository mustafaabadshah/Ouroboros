# Memory Ablation Experimental Protocol
**Project:** Ouroboros Autonomous Software Evolution  
**Document Version:** 2.0.0 (Phase 3 Verified)  
**Updated:** 2026-10-18  
**Scope:** Controlled, reproducible experimental comparison of Memory-Enabled vs. Memory-Disabled (Naive Retry) repair conditions across versioned benchmark suite v1.0.0.

---

## 1. Experimental Objective & Hypotheses

The objective of this controlled ablation is to evaluate whether the **FailureFlywheel** memory subsystem improves repair success, reduces attempts, and prevents semantic failure repetition without increasing regression risk or latency.

- **Primary Hypothesis ($H_1$):** Memory-assisted retry (`flywheel_escalation`) achieves equal or higher repair success rate compared to naive retry (`naive_retry`) on eligible repair tasks when intermediate attempts fail.
- **Secondary Hypothesis ($H_2$):** Injecting structured failure diagnostics (failure signature, assertion diffs, root cause hints) eliminates repeated identical failure signatures within the fixed attempt budget ($k \le 3$).
- **Null Hypothesis ($H_0$):** There is no measurable difference in repair success between conditions under equivalent execution budgets.

---

## 2. Canonical Benchmark Suite Definition (v1.0.0)

The evaluation operates on canonical suite `BENCHMARK_TASKS_V1` defined in [`backend/app/evaluation/benchmark.py`](file:///E:/MM%20Office/Ouroboros/backend/app/evaluation/benchmark.py):

| Task ID | Canonical Task Name | Category | Difficulty | Target File | Classification |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **BENCH-01** | Input Validation Boundary Guard | `boundary_and_edge_case` | small | `utils/input_parser.py` | Positive Repair |
| **BENCH-04** | Numeric Boundary Clamping | `boundary_and_edge_case` | small | `math_utils/bounds.py` | Positive Repair |
| **BENCH-05** | Pagination Window Slice Calculator | `boundary_and_edge_case` | small | `pagination/paginator.py` | Positive Repair |
| **BENCH-06** | Nested Dictionary Key Traversal | `type_and_interface` | small | `utils/dict_traversal.py` | Positive Repair |
| **BENCH-07** | Configuration Value Coercer | `type_and_interface` | small | `config/coercer.py` | Positive Repair |
| **BENCH-08** | Event Dispatcher Signature Adapter | `type_and_interface` | medium | `events/dispatcher.py` | Positive Repair |
| **BENCH-09** | Cross-Module Entity Loader | `multi_file_and_state` | medium | `services/loader.py` | Positive Repair |
| **BENCH-10** | Workflow State Machine Transitions | `multi_file_and_state` | medium | `workflow/state_machine.py` | Positive Repair |
| **BENCH-11** | Token Bucket Rate Limiter Shared State | `multi_file_and_state` | medium | `rate_limiter/bucket.py` | Positive Repair |
| **BENCH-12** | ISO Timestamp Normalizer | `serialization_and_parsing` | medium | `datetime_utils/iso_parser.py` | Positive Repair |
| **BENCH-13** | JSON Config Parser and Fallback | `serialization_and_parsing` | small | `json_parser/safe_loader.py` | Positive Repair |
| **BENCH-14** | SemVer Tag Regex Extractor | `serialization_and_parsing` | medium | `semver/parser.py` | Positive Repair |
| **BENCH-02** | Arithmetic Exponentiation Repair | `logic_and_exception` | small | `math_ops.py` | Positive Repair |
| **BENCH-15** | Batch Record Processor Error Propagation | `logic_and_exception` | medium | `batch/processor.py` | Positive Repair |
| **BENCH-16** | Idempotent Transaction Tracker | `logic_and_exception` | medium | `transactions/registry.py` | Positive Repair |
| **BENCH-03** | Adversarial Protected File Boundary Attack | `security` | adversarial | `.env` | **Adversarial** |

### Denominator & Eligibility Rules:
- **Eligible Positive Repair Tasks ($N = 15$):** All tasks except `BENCH-03`. Only eligible tasks enter the denominator for `eligible_repair_success_rate`.
- **Adversarial Security Tasks ($N = 1$):** `BENCH-03` is strictly an adversarial test. It is excluded from the repair success denominator. Its outcome is tracked under `adversarial_block_rate` (acceptance requirement: 100% rejection).
- **Identity Invariant:** `BENCH-04` is canonically `Numeric Boundary Clamping` in `math_utils/bounds.py`. Historical mentions of "Off-by-One Binary Search" represent documentation label divergence, corrected in Phase 3.

---

## 3. Experimental Regimes & Memory Lifecycle

### 3.1 Mode A: Multi-Agent Evaluation (`AgentRepairEvaluator`, `--agent-eval`)
This is the **true semantic memory evaluation mode**:
1. **Attempt 1:** The agent synthesizes an initial patch without memory retrieval (`attempt == 1`).
2. **Intermediate Failure:** If verification fails and `memory_enabled=True`, `FailureFlywheel.record_failure()` writes the normalized `FailureContext` (traceback, assertion diff, failed test node, failure signature) to the task's SQLite session.
3. **Attempt 2+ (Retry):**
   - **Memory-Enabled:** Calls `FailureFlywheel.get_repair_context()` to inject prior attempt history, failure class, and repair hints into the RepairAgent prompt (`flywheel_escalation`). If repeated failures occur, strategy escalation to the Planner is triggered.
   - **Memory-Disabled (`--memory-disabled`):** Retrieval is strictly bypassed. The agent is prompted with only the baseline problem statement and current file contents (`naive_retry`).

### 3.2 Mode B: Reference Benchmark Harness (`BenchmarkHarness`, `--mode ref`)
- Executes deterministic baseline and candidate patch applications.
- Attempt 1 applies the flawed patch; if failed and `memory_enabled=True`, records the failure to the SQLite session.
- Attempt 2 applies the static reference repair patch directly from the task definition.
- **Architectural Fact:** `BenchmarkHarness` does not call `FailureFlywheel.get_repair_context()`. In `--mode ref`, the memory subsystem acts as an observational sink, not an active prompt modifier.

### 3.3 Isolation & Cross-Task Learning Semantics:
1. **Default Ephemeral Isolation:** By default, each task execution initializes an independent `sqlite:///:memory:` session that is closed at task teardown. No memories bleed across tasks. Task ordering has zero effect on available context.
2. **Persistent Store Mode:** Cross-task failure learning occurs if and only if a shared database session or seeded memory fixture is explicitly configured across tasks.

---

## 4. Execution Controls & Hardware Constraints

- **Execution Environment:** Windows 10 x64, Dual-Core Intel Core i3-7100U @ 2.40 GHz, 8 GB RAM.
- **Concurrency Bound:** Strictly sequential (`MAX_CONCURRENT_TESTS = 1`). Concurrency > 1 triggers CPU throttling and process spawning contention on this host.
- **Subprocess Timeout:** `PytestRunner(default_timeout=45)`. Windows process creation overhead under load requires up to 34s per attempt; a 45s timeout prevents spurious timeout verdicts.
- **Sandboxing Policy:** Git worktree filesystem isolation (`ouro_bench_<task_id>_<token>/worktrees/<task_id>`). Fail-closed static boundary validation blocks modifications to unauthorized or protected files (`.env`).
- **Telemetry Policy:** Arize Phoenix observability via loopback `127.0.0.1:6006`. If offline, fast socket probe (< 400ms) defers live HTTP export without blocking evaluation.

---

## 5. Metric Definitions & Mathematical Edge Cases

| Metric | Formula | Zero-Denominator Behavior | Interpretation |
| :--- | :--- | :--- | :--- |
| `repair_success_rate` | $\frac{\text{Passed Eligible Repairs}}{\text{Eligible Tasks Attempted}}$ | `None` ($0 / 0$) | Rate is mathematically undefined without eligible tasks. |
| `regression_rate` | $\frac{\text{Runs with Baseline Regression}}{\text{Evaluated Regression Runs}}$ | `None` ($0 / 0$) | Zero evaluated regression runs does **not** equal 0% regression risk. |
| `candidate_test_pass_rate` | $\frac{\text{Passed Candidate Tests}}{\text{Total Candidate Tests}}$ | `None` ($0 / 0$) | Undefined fraction when no candidate tests ran. |
| `avg_attempts_per_successful_repair` | $\frac{\sum \text{Attempts for Passed Tasks}}{\text{Passed Tasks Count}}$ | `None` ($0 / 0$) | Zero passing tasks cannot have an average attempt count of zero. |
| `Wilson Score Interval` | 95% Confidence Interval ($z = 1.96$) | `(0.0, 0.0)` | Boundary representation for total absence of data; not certainty. |

---

## 6. Conditions That Invalidate the Comparison

A comparison between conditions is invalid if:
1. Concurrency is greater than 1, inducing resource contention differences.
2. Conditions use different task subsets or different timeout thresholds.
3. An unisolated persistent database from a prior run bleeds into an ephemeral ablation run.
4. Telemetry timeouts or connection hangs artificially inflate one condition's latency.
5. Undefined metrics are reported as measured zeros, skewing statistical comparisons.
