# Ouroboros v0.10: Deterministic Repair Benchmark Suite

## Overview & Mission

The Ouroboros Deterministic Repair Benchmark Suite provides an auditable, reproducible, and standardized test harness for automated software repair workflows. It expands the initial synthetic evaluation from 2 eligible repair tasks to **15 deterministic eligible repair tasks** across 5 distinct defect categories, while strictly isolating **1 adversarial security evaluation task** (16 tasks total).

### Goals
- **Deterministic Evaluation:** Self-contained, reproducible Python bug-fix fixtures with zero flaky assertions, zero external network calls, and zero external API/token dependencies.
- **Explicit Denominators:** Strict separation between eligible repair tasks, adversarial security tasks, timeouts, and infrastructure failures. No metric ever silently uses an implicit or inaccurate denominator.
- **Fail-Closed Security Isolation:** Adversarial attacks (e.g. attempting to touch `.env` or secrets) are classified as `BLOCKED_BY_POLICY` and explicitly excluded from repair success calculations.
- **Memory Ablation Measurement:** Matched trial comparisons between FailureFlywheel persistent memory retrieval (`memory_enabled=True`) and unassisted baseline repairs (`memory_enabled=False`).

### Non-Goals
- Artificial inflation of repair percentages by counting security-blocked tasks as repairs.
- Evaluating ungrounded, non-deterministic model calls without an audited baseline.
- Replacing comprehensive live container isolation qualification.

---

## Benchmark Catalog (16 Tasks)

| Task ID | Human-Readable Title | Category | Difficulty | Target File | Expected Defect Contract |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **BENCH-01** | Input Validation Boundary Guard | `boundary_and_edge_case` | small | `utils/input_parser.py` | Reject non-positive integers (`<= 0`) by raising `ValueError` |
| **BENCH-04** | Numeric Boundary Clamping | `boundary_and_edge_case` | small | `math_utils/bounds.py` | Enforce `low <= high` and correctly clamp values below lower boundary |
| **BENCH-05** | Pagination Window Slice Calculator | `boundary_and_edge_case` | small | `pagination/paginator.py` | Enforce positive parameters and 0-based offset calculation for 1-based page numbers |
| **BENCH-06** | Nested Dictionary Key Traversal | `type_and_interface` | small | `utils/dict_traversal.py` | Guard against missing intermediate keys and non-dict nodes with default fallback |
| **BENCH-07** | Configuration Value Coercer | `type_and_interface` | small | `config/coercer.py` | Accurately parse case-insensitive boolean string representations (`false`, `0`, `off`) |
| **BENCH-08** | Event Dispatcher Signature Adapter | `type_and_interface` | medium | `events/dispatcher.py` | Inspect handler signatures and filter kwargs for handlers without `**kwargs` |
| **BENCH-09** | Cross-Module Entity Loader | `multi_file_and_state` | medium | `services/loader.py` | Resolve entity class across modules and pass required constructor parameters |
| **BENCH-10** | Workflow State Machine Transitions | `multi_file_and_state` | medium | `workflow/state_machine.py` | Guard state transitions against invalid moves in finite-state graph |
| **BENCH-11** | Token Bucket Rate Limiter Shared State | `multi_file_and_state` | medium | `rate_limiter/bucket.py` | Isolate instance state from mutable class-level token pools |
| **BENCH-12** | ISO Timestamp Normalizer | `serialization_and_parsing` | medium | `datetime_utils/iso_parser.py` | Normalize ISO 8601 strings, 'Z' suffixes, and timezone offsets to `timezone.utc` |
| **BENCH-13** | JSON Config Parser and Fallback | `serialization_and_parsing` | small | `json_parser/safe_loader.py` | Handle syntax errors and invalid input types returning `(fallback, error_msg)` |
| **BENCH-14** | SemVer Tag Regex Extractor | `serialization_and_parsing` | medium | `semver/parser.py` | Extract major, minor, patch, and prerelease versions supporting optional 'v' prefix |
| **BENCH-02** | Arithmetic Exponentiation Repair | `logic_and_exception` | small | `math_ops.py` | Implement missing power function using exponentiation operator `**` |
| **BENCH-15** | Batch Record Processor Error Propagation | `logic_and_exception` | medium | `batch/processor.py` | Capture per-record errors with index, input, and exception message |
| **BENCH-16** | Idempotent Transaction Tracker | `logic_and_exception` | medium | `transactions/registry.py` | Deduplicate repeated transactions returning cached execution outcomes |
| **BENCH-03** | Adversarial Protected File Boundary Attack | `security` | adversarial | `.env` | Static boundary policy rejection when patch attempts secret file modification |

---

## Metric Definitions & Formulas

The benchmark engine computes verifiable metrics using explicit denominators:

1. **Eligible Repair Success Rate:**
   $$\text{Eligible Repair Success Rate} = \frac{\text{Eligible Passed Tasks}}{\text{Eligible Repair Tasks}}$$
   *Note: If `Eligible Repair Tasks == 0`, the metric evaluates to `null` (`None`). It is never silently reported as 0.0%.*

2. **Adversarial Block Rate:**
   $$\text{Adversarial Block Rate} = \frac{\text{Adversarial Blocked Tasks}}{\text{Adversarial Tasks}}$$
   *Note: If `Adversarial Tasks == 0`, the metric evaluates to `null`.*

3. **Raw Suite Success Rate:**
   $$\text{Raw Success Rate} = \frac{\text{All Passed Tasks}}{\text{Total Tasks Evaluated}}$$

4. **Task Outcome Distinctions:**
   Each task execution is classified into exactly one mutually exclusive outcome:
   - `PASSED_REPAIR`: Eligible repair task passed all acceptance tests.
   - `FAILED_REPAIR`: Eligible repair task failed candidate test execution.
   - `BLOCKED_BY_POLICY`: Patch attempted boundary violation on protected path.
   - `TIMED_OUT`: Test execution exceeded configured per-task timeout.
   - `INFRASTRUCTURE_ERROR`: Error in git worktree or environment initialization.

---

## Execution Modes & Commands

All commands run through the project virtual environment:

### 1. Fixture Validation Mode (Ground Truth Verification)
Validates that each fixture's baseline test passes, initial defect is reproduced, and reference repair passes:
```powershell
.\.venv\Scripts\python.exe scripts/run_benchmarks.py --validate-fixtures
```

### 2. Single Task Execution
Run a specific task by its unique identifier:
```powershell
.\.venv\Scripts\python.exe scripts/run_benchmarks.py --task-id BENCH-04
```

### 3. Category Filtered Execution
Run all tasks belonging to a specific category:
```powershell
.\.venv\Scripts\python.exe scripts/run_benchmarks.py --category boundary_and_edge_case --eligible-only
```

### 4. Adversarial Security Isolation Run
Run only the adversarial security evaluation tasks:
```powershell
.\.venv\Scripts\python.exe scripts/run_benchmarks.py --security-only
```

### 5. Memory Ablation Study
Run matched runs across all 16 tasks with memory enabled versus memory disabled:
```powershell
.\.venv\Scripts\python.exe scripts/run_benchmarks.py --ablation --output artifacts/benchmark_results.json
```

---

## Priority 2A: Real Agent Evaluation Engine

While the standard benchmark harness tests deterministic *reference repairs* to ensure bug reproducibility, the **Real Agent Evaluation Engine** evaluates actual AI-generated repairs generated by the full Ouroboros multi-agent pipeline (`Planner`, `LocalCoder`, `RepairAgent`, `DeterministicJudge`, `FailureFlywheel`).

### Core Distinction: Reference Repair vs. Real Agent Evaluation

| Dimension | Deterministic Fixture Validation | Reference Repair Harness | Controlled Mock Double | Real Agent Evaluation Engine |
| :--- | :--- | :--- | :--- | :--- |
| **Command** | `run_benchmarks.py --validate-fixtures` | `run_benchmarks.py` | `run_agent_eval.py --mock-agents` | `run_agent_eval.py` |
| **Patch Source** | Hardcoded ground-truth patch | Reference repair patch | Deterministic mock double | Real LLM synthesized Unified Diff |
| **Pipeline Tested** | Fixture syntax & test contract | Static AST & pytest runner | Orchestration & error handling | Planner -> Coder -> Judge -> Flywheel |
| **External Calls** | Zero network or LLM calls | Zero network or LLM calls | Zero network or LLM calls | Real configured LLM provider |
| **Evaluation Scope** | Validates defects are real | Benchmarks runner overhead | Validates evaluator edge-cases | Measures genuine repair accuracy |

### Multi-Agent Pipeline Lifecycle

For each evaluated task, the engine executes the following lifecycle inside a fresh, disposable Git worktree:
1. **Disposable Worktree Initialization:** Spawns a dedicated git repository and candidate worktree containing the raw defective fixture.
2. **Sandbox Capability Check:** Validates runtime security isolation (`sandbox_detector`). Fails closed to `INFRASTRUCTURE_ERROR` if required containerization is missing.
3. **Multi-Agent Planning Phase:** Invokes `planner_agent.create_plan` with problem statement and acceptance criteria to generate structured subtasks.
4. **Synthesis & Coding Phase:**
   - Attempt 1: `local_coder_agent.generate_patch` synthesizes unified diffs using quantized CPU local model (`qwen2.5-coder:1.5b`) with configured fallback (`qwen/qwen3.8-27b`).
   - Retries (Attempt 2+): `repair_agent.synthesize_repair` consumes root cause hypotheses, prior test failures, and AST trajectories retrieved from `FailureFlywheel`.
5. **Static AST & Boundary Gates:** `DeterministicJudge.evaluate_patch_static` validates unified diff headers, strictly enforces target file boundaries, and blocks prohibited paths (`.env`, secrets, git configurations).
6. **Workspace Application:** Applies candidate diff strictly within the disposable worktree (`GitWorktreeManager.apply_patch`).
7. **Dynamic Verification:** Runs isolated pytest runner on:
   - Acceptance test (must transition from red to green).
   - Baseline regression test (must remain green with zero regressions).
8. **Telemetry & Flywheel Recording:** Captures phase latencies, provider token metrics, attempt histories, and redacts credentials before emitting reports.
9. **Guaranteed Cleanup:** `finally` block tears down disposable worktree and temporary repository without polluting the host repo.

### Real Model & Provider Configuration

The engine relies on Ouroboros's unified `ModelRouter`:
- **Local Runtime:** Ollama endpoint (`http://localhost:11434`) targeting quantized CPU models (`qwen2.5-coder:1.5b`).
- **Remote Fallback:** Groq API endpoint (`GROQ_API_KEY` in environment or `.env`) using `qwen/qwen3.8-27b` with automatic exponential backoff.
- **Mock Double:** Deterministic offline mock provider (`--mock-agents`) for offline verification and unit tests.

### Running Agent Evaluation CLI

The evaluation engine is accessible via `scripts/run_agent_eval.py` (dedicated runner) or `scripts/run_benchmarks.py --agent`:

#### 1. Single Task Live Evaluation
Evaluate a single task through the live agent pipeline:
```powershell
.\.venv\Scripts\python.exe scripts/run_agent_eval.py --task-id BENCH-04
```

#### 2. Matched Memory Ablation Study
Compare live repair performance with FailureFlywheel memory enabled vs. disabled:
```powershell
.\.venv\Scripts\python.exe scripts/run_agent_eval.py --task-id BENCH-04 --ablation
```

#### 3. Category Evaluation
Run all tasks in a category sequentially:
```powershell
.\.venv\Scripts\python.exe scripts/run_agent_eval.py --category boundary_and_edge_case --memory-enabled
```

#### 4. Dry Run & Mock Modes
Validate configuration and worktree scaffolding without making external API calls:
```powershell
.\.venv\Scripts\python.exe scripts/run_agent_eval.py --task-id BENCH-04 --dry-run
.\.venv\Scripts\python.exe scripts/run_agent_eval.py --category boundary_and_edge_case --mock-agents
```

### Outcome Taxonomy & Explicit Denominators

The agent evaluation engine reports mutually exclusive task outcomes:
- `PASSED_REPAIR`: Model generated a patch that passed static security checks, applied cleanly, passed acceptance tests, and maintained baseline tests.
- `FAILED_REPAIR`: Model generated patch failed static checks, git apply, or dynamic tests across all retry attempts.
- `BLOCKED_BY_POLICY`: Patch attempted boundary violation (e.g. adversarial BENCH-03).
- `TIMED_OUT`: Dynamic execution exceeded per-attempt budget.
- `INFRASTRUCTURE_ERROR`: Sandbox execution unavailable or worktree creation failed.
- `PROVIDER_UNAVAILABLE`: API key missing or provider endpoint offline.
- `NOT_RUN`: Task skipped (e.g. during `--dry-run`).

All aggregate metrics use explicit denominators:
$$\text{Attempted Repair Success Rate} = \frac{\text{repairs\_passed}}{\text{tasks\_attempted}}$$
$$\text{Eligible Repair Success Rate} = \frac{\text{repairs\_passed}}{\text{eligible\_tasks}}$$
$$\text{Adversarial Block Rate} = \frac{\text{policy\_blocked}}{\text{adversarial\_tasks}}$$

---

## How to Add a New Deterministic Task

To add a task to the benchmark catalog:
1. Open `backend/app/evaluation/benchmark.py`.
2. Define a new entry in `BENCHMARK_TASKS_V1` with:
   - `task_id`: Unique string prefixed with `BENCH-`.
   - `name`: Short descriptive title.
   - `category`: One of the 5 canonical categories or `security`.
   - `is_eligible`: `True` for repair tasks, `False` for adversarial tasks.
   - `is_adversarial`: `True` for security attacks, `False` for repair tasks.
   - `seed_files`: Dict mapping relative paths to initial file contents.
   - `baseline_test`: Pytest node ID for test passing on initial fixture.
   - `acceptance_test`: Pytest node ID for test failing initially and passing after repair.
   - `flawed_patch`: Unified diff representing a plausible flawed attempt.
   - `repair_patch`: Unified diff representing correct reference repair.
3. Run `validate_suite_consistency` and `test_benchmark_expansion.py` to confirm schema validity and deterministic reproducibility.

---

## Known Limitations & Reproducibility Requirements
- The benchmark runs inside isolated disposable Git worktrees on the local filesystem.
- Test concurrency is strictly bounded to 1 concurrent pytest runner process to prevent resource starvation on 8GB host environments.
- Candidate code evaluation requires a working Python interpreter supporting the project's dependencies (`pytest`).
- When Docker container sandboxing is active, candidate patches execute inside isolated containers with `--network none` and `--read-only` root filesystems.

