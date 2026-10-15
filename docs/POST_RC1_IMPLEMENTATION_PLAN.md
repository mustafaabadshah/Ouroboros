# Project Ouroboros — Post-RC1 Implementation Plan
**Milestone:** Post-RC1 Hardening, Evaluation, Intelligence & Release Engineering
**Document Reference:** `docs/POST_RC1_IMPLEMENTATION_PLAN.md`
**Target Release:** Post-RC1 Platform Evolution (`v0.9.1` / `v1.0.0-rc1`)
**Commit Baseline:** `172fa93`

---

## 1. Plan Overview

Following the empirical reproduction of the `v0.9.0-rc1` baseline in Phase 0, this plan outlines the phased execution strategy across all remaining engineering workstreams:

- **Phase 1: Security & Sandbox Assurance** (P0)
- **Phase 2: Full Workflow Reliability** (P0)
- **Phase 3: Agent Orchestration & Model Reliability** (P1)
- **Phase 4: Meta-Graph Codebase Navigator Integration** (P1)
- **Phase 5: Benchmark Science & Failure Memory** (P1)
- **Phase 6: Metrics & Observability** (P1)
- **Phase 7: React Dashboard & API Quality** (P1)
- **Phase 8: Installation, Windows Operations & Resource Safety** (P0)
- **Phase 9: Automated CI & Release Engineering** (P1)
- **Phase 10: Release Decision** (P0)

---

## 2. Phase-by-Phase Roadmap & Acceptance Gates

### Phase 1: Security and Sandbox Assurance
- **Workstreams:**
  - Audit all entry points capable of launching subprocesses in [`docs/EXECUTION_BOUNDARY_AUDIT.md`](file:///e:/MM%20Office/Ouroboros/docs/EXECUTION_BOUNDARY_AUDIT.md).
  - Test container isolation restrictions: non-root execution, network disabled by default, read-only root filesystem, explicit workspace mounting, memory/CPU limits.
  - Extend adversarial security suite with tests for TOCTOU path races, symlink escapes, and stale token replays.
  - Verify merge authorization invariants: diff-hash binding, candidate revision drift invalidation, target branch drift revalidation.
- **Acceptance Gate:** 100% of adversarial fixtures pass; zero host execution fallbacks; fail-closed behavior verified.

### Phase 2: Full Workflow Reliability
- **Workstreams:**
  - Verify state transitions on disposable repositories:
    `DISCOVERED → DRAFT → APPROVED → IN_PROGRESS → EVALUATING → REVIEW_REQUIRED → MERGE_APPROVED → MERGED`.
  - Ensure backend rejects invalid state transitions and unauthorized merges.
  - Implement and test safe refusal: verify that Ouroboros correctly refuses to propose or merge changes when acceptance criteria or safety boundaries are violated.
  - Update [`docs/WORKFLOW_STATE_MACHINE.md`](file:///e:/MM%20Office/Ouroboros/docs/WORKFLOW_STATE_MACHINE.md).
- **Acceptance Gate:** Complete workflow tested end-to-end on multi-file disposable repositories with zero regressions.

### Phase 3: Agent Orchestration and Model Reliability
- **Workstreams:**
  - Formalize typed input/output schemas for Architect, Planner, Coder, Critic, Judge, and Repair Agent.
  - Establish that security decisions are deterministic backend responsibilities (LLMs never override deterministic gates).
  - Enforce provider fallback allowlists and explicit user consent for remote inference.
  - Document model routing and privacy guarantees in [`docs/MODEL_ROUTING_AND_PRIVACY.md`](file:///e:/MM%20Office/Ouroboros/docs/MODEL_ROUTING_AND_PRIVACY.md).
- **Acceptance Gate:** Schema validation catches malformed agent responses; zero silent telemetry leakage.

### Phase 4: Meta-Graph Codebase Navigator Integration
- **Workstreams:**
  - Inspect `E:\MM Office\Meta-Graph-Codebase-Navigator` strictly in read-only mode.
  - Design a clean, optional adapter interface with graceful offline fallback.
  - Add integration tests comparing graph-assisted context retrieval against baseline AST scanning.
  - Document integration contracts in [`docs/CODE_GRAPH_INTEGRATION.md`](file:///e:/MM%20Office/Ouroboros/docs/CODE_GRAPH_INTEGRATION.md).
- **Acceptance Gate:** Navigator integration functions when available and falls back cleanly without crashing when unavailable. Reference repository remains untouched.

### Phase 5: Benchmark Science and Failure Memory
- **Workstreams:**
  - Expand benchmark suite from 3 tasks to 20 deterministic tasks across single-file fixes, multi-file changes, regression traps, boundary attacks, and scope violations.
  - Formalize evaluation methodology and honest denominators in [`docs/EVALUATION_METHODOLOGY.md`](file:///e:/MM%20Office/Ouroboros/docs/EVALUATION_METHODOLOGY.md).
  - Execute matched ablation studies (memory enabled vs disabled) across the expanded suite and document findings in [`docs/FAILURE_MEMORY_EVALUATION.md`](file:///e:/MM%20Office/Ouroboros/docs/FAILURE_MEMORY_EVALUATION.md).
- **Acceptance Gate:** 20-task benchmark runs deterministically; metrics have explicit formulas and denominators.

### Phase 6: Metrics and Observability
- **Workstreams:**
  - Verify that `MetricsCalculator` handles empty datasets, blocked runs, and latency percentiles accurately.
  - Validate Arize Phoenix OpenTelemetry spans and test secret masking against synthetic credentials.
  - Ensure exported JSON reports are valid and schema-versioned.
- **Acceptance Gate:** Zero secret leakage in spans or logs; offline Phoenix collector does not disrupt core workflows.

### Phase 7: React Dashboard and API Quality
- **Workstreams:**
  - Audit all 10 dashboard pages for real backend connectivity, loading states, and error handling.
  - Enhance Evaluation Lab view to render the expanded 20-task benchmark suite and ablation metrics.
  - Verify strict TypeScript typing and production bundling (`npm run build`).
- **Acceptance Gate:** Production bundle compiles cleanly with 0 errors; all interactive UI elements bind to backend endpoints.

### Phase 8: Installation, Windows Operations and Resource Safety
- **Workstreams:**
  - Review and harden PowerShell lifecycle scripts (`check-environment.ps1`, `setup.ps1`, `test.ps1`, `start.ps1`, `stop.ps1`).
  - Document Windows operational guidelines and troubleshooting in [`docs/WINDOWS_OPERATIONS.md`](file:///e:/MM%20Office/Ouroboros/docs/WINDOWS_OPERATIONS.md).
- **Acceptance Gate:** Clean install verified; process-tree cleanup tested; loopback binding enforced.

### Phase 9: Automated CI and Release Engineering
- **Workstreams:**
  - Create GitHub Actions workflow (`.github/workflows/ci.yml`) covering backend tests, frontend build, and secret scanning.
  - Implement a machine-readable release verification script.
- **Acceptance Gate:** CI workflow configured; release verification script executes cleanly.

### Phase 10: Release Decision
- **Workstreams:**
  - Deliver final release artifacts:
    - [`docs/POST_RC1_FINAL_REPORT.md`](file:///e:/MM%20Office/Ouroboros/docs/POST_RC1_FINAL_REPORT.md)
    - [`docs/POST_RC1_RELEASE_CHECKLIST.md`](file:///e:/MM%20Office/Ouroboros/docs/POST_RC1_RELEASE_CHECKLIST.md)
    - [`docs/POST_RC1_KNOWN_LIMITATIONS.md`](file:///e:/MM%20Office/Ouroboros/docs/POST_RC1_KNOWN_LIMITATIONS.md)
    - [`artifacts/post_rc1_release_report.json`](file:///e:/MM%20Office/Ouroboros/artifacts/post_rc1_release_report.json)
  - Issue final release recommendation (`PASS`, `CONDITIONAL`, `BLOCKED`, or `NOT_READY`).
- **Acceptance Gate:** All gates reconciled with empirical evidence; reference repositories verified untouched.
