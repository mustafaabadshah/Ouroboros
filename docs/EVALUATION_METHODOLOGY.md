# PROJECT OUROBOROS — SCIENTIFIC EVALUATION METHODOLOGY
**Document Reference:** `docs/EVALUATION_METHODOLOGY.md`
**Classification:** Research, Evaluation & Metrics Standard
**Version:** 2.0.0
**Status:** ACTIVE
**Last Updated:** October 15, 2026

---

## 1. Core Principles & Scientific Integrity

The objective of Project Ouroboros' evaluation harness is to provide reproducible, empirically verified, and auditable metrics for autonomous software repair.

### Non-Negotiable Methodological Rules:
1. **Honest Denominators:** Blocked runs (due to missing infrastructure or security policy rejections) must **never** be counted as repair successes, nor should infrastructure unavailability be treated as an ordinary model code-generation failure.
2. **Deterministic Isolation:** Every benchmark task is executed inside an ephemeral disposable Git repository (`tempfile.mkdtemp`), seeded from a known baseline commit, and evaluated using an isolated pytest subprocess or rootless container.
3. **No Solution Leakage:** Prompt generation must never leak ground-truth repair diffs or test assertions into the Coder or Repair Agent's context.
4. **Reproducible Provenance:** Every benchmark record persists commit SHA, suite version, timestamp, configuration fingerprint, attempts count, raw failure traces, and execution latencies.

---

## 2. Standardized Metric Formulations

```
+-------------------------------------------------------------------------------------------------------+
|                                    METRICS FORMULATION TAXONOMY                                       |
+-----------------------------+------------------------------------+------------------------------------+
| Metric Name                 | Mathematical Formula               | Operational Notes                  |
+-----------------------------+------------------------------------+------------------------------------+
| Repair Success Rate         | RSR = N_pass / N_eligible          | Denominator excludes BLOCKED runs  |
| Candidate Test Pass Rate    | TPR = T_pass / T_total             | Unit & acceptance test executions  |
| Regression Rate             | RR  = R_regr / R_total             | Prior passing tests broken by diff |
| Security Rejection Rate     | SRR = S_blocked / S_adversarial    | Correct interception of attacks    |
| Infrastructure Blocked Rate | IBR = N_blocked / N_total          | Missing daemon / offline runtime   |
| Attempts per Repair         | APR = Σ(attempts) / N_pass         | Efficiency of repair flywheel      |
| Latency P50 & P95           | Percentiles of duration_ms         | Wall-clock execution time          |
+-----------------------------+------------------------------------+------------------------------------+
```

### 2.1 Repair Success Rate (RSR)
$$\text{RSR} = \frac{N_{\text{passed}}}{N_{\text{eligible\_attempted}}}$$
Where $N_{\text{eligible\_attempted}}$ encompasses runs that reached candidate evaluation (`COMPLETED`, `FAILED`, `AWAITING_APPROVAL`). Runs blocked pre-execution (e.g., policy rejection or offline daemon) are excluded from the denominator to avoid artificial deflation or inflation.

### 2.2 Correct Security Rejection Rate (SRR)
$$\text{SRR} = \frac{S_{\text{blocked}}}{S_{\text{adversarial\_tasks}}}$$
Measures the defensive fidelity of `DeterministicJudge`, `UnifiedDiffParser`, and `ASTSecurityVisitor` against attacks attempting directory traversal, secret file modification, or prohibited primitive execution.

---

## 3. Benchmark Task Taxonomy

Tasks are versioned and categorized into distinct difficulty tiers:

| Task Category | Description | Primary Verification | Eligible for RSR? |
| :--- | :--- | :--- | :---: |
| **Logic & Arithmetic** | Single-function or algorithmic defect | Acceptance assertions | Yes |
| **Input Validation** | Missing defensive guards, type bounds | Value/Type Error assertions | Yes |
| **Multi-File** | Coordinated changes across multiple modules | Dependent module call sites | Yes |
| **Edge-Case Handling** | Off-by-one, None-dereference, division by zero | Boundary test cases | Yes |
| **Regression Trap** | Patch fixes target but breaks legacy API | Baseline regression suite | Yes |
| **Adversarial / Security**| Protected file edit, traversal, socket access | AST & Path Boundary Gate | No (Expected BLOCKED) |
| **Scope Violation** | Edits files outside ticket candidate list | Boundary parser gate | No (Expected BLOCKED) |

---

## 4. Benchmark Suites

### 4.1 Suite V1 (Smoke & CI Regression Suite)
* **Dataset Version:** `v1.0.0`
* **Task Count:** 3 tasks
* **Tasks:** `BENCH-01` (Input Validation), `BENCH-02` (Arithmetic Logic), `BENCH-03` (Adversarial .env attack).
* **Execution Time:** ~5–12 seconds.
* **Purpose:** High-speed CI gate and pre-commit regression testing.

### 4.2 Suite V2 (Comprehensive Scientific Benchmark)
* **Dataset Version:** `v2.0.0`
* **Task Count:** 20 deterministic tasks (`BENCH-01` through `BENCH-20`).
* **Coverage:** Single-file bugs, multi-file imports, regression traps, off-by-one, null safety, resource limits, CI workflow tampering, AST prohibited primitives, and merge conflicts.
* **Execution Time:** ~45–90 seconds.
* **Purpose:** Controlled ablation testing and release qualification.

---

## 5. Ablation Protocol: Failure Memory Flywheel

To empirically evaluate the impact of the **Failure Memory Flywheel** (`FailureFlywheel`), the test harness supports comparative ablation:
1. **Condition A (Memory Enabled):** Failed candidate tracebacks and AST diffs are recorded. The Repair Agent receives prior attempt trajectories.
2. **Condition B (Memory Disabled):** The Repair Agent generates subsequent patches naively without prior failure context.
3. **Controls:** Identical model parameters, temperature (0.0), task definitions, and initial repository states.
4. **Key Hypotheses Tested:**
   - H1: Memory reduces repeat identical patch proposals.
   - H2: Memory decreases total repair attempts per successful task ($APR$).
   - H3: Memory lowers median time-to-repair on multi-attempt tasks.
