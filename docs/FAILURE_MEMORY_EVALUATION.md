# PROJECT OUROBOROS — FAILURE MEMORY EMPIRICAL EVALUATION
**Document Reference:** `docs/FAILURE_MEMORY_EVALUATION.md`
**Classification:** Empirical Research Report & Ablation Study
**Version:** 1.0.0
**Status:** ACTIVE
**Last Updated:** October 15, 2026

---

## 1. Executive Summary

A persistent challenge in autonomous software repair is the **hallucinatory failure loop**, where an LLM repeatedly proposes semantically identical flawed patches across sequential retries.

The **Failure Memory Flywheel** (`FailureFlywheel` in `backend/app/memory/flywheel.py`) provides structured, persistent institutional memory by capturing:
1. Failed test names and assertions.
2. Sanitized traceback excerpts (masked against credential leakage).
3. Cryptographic patch hashes (`SHA-256`) of rejected diffs.
4. Structured AST modifications.
5. Root-cause hypotheses and repair hints.

This report summarizes the empirical ablation results comparing **Memory-Enabled** versus **Memory-Disabled** execution across standardized benchmark tasks.

---

## 2. Experimental Setup & Controls

To eliminate confounding variables, ablation runs adhere to the following controls:
* **Hardware & Runtime:** Windows 10 x64, Python 3.12.3 in isolated `.venv`, 8 GB RAM, Intel HD 620.
* **Deterministic Seeds:** Fixed mock and local prompt templates; temperature = 0.0.
* **Isolated Disposable Repositories:** Each task runs in a freshly initialized, pristine Git repository (`tempfile.mkdtemp`).
* **Identical Tasks:** Evaluated against `BENCHMARK_TASKS_V1` (`BENCH-01`, `BENCH-02`, `BENCH-03`).
* **Resource Budgets:** Maximum 3 repair attempts per task; 20-second execution timeout per pytest invocation.

---

## 3. Empirical Results & Comparative Matrix

### 3.1 Overall Task Outcomes
| Condition | Total Tasks | Passed | Blocked | Failed | Success Rate (All) | Success Rate (Eligible) |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: |
| **Memory Enabled** | 3 | 2 | 1 | 0 | 66.7% | **100.0%** (2/2) |
| **Memory Disabled**| 3 | 2 | 1 | 0 | 66.7% | **100.0%** (2/2) |

*Note on Denominators:* `BENCH-03` is an adversarial protected-file attack targeting `.env`. Its expected and correct terminal outcome is `BLOCKED`. It is correctly excluded from the repair-success denominator.

### 3.2 Latency & Execution Efficiency
| Metric | Memory Enabled | Memory Disabled (Ablation) | Variance / Delta |
| :--- | :---: | :---: | :---: |
| **Median Duration (P50)** | **5,806 ms** | **6,180 ms** | -374 ms (-6.0%) |
| **Total Suite Duration** | 12,884 ms | 13,320 ms | -436 ms (-3.3%) |
| **BENCH-01 (Input Validation)** | 6,183 ms | 6,290 ms | -107 ms |
| **BENCH-02 (Logic Repair)** | 5,806 ms | 6,180 ms | -374 ms |
| **BENCH-03 (Adversarial)** | 895 ms | 850 ms | +45 ms (noise) |

### 3.3 Repetition Detection & Flywheel Telemetry
* **Repeated Failures Detected:** 1 (verified in `test_failure_flywheel_persistence_and_deduplication`).
* **Repeated Loop Halts:** When an identical patch hash and test failure are observed, status is marked `REPEATED` and further redundant execution is preempted.

---

## 4. Scientific Qualifications & Honest Limitations

1. **Sample Size Limitations:**
   - The current smoke benchmark comprises 3 deterministic tasks (2 repair-eligible, 1 adversarial).
   - While latency reductions are consistent across multiple runs (ranging between 374 ms and 500 ms savings), **no claim of broad statistical significance ($p < 0.05$) is made** on a 3-task sample.
2. **CPU Execution Variance:**
   - On CPU-only Windows host environments, background OS process scheduling can introduce small timing jitter (± 150 ms).
3. **Recommended Future Work:**
   - Scale ablation runs to 50+ diverse task fixtures under `BENCHMARK_TASKS_V2` across multiple seed permutations to establish statistical confidence intervals.
