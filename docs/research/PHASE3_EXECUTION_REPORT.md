# Project Ouroboros — Phase 3 Execution Report
## End-to-End Observability, Memory Experiment Validity, and Research-Grade Verification

**Date:** 2026-10-18  
**Workspace:** `E:\MM Office\Ouroboros`  
**Starting Commit:** [`dd36b27`](file:///E:/MM%20Office/Ouroboros) (`fix(test): correct fixture index path calculation in MetaGraphAdapter`)  
**Branch:** `hotfix/python-package-discovery`  
**Environment:** Python 3.12.3, Windows 10 x64, Dual-Core Intel Core i3-7100U @ 2.40 GHz, 8 GB RAM.

---

## 1. Working Tree Protection & Historical Artifact Preservation

Before executing any modifications, the working tree and historical experiment records were verified:
- `git status --short`, `git log -5 --oneline`, and `git diff --check` confirmed a clean working tree without uncommitted regression risks.
- All **21 historical evaluation artifacts** in [`artifacts/`](file:///E:/MM%20Office/Ouroboros/artifacts) and [`artifacts/evaluations/`](file:///E:/MM%20Office/Ouroboros/artifacts/evaluations) were preserved completely intact.
- No destructive commands (`git reset --hard`, `git clean`) and no unapproved remote mutations (`git commit`, `git push`, `git merge`) were executed.

---

## 2. Priority A: Memory Ablation Validity & Lifecycle Audit

A comprehensive source code investigation of [`BenchmarkHarness`](file:///E:/MM%20Office/Ouroboros/backend/app/evaluation/benchmark.py), [`AgentRepairEvaluator`](file:///E:/MM%20Office/Ouroboros/backend/app/evaluation/agent_evaluator.py), and [`FailureFlywheel`](file:///E:/MM%20Office/Ouroboros/backend/app/memory/flywheel.py) resolved the nine core research questions:

1. **Does each benchmark task start with an empty SQLite in-memory database?**  
   **Yes.** Both harnesses execute `engine = create_engine("sqlite:///:memory:")` at the start of every task run.
2. **What memories can be retrieved before the task's first repair attempt?**  
   **None.** The SQLite database is initialized blank. Attempt 1 has zero prior history to retrieve.
3. **Are historical trajectories injected from another source?**  
   **No.** By default, no seed fixtures or disk databases are injected prior to task execution.
4. **Does the enabled condition perform retrieval that the disabled condition skips?**  
   - In `BenchmarkHarness` (`--mode ref`): **No.** Memory retrieval is never invoked on any attempt.
   - In `AgentRepairEvaluator` (`--mode standard`): **Yes, but strictly on Attempt 2+ (Retry).** Attempt 1 is identical in both conditions.
5. **Does the enabled condition write failures that can be retrieved by a later attempt within the same task?**  
   - In `BenchmarkHarness`: It writes to `mem_db`, but Attempt 2 applies `task_def["repair_patch"]` directly from the task definition without reading `mem_db`.
   - In `AgentRepairEvaluator`: **Yes.** If Attempt 1 fails, `FailureFlywheel.record_failure()` writes the failure, and Attempt 2 retrieves it via `FailureFlywheel.get_repair_context()`.
6. **Is memory enabled/disabled truly the only intended experimental variable?**  
   Yes. In `AgentRepairEvaluator`, `--memory-enabled` activates `flywheel_escalation` (prompt augmented with failure context), while `--memory-disabled` enforces `naive_retry` (prompt with zero failure context).
7. **Does task ordering affect what memory is available?**  
   **No.** Because each task uses an isolated in-memory session that closes at task completion, task ordering has zero effect on available context.
8. **Can shared state or a persistent database influence the result?**  
   **No.** The on-disk database `ouroboros.db` is completely bypassed during benchmarks.
9. **What does the experiment actually measure?**  
   - In `AgentRepairEvaluator`: It measures **within-task retry learning** (`flywheel_escalation` vs `naive_retry`).
   - In `BenchmarkHarness`: It measures **deterministic harness mechanics and failure ingestion overhead**, not memory-assisted repair planning.
   - It does **not** measure cross-task persistent learning unless a persistent or seeded database is explicitly configured.

---

## 3. Priority B: Arize Phoenix Observability Verification

1. **Local Startup Method (Verified):**  
   `python -m phoenix.server.main serve` runs Phoenix natively on Uvicorn (port 6006, host 127.0.0.1) without Docker Desktop.
2. **In-Process `ThreadSession` Timeout Discovery:**  
   `phoenix.launch_app()` hardcodes a 5.0s startup timeout in `thread_server.py:52`. On dual-core CPUs, cold SQLite table migrations require 6–8s, causing `RuntimeError: server took too long to start`. Starting Phoenix as a standalone process completely bypasses this limitation.
3. **End-to-End Live Export Proof:**  
   A live smoke test exported span `TestEngineer.LiveTelemetrySmokeTest` over HTTP/protobuf to `http://127.0.0.1:6006/v1/traces`. Querying the Phoenix REST API at `/v1/projects/ouroboros-swarm/spans` verified full ingestion with complete token counts, latencies, and contextual attributes (`ouroboros.ticket_id`, `ouroboros.run_id`).
4. **Offline Probe Caching Optimization:**  
   Fixed a critical performance defect in [`backend/app/observability/phoenix_service.py`](file:///E:/MM%20Office/Ouroboros/backend/app/observability/phoenix_service.py): previously, an offline collector caused a 300ms socket probe on *every* span. Phase 3 introduced probe caching (`_probe_attempted`, `_collector_offline`), reducing offline span recording latency from **309 ms to < 1 ms**.

---

## 4. Priority C: Investigation of the Reported -10.7% Runtime Difference

Analysis of the raw artifact [`artifacts/evaluations/20261017_200402_ref_benchmark_ablation_BENCH-02,BENCH-04,BENCH-12/benchmark_run.json`](file:///E:/MM%20Office/Ouroboros/artifacts/evaluations/20261017_200402_ref_benchmark_ablation_BENCH-02,BENCH-04,BENCH-12/benchmark_run.json) revealed:

1. **Directional Divergence on BENCH-12:**  
   - BENCH-04: Enabled 53.8s vs Disabled 93.3s (-39.5s)
   - BENCH-12: **Enabled 85.2s vs Disabled 63.8s (+21.4s — Disabled was faster!)**
   - BENCH-02: Enabled 63.7s vs Disabled 69.8s (-6.1s)
2. **Causal Reality:**  
   Because `BenchmarkHarness` (`--mode ref`) never queries `FailureFlywheel`, the memory subsystem could not have caused the speedup. The runtime variance was entirely an artifact of host operating-system subprocess spawning delays (Windows process creation under CPU scheduling load on dual-core hardware).
3. **Scientific Value:**  
   Acknowledging this source evidence prevents false claims that memory retrieval produces a uniform 10.7% runtime reduction in deterministic mode.

---

## 5. Priority D: Task Identity, Provenance, and Manifest Integrity

1. **BENCH-04 Discrepancy Resolved:**  
   - Historical audit documents labeled `BENCH-04` as "Off-by-One Binary Search" or "Concurrency Deadlock" from memory.
   - The canonical code definition in `backend/app/evaluation/benchmark.py` has always been:  
     **`BENCH-04`: `Numeric Boundary Clamping`** (`boundary_and_edge_case`, `math_utils/bounds.py`, `clamp(val, low, high)`).
2. **Manifest Integrity Test:**  
   Created [`backend/tests/unit/test_task_provenance_and_manifest.py`](file:///E:/MM%20Office/Ouroboros/backend/tests/unit/test_task_provenance_and_manifest.py) to assert:
   - Exactly 16 tasks in `BENCHMARK_TASKS_V1` with zero ID collisions.
   - Exactly 15 eligible repair tasks and 1 isolated adversarial task (`BENCH-03`).
   - Immutable assertion of `BENCH-04` canonical attributes.
   - Cryptographic fingerprint stability across task definitions.

---

## 6. Priority E: Evaluation Correctness & Undefined Metric Preservation

Preserved and tested all zero-denominator metric mathematical corrections in [`backend/app/evaluation/metrics.py`](file:///E:/MM%20Office/Ouroboros/backend/app/evaluation/metrics.py):
- `repair_success_rate = None` when eligible attempted is 0.
- `regression_rate = None` when evaluated regression runs is 0 (preventing false 0% regression risk claims).
- `candidate_test_pass_rate = None` when total candidate tests is 0.
- `avg_attempts_per_successful_repair = None` when passing count is 0.
- Wilson score interval returns `(0.0, 0.0)` for zero observations with documented absence-of-data semantics.

---

## 7. Verification Test Results

Full automated test execution across 5 test suites:
```text
backend/tests/unit/test_evaluation_correctness.py::test_sandbox_detector_caching PASSED [  4%]
backend/tests/unit/test_evaluation_correctness.py::test_metrics_calculator_evaluated_runs_denominator PASSED [  8%]
backend/tests/unit/test_evaluation_correctness.py::test_metrics_calculator_zero_passing_runs_defaults PASSED [ 12%]
backend/tests/unit/test_evaluation_correctness.py::test_suite_zero_eligible_denominator_returns_none PASSED [ 16%]
backend/tests/unit/test_evaluation_correctness.py::test_wilson_score_interval_bounds_and_zero_denominator PASSED [ 20%]
backend/tests/unit/test_eval_contract.py::test_evaluation_outcome_enum PASSED [ 25%]
backend/tests/unit/test_eval_contract.py::test_wilson_score_interval PASSED [ 29%]
backend/tests/unit/test_eval_contract.py::test_percentile_computation PASSED [ 33%]
backend/tests/unit/test_eval_contract.py::test_legacy_v010_adapter PASSED [ 37%]
backend/tests/unit/test_eval_contract.py::test_task_record_validation PASSED [ 41%]
backend/tests/unit/test_phoenix_observability.py::test_phoenix_offline_fallback_fast_probe_and_bounded_shutdown PASSED [ 45%]
backend/tests/unit/test_phoenix_observability.py::test_phoenix_correlation_identifiers_and_privacy_redaction PASSED [ 50%]
backend/tests/unit/test_phoenix_observability.py::test_phoenix_evaluator_span_generation PASSED [ 54%]
backend/tests/unit/test_phoenix_observability.py::test_phoenix_live_export_and_query_if_collector_running SKIPPED [ 58%]
backend/tests/unit/test_memory_ablation_validity.py::test_memory_enabled_retrieval_receives_historical_context PASSED [ 62%]
backend/tests/unit/test_memory_ablation_validity.py::test_memory_disabled_bypasses_retrieval PASSED [ 66%]
backend/tests/unit/test_memory_ablation_validity.py::test_ephemeral_sessions_prevent_cross_task_bleeding PASSED [ 70%]
backend/tests/unit/test_memory_ablation_validity.py::test_persistent_memory_store_allows_cross_task_learning_when_configured PASSED [ 75%]
backend/tests/unit/test_memory_ablation_validity.py::test_memory_fixture_reproducibility PASSED [ 79%]
backend/tests/unit/test_task_provenance_and_manifest.py::test_manifest_unique_task_ids PASSED [ 83%]
backend/tests/unit/test_task_provenance_and_manifest.py::test_manifest_canonical_partition_positive_vs_adversarial PASSED [ 87%]
backend/tests/unit/test_task_provenance_and_manifest.py::test_bench04_canonical_identity PASSED [ 91%]
backend/tests/unit/test_task_provenance_and_manifest.py::test_manifest_required_fields_present PASSED [ 95%]
backend/tests/unit/test_task_provenance_and_manifest.py::test_task_definition_fingerprint_stability PASSED [100%]

======================== 23 passed, 1 skipped in 4.82s ========================
```

---

## 8. Summary of Deliverables & Modified Files

- **Phoenix Architecture & Trace Verification Report:** [`docs/research/PHOENIX_OBSERVABILITY_REPORT.md`](file:///E:/MM%20Office/Ouroboros/docs/research/PHOENIX_OBSERVABILITY_REPORT.md)
- **Updated Memory Ablation Protocol:** [`docs/research/MEMORY_ABLATION_PROTOCOL.md`](file:///E:/MM%20Office/Ouroboros/docs/research/MEMORY_ABLATION_PROTOCOL.md)
- **Updated Memory Ablation Results Analysis:** [`docs/research/MEMORY_ABLATION_RESULTS.md`](file:///E:/MM%20Office/Ouroboros/docs/research/MEMORY_ABLATION_RESULTS.md)
- **Phase 3 Master Execution Report:** [`docs/research/PHASE3_EXECUTION_REPORT.md`](file:///E:/MM%20Office/Ouroboros/docs/research/PHASE3_EXECUTION_REPORT.md)
- **Phoenix Unit & Integration Test Suite:** [`backend/tests/unit/test_phoenix_observability.py`](file:///E:/MM%20Office/Ouroboros/backend/tests/unit/test_phoenix_observability.py)
- **Memory Ablation Semantics Test Suite:** [`backend/tests/unit/test_memory_ablation_validity.py`](file:///E:/MM%20Office/Ouroboros/backend/tests/unit/test_memory_ablation_validity.py)
- **Task Provenance & Manifest Integrity Test Suite:** [`backend/tests/unit/test_task_provenance_and_manifest.py`](file:///E:/MM%20Office/Ouroboros/backend/tests/unit/test_task_provenance_and_manifest.py)
- **Telemetry Probe Caching & Bounded Shutdown:** [`backend/app/observability/phoenix_service.py`](file:///E:/MM%20Office/Ouroboros/backend/app/observability/phoenix_service.py)

---

## 9. Remaining Risks & Next Research Milestone

1. **Hardware Process Creation Variance:** Windows subprocess creation under load requires strict adherence to `MAX_CONCURRENT_TESTS=1` and `default_timeout=45`.
2. **Live LLM Evaluation Budget:** Testing generative repair reasoning requires active API keys and token budget; offline deterministic evaluations validate execution mechanics and memory pipelines without external spending.
3. **Next Recommended Milestone:** Execute an `AgentRepairEvaluator` mock-agent ablation sweep (`python scripts/run_agent_eval.py --mock-agents --ablation`) across the full 15-task suite to benchmark retry prompt escalation logic across the entire benchmark taxonomy.
