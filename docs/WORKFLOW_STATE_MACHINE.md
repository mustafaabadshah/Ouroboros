# PROJECT OUROBOROS — WORKFLOW STATE MACHINE SPECIFICATION
**Document Reference:** `docs/WORKFLOW_STATE_MACHINE.md`  
**Version:** 1.0.0  
**Status:** ACTIVE  
**Last Updated:** October 15, 2026  

---

## 1. STATE MACHINE PRINCIPLES

1. **Deterministic Authority:** The state machine is governed strictly by hardcoded Python logic (`backend/app/orchestration/state_machine.py`), never by LLM output.
2. **Terminal Invariance:** Terminal states (`COMPLETED`, `FAILED`, `BLOCKED`, `CANCELLED`, `TIMED_OUT`) have zero outgoing transitions. Once a run enters a terminal state, it cannot transition further.
3. **Fail-Closed Routing:** Any unhandled exception, security violation, or missing container runtime immediately transitions the run to `BLOCKED` or `FAILED`.

---

## 2. STATE DEFINITIONS

| State Name | Classification | Description |
| :--- | :--- | :--- |
| `IDLE` | Initial | Initial unstarted state before workflow pipeline begins. |
| `REPOSITORY_ANALYSIS` | Discovery | Pure AST scanning of repository structure, modules, and tests. |
| `TICKET_GENERATION` | Proposal | Lead Architect proposes structured, evidence-backed Jira-style ticket. |
| `TICKET_REVIEW` | Human Gate | Ticket is presented for human inspection and approval. |
| `BASELINE_VALIDATION`| Verification | Baseline test suite executed against clean, unpatched target repository. |
| `PLANNING` | Deconstruction | Lead Planner converts approved ticket into ordered subtasks. |
| `CODING` | Generation | Local Coder / Lead Coder synthesizes candidate diff inside worktree. |
| `PATCH_VALIDATION` | Static Gate | AST check and path boundary check verify diff safety. |
| `ACCEPTANCE_TESTS` | Evaluation | Target acceptance test assertions evaluated against candidate code. |
| `REGRESSION_TESTS` | Evaluation | Full baseline test suite evaluated against candidate code to catch regressions. |
| `REPAIR_REQUIRED` | Recovery | Candidate failed evaluation; failure trajectory dispatched to Repair Agent. |
| `REVIEW` | Review | Candidate patch and evaluation summary formatted for review. |
| `AWAITING_APPROVAL` | Human Gate | Passing candidate revision hash frozen; awaiting human merge authorization. |
| `COMPLETED` | Terminal | Human approved merge; candidate cleanly integrated into repository. |
| `FAILED` | Terminal | Run terminated due to exhausted retries, unrecoverable test failures, or crash. |
| `BLOCKED` | Terminal | Run prevented by security violation, missing sandbox, or policy rejection. |
| `CANCELLED` | Terminal | Run explicitly halted by human operator. |
| `TIMED_OUT` | Terminal | Subprocess or agent task exceeded configured execution budget. |

---

## 3. STATE TRANSITION GRAPH

```mermaid
stateDiagram-v2
    [*] --> IDLE
    IDLE --> REPOSITORY_ANALYSIS
    IDLE --> TICKET_GENERATION
    IDLE --> BASELINE_VALIDATION
    IDLE --> PLANNING
    IDLE --> CANCELLED

    REPOSITORY_ANALYSIS --> TICKET_GENERATION
    REPOSITORY_ANALYSIS --> FAILED
    REPOSITORY_ANALYSIS --> CANCELLED

    TICKET_GENERATION --> TICKET_REVIEW
    TICKET_GENERATION --> FAILED
    TICKET_GENERATION --> CANCELLED

    TICKET_REVIEW --> BASELINE_VALIDATION
    TICKET_REVIEW --> PLANNING
    TICKET_REVIEW --> BLOCKED
    TICKET_REVIEW --> CANCELLED

    BASELINE_VALIDATION --> PLANNING
    BASELINE_VALIDATION --> BLOCKED
    BASELINE_VALIDATION --> FAILED
    BASELINE_VALIDATION --> CANCELLED

    PLANNING --> CODING
    PLANNING --> BLOCKED
    PLANNING --> FAILED
    PLANNING --> CANCELLED

    CODING --> PATCH_VALIDATION
    CODING --> FAILED
    CODING --> CANCELLED

    PATCH_VALIDATION --> ACCEPTANCE_TESTS
    PATCH_VALIDATION --> REPAIR_REQUIRED
    PATCH_VALIDATION --> CODING
    PATCH_VALIDATION --> BLOCKED
    PATCH_VALIDATION --> FAILED
    PATCH_VALIDATION --> CANCELLED

    ACCEPTANCE_TESTS --> REGRESSION_TESTS
    ACCEPTANCE_TESTS --> AWAITING_APPROVAL
    ACCEPTANCE_TESTS --> REPAIR_REQUIRED
    ACCEPTANCE_TESTS --> CODING
    ACCEPTANCE_TESTS --> FAILED
    ACCEPTANCE_TESTS --> CANCELLED

    REGRESSION_TESTS --> REVIEW
    REGRESSION_TESTS --> AWAITING_APPROVAL
    REGRESSION_TESTS --> REPAIR_REQUIRED
    REGRESSION_TESTS --> CODING
    REGRESSION_TESTS --> FAILED
    REGRESSION_TESTS --> CANCELLED

    REPAIR_REQUIRED --> CODING
    REPAIR_REQUIRED --> FAILED
    REPAIR_REQUIRED --> BLOCKED
    REPAIR_REQUIRED --> CANCELLED

    REVIEW --> AWAITING_APPROVAL
    REVIEW --> FAILED
    REVIEW --> CANCELLED

    AWAITING_APPROVAL --> COMPLETED
    AWAITING_APPROVAL --> FAILED
    AWAITING_APPROVAL --> CANCELLED

    COMPLETED --> [*]
    FAILED --> [*]
    BLOCKED --> [*]
    CANCELLED --> [*]
    TIMED_OUT --> [*]
```
