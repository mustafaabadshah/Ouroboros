# Project Ouroboros — Phase 5.1 Metric Reconciliation
## Independent Recalculation, Mathematical Reconciliation, and Discrepancy Analysis

**Document Status:** `AUTHORITATIVE MATHEMATICAL RECONCILIATION`  
**Execution Timestamp:** `2026-10-18T20:10:00+05:00`  
**Author:** ML Systems Auditor & Research Methodology Reviewer  
**Primary Source of Truth:** Raw Evaluation JSON at [`artifacts/v0_11/phase5_live_llm_pilot_4tasks.json`](file:///E:/MM%20Office/Ouroboros/artifacts/v0_11/phase5_live_llm_pilot_4tasks.json)  
**Byte-Identical Archive:** [`artifacts/evaluations/20261018_104036_agent_eval/agent_eval_run.json`](file:///E:/MM%20Office/Ouroboros/artifacts/evaluations/20261018_104036_agent_eval/agent_eval_run.json)  
**Verified SHA-256 Digest:** `eff1e9c1088db86ee717b0d7a3645a200dc1398e114a5ce3e3a4471f14d33442`

---

## 1. Executive Summary of Recalculated Metrics

Every reported metric from Phase 5 was independently recalculated directly from the raw task and attempt observations. The summary table below compares the originally reported values against the authoritative recalculated values:

| Metric Name | Phase 5 Reported Value | Authoritative Recalculated Value | Status / Reconciled Explanation |
| :--- | :---: | :---: | :--- |
| **SHA-256 Digest** | `86f9e31d4597bce...` | `eff1e9c1088db86ee717b0d7a3645a200dc1398e114a5ce3e3a4471f14d33442` | **RECONCILED**: Stated hash was a documentation typo. Verified digest computed on raw file. |
| **Total Tasks Evaluated** | 4 | 4 | **VERIFIED EXACT** |
| **Complete Paired Tasks** | 4 | 4 | **VERIFIED EXACT** |
| **Flywheel Pass Rate** | 4 / 4 (100.0%) | 4 / 4 (100.0%) | **VERIFIED EXACT** |
| **Naive Retry Pass Rate** | 1 / 4 (25.0%) | 1 / 4 (25.0%) | **VERIFIED EXACT** |
| **Success Rate Delta ($\Delta$)** | +75.0 pp | +75.0 pp | **VERIFIED EXACT** |
| **Flywheel Wilson 95% CI** | `[0.5101, 1.0000]` | `[0.5101, 1.0000]` | **VERIFIED EXACT** |
| **Naive Retry Wilson 95% CI** | `[0.0456, 0.6994]` | `[0.0456, 0.6994]` | **VERIFIED EXACT** |
| **Flywheel Mean Attempts** | 2.00 | **2.00** (all tasks) / **2.00** (passed tasks) | **VERIFIED EXACT** |
| **Naive Mean Attempts** | 1.00 | **2.50** (all tasks) / **1.00** (passed tasks) | **RECONCILED**: 1.00 reflects passed tasks only. Across all tasks, naive mean is 2.50. |
| **Flywheel Latency p50** | 150,779 ms | **150,779 ms** (code `durations[len//2]`) / **121,027.5 ms** (math median) | **RECONCILED**: Codebase uses upper-index integer division (`4//2 = 2`). |
| **Naive Latency p50** | 92,940 ms | **92,940 ms** (code `durations[len//2]`) / **92,738.5 ms** (math median) | **RECONCILED**: Codebase uses upper-index integer division (`4//2 = 2`). |
| **Total Tokens Consumed** | 11,161 tokens | 11,161 tokens (7,979 in, 3,182 out) | **VERIFIED EXACT** |
| **Invoiced API Spend** | $0.00 USD | $0.00 USD | **VERIFIED EXACT** (Groq free developer tier) |
| **Discordant Pairs ($b, c$)** | $b = 3, c = 0$ | $b = 3, c = 0$ | **VERIFIED EXACT** |
| **Exact McNemar $p$-value** | $p = 0.125$ | **0.1250** (one-tailed) / **0.2500** (two-tailed) | **RECONCILED**: Report stated one-tailed $p=0.125$. Two-tailed is $p=0.250$. |

---

## 2. Deep Reconciliation of Identified Discrepancies

### 2.1 The Attempt Count Discrepancy (2.00 vs 1.00 vs 2.50)

#### Observation in Raw Data:
- `flywheel_escalation` attempts: `[2, 3, 1, 2]`
- `naive_retry` attempts: `[3, 3, 1, 3]`

#### Mathematical Derivations:
1. **Definition A: Mean Attempts Across All Evaluated Tasks**
   $$\bar{A}_{\text{all}} = \frac{1}{N} \sum_{i=1}^N A_i$$
   - `flywheel_escalation`: $\frac{2 + 3 + 1 + 2}{4} = \frac{8}{4} = \mathbf{2.00}$
   - `naive_retry`: $\frac{3 + 3 + 1 + 3}{4} = \frac{10}{4} = \mathbf{2.50}$

2. **Definition B: Mean Attempts to Success (Conditioned on `passed == True`)**
   $$\bar{A}_{\text{passed}} = \frac{1}{|\mathcal{S}|} \sum_{i \in \mathcal{S}} A_i \quad \text{where } \mathcal{S} = \{i : \text{passed}_i = \text{True}\}$$
   - `flywheel_escalation`: All 4 tasks passed $\implies \mathcal{S} = \{\text{BENCH-05, 13, 14, 15}\}$.  
     $\bar{A}_{\text{passed}} = \frac{2 + 3 + 1 + 2}{4} = \mathbf{2.00}$
   - `naive_retry`: Only 1 task passed (`BENCH-14`, which passed on Attempt 1) $\implies \mathcal{S} = \{\text{BENCH-14}\}$.  
     $\bar{A}_{\text{passed}} = \frac{1}{1} = \mathbf{1.00}$

#### Discrepancy Reconciliation:
The Phase 5 report stated:
> "Mean Attempts to Success:
> - `flywheel_escalation`: 2.00 attempts (among passed tasks: Attempt 1 = 1, Attempt 2 = 2, Attempt 3 = 1).
> - `naive_retry`: 1.00 attempts (only 1 task passed, on cold Attempt 1)."

**Methodological Implication:**  
Conditioning attempt count on success introduces extreme **survivorship bias**. Under this conditioned definition, a strategy that fails 99% of tasks on attempt 3 but gets lucky on a single attempt 1 task would report a "mean attempts" of 1.00, appearing superficially more efficient than a strategy that successfully repairs 100% of tasks in 2 attempts!  
**Authoritative Standard:** Both metrics must be reported with explicit labels:
- **Attempt Budget Expenditure (All Tasks):** Flywheel = **2.00**, Naive = **2.50**. (Flywheel was 20% more attempt-efficient).
- **Attempts to Success (Passed Only):** Flywheel = **2.00**, Naive = **1.00** ($N=1$).

---

### 2.2 Latency Reconciliation (Code Indexing vs Standard Mathematical Median)

#### Observation in Raw Data:
- `flywheel_escalation` task durations (ms):
  $$\text{Raw: } [170538, 150779, 45856, 91276]$$
  $$\text{Sorted: } [45856, 91276, 150779, 170538]$$
- `naive_retry` task durations (ms):
  $$\text{Raw: } [137862, 92940, 44455, 92537]$$
  $$\text{Sorted: } [44455, 92537, 92940, 137862]$$

#### Reconciliation Analysis:
In [`backend/app/evaluation/agent_evaluator.py`](file:///E:/MM%20Office/Ouroboros/backend/app/evaluation/agent_evaluator.py#L620-L623):
```python
durations = [r["duration_ms"] for r in results if r.get("duration_ms", 0) > 0]
durations.sort()
p50 = durations[len(durations) // 2] if durations else 0
```
For an array of even length $N = 4$:
- `len(durations) // 2` evaluates to `4 // 2 = 2`.
- `durations[2]` selects the **3rd sorted element** (0-indexed: `[0, 1, 2, 3]`).
- For Flywheel: `durations[2] = 150,779 ms`.
- For Naive: `durations[2] = 92,940 ms`.

In standard mathematical statistics, the median of an even-sized sample $x_{(1)} \le x_{(2)} \le x_{(3)} \le x_{(4)}$ is defined as:
$$\text{Median} = \frac{x_{(2)} + x_{(3)}}{2}$$
- For Flywheel: $\frac{91276 + 150779}{2} = \mathbf{121,027.5\text{ ms}}$
- For Naive: $\frac{92537 + 92940}{2} = \mathbf{92,738.5\text{ ms}}$

For completeness, the arithmetic means are:
- Flywheel Arithmetic Mean: $\frac{45856 + 91276 + 150779 + 170538}{4} = \mathbf{114,612.2\text{ ms}}$
- Naive Arithmetic Mean: $\frac{44455 + 92537 + 92940 + 137862}{4} = \mathbf{91,948.5\text{ ms}}$

| Condition | Code Implementation (`durations[len//2]`) | Standard Mathematical Median | Arithmetic Mean |
| :--- | :---: | :---: | :---: |
| **`flywheel_escalation`** | **150,779 ms** | **121,027.5 ms** | **114,612.2 ms** |
| **`naive_retry`** | **92,940 ms** | **92,738.5 ms** | **91,948.5 ms** |

**Conclusion:** The discrepancy was caused entirely by 0-indexed integer division `4 // 2 = 2` selecting the upper middle element instead of interpolating the two middle elements. Both figures are mathematically accounted for.

---

### 2.3 Token Accounting Recalculation

Each task's token usage was extracted from `task_results`:

#### Flywheel Condition:
- `BENCH-05`: 943 in, 228 out = 1,171 tokens
- `BENCH-13`: 1,707 in, 482 out = 2,189 tokens
- `BENCH-14`: 411 in, 205 out = 616 tokens
- `BENCH-15`: 1,033 in, 478 out = 1,511 tokens
- **Subtotal:** Input = **4,094 tokens**, Output = **1,393 tokens**, Total = **5,487 tokens**.

#### Naive Baseline Condition:
- `BENCH-05`: 1,098 in, 510 out = 1,608 tokens
- `BENCH-13`: 1,169 in, 563 out = 1,732 tokens
- `BENCH-14`: 409 in, 204 out = 613 tokens
- `BENCH-15`: 1,209 in, 512 out = 1,721 tokens
- **Subtotal:** Input = **3,885 tokens**, Output = **1,789 tokens**, Total = **5,674 tokens**.

#### Grand Totals Across Evaluation:
- **Input Tokens:** $4094 + 3885 = \mathbf{7,979\text{ tokens}}$
- **Output Tokens:** $1393 + 1789 = \mathbf{3,182\text{ tokens}}$
- **Grand Total:** $7979 + 3182 = \mathbf{11,161\text{ tokens}}$
- **API Invoiced Spend:** $\$0.00\text{ USD}$ (completed within Groq free developer tier).

The token totals reported in Phase 5 are **verified 100% exact**.

---

### 2.4 Verdict Semantics: BENCH-15 Naive Condition ("BLOCKED")

In the Phase 5 report table, `BENCH-15` naive retry was displayed with verdict `BLOCKED`.

#### Investigation of Attempt History in Raw JSON:
- **Attempt 1:** Executed `pytest`. Failed: `AssertionError: assert {'index': 1, ...} == {'index': 1, ...}` (missing `{'item': -2}`). Verdict: `FAIL`.
- **Attempt 2:** Executed `pytest`. Failed identical assertion (missing `{'item': -2}`). Verdict: `FAIL`.
- **Attempt 3:** Model generated invalid patch syntax without standard unified diff headers `--- a/...` and `+++ b/...`.
  - The patch was parsed by `DeterministicJudge._validate_patch_headers(patch)`.
  - Judge raised validation failure: `Malformed patch: Could not identify valid unified diff headers (--- a/..., +++ b/...) or no modifications found.`
  - Attempt 3 verdict recorded: `BLOCKED` (blocked by deterministic judge patch validator).
- **Task-Level Aggregation:**
  - `attempts_executed`: **3**
  - `passed`: **false**
  - `outcome`: **`FAILED_REPAIR`**

#### Clarification of Semantics:
1. `BLOCKED` in Attempt 3 was **not** an infrastructure crash, network timeout, or evaluation engine abort.
2. It was a deterministic rejection of a malformed patch generated by an unguided LLM that lost formatting discipline on Attempt 3.
3. The task exhausted its allotted budget of 3 attempts without producing a passing repair.
4. It was correctly counted in the denominator of attempted repairs and correctly classified as a repair failure (`FAILED_REPAIR`).

---

### 2.5 Paired Concordance & Exact Statistical Tests ($N = 4$)

#### 2x2 Paired Concordance Table:

| | **Naive Retry Pass** | **Naive Retry Fail** | **Total Flywheel** |
| :--- | :---: | :---: | :---: |
| **Flywheel Pass** | $a = 1$ (`BENCH-14`) | $b = 3$ (`BENCH-05, 13, 15`) | 4 |
| **Flywheel Fail** | $c = 0$ | $d = 0$ | 0 |
| **Total Naive** | 1 | 3 | **$N = 4$** |

#### McNemar Exact Test Derivation:
- Discordant pairs: $n = b + c = 3 + 0 = 3$.
- Under null hypothesis $H_0$: each discordant pair is equally likely to favor either strategy ($p = 0.5$).
- Probability of observing $b \ge 3$ successes out of $n = 3$ trials:
  $$P(X \ge 3 \mid n=3, p=0.5) = \binom{3}{3} (0.5)^3 = 1 \times 0.125 = \mathbf{0.1250} \quad \text{(one-tailed)}$$
- Two-tailed exact $p$-value:
  $$p_{\text{two-tailed}} = 2 \times 0.1250 = \mathbf{0.2500}$$

#### Epistemic Conclusion on Statistical Significance:
- Because $p = 0.2500 > 0.05$, the pilot **does not achieve statistical significance** under standard scientific criteria.
- Even if all 4 tasks had favored Flywheel ($b = 4, c = 0$), the two-tailed binomial probability would be $2 \times (0.5)^4 = 0.1250 > 0.05$.
- **Theorem:** An evaluation with $N \le 5$ tasks cannot mathematically reject $H_0$ at $\alpha = 0.05$ under a two-tailed McNemar test (minimum discordant sample size for two-tailed significance is $n = 6$, where $2 \times 0.5^6 = 0.03125$).
- Therefore, Phase 5 provides **qualitative and directional proof-of-concept**, but Phase 6 must evaluate a sufficiently large task suite ($N \ge 15$) to achieve statistical power.
