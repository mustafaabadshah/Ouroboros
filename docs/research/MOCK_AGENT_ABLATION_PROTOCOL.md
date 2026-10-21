# Full-Catalog Mock-Agent Ablation Protocol (v0.11)
**Project:** Project Ouroboros — Phase 4 Research Milestone  
**Document Version:** 1.0.0  
**Date:** 2026-10-18  
**Scope:** Controlled, reproducible, zero-cost evaluation of within-task failure-learning (`flywheel_escalation`) versus baseline retry (`naive_retry`) across all 15 positive repair tasks and 5 benchmark categories using deterministic mock agents.

---

## 1. Research Question & Hypotheses

### Primary Research Question
Does Ouroboros's within-task failure-learning strategy (`flywheel_escalation`) improve repair success, reduce required attempts, and avoid repeated failure patterns compared with an unassisted retry strategy (`naive_retry`), when both operate under an identical deterministic mock-agent environment, identical task fixtures, and identical resource budgets?

### Formal Hypotheses
- **Primary Hypothesis ($H_1$):** Across eligible positive repair tasks, within-task failure-learning (`flywheel_escalation`) achieves significantly higher repair success ($p < 0.05$ via paired McNemar test) than unassisted retry (`naive_retry`) when initial attempts fail.
- **Secondary Hypothesis ($H_2$):** Within-task failure-learning resolves defects within the bounded budget ($k \le 3$) upon receiving structured failure diagnostics, while unassisted retry exhausts the attempt budget repeating baseline attempts without diagnostic guidance.
- **Null Hypothesis ($H_0$):** There is no significant difference in repair success between `flywheel_escalation` and `naive_retry` under identical mock-agent constraints ($b = c$ in paired discordant analysis).

---

## 2. Benchmark Suite Catalog & Task Categorization

The evaluation strictly executes across canonical suite `BENCHMARK_TASKS_V1` defined in [`backend/app/evaluation/benchmark.py`](file:///E:/MM%20Office/Ouroboros/backend/app/evaluation/benchmark.py).

The positive benchmark comprises exactly 15 eligible tasks partitioned across five distinct software defect categories (3 tasks per category), plus one excluded adversarial task:

| Category | Category Identifier | Tasks | Target Files | Defect Types |
| :--- | :--- | :--- | :--- | :--- |
| **A. Boundary & Edge Case** | `boundary_and_edge_case` | BENCH-01, BENCH-04, BENCH-05 | `utils/input_parser.py`, `math_utils/bounds.py`, `pagination/paginator.py` | Non-positive int guard, clamping boundaries, zero-indexed page slicing |
| **B. Type & Interface** | `type_and_interface` | BENCH-06, BENCH-07, BENCH-08 | `utils/dict_traversal.py`, `config/coercer.py`, `events/dispatcher.py` | Safe nested key traversal, boolean/integer coercion, event callback signature adaptation |
| **C. Multi-File & State** | `multi_file_and_state` | BENCH-09, BENCH-10, BENCH-11 | `services/loader.py`, `workflow/state_machine.py`, `rate_limiter/bucket.py` | Cross-module entity resolution, state transition validation, shared token bucket synchronization |
| **D. Serialization & Parsing** | `serialization_and_parsing` | BENCH-12, BENCH-13, BENCH-14 | `datetime_utils/iso_parser.py`, `json_parser/safe_loader.py`, `semver/parser.py` | ISO-8601 normalization, JSON fallback parsing, SemVer regex tag extraction |
| **E. Logic & Exception** | `logic_and_exception` | BENCH-02, BENCH-15, BENCH-16 | `math_ops.py`, `batch/processor.py`, `transactions/registry.py` | Exponentiation precedence, batch error propagation, idempotent transaction deduplication |
| **Excluded: Adversarial** | `security` | BENCH-03 | `.env` | Prompt injection unauthorized file boundary violation (Excluded from positive repair ablation) |

### Task Selection & Eligibility Rules
- **Eligible Tasks ($N = 15$):** All positive repair tasks (`is_eligible=True`, `is_adversarial=False`). Only these 15 tasks enter the repair success denominator.
- **Security Task Exclusion:** `BENCH-03` is strictly an adversarial prompt-injection challenge (`is_adversarial=True`, `is_eligible=False`). Because its target is unauthorized security enforcement rather than functional code repair, it is systematically excluded from the repair ablation sweep.

---

## 3. Strategies Compared

Both strategies operate within [`AgentRepairEvaluator`](file:///E:/MM%20Office/Ouroboros/backend/app/evaluation/agent_evaluator.py) with an identical maximum budget of $k = 3$ attempts per task.

### Strategy 1: `flywheel_escalation` (Memory-Enabled)
- **Attempt 1:** Executes `LocalCoderLead` using baseline problem statement and candidate file content. Operates completely cold with zero historical memory.
- **Intermediate Failure:** Verifier captures failure output via [`FailureContextNormalizer`](file:///E:/MM%20Office/Ouroboros/backend/app/evaluation/failure_context.py), extracting failed test nodes, assertion diffs, and stack traces. A structured failure trajectory is committed to the task's isolated in-memory SQLite store via [`FailureFlywheel.record_failure()`](file:///E:/MM%20Office/Ouroboros/backend/app/memory/flywheel.py).
- **Attempt 2+ (Retry Learning):** Evaluator engages `RepairAgent`, providing structured failure diagnostics (`STRUCTURED FAILURE DIAGNOSTICS`) retrieved via [`FailureFlywheel.get_repair_context()`](file:///E:/MM%20Office/Ouroboros/backend/app/memory/flywheel.py). If identical failure signatures repeat, strategy escalation re-engages the Planner.

### Strategy 2: `naive_retry` (Memory-Disabled Baseline)
- **Attempt 1:** Identical to Strategy 1 Attempt 1.
- **Intermediate Failure:** Failure is recorded by the test runner for attempt tracking, but diagnostic history is **not** injected into subsequent agent prompts (`memory_enabled=False`, `retry_strategy="naive_retry"`).
- **Attempt 2+ (Unassisted Retry):** Evaluator re-executes `LocalCoderLead` using only the unassisted task description and current file contents. The agent receives zero failure trace, zero assertion error context, and zero repair hints, reflecting the industry-standard naive retry loop.

---

## 4. Deterministic Mock-Agent Implementation

To eliminate external LLM API costs ($0.00 spent), token quotas, and non-deterministic generation noise, the evaluation utilizes [`MockProvider`](file:///E:/MM%20Office/Ouroboros/backend/app/providers/mock_provider.py).

### Mock Dispatch Logic
1. **Offline Isolation:** Runs 100% locally. Does not require API keys (Groq, Anthropic, OpenAI) and makes zero external network calls.
2. **Task Header Matching:** `_find_benchmark_task(prompt)` inspects candidate file paths, problem statements, and task titles from prompt text to identify the active benchmark task.
3. **Role-Based Behavioral Dispatch:**
   - **Planner Agent:** Synthesizes structured JSON execution plan containing `target_file` and bounded subtasks.
   - **LocalCoder (Attempt 1 & Naive Retry):** Synthesizes `task_def["flawed_patch"]`. This deliberately introduces the realistic initial defect or partial fix, ensuring Attempt 1 fails verification across both conditions.
   - **Repair Agent (Flywheel Escalation):** Inspects prompt text for `STRUCTURED FAILURE DIAGNOSTICS`. When diagnostics are present, it synthesizes `task_def["repair_patch"]`, simulating an agent successfully leveraging verifier feedback to correct the bug.
4. **Reproducibility Guarantee:** Mock generation is strictly deterministic and stateless. Given identical input prompts, output diffs are byte-for-byte identical.

---

## 5. Isolation & Boundary Guarantees

1. **Per-Task SQLite Isolation:**
   - Every benchmark task instantiates an independent in-memory database: `create_engine("sqlite:///:memory:")`.
   - All tables are created fresh via `Base.metadata.create_all(bind=engine)`.
   - At task completion, `mem_db.close()` drops the in-memory database.
   - Cross-task memory contamination is architecturally impossible: memory recorded during Task $N$ cannot leak into Task $N+1$.
2. **Worktree Filesystem Isolation:**
   - Each attempt runs inside a disposable Git worktree managed by [`GitWorktreeManager`](file:///E:/MM%20Office/Ouroboros/backend/app/integrations/git/worktree.py) in local temp directory.
   - Fail-closed security boundary blocks modifications outside authorized paths (`.env`, protected directories).
   - On completion, worktrees are pruned and temporary directories are recursively unlinked.

---

## 6. Execution Command & Configuration

The experimental sweep is executed via:

```powershell
.venv\Scripts\python.exe scripts\run_agent_eval.py --mock-agents --ablation --output artifacts/v0_11/mock_agent_ablation_15tasks.json
```

### Parameter Specification
- `--mock-agents`: Forces `AgentRepairEvaluator` to route all agent roles to `MockProvider`.
- `--ablation`: Automatically executes paired conditions (`flywheel_escalation` followed by `naive_retry`) across the suite.
- `--output`: Specifies the machine-readable JSON artifact destination.
- `concurrency`: Exactly 1 (strictly sequential execution; eliminates CPU contention on host).
- `max_attempts`: 3 attempts maximum per task budget.
- `timeout`: 45 seconds per pytest invocation.

---

## 7. Metrics & Denominator Definitions

All metrics adhere to honest, mathematically sound denominator definitions:

| Metric Name | Mathematical Definition | Zero-Denominator Value | Interpretation |
| :--- | :--- | :--- | :--- |
| **Eligible Repair Success Rate** | $\frac{\text{Repairs Passed}}{\text{Eligible Tasks Total}}$ | `None` / `null` ($0 / 0$) | Fraction of 15 positive repair tasks resolved. |
| **Attempted Repair Success Rate** | $\frac{\text{Repairs Passed}}{\text{Tasks Attempted}}$ | `None` / `null` ($0 / 0$) | Success rate over tasks that actually executed. |
| **Attempts Per Successful Repair** | $\frac{\sum_{i \in \text{Passed}} \text{Attempts}_i}{|\text{Passed}|}$ | `None` / `null` ($0 \text{ passed}$) | Mean attempt cost for resolved tasks only. |
| **Regression Rate** | $\frac{\text{Runs with Baseline Test Regression}}{\text{Evaluated Regression Runs}}$ | `None` / `null` ($0 \text{ evaluated}$) | Risk of breaking existing passing tests. |
| **Wilson 95% Score Interval** | $\frac{\hat{p} + \frac{z^2}{2n} \pm z \sqrt{\frac{\hat{p}(1-\hat{p})}{n} + \frac{z^2}{4n^2}}}{1 + \frac{z^2}{n}}$ | `[0.0, 0.0]` | Exact binomial confidence interval ($z = 1.96$). |
| **Paired McNemar Exact Test** | $p = 2 \sum_{k=b}^{n} \binom{n}{k} 0.5^n$ | Undefined if $b + c = 0$ | Exact two-tailed binomial test on discordant pairs ($b$: Flywheel wins, $c$: Naive wins). |

---

## 8. Artifact Immutability & Archival Schema

1. Primary output is saved to the designated `--output` path.
2. An immutable, collision-safe timestamped record is automatically created under `artifacts/evaluations/<timestamp>_agent_eval/agent_eval_run.json`.
3. Historical evaluation artifacts (`artifacts/evaluations/`, `artifacts/agent_eval_p2c_sweep.json`, etc.) are treated as read-only historical records and are never overwritten.
4. Output JSON schema conforms to `v0.11.0` containing `configuration`, `statistical_summary`, and `raw_trials` with full attempt-by-attempt traces.

---

## 9. Threats to Validity

1. **Mock Agent Generalizability:** `MockProvider` tests the **mechanical correctness of the failure-learning pipeline** (traceback capture, normalized schema delivery, memory isolation, retry escalation). It does not evaluate open-ended reasoning capabilities of frontier LLMs on novel unseen bugs.
2. **Host Hardware Constraints:** The Intel Core i3-7100U host incurs significant Windows subprocess creation latency (~25-35s per pytest execution). Latency differences reflect subprocess count rather than inference time.
3. **Sample Size:** 15 tasks provide high statistical power for large effect sizes ($> 25\%$), but cannot detect subtle single-digit percentage advantages.

---

## 10. Reproduction Protocol

To reproduce this experiment from a clean checkout:
1. Verify working branch and environment: Python 3.12.3 in `.venv`.
2. Run Stage Two contract tests:
   ```powershell
   .venv\Scripts\python.exe -m pytest backend/tests/unit/test_mock_agent_ablation_contract.py -v
   ```
3. Execute the full paired ablation:
   ```powershell
   .venv\Scripts\python.exe scripts\run_agent_eval.py --mock-agents --ablation --output artifacts/v0_11/mock_agent_ablation_15tasks.json
   ```
4. Verify that generated JSON records 15 unique task IDs across both conditions and matches the reported statistical summaries.

---

## 11. Epistemic Classification: Integration Demonstration vs. Causal Learning Evidence

To preserve scientific rigor, this experiment must be accurately labeled:

### 11.1 Experiment Classification
This evaluation is characterized as a **Mock-Agent Integration and Retry-Orchestration Demonstration**, **not** conclusive empirical proof of causal LLM failure learning.

### 11.2 Forensic Audit of Mock Dispatch Mechanics
1. **Marker-Based Triggering:** `MockProvider` checks substring presence (`"structured failure diagnostics"` or `"repair specialist"`). It does not parse or evaluate semantic diagnostic accuracy.
2. **Predetermined Outcome Rule:** Any prompt bearing the diagnostic marker triggers `task_def["repair_patch"]`, whereas unassisted prompts receive `task_def["flawed_patch"]`. The repair outcome is conditioned on the harness route, not open-ended reasoning over traces.
3. **Absence of Diagnostic Control:** Under the current benchmark harness, there is no intermediate control that receives diagnostics without the `FailureFlywheel` database retrieval loop.

### 11.3 What This Experiment Proves (Integration Validity)
- **Harness Plumbing:** Confirms end-to-end multi-agent orchestration, Planner decomposition, worktree management, test execution, and patch verification.
- **Trace Propagation:** Confirms that Attempt 1 failures successfully capture pytest traces and normalize them into `FailureFlywheel`.
- **Strategy Routing:** Confirms that `flywheel_escalation` correctly escalates to `RepairAgent` on Attempt 2, whereas `naive_retry` strictly re-executes `LocalCoderLead` without prior history.
- **Task Boundary Memory Isolation:** Confirms that per-task ephemeral SQLite sessions prevent cross-task memory bleed.
- **Telemetry & Artifact Integrity:** Confirms clean OTLP trace export and immutable artifact archival without data corruption.

### 11.4 What This Experiment Does NOT Prove (Learning Validity)
- Does **not** prove that a live neural language model (e.g. Qwen, Claude, GPT) can read and logically interpret arbitrary pytest failures without hallucinations.
- Does **not** measure real-world generalized software engineering repair capabilities beyond the 15 benchmark fixtures.
- Does **not** isolate whether structured failure formatting provides an incremental advantage over raw stack trace concatenation for live models.

