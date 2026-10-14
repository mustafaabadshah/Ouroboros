# Project Ouroboros: Deterministic Evaluation & Regression Protocol
**Document ID:** EVAL-OURO-001  
**Authority:** Deterministic Judge (Host Python Engine)  

---

## 1. Evaluation Methodology

The core tenet of Project Ouroboros is **empirical determinism**:
> An autonomous agent may never approve its own work, and the system may never claim an improvement unless measured regression gates confirm it.

```
Target Repository Baseline
           │
           ├─► [Phase 1: Baseline Validation]
           │   Execute existing test suite (e.g. 19 tests in Agent Chess).
           │   Record baseline exit codes, duration, and passed test names.
           │
           ├─► [Phase 2: Candidate Patch Application]
           │   Apply candidate diff in isolated Git worktree.
           │   Verify diff syntax, boundaries, and protected paths.
           │
           ├─► [Phase 3: Static AST Inspection]
           │   Parse Python AST; detect added/removed symbols.
           │   Flag modifications to protected engine symbols.
           │
           └─► [Phase 4: Candidate Test & Regression Suite]
               Execute candidate tests + full regression suite.
               Compare candidate test results against baseline outcomes.
               VERDICT: PASS only if regressions == 0 and all tests pass.
```

---

## 2. Regression Policy

A candidate patch is rejected (`FAIL`) under any of the following conditions:
1. **Any Regression in Baseline Tests:** If a test that passed in the baseline fails in the candidate worktree, the patch is rejected immediately.
2. **Pre-existing Baseline Failures:** Failures present in the clean baseline are segregated and not attributed to the candidate, but are flagged in the report.
3. **Protected Path Modifications:** Changes to `backend/app/chess/validator.py`, `stockfish.py`, or security configurations trigger an automatic `BLOCKED` verdict.
4. **Non-deterministic Flakiness:** Any test that exhibits non-deterministic outcomes across identical runs is flagged by `TestAnalystAgent`.

---

## 3. Judge Verdict Taxonomies

The `DeterministicJudge` produces an immutable, machine-readable verdict:

| Verdict | Meaning | Next Swarm Action |
| :--- | :--- | :--- |
| **`PASS`** | Patch applies cleanly; AST analysis passes; zero regressions; acceptance tests pass. | State transitions to `AWAITING_APPROVAL`. Human operator notified. |
| **`FAIL`** | Patch caused a test failure or regression. | Failure trajectory recorded in SQLite. Flywheel dispatches `RepairAgent`. |
| **`BLOCKED`** | Patch violates security policies (protected file edit, path traversal). | Execution halted immediately; no repair attempted. |
| **`NEEDS_HUMAN_REVIEW`** | Complex AST alterations detected on critical interfaces. | Pauses for human operator inspection. |

---

## 4. Persistent Failure Flywheel Protocol

When a test failure occurs during an evaluation cycle:
1. **Capture:** The judge extracts:
   - Failed test name and line number
   - Exact traceback excerpt
   - AST diff summary
   - Patch hash
2. **Persist:** A new record is inserted into SQLite table `failure_trajectories`.
3. **Analyze:** The flywheel queries prior attempts for the same ticket:
   - If the same error occurred in Attempt 1 and Attempt 2, it flags `repeated_failure = True`.
4. **Feed Forward:** The `RepairAgent` prompt receives the exact failure traceback, avoiding repetition of rejected patch strategies.
