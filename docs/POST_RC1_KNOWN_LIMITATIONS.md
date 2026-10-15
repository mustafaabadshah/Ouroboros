# PROJECT OUROBOROS — POST-RC1 KNOWN LIMITATIONS & RISK REGISTER
**Document Reference:** `docs/POST_RC1_KNOWN_LIMITATIONS.md`
**Classification:** Product Reliability, Operational Constraints & Risk Register
**Version:** 1.0.0
**Status:** ACTIVE
**Last Updated:** October 15, 2026

---

## 1. Executive Summary

In adherence to the core engineering philosophy of Project Ouroboros—**honesty over marketing claims**—this document explicitly identifies all technical constraints, runtime boundaries, hardware limits, and operational limitations in the post-RC1 platform.

---

## 2. Detailed Technical Limitations

### 2.1 Container Sandbox & Execution Isolation
* **Limitation:** Containerized evaluation depends on an active Docker Desktop daemon (`\\.\pipe\docker_engine` via WSL2).
* **Fail-Closed Behavior:** When Docker Desktop is closed, the system strictly halts candidate test runs with `BLOCKED` (`reason_code: RUNTIME_UNAVAILABLE`). Candidate code is **never executed directly on the host**.
* **Impact:** Offline development environments without container runtimes can perform repository ingestion, AST analysis, ticket generation, and planning, but automated repair test execution remains blocked until the container runtime is started.

### 2.2 Host Hardware Ceiling (8 GB RAM / No Dedicated GPU)
* **Limitation:** The host operates on Windows 10 x64 with 8 GB of visible physical RAM and Intel HD Graphics 620 integrated graphics (no CUDA acceleration).
* **Mitigation:**
  - Strict single-task inference serialization (global async lock).
  - Memory guardrail (`check_memory_threshold`): warns if available RAM < 1,500 MB.
  - Local model support is capped at 1.5B–7B parameters quantized to 4-bit (e.g., Qwen 2.5 Coder 1.5B Q4_K_M).
  - Heavy multi-model loads or concurrent multi-agent inference will cause disk swap thrashing.

### 2.3 Remote Inference & Privacy Policy
* **Limitation:** Local CPU inference has lower reasoning capability than frontier models on complex multi-file architectural refactorings.
* **Mitigation:**
  - Cloud provider fallback (Groq Cloud API) is supported for Architect and Planner roles.
  - Requires explicit operator configuration (`ALLOW_REMOTE_FALLBACK=True` and `STRICT_LOCAL_ONLY=False`).
  - Sensitive files (`.env`, `id_rsa`, certificates) are stripped by `mask_secret()` before prompt formatting.

### 2.4 Codebase Graph Integration (Meta-Graph Navigator)
* **Limitation:** Live graph mutations and real-time Neo4j queries require an external MetaGraph Navigator daemon running on port 8001.
* **Mitigation:**
  - Decoupled 3-tier architecture: falls back automatically to direct in-memory NetworkX JSON index ingestion (`data/indexes/{repo_id}_nx.json`) or static AST symbol analysis without failing the workflow.

### 2.5 Local Observability (Arize Phoenix)
* **Limitation:** Arize Phoenix trace dashboard requires the Phoenix background server on port 6006.
* **Mitigation:**
  - OpenTelemetry exporter is non-fatal: if port 6006 is closed, spans are silently dropped after bounded retries, ensuring workflow execution is never halted by observability outages.

---

## 3. Operational Risk Matrix

| Risk Factor | Severity | Probability | Built-In Safeguard |
| :--- | :---: | :---: | :--- |
| **Accidental Host Execution** | CRITICAL | ZERO | Deterministic fail-closed gate blocks non-container execution. |
| **Unapproved Git Merge** | HIGH | ZERO | Merge gate strictly checks `run.verdict == PASS`, candidate hash, and operator authorization. |
| **Target Branch Drift Race** | HIGH | ZERO | Diff hash and base commit re-verified inside `_merge_lock`; raises 409 Conflict on drift. |
| **Credential / Key Leakage** | HIGH | LOW | `mask_secret()` sanitizes logs and traces; protected files rejected by diff parser. |
| **Process Tree Orphanage** | MEDIUM | LOW | `taskkill /F /T /PID` terminates entire subprocess hierarchy on cancellation or timeout. |
| **RAM Exhaustion on CPU Model** | MEDIUM | LOW | Pre-flight memory check blocks generation if free RAM < 1.5 GB. |
