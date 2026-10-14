# PROJECT OUROBOROS: INTEGRATION AUDIT & BASELINE VERIFICATION REPORT
**Document ID:** DOC-OUROBOROS-AUDIT-001  
**Target Environments:** `E:\MM Office\Agent Chess`, `E:\MM Office\Meta-Graph-Codebase-Navigator`  
**Host Machine:** Windows 10/11 x64, 8 GB RAM Total (1.38 GB Free Physical RAM), Intel CPU with Intel HD Graphics 620 (No CUDA/NVIDIA GPU).  
**Audit Date:** October 14, 2026  
**Status:** COMPLETE & VERIFIED

---

## 1. Executive Summary

This audit establishes the empirical baseline for **Project Ouroboros: Hierarchical Software Evolution and Deterministic Repair Engine**. Prior to any architectural or implementation decisions, both target codebases were inspected directly on the filesystem, their Git working trees were checked, dependencies and test suites were cataloged, and graph schema/serialization formats were decoded.

Key findings:
1. **Target Working Trees**: Both `Agent Chess` and `Meta-Graph-Codebase-Navigator` are clean Git repositories on branch `main` with zero uncommitted changes. Neither repository will be mutated directly; all candidate changes will operate strictly in isolated Git worktrees.
2. **Meta-Graph Integration Ready**: `Meta-Graph-Codebase-Navigator` already contains an indexed snapshot for `agent_chess` (`data/indexes/agent_chess_nx.json`, 1,014,484 bytes) comprising **750 nodes and 2,205 edges** across 8 relationship types (`CALLS`, `IMPORTS`, `CONTAINS`, `DEFINES`, `INHERITS`, `RAISES`, `HANDLES`, `TESTS`).
3. **Graph Dependency Isolation**: Directly importing `app.graph` from Meta-Graph raises a `ModuleNotFoundError: No module named 'neo4j'` if Neo4j is not installed in the host Python environment. Therefore, Ouroboros's `MetaGraphAdapter` will adopt a decoupled strategy:
   - **Tier 1 (HTTP API)**: Connect to Meta-Graph REST server if online.
   - **Tier 2 (Direct File Index)**: Read `data/indexes/{repo_id}_nx.json` via pure Python JSON/NetworkX without requiring Neo4j or Redis.
   - **Tier 3 (Local AST Scanner Fallback)**: Perform zero-dependency Python `ast` scanning for live AST diffs and symbol resolution.
4. **ChessMind Arena Test Suite**: When executed inside its virtual environment (`E:\MM Office\Agent Chess\backend\venv`), ChessMind Arena passes **19 out of 19 automated tests** in 12.13s across agents, REST APIs, move validation, Stockfish evaluator, game loops, and tournaments.
5. **Hardware & Resource Guardrails**: With only 1.38 GB free RAM on an 8 GB Intel HD 620 system, local inference must strictly enforce **single active model** (`qwen2.5-coder:1.5b` default, 2048 token window, 1 concurrent inference process) and local test concurrency must be limited to 1 worker. Missing Ollama/Docker runtime capabilities must trigger graceful local fallbacks rather than fatal crashes.

---

## 2. Codebase Audits

### 2.1 ChessMind Arena (`E:\MM Office\Agent Chess`)

#### Directory Structure
```
E:\MM Office\Agent Chess
├── .env / .env.example / .gitignore / docker-compose.yml / README.md
├── backend
│   ├── app
│   │   ├── config.py             # Settings, API keys, DB & engine paths
│   │   ├── main.py               # FastAPI entry point & CORS
│   │   ├── agents/               # base.py, groq_agent.py, mock_agent.py, personalities.py, prompts.py
│   │   ├── api/                  # analysis, games, health, models, moves, research, tournament, websocket
│   │   ├── chess/                # board_manager.py, evaluator.py, openings.py, stockfish.py, validator.py
│   │   ├── database/             # models.py, repositories.py, session.py (SQLAlchemy + SQLite fallback)
│   │   ├── schemas/              # Pydantic schemas: agent, analysis, games, moves, research, tournament
│   │   └── services/             # game_service, model_service, research_service, tournament_service, etc.
│   ├── bin/stockfish.exe         # Local Stockfish engine binary
│   ├── chessmind.db              # SQLite development database
│   ├── requirements.txt
│   └── tests/                    # 6 test modules (19 tests)
└── frontend/                     # React + Vite + Tailwind CSS dashboard
```

#### Verified Git Status
- Branch: `main`
- Status: `clean` (up to date with `origin/main`, nothing to commit)

#### Protected Components & Critical Behavior
The following files embody protected domain logic and must never be weakened or modified without explicit review:
- `backend/app/chess/validator.py`: FEN validation and strict chess legality verification (`board.legal_moves`).
- `backend/app/chess/board_manager.py`: Board state tracking, history, fen generation, material counting, tactical signals.
- `backend/app/chess/stockfish.py`: Binary subprocess management, UCI protocol communication, depth limit enforcement.
- `backend/app/config.py`: Secret handling for `GROQ_API_KEY`.

#### Telemetry Situation & First Opportunity Candidate
Inspection of `backend/app/agents/groq_agent.py` and `backend/app/agents/mock_agent.py` revealed:
- `latency_ms`, `input_tokens`, and `output_tokens` are tracked per move in `MoveModel`.
- However, API retry exhaustion in `groq_agent.py` falls back to `_select_emergency_move` where `move_source` is set to `"fallback"`, but tournament-level telemetry lacks detailed error taxonomy, timeout counters, and per-round token accounting.
- Furthermore, `backend/tests/test_agents.py` currently tests `test_mock_chess_agent_select_move` and `test_personalities_presets`, but does not test deterministic error backoff, token recording bounds, or timeout thresholds. This constitutes an ideal, bounded, low-risk first ticket.

#### Existing Baseline Tests (19/19 Passing)
| Test Module | Tests | Status |
|---|---|---|
| `tests/test_agents.py` | Schema validation, mock agent move selection, personality presets | 3 PASSED |
| `tests/test_api.py` | Health endpoint, models/personalities list, game creation & lifecycle | 3 PASSED |
| `tests/test_chess.py` | FEN validation, move validation, board manager, opening identification, tactical context | 5 PASSED |
| `tests/test_evaluator.py` | Stockfish/heuristic evaluation, CPL & move quality, accuracy, critical moments | 4 PASSED |
| `tests/test_game_loop.py` | Mock game loop & analysis execution | 1 PASSED |
| `tests/test_tournament.py` | 4-participant, 6-participant round robin, tournament REST API endpoints | 3 PASSED |

---

### 2.2 Meta-Graph Codebase Navigator (`E:\MM Office\Meta-Graph-Codebase-Navigator`)

#### Directory Structure
```
E:\MM Office\Meta-Graph-Codebase-Navigator
├── .env / .env.example / .gitignore / docker-compose.yml / pytest.ini / README.md
├── backend
│   ├── app
│   │   ├── config.py, exceptions.py, logging.py
│   │   ├── main.py
│   │   ├── api/routes/           # evaluations, graph, health, indexing, query, repositories
│   │   ├── graph/                # base.py, neo4j_store.py, networkx_store.py, queries.py, redis_store.py, schema.py
│   │   ├── parser/               # ast_parser.py, incremental.py, models.py, scanner.py, symbol_resolver.py
│   │   ├── retrieval/            # answer_generator, evidence_validator, graph_retriever, lexical_retriever, planner, workflow
│   │   ├── schemas/              # evidence, graph, indexing, query, repository
│   │   └── services/             # evidence_service, indexing_service, query_service, repository_service
│   └── tests/                    # unit (diff, store, parser, redis, retrieval, workflow) and api tests
├── data
│   ├── indexes/                  # agent_chess_graph.json, agent_chess_nx.json, repositories.json
│   └── cache/                    # query_history.json
└── frontend/                     # React + Vite + Tailwind graph visualization UI
```

#### Verified Git Status
- Branch: `main`
- Status: `clean` (up to date with `origin/main`, nothing to commit)

#### Graph Schema & Existing Index Verification
`data/indexes/repositories.json` registers `agent_chess`:
```json
{
  "agent_chess": {
    "id": "agent_chess",
    "name": "Agent Chess",
    "path": "E:\\MM Office\\Agent Chess",
    "is_valid": true,
    "commit_hash": "7a614f3b50eb799f4c60463c42d769b45daa48cb",
    "file_count": 48
  }
}
```
`data/indexes/agent_chess_nx.json` (1 MB) contains:
- **750 Nodes**: Node types include `Repository`, `File`, `Module`, `Class`, `Function`, `ExternalSymbol`.
- **2,205 Edges**: Relationship types include `HAS_FILE`, `CONTAINS`, `DEFINES`, `IMPORTS`, `CALLS`, `INHERITS`, `RAISES`, `HANDLES`, `TESTS`.
- Node properties include `id`, `rel_path`, `module_name`, `line_count`, `file_hash`, `start_line`, `end_line`, `is_async`, `is_method`, `parameters`, `return_annotation`, `docstring`.

---

## 3. Integration Strategy for Project Ouroboros

### 3.1 Decoupled Meta-Graph Adapter
Rather than creating fragile Python import dependencies on `Meta-Graph-Codebase-Navigator`'s internal packages (which pull in `neo4j`, `redis`, and `langgraph`), Ouroboros will implement a dedicated `MetaGraphAdapter`:
1. **HTTP Probe**: Check if Meta-Graph server is running on `http://localhost:8000`.
2. **File-Based NetworkX Ingestion**: If HTTP is offline, parse `data/indexes/{repo_id}_nx.json` directly into an in-memory `networkx.MultiDiGraph`.
3. **Query Interface**:
   - `get_file_dependencies(rel_path)` -> list of imported files and callers.
   - `get_symbol_callers(symbol_name)` -> list of calling functions/classes.
   - `get_associated_tests(rel_path)` -> tests linked via `TESTS` or `IMPORTS`.
   - `get_neighborhood_subgraph(symbol_id, depth=2)` -> bounded context subgraph for the Planner Agent.
4. **Standalone AST Fallback**: If no index exists, use Python's built-in `ast` module to scan the target repository and construct a localized dependency graph.

### 3.2 Git Worktree Isolation Policy
To guarantee that the original `Agent Chess` working tree is never corrupted:
1. Candidate branches are branched off the active commit hash: `git -C <repo> worktree add -b candidate/<ticket_id> <worktree_dir> <base_commit>`.
2. All patch generation, AST validation, pytest execution, and linting run inside `<worktree_dir>`.
3. After evaluation, the worktree is preserved for human review until explicit approval or rejection.
4. No automated commits or merges are made to `main`.

---

## 4. Hardware Safeguards & Execution Limits

| Parameter | Configuration | Rationale |
|---|---|---|
| **Max RAM Budget** | 8 GB total | Windows + IDE + Browser consumes ~6.6 GB. Available RAM is ~1.4 GB. |
| **Local Model** | `qwen2.5-coder:1.5b` (quantized ~986 MB) | Fits comfortably in remaining RAM. Zero GPU/CUDA dependencies. |
| **Context Window** | 2,048 tokens | Prevents memory spikes during local inference. |
| **Local Concurrency** | 1 process | Single active LLM inference lock across entire application. |
| **Remote Provider** | Groq API (`llama-3.3-70b-versatile` / `llama-3.1-8b-instant`) | Zero local RAM cost, fast reasoning for Architect/Planner. |
| **Test Concurrency** | 1 pytest process | Avoids multi-process CPU/RAM thrashing. |
| **Execution Security** | Restricted Subprocess with Disposable Worktree | Docker daemon offline; isolated local runner with sanitized env and strict timeouts. |

---

## 5. Next Steps

With Stage 1 (Audit) complete:
1. Proceed to **Stage 2: Foundation**:
   - Scaffold Project Ouroboros in `E:\MM Office\Ouroboros`.
   - Implement configuration, SQLite schema, FastAPI backend, and React/TypeScript dashboard.
   - Create Windows PowerShell automation scripts (`setup.ps1`, `start.ps1`, `stop.ps1`, `test.ps1`, `check-environment.ps1`).
2. Proceed to **Stage 3: Provider & Graph Adapters**.
3. Implement **Deterministic Pipeline & End-to-End Fixture Demonstration**.
