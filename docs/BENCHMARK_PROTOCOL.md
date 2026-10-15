# PROJECT OUROBOROS: SWE-BENCH-STYLE BENCHMARK PROTOCOL
**Document Version:** 1.0.0 (Research Specification)  
**Classification:** Empirical Methodology & Evaluation Guidelines  
**Status:** ACTIVE  

---

## 1. Benchmarking Positioning & Scope

Project Ouroboros is an **experimental, hierarchical multi-agent code evolution and repair platform**. It adopts the task structure of **SWE-bench** (problem statement $\to$ patch $\to$ pytest verification $\to$ regression gate), but operates as a developer tool and local repair swarm.

### Honest Research Positioning
* **No Exaggerated Claims:** Ouroboros does not claim 100% autonomous software engineering or official SWE-bench leaderboard comparability unless tasks follow the strict public SWE-bench test split harness.
* **No Fabricated Benchmarks:** All reported metrics must explicitly state task count, pass count, denominator, hardware specification, and whether inference used quantized local CPU or cloud APIs.

---

## 2. Reproducible Fixture Task Matrix

The benchmark test harness (`backend/tests/fixtures/`) validates the swarm against 7 controlled scenarios:

| Task ID | Task Scenario | Expected Behavior | Verification Gate |
| :--- | :--- | :--- | :--- |
| **`TASK-01`** | **Known Good Patch** | Code matches acceptance criteria and introduces no regressions. | Deterministic Judge returns `PASS`. |
| **`TASK-02`** | **Logic Flaw $\to$ Repair** | Initial patch fails assertion. Repair Agent uses failure trajectory to fix on attempt 2. | Attempt 1 `FAIL`, Attempt 2 `PASS`. |
| **`TASK-03`** | **Syntax Invalid Patch** | LLM emits malformed Python syntax or unclosed delimiters. | Static AST check returns `FAIL`. |
| **`TASK-04`** | **Out-of-Scope Modification** | Patch attempts to modify files outside `candidate_files`. | Diff Parser returns `BLOCKED`. |
| **`TASK-05`** | **Security Violation** | Patch invokes `os.system` or imports `socket`. | AST Security Visitor returns `BLOCKED`. |
| **`TASK-06`** | **Repeated Failure Loop** | Patch fails with identical signature twice. | Failure Flywheel returns `REPEATED`, halting loop. |
| **`TASK-07`** | **Regression-Inducing Patch** | Patch fixes target assertion but breaks pre-existing baseline test. | Judge detects $\Delta \text{Failures} > 0$, returns `FAIL`. |

---

## 3. Measured Metrics & Reporting Standards

Every benchmark report must calculate and present:

1. **Resolved Rate ($R$):**
   $$R = \frac{N_{\text{resolved}}}{N_{\text{total}}}$$
   *(Must always report both numerator and denominator, e.g. 11/11).*
2. **First-Attempt Pass Rate ($P_1$):**
   $$P_1 = \frac{N_{\text{attempt}=1}}{N_{\text{total}}}$$
3. **Repair Convergence Rate ($R_{\text{repair}}$):**
   Fraction of initial failures successfully resolved within $\le 3$ retries.
4. **Duplicate Failure Rate ($D$):**
   Frequency with which an agent produces an identical failed diff.
5. **Compute & Resource Profile:**
   - Mean wall-clock time per task (seconds).
   - Mean prompt tokens & completion tokens.
   - Peak physical RAM consumption (MB).

---

## 4. Threats to Validity

* **Data Contamination:** Public benchmark problems appearing in LLM pre-training data.
* **Heuristic Acceptance Criteria:** Tests written by the same model generating the patch can suffer from shared cognitive biases.
* **Hardware Variability:** CPU inference latency fluctuates depending on host background processes. All runs must record host specs and CPU usage.
