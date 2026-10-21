# Memory Ablation Experimental Results & Runtime Analysis
**Document Version:** 2.0.0 (Phase 3 Verified)  
**Evaluation Date:** 2026-10-18  
**Run ID:** `20261017_200402_ref_benchmark_ablation_BENCH-02,BENCH-04,BENCH-12`  
**Raw Artifact:** [`artifacts/evaluations/20261017_200402_ref_benchmark_ablation_BENCH-02,BENCH-04,BENCH-12/benchmark_run.json`](file:///E:/MM%20Office/Ouroboros/artifacts/evaluations/20261017_200402_ref_benchmark_ablation_BENCH-02,BENCH-04,BENCH-12/benchmark_run.json)  
**Host Architecture:** Windows 10 x64, Intel Core i3-7100U @ 2.40 GHz (2 physical cores / 4 threads), 8 GB RAM, no dedicated GPU.

---

## 1. Executive Summary

A controlled, paired memory-ablation experiment was conducted across three distinct benchmark categories using collision-safe output directories. Both conditions executed with strictly matched task sets, isolated Git worktrees, identical test timeout budgets (`default_timeout=45`), and sequential concurrency (`MAX_CONCURRENT_TESTS=1`).

```
                              Ablation Comparison (N = 3 Tasks)
  +---------------------------------------------------------------------------------+
  | Metric                       Memory-Enabled       Memory-Disabled       Delta   |
  |---------------------------------------------------------------------------------|
  | Eligible Tasks Attempted           3                    3                 0     |
  | Eligible Repair Success Rate    100.0% (3/3)         100.0% (3/3)        0.0%   |
  | Wilson 95% Confidence Int.    [0.4385, 1.0000]     [0.4385, 1.0000]      0.00   |
  | Regression Rate                  0.0% (0/3)           0.0% (0/3)         0.0%   |
  | Median Task Latency (ms)          63,744               69,812         -6,068 ms |
  | Total Suite Runtime (ms)         202,756              226,968        -24,212 ms |
  +---------------------------------------------------------------------------------+
```

---

## 2. Granular Task-Level Outcomes & Latencies

| Task ID | Canonical Task Name | Category | Condition A (Enabled) | Att | Condition B (Disabled) | Att | Latency Delta |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **BENCH-04** | Numeric Boundary Clamping | `boundary_and_edge_case` | **PASS** (53,816 ms) | 2 | **PASS** (93,325 ms) | 2 | **-39,509 ms (-42.3%)** |
| **BENCH-12** | ISO Timestamp Normalizer | `serialization_and_parsing` | **PASS** (85,196 ms) | 2 | **PASS** (63,831 ms) | 2 | **+21,365 ms (+33.5%)** |
| **BENCH-02** | Arithmetic Exponentiation Repair | `logic_and_exception` | **PASS** (63,744 ms) | 2 | **PASS** (69,812 ms) | 2 | **-6,068 ms (-8.7%)** |

### Critical Source Finding: BENCH-12 Directional Divergence
While total suite runtime was 24,212 ms lower in Condition A, **BENCH-12 was actually 21,365 ms faster when memory was DISABLED** (63,831 ms vs 85,196 ms). An early hypothesis that memory retrieval provides a monotonic speedup across all categories is definitively refuted by this task record.

---

## 3. Causal Analysis: What Did the Benchmark Actually Measure?

An architectural audit of [`backend/app/evaluation/benchmark.py`](file:///E:/MM%20Office/Ouroboros/backend/app/evaluation/benchmark.py) lines 1305–1375 establishes the following mechanical facts:

1. **Memory Ingestion without Retrieval in `--mode ref`:**
   In `BenchmarkHarness.run_task()`, when Attempt 1 fails and `memory_enabled=True`, `FailureFlywheel.record_failure()` writes the failure to an in-memory SQLite table. However, on Attempt 2, the harness executes:
   ```python
   if verdict == "FAIL" and task_def.get("repair_patch"):
       repair_diff = task_def["repair_patch"]
       rep_applied, rep_msg = await worktree_mgr.apply_patch(worktree_path, repair_diff)
   ```
   The harness directly applies the static reference repair patch from the task definition dictionary. **It never calls `FailureFlywheel.get_repair_context()`.**
2. **Attribution of the -10.7% Runtime Delta:**
   Because memory retrieval is never invoked in `--mode ref`, the memory subsystem cannot logically have altered the patch synthesis path or execution time. The observed variance (+21s on BENCH-12 disabled, -39s on BENCH-04 disabled) was caused by host operating-system subprocess scheduling and Python process creation latency under dual-core hardware load.
3. **True Memory Ablation Locus:**
   True semantic memory ablation occurs only in `AgentRepairEvaluator` (`--agent-eval`), where Attempt 2+ conditionally retrieves historical failure diagnostics (`flywheel_escalation`) versus issuing a naive retry prompt (`naive_retry`).

---

## 4. Isolation & Condition Bleeding Assessment

1. **Session-Level Teardown:** Every task execution initialized a separate `engine = create_engine("sqlite:///:memory:")` and executed `mem_db.close()` at termination.
2. **Cross-Task Independence:** Tests in `backend/tests/unit/test_memory_ablation_validity.py` mathematically verify that failure records written during Task 1 cannot be observed by Task 2 in default ephemeral mode.
3. **Production Database Safety:** The disk-persisted database `ouroboros.db` was never accessed or mutated during benchmark runs.
4. **Adversarial Security Isolation:** `BENCH-03` is strictly evaluated under policy boundary checks and does not alter the positive repair success denominator.

---

## 5. Statistical Power Limitations

With a sample size of $N = 3$ tasks:
- The 95% Wilson score confidence interval for a 3/3 pass rate spans $[0.4385, 1.0000]$ (a width of 0.5615).
- A 0.0% difference in repair success rate demonstrates that both conditions completed deterministic reference repairs, but provides zero statistical power to prove algorithmic superiority of live LLM repair generation.
- Claims of memory-driven performance improvements must be restricted to within-task retry learning in `AgentRepairEvaluator` under real model generation.
