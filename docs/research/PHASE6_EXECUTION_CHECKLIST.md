# Project Ouroboros — Phase 6 Pre-Flight Execution Checklist
## Operational Verification, Safeguards, and Live Inference Authorization Protocol

**Milestone:** Phase 6 Pre-Flight Safety Protocol  
**Date:** `2026-10-18`  
**Target Repository:** `E:\MM Office\Ouroboros`  
**Git Branch:** `hotfix/python-package-discovery`  
**Git HEAD:** `dd36b27007bb369972ecd502a82c4ce15a8a8c94`  

---

## 1. Prerequisites and Environment Verification

Before Phase 6 live execution can be authorized or initiated, all of the following conditions must be satisfied:

### 1.1 Integrity & Historical Artifact Invariance
- [ ] Working tree status inspected via `git status --short`.
- [ ] No destructive Git commands (`git reset`, `git clean`, `checkout -f`, `stash`) used.
- [ ] SHA-256 hashes of historical artifacts verified as identical:
  - `artifacts/v0_11/phase5_live_llm_pilot_4tasks.json` (`eff1e9c1088db86ee717b0d7a3645a200dc1398e114a5ce3e3a4471f14d33442`)
  - `artifacts/evaluations/20261018_104036_agent_eval/agent_eval_run.json` (`eff1e9c1088db86ee717b0d7a3645a200dc1398e114a5ce3e3a4471f14d33442`)
  - `artifacts/v0_11/memory_ablation.json` (`eff1e9c1088db86ee717b0d7a3645a200dc1398e114a5ce3e3a4471f14d33442`)
- [ ] `git diff --check` passes with exit code 0.

### 1.2 Telemetry & Observability Health
- [ ] Phoenix service is running on `http://127.0.0.1:6006` or local OTLP port `4317`/`4318`.
- [ ] Phoenix health check passes (`curl http://127.0.0.1:6006/` or python request).
- [ ] Tracing exporter endpoint configured in `backend/app/observability/phoenix_service.py`.

### 1.3 Provider Authentication & Quota
- [ ] `GROQ_API_KEY` is set in the runtime environment (never hardcoded in code, git diffs, or logs).
- [ ] Verified valid Groq account tier and sufficient credit balance for target model `llama-3.3-70b-versatile`.
- [ ] Rate limits understood (Groq free/tier limits: RPM / TPM constraints).

---

## 2. Structural Safety Controls Audit

Ensure that the structural safety controls implemented in Phase 5.1.2 are active:

### 2.1 Fail-Closed Provider Routing
- [ ] `ModelRouter` is initialized in `live` mode.
- [ ] Any provider error (`401 Unauthorized`, `429 Rate Limit`, `500 Server Error`, timeouts) returns a typed status code and **does not fall back to `MockProvider`**.
- [ ] API keys are redacted from error logs.
- [ ] No synthetic diffs are injected upon provider failure.

### 2.2 Output Destination Safety
- [ ] A dedicated, unique output path is specified (e.g. `--output artifacts/v0_11/phase6_live_llm_experiment_15tasks.json`).
- [ ] Output destination does not exist, or `--overwrite` is explicitly provided if replacing an intentional run.
- [ ] Destination path is within repository bounds.
- [ ] Atomic write mechanism verified via `.tmp` file and `os.replace`.
- [ ] Historical `memory_ablation.json` will NOT be touched (flag `--export-ablation-report` omitted unless explicitly requested).

### 2.3 Central Budget Controller
- [ ] Central request limit configured (e.g., maximum 90 requests for 15 tasks × 2 strategies × 3 attempts).
- [ ] Token ceiling enforced at maximum 60,000 tokens (fails closed before dispatch if reserved tokens exceed remaining balance).
- [ ] Dollar spend ceiling enforced at $0.10 USD (calculated at $0.20 per 1M tokens with fail-closed pricing validation).
- [ ] Minimum 3.0-second pacing interval between consecutive outbound API calls active.

---

## 3. Live Execution Authorization Protocol

### 3.1 Interactive Mode Confirmation
When executing from an interactive terminal:
```powershell
python scripts/run_agent_eval.py --live --tasks bench01 bench02 bench03 bench04 bench05 bench06 bench07 bench08 bench09 bench10 bench11 bench12 bench13 bench14 bench15 --output artifacts/v0_11/phase6_live_llm_experiment_15tasks.json
```
The operator must review the authorization banner displayed on stdout:
1. Target Model identifier (`llama-3.3-70b-versatile`)
2. Evaluated Task IDs and count
3. Evaluation Strategies (`flywheel_escalation`, `naive_retry`)
4. Maximum request count ceiling
5. Total token ceiling (60,000)
6. Total dollar cost ceiling ($0.10 USD)
7. Minimum pacing interval (3.0s)
8. Output path verification
9. **Interactive Prompt:** Type `yes` to proceed. Typing any other string terminates the run immediately with exit code 2 before any remote call is dispatched.

### 3.2 Non-Interactive / CI Confirmation Safeguard
If executed in a headless or automated runner (`sys.stdin.isatty() == False`), the runner will terminate immediately with code 2 unless the environment variable is explicitly set:
```powershell
$env:OUROBOROS_LIVE_AUTH = "I_CONFIRM_LIVE_API_CALLS"
```

---

## 4. Run Monitoring and Abort Procedures

During execution:
- [ ] Monitor real-time logs for provider status codes.
- [ ] If HTTP 429 rate limits occur, verify bounded backoff is respected.
- [ ] If unexpected errors occur, press `Ctrl+C` once.
- [ ] Verify that upon interrupt, `scripts/run_agent_eval.py` writes partial records to `*_partial.json` safely without corrupting primary files.
- [ ] Check Phoenix dashboard (`http://localhost:6006`) to monitor trace graphs, latency, and span tags.

---

## 5. Post-Run Verification and Analysis

Upon completion of Phase 6:
- [ ] Verify output file exists and is valid JSON.
- [ ] Confirm timestamped archive exists in `artifacts/evaluations/<timestamp>_agent_eval/`.
- [ ] Verify total requests, total tokens, and total dollar spend remained strictly within configured ceilings.
- [ ] Audit complete-pair vs. incomplete-pair breakdown using `analyze_paired_complete_pairs`.
- [ ] Compute McNemar's exact test and Odds Ratio for paired concordance matrix.
- [ ] Re-verify historical artifact SHA-256 hashes to guarantee zero retroactive pollution.
