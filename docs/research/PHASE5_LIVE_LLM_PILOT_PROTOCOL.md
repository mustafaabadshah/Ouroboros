# Project Ouroboros — Phase 5 Research Protocol
## Controlled Live-LLM Retry-Learning Pilot: `flywheel_escalation` vs. `naive_retry`

**Document Version:** `v1.0.0-draft`  
**Date:** `2026-10-18`  
**Repository Branch:** `hotfix/python-package-discovery`  
**Commit Baseline:** `dd36b27`  
**Execution Environment:** Windows 10 x64, Intel Core i3-7100U (2 cores, 4 threads), 8 GB RAM, Python 3.12.3  

---

## 1. Executive Summary & Scientific Motivation

### 1.1 Background from Phase 4
Phase 4 evaluated the Ouroboros retry orchestration architecture across all 15 positive benchmark repair tasks in `BENCHMARK_TASKS_V1` using a deterministic mock agent provider (`artifacts/v0_11/mock_agent_ablation_15tasks.json`). That evaluation formally verified **Integration Validity** (control flow, retry state machines, AST boundary enforcement, and ephemeral SQLite memory isolation). 

However, Phase 4's forensic sensitivity audit proved that the mock provider responded to the structural presence of prompt markers rather than semantic defect diagnostics. Mock evaluation therefore **does not establish causal failure learning**.

### 1.2 Phase 5 Research Objective
Phase 5 transitions from synthetic mock integration to an empirical pilot with a **real Large Language Model (LLM)**. The primary scientific objective is to determine:

> **Does within-task diagnostic feedback (`flywheel_escalation`) improve autonomous software repair outcomes over an unguided retry baseline (`naive_retry`) when evaluated on genuine defects with a real LLM provider under identical, controlled conditions?**

---

## 2. Experimental Design & Hypotheses

### 2.1 Research Questions
1. **Primary RQ:** Does providing structured failure diagnostics (failed test nodes, traceback tail, assertion failure, expected vs. actual values) significantly increase task-level repair success rate within a 3-attempt budget compared to unguided re-prompting?
2. **Secondary RQ 1 (Efficiency):** Does failure feedback reduce the number of attempts required to achieve a verified repair among successful tasks?
3. **Secondary RQ 2 (First-Attempt Cold Parity):** Do both conditions exhibit identical behavior and success probability on Attempt 1 prior to any diagnostic feedback?
4. **Secondary RQ 3 (Diagnostic Responsiveness):** On Attempts 2 and 3, does the real LLM alter its code synthesis in a manner directly addressing the failure diagnostic rather than repeating previous errors?
5. **Secondary RQ 4 (Regression Invariance):** Does retry learning preserve regression test suite pass rates, or does iterative patch modification increase regression risks?

### 2.2 Operational Hypotheses
- **$H_0$ (Null Hypothesis):** The probability of repair success given failure diagnostics equals the probability of repair success without diagnostics: $P(\text{Success} \mid \text{Flywheel}) = P(\text{Success} \mid \text{Naive Retry})$.
- **$H_1$ (Alternative Hypothesis):** The probability of repair success is higher when grounded failure diagnostics are supplied: $P(\text{Success} \mid \text{Flywheel}) > P(\text{Success} \mid \text{Naive Retry})$.

---

## 3. Independent & Controlled Variables

To guarantee strict scientific validity, the experiment isolates exactly one independent variable while holding all environmental and algorithmic parameters invariant.

| Experimental Parameter | `flywheel_escalation` (Condition A) | `naive_retry` (Condition B) | Control Guarantee |
| :--- | :--- | :--- | :--- |
| **Inference Provider** | Groq Remote API | Groq Remote API | Identical |
| **Model Identifier** | `qwen/qwen3.8-27b` | `qwen/qwen3.8-27b` | Identical |
| **Temperature** | `0.2` | `0.2` | Identical |
| **Attempt 1 Prompt** | Standard `CoderLead` subtask prompt | Standard `CoderLead` subtask prompt | **100% Cold Parity** |
| **Attempt 1 Context** | Zero diagnostic history | Zero diagnostic history | **Identical** |
| **Attempt 2+ Prompt** | `RepairAgent` + Structured Diagnostics | `CoderLead` standard prompt | **Independent Variable** |
| **Attempt 2+ Diagnostics**| Test failures, traceback, assertion, expected/actual | **None** (blind retry) | **Independent Variable** |
| **Task Fixture & Seeds** | Fresh disposable Git worktree per run | Fresh disposable Git worktree per run | **Identical & Isolated** |
| **Maximum Attempt Budget** | Exactly 3 attempts | Exactly 3 attempts | **Identical** |
| **Execution Timeout** | 45s pytest timeout, 60s model timeout | 45s pytest timeout, 60s model timeout | **Identical** |
| **Static AST & Policy Gate** | `DeterministicJudge` AST verification | `DeterministicJudge` AST verification | **Identical** |
| **Acceptance Test Suite** | Benchmark-specific pytest suite | Benchmark-specific pytest suite | **Identical** |
| **Baseline Regression Suite**| Benchmark-specific pytest suite | Benchmark-specific pytest suite | **Identical** |
| **Ephemeral Memory State** | Brand new SQLite `:memory:` DB per task | Brand new SQLite `:memory:` DB per task | **Zero Cross-Task Leakage** |

---

## 4. Task Selection: 4-Task Bounded Pilot Suite

A bounded 4-task pilot was selected to balance category diversity, defect representation, and strict budget conservation.

| Task ID | Task Name | Category | Difficulty | Target File | Bug Description |
| :--- | :--- | :--- | :---: | :--- | :--- |
| **`BENCH-05`** | Pagination Window Slice Calculator | `boundary_and_edge_case` | `small` | `pagination/paginator.py` | 0-based offset computed incorrectly for 1-based page numbers; missing non-positive parameter validation. |
| **`BENCH-13`** | JSON Config Parser and Fallback | `serialization_and_parsing` | `small` | `json_parser/safe_loader.py` | Crashes with `JSONDecodeError` / `TypeError` on invalid input instead of returning `(fallback, error_msg)` tuple. |
| **`BENCH-14`** | SemVer Tag Regex Extractor | `serialization_and_parsing` | `medium` | `semver/parser.py` | Regex fails to capture optional `v` prefix and prerelease tags (`-rc2`). |
| **`BENCH-15`** | Batch Record Processor Error Propagation | `logic_and_exception` | `medium` | `batch/processor.py` | Swallows all exceptions silently; fails to record failed indices and error strings. |

### Suitability Criteria:
1. **Category Breadth:** Spans 3 of the 5 benchmark categories.
2. **Deterministic Fast Execution:** Each test suite completes in $< 1.0$ second on host hardware.
3. **No External Dependencies:** All four tasks rely strictly on Python 3.12 standard library modules (`json`, `re`, `typing`).
4. **Verified Fixtures:** All four tasks have verified flawed patches (failing 100% of acceptance assertions) and verified repair patches (passing 100% of acceptance and regression assertions).

---

## 5. Execution Protocol & Budget Bounds

### 5.1 Request and Token Budget Accounting
- **Total Tasks:** 4 tasks (`BENCH-05`, `BENCH-13`, `BENCH-14`, `BENCH-15`).
- **Total Conditions:** 2 (`flywheel_escalation`, `naive_retry`).
- **Total Task Runs:** $4 \times 2 = 8$ task observations.
- **Max Model Turns per Task:**
  - Planning turn: 1 call.
  - Coding attempts: up to 3 calls.
  - Maximum calls per task: 4 calls.
- **Maximum Total API Calls:** $8 \times 4 = 32$ requests.
- **Token Estimation:**
  - Average prompt length: ~800 tokens.
  - Average completion length: ~250 tokens.
  - Total prompt tokens: $\approx 25,600$.
  - Total completion tokens: $\approx 8,000$.
  - Total token budget: $\approx 33,600$ tokens ($\approx 0.034$ M tokens).
- **Projected Financial Cost:**
  - Groq `qwen/qwen3.8-27b` pricing: Under free developer quota ($0.00) or $\le \$0.02$ total spend.
  - **Hard Cost Ceiling:** $\$1.00$ USD (run automatically halts if usage exceeds 50,000 tokens).

### 5.2 Condition Balancing & Order Schedule
To eliminate systematic temporal bias, network congestion artifacts, or host background contention, task conditions are interleaved:
1. `BENCH-05`: Condition A (`flywheel_escalation`) then Condition B (`naive_retry`).
2. `BENCH-13`: Condition B (`naive_retry`) then Condition A (`flywheel_escalation`).
3. `BENCH-14`: Condition A (`flywheel_escalation`) then Condition B (`naive_retry`).
4. `BENCH-15`: Condition B (`naive_retry`) then Condition A (`flywheel_escalation`).

---

## 6. Telemetry, Observability & Secret Protection

1. **Arize Phoenix Tracing:**
   - Active on `http://127.0.0.1:6006` with OpenTelemetry collector endpoint `http://127.0.0.1:6006/v1/traces`.
   - Each model turn exports agent spans capturing role, task name, model identifier, latency, prompt tokens, completion tokens, and status.
   - If the Phoenix collector becomes unreachable, telemetry automatically degrades gracefully to local in-memory recording without interrupting or failing evaluations.
2. **Secret Redaction:**
   - Prompt text and error outputs pass through `redact_sensitive_strings`.
   - API keys matching `gsk_[a-zA-Z0-9]{20,}` are masked as `[REDACTED_GROQ_KEY]`.
   - Bearer tokens are masked as `[REDACTED_TOKEN]`.
   - No secrets are ever written to JSON evaluation artifacts or console logs.

---

## 7. Artifact Preservation & Immutability

All pilot artifacts must be written to an immutable timestamped directory:
```
artifacts/evaluations/<YYYYMMDD_HHMMSS>_phase5_live_llm_pilot/
├── live_pilot_run.json              # Complete machine-readable attempt-level telemetry
├── manifest.json                    # Task definition hashes, git SHA, and environment metadata
├── comparison_summary.json          # Paired outcome matrix and statistical analysis
└── phoenix_traces_summary.json      # OTLP span identifiers and latency metrics
```
Historical Phase 4 artifacts (`artifacts/v0_11/mock_agent_ablation_15tasks.json`) and Phase 3 checkpoints are protected and will never be overwritten.
