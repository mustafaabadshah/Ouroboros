# PROJECT OUROBOROS: PRIVACY, SECRETS & TELEMETRY POLICY
**Document Version:** 1.0.0 (Production Hardening)  
**Classification:** Data Privacy & Telemetry Standard  
**Status:** ACTIVE  

---

## 1. Principles of Code Privacy

Project Ouroboros is built to respect proprietary source code and intellectual property. The system enforces strict boundaries to ensure that source code, environment credentials, and internal architectures are not leaked to external providers or unauthenticated telemetry endpoints without explicit operator consent.

---

## 2. Model Provider Privacy Controls

### 2.1 Dual-Tier Isolation
1. **Tier 1: Local Quantized Model (Ollama CPU):**
   - Inference runs 100% offline on the host machine.
   - **Zero network bytes** leave your computer.
   - Ideal for confidential, air-gapped, or regulated environments.
2. **Tier 2: Remote Fallback (Groq Cloud API):**
   - **Explicit Consent Required:** Governed by `ALLOW_REMOTE_FALLBACK=True` and `STRICT_LOCAL_ONLY=False`.
   - If `STRICT_LOCAL_ONLY=True`, Ouroboros will **never** transmit code to any external API; if local models fail or are unavailable, execution halts with a `BLOCKED` status.
   - API keys are stored strictly in backend server environment variables (`.env`) and are **never** delivered to the frontend, browser localStorage, or client logs.

---

## 3. Arize Phoenix & OpenTelemetry Privacy

Arize Phoenix is embedded locally at `http://127.0.0.1:6006/` for tracing agent reasoning trajectories.

### 3.1 Privacy Configurations (`backend/app/core/config.py`)
* `PHOENIX_CAPTURE_PROMPTS=False` (Default):
  - When disabled, prompt text and raw LLM completion content are stripped from OpenTelemetry spans.
  - Spans record only execution metadata: duration, token count, model identifier, and pass/fail verdict.
* `PHOENIX_MASK_CODE_SNIPPETS=True` (Default):
  - Automatically redacts long source file listings and diff hunks from telemetry attributes.
* **Secret Scrubbing:**
  - The `mask_secret()` sanitizer scrubs all recognized API keys (e.g. `gsk_...Uctb`) and password patterns before any span is exported to the collector.

---

## 4. Secret Protection Checklist

| Secret Type | Storage Location | Protection Mechanism |
| :--- | :--- | :--- |
| **Groq API Key** | Backend `.env` only | Scrubbed via `mask_secret()`; excluded from git (`.gitignore`). |
| **SSH Keys / Certs** | `~/.ssh` / OS keystore | Blocked by `validate_safe_path()` from reading `.pem`, `id_rsa`. |
| **Local SQLite DB** | `ouroboros.db` | Scrubbed of raw keys; excluded from public commits. |
| **Phoenix Traces** | Local SQLite / Memory | Bound to `127.0.0.1` only; no external telemetry collector. |
