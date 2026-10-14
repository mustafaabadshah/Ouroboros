# Project Ouroboros: Hardware Resource & Concurrency Guide
**Document ID:** RES-OURO-001  
**Target Hardware:** Intel Core (Intel HD Graphics 620), 8 GB RAM, Windows 10/11 x64  

---

## 1. System Memory Budget (8 GB Physical RAM)

Operating a multi-agent autonomous swarm alongside an IDE, web browser, backend server, and test runners requires strict memory partitioning.

| Component | Normal Memory Usage | Peak Memory Boundary | Mitigation Strategy |
| :--- | :--- | :--- | :--- |
| **Windows OS & Background Services** | 2.8 GB | 3.5 GB | Baseline OS requirement. |
| **Antigravity IDE & Node Server** | 1.8 GB | 2.5 GB | Monitored via `psutil`. |
| **Ouroboros FastAPI + SQLite** | 120 MB | 250 MB | In-memory caches bounded; lazy loading. |
| **React Dashboard (Browser Tab)** | 180 MB | 350 MB | Virtualized diff view; TanStack Query GC. |
| **Ollama CPU Model (`qwen2.5-coder:1.5b`)** | 986 MB | 1.4 GB | 5-minute keepalive; 2048 token context. |
| **Isolated Pytest Subprocess** | 150 MB | 400 MB | Strict concurrency limit: 1 test process max. |
| **Available Headroom** | **~1.2 – 1.8 GB** | **Safety Buffer** | Alert triggered if free RAM < 1500 MB. |

---

## 2. Local Inference Runtime: Ollama on CPU

### Model Selection Policy
- **Default Active Model:** `qwen2.5-coder:1.5b` (~986 MB download size).
- **Lighter Alternative:** `qwen2.5-coder:0.5b` (~390 MB).
- **Optional Upgrade:** `qwen2.5-coder:3b` (~1.9 GB) — Requires explicit user confirmation and > 2500 MB free RAM.
- **Strictly Banned:** `qwen2.5-coder:latest` (unpredictable model footprint).

### Ollama Configuration Parameters
```env
OLLAMA_BASE_URL="http://localhost:11434"
LOCAL_MODEL_NAME="qwen2.5-coder:1.5b"
LOCAL_MODEL_CONTEXT_TOKENS=2048
LOCAL_MODEL_KEEP_ALIVE="5m"
MAX_LOCAL_CONCURRENCY=1
AUTO_DOWNLOAD_LOCAL_MODELS=false
```
- **No Automatic Downloads:** Models are never downloaded without explicit user approval.
- **Model Keep-Alive:** Set to 5 minutes so inactive models are freed from system RAM.

---

## 3. Concurrency Limiting Architecture

To prevent CPU thrashing and out-of-memory crashes:
1. **Pytest Concurrency Lock:**
   `app.evaluation.runner.PytestRunner` utilizes an `asyncio.Lock()` to ensure that only **one test suite** executes at any given instant across all tickets and candidate branches.
2. **Local Model Request Lock:**
   `app.providers.ollama.OllamaProvider` enforces `MAX_LOCAL_CONCURRENCY = 1`. Multiple agents queue behind a global inference lock rather than overwhelming CPU cores.
3. **Subprocess Timeout:**
   All candidate test executions are killed after 60 seconds if they fail to terminate.

---

## 4. Remote Fallback & Cost Guardrails

When local memory is constrained (< 1500 MB free RAM) or local inference times out:
- **Groq Fallback:** Seamlessly routes reasoning tasks to Groq (`llama-3.3-70b-versatile` or `llama-3.1-8b-instant`).
- **Cost Accounting:** Input and output tokens are tracked per agent task. Estimated cost is calculated using published pricing metadata and displayed in the **Observability** dashboard tab.
- **Strict Local Mode:** Operators can enable `STRICT_LOCAL_ONLY=true` in settings to guarantee zero source snippets are ever transmitted over the network.
