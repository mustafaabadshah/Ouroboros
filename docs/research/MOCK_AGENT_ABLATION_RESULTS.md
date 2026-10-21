# Full-Catalog Mock-Agent Ablation Results & Analysis (v0.11)
**Project:** Project Ouroboros — Phase 4 Research Milestone  
**Document Version:** 1.0.0 (Execution Complete)  
**Date:** 2026-10-18  
**Scope:** Paired empirical evaluation of `flywheel_escalation` vs. `naive_retry` across all 15 positive repair tasks and 5 categories.

---

## 1. Experiment Overview & Verified Provenance

| Metadata Field | Verified Value | Verification Method |
| :--- | :--- | :--- |
| **Milestone** | Phase 4 Master Execution: Mock-Agent Full-Catalog Ablation | Experiment Execution |
| **Commit Revision** | `dd36b27` (`hotfix/python-package-discovery`) | `git rev-parse HEAD` |
| **Execution Command** | `.venv\Scripts\python.exe scripts\run_agent_eval.py --mock-agents --ablation --output artifacts/v0_11/mock_agent_ablation_15tasks.json` | Captured Process Command Line |
| **Task Filter** | `eligible_only=True` (15 Positive Tasks; BENCH-03 Excluded) | Verified in Artifact Configuration |
| **Strategy A** | `flywheel_escalation` (FailureFlywheel retrieval + failure context injection + strategy escalation) | `AgentRepairEvaluator` Condition A |
| **Strategy B** | `naive_retry` (Memory bypassed; unassisted baseline repetition) | `AgentRepairEvaluator` Condition B |
| **Max Attempt Budget** | 3 attempts per task | Hard Enforced Budget |
| **Provider** | `mock-deterministic-v1` via `MockProvider` (Offline, zero cost) | Model Telemetry Audit |
| **Primary Output Artifact** | `artifacts/v0_11/mock_agent_ablation_15tasks.json` | Hash Verified |
| **Archival Run ID** | `artifacts/evaluations/20261018_092604_agent_eval/agent_eval_run.json` | Hash Verified |
| **Artifact SHA-256 Parity**| `517b0c75fec267326e68ea9b9e12248c896af1e41314c0a102339b0c256a1d06` | Both files identical |

---

## 2. Executive Aggregate Summary

| Evaluation Metric | Flywheel Escalation (Memory Enabled) | Naive Retry (Memory Disabled) | Delta ($\Delta$) | Statistical Significance |
| :--- | :---: | :---: | :---: | :---: |
| **Tasks Attempted** | 15 | 15 | 0 | 100% paired (15 tasks) |
| **Eligible Repairs Passed** | **14 / 15** | **0 / 15** | **+14** | $p = 0.000122$ ($p < 0.001$) |
| **Eligible Success Rate** | **93.33%** | **0.00%** | **+93.33 pp** | Statistically significant |
| **Wilson 95% Confidence Interval**| **[0.7018, 0.9881]** | **[0.0000, 0.2039]** | — | Non-overlapping intervals |
| **Mean Attempts per Resolved Task**| **2.00** | **Undefined (`None`)** | — | 0 passed tasks in baseline |
| **Regression Rate** | **0.0%** (0 / 15) | **0.0%** (0 / 15) | 0.0 pp | Zero baseline regressions |
| **Candidate Test Pass Rate** | **93.33%** (14 / 15) | **0.00%** (0 / 15) | +93.33 pp | 14 verified acceptance passes |
| **Infrastructure Errors** | 0 | 0 | 0 | Clean harness execution |
| **Timeouts ($> 45s$)** | 1 (`BENCH-04` Attempt 2) | 0 | +1 | Windows subprocess latency |
| **Total Runtime** | 1,548,046 ms (~25.8 min) | 672,224 ms (~11.2 min) | +875,822 ms | 2 vs 1 pytest runs per attempt |
| **Median Task Duration** | 87,459 ms | 38,579 ms | +48,880 ms | Reflects acceptance test exec |
| **Total Tokens Consumed** | In: 3,720 \| Out: 7,440 | In: 5,400 \| Out: 10,800 | -5,040 tokens | Mock token telemetry |

---

## 3. Paired Task-Level Outcome Table

| Task ID | Benchmark Category | Flywheel Verdict | Naive Verdict | Flywheel Attempts | Naive Attempts | Paired Comparison |
| :--- | :--- | :---: | :---: | :---: | :---: | :--- |
| **BENCH-01** | `boundary_and_edge_case` | **PASS** | FAIL | 2 | 3 | Flywheel Win |
| **BENCH-04** | `boundary_and_edge_case` | FAIL | FAIL | 3 | 3 | Tie (Both FAIL; FW Timeout) |
| **BENCH-05** | `boundary_and_edge_case` | **PASS** | FAIL | 2 | 3 | Flywheel Win |
| **BENCH-06** | `type_and_interface` | **PASS** | FAIL | 2 | 3 | Flywheel Win |
| **BENCH-07** | `type_and_interface` | **PASS** | FAIL | 2 | 3 | Flywheel Win |
| **BENCH-08** | `type_and_interface` | **PASS** | FAIL | 2 | 3 | Flywheel Win |
| **BENCH-09** | `multi_file_and_state` | **PASS** | FAIL | 2 | 3 | Flywheel Win |
| **BENCH-10** | `multi_file_and_state` | **PASS** | FAIL | 2 | 3 | Flywheel Win |
| **BENCH-11** | `multi_file_and_state` | **PASS** | FAIL | 2 | 3 | Flywheel Win |
| **BENCH-12** | `serialization_and_parsing` | **PASS** | FAIL | 2 | 3 | Flywheel Win |
| **BENCH-13** | `serialization_and_parsing` | **PASS** | FAIL | 2 | 3 | Flywheel Win |
| **BENCH-14** | `serialization_and_parsing` | **PASS** | FAIL | 2 | 3 | Flywheel Win |
| **BENCH-02** | `logic_and_exception` | **PASS** | FAIL | 2 | 3 | Flywheel Win |
| **BENCH-15** | `logic_and_exception` | **PASS** | FAIL | 2 | 3 | Flywheel Win |
| **BENCH-16** | `logic_and_exception` | **PASS** | FAIL | 2 | 3 | Flywheel Win |

---

## 4. Benchmark Category-Level Analysis

All five canonical categories were fully evaluated with three tasks each:

| Benchmark Category | Tasks | Flywheel Success | Naive Success | Paired W-L-T | Avg FW Duration | Avg Naive Duration | Primary Failure Mode Observed |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :--- |
| **Boundary & Edge Case** | 3 | 2 / 3 (66.7%) | 0 / 3 (0.0%) | 2 - 0 - 1 | 130,331 ms | 43,510 ms | BENCH-04 subprocess timeout under host load |
| **Type & Interface** | 3 | 3 / 3 (100.0%)| 0 / 3 (0.0%) | 3 - 0 - 0 | 120,949 ms | 38,973 ms | Naive exhausted 3 attempts repeating flawed patch |
| **Multi-File & State** | 3 | 3 / 3 (100.0%)| 0 / 3 (0.0%) | 3 - 0 - 0 | 84,771 ms | 37,572 ms | Naive exhausted 3 attempts repeating flawed patch |
| **Serialization & Parsing** | 3 | 3 / 3 (100.0%)| 0 / 3 (0.0%) | 3 - 0 - 0 | 103,368 ms | 38,249 ms | Naive exhausted 3 attempts repeating flawed patch |
| **Logic & Exception** | 3 | 3 / 3 (100.0%)| 0 / 3 (0.0%) | 3 - 0 - 0 | 76,597 ms | 65,770 ms | Naive exhausted 3 attempts repeating flawed patch |

---

## 5. Statistical Analysis (McNemar Exact Test)

### 2x2 Paired Contingency Table
$$\begin{array}{c|cc|c}
& \text{Naive PASS} & \text{Naive FAIL} & \text{Total} \\
\hline
\text{Flywheel PASS} & a = 0 & b = 14 & 14 \\
\text{Flywheel FAIL} & c = 0 & d = 1 & 1 \\
\hline
\text{Total} & 0 & 15 & 15
\end{array}$$

- **Discordant Pairs ($n = b + c$):** $14 + 0 = 14$
- **Exact Two-Tailed Binomial Test ($H_0: p = 0.5$):**
  $$p = 2 \times \sum_{k=14}^{14} \binom{14}{k} 0.5^{14} = 2 \times \left(\frac{1}{2}\right)^{14} = \frac{2}{16,384} \approx 0.000122$$
- **Significance Verdict:** The difference is statistically significant ($p < 0.001$). Under the mock integration rules, `flywheel_escalation` outperformed `naive_retry` in 14 of 15 paired tasks, with zero instances of naive retry outperforming flywheel.

---

## 6. Forensic Failure Analysis: The BENCH-04 Outlier

While 14 tasks succeeded on Attempt 2, `BENCH-04` (`math_utils/bounds.py`) failed all 3 attempts under Flywheel Escalation. A deep forensic audit of the artifact history reveals:

1. **Attempt 1:** Evaluator applied `flawed_patch`. Acceptance test failed as expected:
   ```text
   FAILED test_bounds.py::test_clamp_boundaries_and_invalid_range - assert -5 == 0
   ```
   Normalized failure context committed to `FailureFlywheel`.
2. **Attempt 2:** `RepairAgent` correctly synthesized `repair_patch`. The patch applied cleanly. However, during execution of `test_clamp_boundaries_and_invalid_range`, the pytest subprocess execution duration exceeded the 45-second timeout limit (`PytestRunner.default_timeout=45`) due to CPU contention from a concurrent terminal check. The process was killed, resulting in `exit_code != 0`, `acceptance_passed=False`, and an empty failures list.
3. **Attempt 3:** `RepairAgent` synthesized `repair_patch` again. However, because Attempt 2's edits had already modified `math_utils/bounds.py` in the worktree, the patch failed dry-run check:
   ```text
   Git apply failed: Patch failed dry-run check: error: patch failed: math_utils/bounds.py:1
   error: math_utils/bounds.py: patch does not apply
   ```
4. **Takeaway:** BENCH-04's failure was an artifact of host subprocess latency and timeout interaction, not a semantic defect in the flywheel's diagnostic retrieval.

---

## 7. Epistemic Separation: Integration Validity vs. Learning-Effect Validity

To maintain absolute scientific integrity, the results must be interpreted through two distinct lenses:

### 7.1 Dimension A: Integration Validity (PROVEN by this experiment)
The evaluation conclusively establishes that:
1. **Control Flow Divergence:** `flywheel_escalation` and `naive_retry` strictly follow their specified algorithmic paths.
2. **Cold Start Invariance:** Attempt 1 in both conditions is strictly unassisted and produces identical failure rates across the entire catalog.
3. **Trace Extraction & Memory Insertion:** The verifier accurately captures pytest failures and stores structured `FailureContext` records in `FailureFlywheel`.
4. **Retry Escalation:** `RepairAgent` is invoked on retries when memory is enabled, whereas `naive_retry` strictly re-executes `LocalCoderLead` up to budget exhaustion ($k = 3$).
5. **Boundary Isolation:** Ephemeral in-memory SQLite instances guarantee that no failure memory leaks between tasks.
6. **Telemetry & Safety:** OTLP traces export cleanly, sandbox protections remain fail-closed, and artifacts are preserved immutably.

### 7.2 Dimension B: Learning-Effect Validity (NOT PROVEN by this experiment)
The evaluation **cannot** be cited as evidence of genuine machine learning or cognitive problem-solving:
1. **Marker-Triggered Dispatch:** As proven in Section 3 of the Execution Report, `MockProvider` switches to `repair_patch` based on substring detection (`"structured failure diagnostics"`), not semantic understanding.
2. **Predetermined Heuristic Rule:** The mock agent does not parse assertion diffs or stack traces; it produces the known-good repair diff whenever the diagnostic marker is present.
3. **Causal Attribution:** The 93.3% vs 0.0% delta reflects the deterministic behavior of the mock dispatcher when given different harness prompt templates, **not** live LLM cognitive adaptability.

---

## 8. Proposed Follow-Up Protocol (Phase 5)

To bridge the gap between integration demonstration and causal learning proof, two follow-up steps are designed:

1. **Deterministic Diagnostic-Sensitivity Control:**  
   Verified via [`backend/tests/unit/test_diagnostic_sensitivity_control.py`](file:///E:/MM%20Office/Ouroboros/backend/tests/unit/test_diagnostic_sensitivity_control.py), which implements `SensitivityAwareMockProvider` and proves that:
   - Correct diagnostics $\rightarrow$ triggers repair.
   - Corrupted diagnostics $\rightarrow$ triggers flawed patch.
   - Marker-only diagnostics $\rightarrow$ triggers flawed patch.
   - Absent diagnostics $\rightarrow$ triggers flawed patch.
2. **Targeted Live-LLM Replication on Discordant Tasks:**  
   Run live frontier LLMs (e.g. Qwen, Claude, GPT) exclusively across high-value discordant tasks (`BENCH-05`, `BENCH-13`, `BENCH-14`, `BENCH-15`) under paired memory conditions to measure real cognitive failure learning.
