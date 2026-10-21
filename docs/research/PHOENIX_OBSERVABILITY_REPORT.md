# Arize Phoenix AI Observability Architecture & Verification Report
**Project:** Ouroboros Autonomous Software Evolution  
**Document Version:** 1.0.0  
**Generated:** 2026-10-18  
**Package Version:** `phoenix` v20.21.3  
**Tracing Protocol:** OpenTelemetry / OpenInference HTTP/Protobuf (`/v1/traces`)  
**Collector Target:** `http://127.0.0.1:6006`  
**Target Project:** `ouroboros-swarm`

---

## 1. Observability Architecture & Components

Project Ouroboros integrates Arize Phoenix for tracing multi-agent interactions, token usage, latency, and deterministic evaluations across the swarm lifecycle.

```
+-------------------------------------------------------------------------------+
|                       Ouroboros Multi-Agent Pipeline                          |
|  [Architect]  [Planner]  [Coder]  [TestEngineer]  [Evaluator]  [Reviewer]     |
+-------------------------------------------------------------------------------+
                                      |
                     record_agent_span / record_evaluator_span
                                      v
+-------------------------------------------------------------------------------+
|                        PhoenixTracingService                                  |
|  - In-Memory Circular Buffer (deque maxlen=100)                               |
|  - Context Variables (run_id, ticket_id)                                      |
|  - Privacy Sanitizer (prompt/output masking)                                  |
|  - Cached Non-Blocking Socket Probe (< 400ms)                                 |
+-------------------------------------------------------------------------------+
           |                                                 |
  (Collector Online)                                (Collector Offline)
           v                                                 v
+-----------------------+                         +---------------------+
|   OpenTelemetry OTLP  |                         | In-Memory Fallback  |
|   BatchSpanProcessor  |                         | Fast return (<50ms) |
+-----------------------+                         +---------------------+
           v                                                 v
+-----------------------+                         +---------------------+
| Arize Phoenix Server  |                         | Zero Network Hangs  |
| http://127.0.0.1:6006 |                         | Clean Shutdown      |
+-----------------------+                         +---------------------+
```

---

## 2. Server Startup Protocols & Hardware Compatibility

### 2.1 Supported Startup Command (Verified)
The verified, official startup command in this environment is:
```powershell
.venv\Scripts\python.exe -m phoenix.server.main serve
```
- **Host Binding:** `127.0.0.1` / `0.0.0.0`
- **Port:** `6006` (or configured via environment variable `PHOENIX_PORT`)
- **Database:** SQLite database persisted at `~/.phoenix/phoenix.db`
- **Docker Dependency:** None. Arize Phoenix runs natively in Python on Uvicorn without Docker Desktop.

### 2.2 In-Process `ThreadSession` Root Cause Finding
When executing in-process via `phoenix.launch_app()`, two distinct issues were diagnosed and resolved:
1. **Windows Charmap `cp1252` Encoding:**
   Phoenix emits Unicode emojis (e.g., `❗️`) in deprecation warnings. On Windows, default standard streams raise `UnicodeEncodeError`. Reconfiguring standard output streams (`sys.stdout.reconfigure(encoding='utf-8', errors='replace')`) resolves the issue.
2. **Hardcoded 5-Second Startup Timeout:**
   In `phoenix/server/thread_server.py:52`, Phoenix hardcodes `time_limit = time() + 5`. On dual-core CPUs (Intel Core i3-7100U), database migration and table reflection require 6–8 seconds on cold launch. Exceeding 5.0 seconds causes `RuntimeError: server took too long to start`. Starting the server as a standalone daemon bypasses this hardcoded thread timeout completely.

---

## 3. End-to-End Live Export Verification

Live end-to-end telemetry export was validated against the running Phoenix collector at `http://127.0.0.1:6006`:

1. **Span Generation:**
   `record_agent_span()` created test span `TestEngineer.LiveTelemetrySmokeTest` with `ouroboros.ticket_id = PHOENIX-LIVE-1792270270` and `ouroboros.run_id = run-PHOENIX-LIVE-1792270270`.
2. **Flush:**
   `tracer_provider.force_flush()` successfully delivered the protobuf payload to `http://127.0.0.1:6006/v1/traces`.
3. **Collector-Side Ingestion Proof:**
   The Phoenix REST API at `/v1/projects/ouroboros-swarm/spans` was queried, confirming ingestion:
   ```json
   {
     "name": "TestEngineer.LiveTelemetrySmokeTest",
     "span_kind": "AGENT",
     "status_code": "OK",
     "attributes": {
       "ouroboros.role": "TestEngineer",
       "ouroboros.task": "LiveTelemetrySmokeTest",
       "ouroboros.ticket_id": "PHOENIX-LIVE-1792270270",
       "ouroboros.run_id": "run-PHOENIX-LIVE-1792270270",
       "llm.model_name": "mock-model",
       "llm.token_count.prompt_tokens": 10,
       "llm.token_count.completion_tokens": 5,
       "llm.token_count.total_tokens": 15,
       "input.value": "[Privacy Mode: Prompt text omitted (24 chars)]"
     }
   }
   ```

---

## 4. Graceful Offline Fallback & Probe Optimization

### 4.1 Probe Caching Fix
- **Prior Bottleneck:** Previously, if Phoenix was offline, `record_agent_span` called `_init_tracer()` on every span, incurring a 300ms TCP connection attempt for every agent turn.
- **Phase 3 Optimization:** Implemented `_probe_attempted` and `_collector_offline` caching in [`backend/app/observability/phoenix_service.py`](file:///E:/MM%20Office/Ouroboros/backend/app/observability/phoenix_service.py). After the initial 300ms probe detects port closure, subsequent span recordings bypass socket probes entirely.
- **Latency Benchmark:** In-memory append latency dropped from **309 ms to < 1 ms** per span.

### 4.2 Bounded Shutdown
- Added `flush(timeout_ms)` and `shutdown(timeout_ms)` methods to `PhoenixTracingService`.
- If the collector is offline, shutdown returns immediately without blocking on network retry queues.

---

## 5. Trace Correlation & Privacy Governance

1. **Contextual Propagation:** Ambient context variables (`current_run_id_var`, `current_ticket_id_var`) ensure that spans emitted across nested agent calls automatically correlate to the root task and ticket.
2. **Privacy Redaction:** When `PHOENIX_CAPTURE_PROMPTS = False`, input prompts and generated code are replaced with bounded metadata tokens (`[Privacy Mode: Prompt text omitted (N chars)]`), preventing intellectual property and secret leaks.

---

## 6. Automated Test Coverage

Suite: [`backend/tests/unit/test_phoenix_observability.py`](file:///E:/MM%20Office/Ouroboros/backend/tests/unit/test_phoenix_observability.py)
- `test_phoenix_offline_fallback_fast_probe_and_bounded_shutdown`: PASS (0.31s initial probe, < 1ms subsequent append)
- `test_phoenix_correlation_identifiers_and_privacy_redaction`: PASS
- `test_phoenix_evaluator_span_generation`: PASS
- `test_phoenix_live_export_and_query_if_collector_running`: PASS when online / cleanly SKIPPED when offline
