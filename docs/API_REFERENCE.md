# Project Ouroboros: REST & SSE API Reference
**Base URL:** `http://127.0.0.1:8000/api`  
**Interactive Swagger UI:** `http://127.0.0.1:8000/docs`  

---

## 1. System & Health Endpoints

### `GET /health`
Returns the operational status of the Ouroboros backend application.
- **Response `200 OK`:**
  ```json
  {
    "status": "healthy",
    "app": "Project Ouroboros",
    "version": "1.0.0"
  }
  ```

### `GET /system/status`
Returns real-time hardware telemetry and provider connectivity.
- **Response `200 OK`:**
  ```json
  {
    "system": {
      "free_ram_mb": 1380,
      "total_ram_mb": 8192,
      "ram_usage_percent": 83.1,
      "cpu_percent": 14.2,
      "ram_warning": true
    },
    "ollama": {
      "connected": false,
      "active_model": "qwen2.5-coder:1.5b"
    },
    "groq": {
      "connected": true,
      "active_model": "llama-3.3-70b-versatile"
    }
  }
  ```

---

## 2. Repository Endpoints

### `GET /repositories`
Lists all registered target codebases.

### `GET /repositories/{id}/graph-status`
Returns the AST graph connectivity status for the specified repository.
- **Response `200 OK`:**
  ```json
  {
    "repo_id": "agent_chess",
    "status": "connected",
    "provider": "direct_networkx_json",
    "nodes_count": 750,
    "edges_count": 2105,
    "source_file": "agent_chess_nx.json"
  }
  ```

### `POST /repositories/{id}/analyze`
Triggers an architectural AST dependency scan or reads the grounded graph index.

---

## 3. Ticket Endpoints

### `GET /tickets`
Lists Jira-style tickets. Supports query filtering: `?repo_id=...&status=...`.

### `POST /tickets/generate`
Invokes the Architect Agent to analyze grounded AST graph summaries and synthesize a feature ticket.
- **Request Body:**
  ```json
  {
    "repo_id": "agent_chess",
    "target_area": "Missing telemetry counters"
  }
  ```

### `POST /tickets/{id}/approve`
Approves a proposed ticket for swarm implementation.

### `POST /tickets/{id}/reject`
Rejects a ticket and sets status to `REJECTED`.

---

## 4. Run Execution Endpoints

### `GET /runs`
Lists all swarm execution lifecycles.

### `POST /runs`
Initializes and asynchronously launches the state machine workflow for an approved ticket.
- **Request Body:**
  ```json
  {
    "ticket_id": "ouro-de9451",
    "autonomy_mode": "SUPERVISED",
    "use_mock_agents": false
  }
  ```

### `GET /runs/{id}`
Returns the current state machine stage, active agent, base commit, and candidate branch.

### `GET /runs/{id}/events` *(Server-Sent Events)*
Streams real-time state transitions and agent logs to the frontend dashboard:
- Format: `data: {"event": "STATE_CHANGED", "payload": {"state": "CODING", "active_agent": "LocalCoder"}}`

### `POST /runs/{id}/cancel`
Requests graceful cancellation of a running lifecycle.

---

## 5. Evaluation & Human Merge Endpoints

### `GET /runs/{id}/diff`
Returns the candidate patch diff inspection:
- `diff_content`: Unified diff text
- `lines_added`, `lines_removed`
- `ast_changes`: Structured AST modifications
- `verdict`: `PASS` | `FAIL` | `BLOCKED`

### `GET /runs/{id}/results`
Returns structured test results (baseline vs candidate acceptance vs regression tests).

### `POST /runs/{id}/approve-merge`
**Explicit Human Approval Gate:** Merges candidate branch into target branch (`main`) and discards the isolated worktree.
- **Request Body:**
  ```json
  {
    "action": "approve",
    "notes": "Approved by Lead Architect - Pilot Verification"
  }
  ```

### `POST /runs/{id}/reject-merge`
Discards the candidate branch and tears down the worktree without merging.

---

## 6. Failure Memory Endpoints

### `GET /failures`
Lists recorded failure trajectories across runs for search and analysis.

### `DELETE /failures/{id}`
Purges a failure trajectory from SQLite memory.
