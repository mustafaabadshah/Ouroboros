# Project Ouroboros — Phase 6 Experiment Design
## Scaled Multi-Task Live-LLM Evaluation Protocol: Full-Catalog Retry-Learning Sweep

**Document Version:** `v1.0.0-draft`  
**Protocol Status:** `APPROVED FOR EXPERIMENTAL READINESS (EXECUTION GATED)`  
**Authors:** Senior ML Systems Engineer, Research Methodology Reviewer  
**Creation Timestamp:** `2026-10-18T20:15:00+05:00`  
**Target Provider:** Groq Cloud Remote Inference  
**Target Model:** `qwen/qwen3.8-27b` (Open-Weights 27B Dense Model)  
**Task Scope:** All 15 positive, eligible repair tasks in `BENCHMARK_TASKS_V1`  

---

## 1. Executive Summary & Research Mandate

Phase 5 demonstrated directional proof-of-concept for Ouroboros's within-task failure learning flywheel on 4 pilot tasks. However, as established in the Phase 5.1 audit, an $N = 4$ sample cannot mathematically achieve statistical significance ($p_{\text{exact}} \ge 0.125$).

Phase 6 scales the empirical evaluation to the **entire 15-task positive catalog** across all five defect categories in `BENCHMARK_TASKS_V1`. This document defines the formal, pre-registered experimental protocol to ensure statistical power, strict treatment isolation, diagnostic provenance, deterministic judging, and bounded resource consumption.

> [!IMPORTANT]
> **Execution Gate Policy:**
> This protocol is pre-registered and approved for experimental readiness. **No live LLM calls, benchmark sweeps, or API credit expenditures shall occur without explicit, interactive user authorization.**

---

## 2. Research Question and Formal Hypotheses

### 2.1 Research Question
> Does structured within-task failure diagnostics and strategy escalation (`flywheel_escalation`) significantly increase task repair success rates and attempt efficiency compared to unguided repeated retry (`naive_retry`) across a diverse catalog of software defects when evaluated on a frontier open-weights LLM?

### 2.2 Formal Statistical Hypotheses
Let $\mathcal{T} = \{t_1, t_2, \dots, t_N\}$ be the suite of $N = 15$ eligible benchmark tasks.  
For each task $t_i$, let $Y_{i}^{\text{flywheel}} \in \{0, 1\}$ and $Y_{i}^{\text{naive}} \in \{0, 1\}$ denote repair success under each strategy.

- **Null Hypothesis ($H_0$):** Within-task failure feedback confers no performance advantage. Among discordant task outcomes ($Y_i^{\text{flywheel}} \ne Y_i^{\text{naive}}$), the probability of Flywheel success equals 0.5:
  $$H_0: P(Y_i^{\text{flywheel}} = 1, Y_i^{\text{naive}} = 0 \mid \text{discordant}) = 0.5$$
- **Alternative Hypothesis ($H_1$):** Within-task failure feedback significantly improves repair success:
  $$H_1: P(Y_i^{\text{flywheel}} = 1, Y_i^{\text{naive}} = 0 \mid \text{discordant}) > 0.5$$
- **Significance Criterion:** Two-tailed exact McNemar test at $\alpha = 0.05$.

### 2.3 Statistical Power Justification
With $N = 15$ tasks:
- If 8 discordant pairs occur ($b + c = 8$) with Flywheel winning 7 ($b = 7, c = 1$), two-tailed exact $p = 2 \times \binom{8}{7} (0.5)^8 + 2 \times \binom{8}{8} (0.5)^8 = 2 \times (8 + 1)/256 = 0.0703$.
- If Flywheel wins all 8 ($b = 8, c = 0$), two-tailed exact $p = 2 \times (0.5)^8 = \mathbf{0.0078} < 0.05$.
- If discordant pairs $n \ge 6$ and $b = n$, $p \le 0.03125$.
- Evaluating $N = 15$ provides adequate statistical power to detect large effect sizes ($\Delta \ge 40$ percentage points).

---

## 3. Experimental Conditions & Controlled Invariants

```
                                    ┌────────────────────────────────────────────────────────┐
                                    │               Task Specification & Clean Seed          │
                                    │            (Same file, tests, timeout, and judge)      │
                                    └──────────────────────────┬─────────────────────────────┘
                                                               │
                                  ┌────────────────────────────┴───────────────────────────┐
                                  ▼                                                         ▼
                    ┌────────────────────────────┐                            ┌────────────────────────────┐
                    │   Flywheel Escalation      │                            │      Naive Retry           │
                    │      (Treatment)           │                            │       (Control)            │
                    ├────────────────────────────┤                            ├────────────────────────────┤
                    │ Attempt 1: Cold unguided   │                            │ Attempt 1: Cold unguided   │
                    │ Attempt 2: Grounded diag   │                            │ Attempt 2: Cold re-prompt  │
                    │ Attempt 3: Escalate to Plan│                            │ Attempt 3: Cold re-prompt  │
                    │ Workspace: Fresh per task  │                            │ Workspace: Fresh per task  │
                    │ Memory: In-memory SQLite   │                            │ Memory: Disabled           │
                    └────────────────────────────┘                            └────────────────────────────┘
```

### 3.1 Treatment Condition (`flywheel_escalation`)
1. **Attempt 1:** Standard cold prompt (`CoderLead.prepare_coding_prompt`) with zero prior diagnostics.
2. **Attempt 2:** If Attempt 1 fails, inject structured failure diagnostics (`FailureFlywheel.get_repair_context`) including failed test node IDs, exact assertion diff, and traceback tail.
3. **Attempt 3:** If Attempt 2 also fails, trigger **strategy escalation to the Planner** (`planner_agent.analyze_failure_trajectory`) to synthesize a revised, decomposed subtask before invoking CoderLead.

### 3.2 Control Condition (`naive_retry`)
1. **Attempt 1:** Identical cold prompt to Treatment.
2. **Attempt 2:** If Attempt 1 fails, issue a fresh re-prompt with the original subtask and seed code. No failure diagnostics, assertion traces, or error strings are provided.
3. **Attempt 3:** If Attempt 2 fails, issue a third unguided re-prompt. No planner escalation occurs.

### 3.3 Controlled Invariants (Held Strictly Constant)
- **Model:** `qwen/qwen3.8-27b` hosted on Groq Cloud remote inference API.
- **Sampling Parameters:** Temperature = $0.2$, top-p = $0.95$.
- **Attempt Budget:** Exactly 3 attempts maximum per task condition.
- **Acceptance Criteria:** Authoritative `pytest` acceptance suite defined in `BENCHMARK_TASKS_V1`.
- **Regression Criteria:** Authoritative baseline tests that must remain passing.
- **Patch Validator:** `DeterministicJudge` with unified diff parsing, AST change validation, and worktree isolation.
- **Test Runner Timeout:** 45.0 seconds per pytest execution.
- **Environment:** Clean Python 3.12.3 virtual environment on Windows 10 x64.

---

## 4. Worktree Isolation, Diagnostic Provenance & Memory Scoping

### 4.1 Ephemeral Worktree Isolation
- Every task attempt must execute in an isolated, temporary directory managed by Python `tempfile.TemporaryDirectory`.
- Seed files are populated from pristine dictionary definitions in `BENCHMARK_TASKS_V1["seed_files"]`.
- When an attempt completes, the temporary worktree is unlinked, preventing dirty file residues or unstaged diffs from affecting subsequent attempts or tasks.

### 4.2 Diagnostic Provenance Requirements
- Every diagnostic passed to Attempt 2+ must originate strictly from the output of `pytest` in Attempt $k-1$ for that specific task.
- Diagnostics must contain:
  1. Failed test node identifiers (e.g. `test_paginate.py::test_boundary`).
  2. Failure classification (e.g. `AssertionError`, `TypeError`, `JSONDecodeError`).
  3. Exact assertion message and diff (e.g. `Regex pattern did not match`).
  4. Traceback tail (last 10 lines of stack trace).
- No future information, cross-task data, or synthetic hints may be injected.

### 4.3 Memory Scoping: Within-Task Only
- A fresh in-memory SQLite database (`sqlite:///:memory:`) shall be initialized at the beginning of each task and closed immediately upon task completion.
- Cross-task memory transfer is strictly prohibited to guarantee task independence.

---

## 5. Task Suite Selection and Pre-Registered Exclusions

### 5.1 Suite Selection (15 Tasks)
The evaluation encompasses all 15 positive repair tasks in `BENCHMARK_TASKS_V1`:

| Category | Tasks Included | Defect Description |
| :--- | :--- | :--- |
| **`boundary_edge_case`** | `BENCH-01`, `BENCH-04`, `BENCH-05` | Off-by-one errors, empty sequence handling, pagination bounds |
| **`syntax_type_error`** | `BENCH-02`, `BENCH-06`, `BENCH-07` | Type mismatch, missing optional parameters, invalid signature |
| **`concurrency_race`** | `BENCH-03`, `BENCH-08`, `BENCH-09` | Thread-safety races, lock release on exception, atomic counters |
| **`serialization`** | `BENCH-10`, `BENCH-13`, `BENCH-14` | JSON parsing fallback, datetime roundtrips, custom deserializers |
| **`logic_exception`** | `BENCH-11`, `BENCH-12`, `BENCH-15` | Batch error collection, recursive cycle detection, cache invalidation |

### 5.2 Pre-Registered Exclusions
- Adversarial tasks (`is_adversarial: True`) are excluded from the positive repair ablation because their correct behavior is policy rejection, not code repair.
- Any task marked `is_eligible: False` is excluded.

---

## 6. Metrics & Statistical Analysis Plan

### 6.1 Primary Metric
- **Eligible Repair Pass Rate:**
  $$\text{Pass Rate} = \frac{\sum_{i=1}^N \mathbf{1}(Y_i = 1)}{N}$$
  Reported with 95% Wilson Score Confidence Intervals.

### 6.2 Secondary Metrics
1. **Mean Attempt Expenditure (All Tasks):** Average attempts executed across all 15 tasks (1 to 3).
2. **Mean Attempts to Success (Passed Only):** Average attempts conditioned on `passed == True`.
3. **Median Task Latency:** Standard mathematical median ($p50$) duration in milliseconds.
4. **Token Consumption:** Input, output, and total tokens per task and condition.
5. **Patch Formatting Integrity:** Frequency of malformed patch rejections by `DeterministicJudge`.

### 6.3 Handling of Special Outcomes
- **`BLOCKED` (Patch Syntax Error):** Counted as a repair failure (`passed: false`). The model exhausted an attempt without producing an applicable patch.
- **`TIMED_OUT` (Pytest Timeout > 45s):** Counted as a repair failure (`passed: false`).
- **`INFRASTRUCTURE_ERROR` (Groq API 500 / Network Disconnect):**
  - Evaluator retries transient API errors up to 3 times with exponential backoff.
  - If unrecoverable, the affected task is flagged `INFRASTRUCTURE_ERROR`.
  - To preserve paired comparison validity, if task $t_i$ suffers an infrastructure abort in either condition, the pair $(Y_i^{\text{flywheel}}, Y_i^{\text{naive}})$ is rerun or marked incomplete and excluded from paired concordance.

---

## 7. Resource Ceilings, Rate Limiting, and Governance Gate

### 7.1 Resource Caps
- **Maximum Attempt Budget:** $15 \text{ tasks} \times 2 \text{ conditions} \times 3 \text{ max attempts} = \mathbf{90\text{ max LLM calls}}$.
- **Estimated Calls:** ~40–50 LLM calls (due to early stopping on pass).
- **Token Budget Ceiling:** 60,000 total tokens (~4,000 tokens per task pair).
- **Financial Cost Ceiling:** $\$0.10\text{ USD}$ (fully covered under Groq developer free tier).
- **Rate-Limit Pacing:** 3.0-second mandatory inter-request delay to prevent HTTP 429 rate limit errors on Groq.

### 7.2 Formal Stop/Go Audit Verdict
- **Audit Recommendation:** **`GO (PROTOCOL APPROVED)`**.
- The Phase 5.1 audit verified that test harnesses, fixture isolation, deterministic judging, and secret redactions are completely solid.
- **Execution Condition:** Phase 6 shall NOT execute automatically. It requires explicit user command:
  ```powershell
  python scripts/run_agent_eval.py --repeat 1 --ablation --output artifacts/v0_11/phase6_live_llm_15tasks.json
  ```
