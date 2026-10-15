# PROJECT OUROBOROS — CODE GRAPH INTEGRATION ARCHITECTURE
**Document Reference:** `docs/CODE_GRAPH_INTEGRATION.md`
**Classification:** Systems Architecture & Codebase Intelligence Specification
**Integration Target:** `Meta-Graph-Codebase-Navigator`
**Status:** ACTIVE
**Last Updated:** October 15, 2026

---

## 1. Executive Summary & Purpose

Modern automated software repair systems require deep structural awareness to correctly assess the blast radius of changes, identify all call sites of modified functions, and associate candidate patches with relevant acceptance and regression test suites.

Project Ouroboros integrates with `Meta-Graph-Codebase-Navigator` via a decoupled, resilient, multi-tiered adapter (`MetaGraphAdapter` in `backend/app/integrations/graph/adapter.py`).

### Absolute Architectural Mandates:
1. **Strictly Read-Only Access:** The reference repository `E:\MM Office\Meta-Graph-Codebase-Navigator` is treated as strictly read-only. Ouroboros **never** writes, modifies, deletes, renames, or executes code within the reference repository.
2. **Zero Paid/Heavy Infrastructure Dependency:** Does not require Neo4j, Redis, or cloud graph services for local development. Graph representations are ingested into memory using lightweight Python `networkx` graphs.
3. **Optional Subsystem with Resilient Fallback:** If the graph service or index files are unavailable, Ouroboros falls back seamlessly to offline Python AST static scanning without failing runs or interrupting repairs.
4. **Bounded Memory Footprint:** Caches graph models in memory; respects the 8 GB RAM environment constraint by scoping queries to affected symbols and capping caller/dependency lists.

---

## 2. Three-Tier Resilient Integration Architecture

```
+---------------------------------------------------------------------------------------------------+
|                                 METAGRAPH 3-TIER RESOLUTION ENGINE                                |
+---------------------------------------------------------------------------------------------------+
| Tier 1: Live HTTP API Probe (http://localhost:8001/api/health)                                    |
|   - Real-time graph queries via fast REST endpoint when navigator service is running             |
|   - Timeout: 1,500 ms (fail-fast)                                                                 |
+---------------------------------------------------------------------------------------------------+
                                         │  (if offline / connection refused)
                                         ▼
+---------------------------------------------------------------------------------------------------+
| Tier 2: Direct File Index Ingestion (data/indexes/{repo_id}_nx.json)                              |
|   - Ingests pre-indexed graph into in-memory NetworkX MultiDiGraph                                |
|   - Caches parsed graph per repository in memory                                                  |
|   - Zero network overhead; zero external process dependency                                       |
+---------------------------------------------------------------------------------------------------+
                                         │  (if index file absent)
                                         ▼
+---------------------------------------------------------------------------------------------------+
| Tier 3: Standalone Python AST Static Scanner                                                      |
|   - In-memory AST parse of candidate files (`ASTChangeAnalyzer`)                                  |
|   - Resolves symbol definitions, imports, and syntax trees directly from workspace source         |
+---------------------------------------------------------------------------------------------------+
```

---

## 3. Data Contracts & Graph Schema

The indexed graph structure follows a typed node-edge schema:

### 3.1 Node Types
| Node Type | Key Properties | Example ID |
| :--- | :--- | :--- |
| `File` | `rel_path`, `lines_count`, `sha256` | `agent_chess:file:backend/app/agents/groq_agent.py` |
| `Class` | `name`, `rel_path`, `start_line`, `end_line` | `agent_chess:class:GroqAgent` |
| `Function` | `name`, `rel_path`, `start_line`, `end_line`, `is_async` | `agent_chess:func:synthesize_move` |
| `Symbol` | `name`, `type`, `start_line`, `end_line` | `agent_chess:sym:MAX_RETRIES` |

### 3.2 Edge Relationships
| Edge Type | Source Node | Target Node | Semantics |
| :--- | :--- | :--- | :--- |
| `CONTAINS` | `File` | `Class` / `Function` | Structural containment |
| `DEFINES` | `File` / `Class` | `Function` / `Symbol` | Scope definition |
| `IMPORTS` | `File` | `File` / `Module` | Module dependency |
| `CALLS` | `Function` | `Function` / `Method` | Invocation call-site |
| `TESTS` | `File` (Test) | `File` (Implementation) | Verification linkage |

---

## 4. Retrieval & Intelligence Capabilities

### 4.1 Affected File & Dependency Discovery (`get_file_dependencies`)
* Resolves the target file to its AST node.
* Discovers all functions and classes defined within the file.
* Traverses incoming `CALLS` edges to locate external callers in other files that depend on the modified symbols.
* Bounded context: limits returned callers to top 20 to prevent token blowout in LLM prompts.

### 4.2 Associated Test File Resolution (`get_associated_tests`)
* Inspects `TESTS` edges directly linking candidate implementation files to test suites.
* Supplements with deterministic heuristic pattern matching (e.g., `test_{name}.py`, `tests/{module}/...`).
* Enables targeted pytest execution during baseline and regression validation stages.

### 4.3 Architectural Summaries for Architect Agent (`get_architectural_summary`)
* Ingests high-level module hierarchy, key classes, and public functions.
* Formats concise architectural context for the Architect Agent during ticket generation.

---

## 5. Verification & Test Evidence

The MetaGraph integration is verified by integration tests:
* `test_meta_graph_adapter_agent_chess` in `backend/tests/integration/test_integration_pipeline.py`:
  - Validates `check_connection("agent_chess")` successfully loads the graph.
  - Confirms node count > 100 and edge count > 200.
  - Verifies dependency querying on `backend/app/agents/groq_agent.py`.
  - Verifies test discovery links candidate files to corresponding test suites.
