# Project Ouroboros: System Architecture Specification
**Subtitle:** Hierarchical Software Evolution and Deterministic Repair Engine  
**Version:** 1.0.0-rc1  
**Author:** Antigravity Autonomous Systems Architecture Team  

---

## 1. Architectural Philosophy & Hard Physical Constraints

Project Ouroboros is an engineering-first, multi-agent autonomous software evolution swarm designed to execute reliably on consumer-grade hardware under strict memory boundaries.

### Physical Resource Envelope
- **Host OS:** Windows 10/11 x64
- **Processor:** Intel Core with integrated Intel HD Graphics 620 (**Strictly NO CUDA/GPU requirements**)
- **Physical Memory:** 8 GB Total System RAM (~1.38 GB free physical RAM under operational load)
- **Local Model Runtime:** CPU-quantized inference via Ollama (`qwen2.5-coder:1.5b`, 986 MB footprint, 2048 context window)
- **Remote Reasoning Model:** Groq API (`llama-3.3-70b-versatile` and `llama-3.1-8b-instant`)

### Fundamental Invariants
1. **Never mutate baseline branches directly:** Code modifications occur exclusively in isolated Git worktrees.
2. **Never claim unmeasured self-improvement:** Patches are accepted only when deterministic regression tests and AST diff gates pass.
3. **Deterministic State Machine Control:** The workflow controller—not an LLM—decides what state transitions are valid.
4. **Human Merge Gate:** No code is merged into the default branch without explicit human operator confirmation.

---

## 2. High-Level Component Topology

![Project Ouroboros System Architecture](images/architecture_diagram.jpg)

```
+-----------------------------------------------------------------------------------+
|                        React 19 + TypeScript Dashboard                            |
|    - System Telemetry & RAM Meter   - Jira-Style Ticket Management                |
|    - Live SSE Execution Graph       - Side-by-Side Unified Diff Inspection        |
|    - Deterministic Evaluation Lab   - Failure Trajectory Flywheel Browser         |
+------------------------------------------^----------------------------------------+
                                           | HTTP REST / SSE Stream
+------------------------------------------v----------------------------------------+
|                               FastAPI Backend                                     |
|  +--------------------+  +----------------------+  +---------------------------+  |
|  | REST Router Layer  |  | In-Memory SSE Bus    |  | SQLite Persistence Layer  |  |
|  | - /api/health      |  | - State Transitions  |  | - runs, tickets, cand.    |  |
|  | - /api/tickets     |  | - Agent Output Feed  |  | - failure_trajectories    |  |
|  | - /api/runs        |  | - Telemetry Ticks    |  | - audit_events, settings  |  |
|  +---------^----------+  +----------^-----------+  +-------------^-------------+  |
+------------|------------------------|----------------------------|----------------+
             |                        |                            |
+------------v------------------------v----------------------------v----------------+
|                        Workflow State Controller                                  |
|  IDLE -> BASELINE_VALIDATION -> PLANNING -> WORKTREE_ISOLATION                    |
|       -> CODING -> PATCH_VALIDATION -> ACCEPTANCE_TESTS                           |
|       -> REGRESSION_TESTS -> [REPAIR_LOOP] -> AWAITING_APPROVAL -> COMPLETED      |
+------------------------------------------^----------------------------------------+
                                           |
    +--------------------------------------+-----------------------------------+
    |                                      |                                   |
+---v--------------------+       +---------v----------+       +----------------v----+
| Agent Swarm Layer      |       | Evaluation Harness |       | Integration Layer   |
| - ArchitectAgent       |       | - PytestRunner     |       | - MetaGraphAdapter  |
| - PlannerAgent         |       | - Deterministic    |       |   (API->JSON->AST)  |
| - CoderLead            |       |   Judge            |       | - GitWorktreeManager|
| - LocalCoderWorker     |       | - AST Diff Analyzer|       | - UnifiedDiffParser |
| - RepairAgent          |       | - Concurrency Lock |       +---------------------+
+-----------^------------+       +--------------------+
            |
+-----------v--------------------+
| ModelRouter & Guardrails       |
| - Local: Ollama (Qwen 1.5B)    |
| - Remote: Groq (Llama 70B/8B)  |
| - MockProvider (Offline E2E)   |
| - Backend Secret Masking       |
+--------------------------------+
```

---

## 3. Agent Hierarchy & Responsibilities

| Agent Role | Model Provider | Responsibilities | Output Boundary |
| :--- | :--- | :--- | :--- |
| **Architect Agent** | Groq (`llama-3.3-70b-versatile`) | Ingests Meta-Graph AST summaries; identifies bounded tech debt; outputs Jira-style tickets with deterministic pytest acceptance criteria. | Strict Pydantic JSON envelope; zero command execution privileges. |
| **Planner Agent** | Groq / Local Coder | Maps ticket requirements to AST entities, files, imports, and callers; produces ordered subtasks with explicit file ownership. | Subtask list with symbol dependencies and completion conditions. |
| **Coder Lead** | Host Application | Enforces patch scope boundaries; validates file ownership; formats unified diff instructions. | Validated coding prompts with current source code snippets. |
| **Local Coder Worker** | Ollama (`qwen2.5-coder:1.5b`) | Generates focused unified diffs; adheres to file allowlists; runs on quantized CPU inference. | Standard unified diff envelope (`--- a/...`, `+++ b/...`). |
| **Test Analyst** | Host / Groq | Audits acceptance test determinism; flags external network calls, timestamps, or unseeded randomness. | Acceptance test review report. |
| **Repair Agent** | Groq / Local Coder | Ingests exact failure trajectories from SQLite (traceback, AST diff, prior hints); synthesizes targeted fixes. | Minimal replacement patch targeting failed assertions. |
| **Deterministic Judge** | Host Python Code | Ordinary application code (NOT an LLM); runs pytest regression suites; inspects AST changes; produces machine-readable verdicts (`PASS`, `FAIL`, `BLOCKED`). | Immutable evaluation verdict and execution metrics. |

---

## 4. Deterministic State Machine

The workflow state machine is persisted in SQLite across process restarts:

```
[IDLE]
  │
  ├─► [BASELINE_VALIDATION]  (Validates clean baseline test suite)
  │        │
  │        ├─► [PLANNING]    (AST-aware symbol mapping & subtask breakdown)
  │        │        │
  │        │        ├─► [CODING]  (Local coder or repair agent synthesis)
  │        │        │        │
  │        │        │        ├─► [PATCH_VALIDATION]  (Static AST & bounds check)
  │        │        │        │        │
  │        │        │        │        ├─► [ACCEPTANCE_TESTS]
  │        │        │        │        │        │
  │        │        │        │        │        ├─► [REGRESSION_TESTS]
  │        │        │        │        │        │        │
  │        │        │        │        │        │        ├─► [PASS] ──► [AWAITING_APPROVAL] ──► [COMPLETED]
  │        │        │        │        │        │        │
  │        │        ▼        ▼        ▼        ▼        │
  │        └─────── [REPAIR_REQUIRED] ◄─────────────────┘ (Flywheel loop: Max 3 attempts)
  │                        │
  └────────────────────────┴─► [FAILED] / [BLOCKED] / [CANCELLED]
```

---

## 5. Persistence Architecture & SQLite Schema

All operational state is stored locally in `ouroboros.db`:
- **`repositories`**: Registered target codebases (`id`, `name`, `path`, `is_valid`, `git_branch`).
- **`tickets`**: Jira-style feature tickets (`id`, `title`, `acceptance_criteria`, `candidate_files`, `risk_level`, `status`).
- **`runs`**: Lifecycle execution records (`id`, `ticket_id`, `state`, `active_agent`, `verdict`, `worktree_path`, `candidate_branch`).
- **`candidates`**: Candidate patches evaluated per attempt (`diff_content`, `diff_hash`, `ast_changes`, `status`).
- **`test_results`**: Pytest execution logs (`test_type`, `exit_code`, `duration_ms`, `passed_count`, `failed_count`, `failures_json`).
- **`failure_trajectories`**: Persistent failure memory flywheel (`failed_tests_json`, `traceback_excerpt`, `ast_diff`, `repair_hint`, `attempt`).
- **`audit_events`**: Immutable audit trails (`event_type`, `details_json`, `created_at`).
- **`app_settings`**: Key-value system configuration.
