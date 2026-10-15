# PROJECT OUROBOROS: CONTAINER RUNTIME & ISOLATION VERIFICATION REPORT

**Document Version:** 1.0.0 (Release Candidate Verification)  
**Host Environment:** Windows 10 x64, Intel HD Graphics 620, 8 GB RAM Limit, Python 3.12.3, Node.js v24.14.1  
**Audit Purpose:** Verify live container sandboxing capabilities (Docker / Podman) and fail-closed security enforcement.  
**Runtime Status:** **DOCKER DAEMON OFFLINE — CONTAINER EXECUTION BLOCKED (SAFE)**  

---

## 1. Runtime Detection & Host Probes

Probes were executed directly on the host to assess container availability:

### 1.1 Docker CLI & Engine Probe
* **Command:** `docker version; docker info`
* **Exit Code:** `1 (ERROR)`
* **Output:**
  ```text
  Client:
   Cloud integration: v1.0.35+desktop.11
   Version:           25.0.3
   API version:       1.44
   Go version:        go1.21.6
   Git commit:        4debf41
   Built:             Tue Feb  6 21:13:02 2024
   OS/Arch:           windows/amd64
   Context:           default

  Server:
  ERROR: error during connect: this error may indicate that the docker daemon is not running:
  Get "http://%2F%2F.%2Fpipe%2Fdocker_engine/v1.24/info":
  open //./pipe/docker_engine: The system cannot find the file specified.
  ```
* **Observation:** Docker CLI version 25.0.3 is installed, but Docker Desktop / daemon is **not running**.

### 1.2 Podman Probe
* **Command:** `podman version`
* **Exit Code:** `1 (CommandNotFoundException)`
* **Output:**
  ```text
  podman : The term 'podman' is not recognized as the name of a cmdlet, function, script file, or operable program.
  ```
* **Observation:** Podman is not installed on this host.

---

## 2. Safe Fail-Closed Enforcement Verification

In accordance with strict application security principles:
> *"If no supported runtime is available, keep container execution marked BLOCKED and continue with safe, non-executing checks."*

### 2.1 Intrinsic Fail-Closed Test
* **Test Case:** `backend/tests/unit/test_adversarial_validation.py::test_pytest_runner_fails_closed_when_container_required`
* **Execution:**
  1. `monkeypatch.setattr(settings, "REQUIRE_CONTAINER_SANDBOX", True)`
  2. Invoke `pytest_runner.run_tests(working_dir=repo_path)`
* **Observed Result:**
  - `exit_code`: `1`
  - `passed`: `False`
  - `command`: `"BLOCKED"`
  - `failures`: `["EXECUTION BLOCKED: Strict container sandbox required by policy, but Docker is offline."]`
* **Subprocess Execution on Host:** **ZERO (0 subprocesses spawned).**
* **Status:** `VERIFIED (PASS)`.

---

## 3. Container Isolation Specification Matrix

When a live container runtime (Docker or Podman) is active, Project Ouroboros is configured with the following command-line and cgroup parameters:

| Security Parameter | Intended Flag / Configuration | Empirical Verification State | Rationale / Mitigation |
| :--- | :--- | :---: | :--- |
| **Non-Root User** | `--user 1000:1000` | `BLOCKED` (Daemon Offline) | Prevents containerized candidate code from escalating to root inside container. |
| **Network Isolation** | `--network none` | `BLOCKED` (Daemon Offline) | Prevents outbound credential exfiltration or C2 beaconing. |
| **Memory Bound** | `--memory 1500m` | `BLOCKED` (Daemon Offline) | Enforces strict host memory limits on 8 GB RAM system. |
| **CPU Bound** | `--cpus 1.0` | `BLOCKED` (Daemon Offline) | Prevents runaway multi-threaded infinite loops. |
| **PID Limit** | `--pids-limit 100` | `BLOCKED` (Daemon Offline) | Defends against fork-bombs inside container. |
| **Read-Only Root Filesystem** | Read-only base image (`python:3.12-slim`) | `BLOCKED` (Daemon Offline) | Base system binaries cannot be tampered with. |
| **Writable Volume** | `-v <worktree>:/workspace:rw -w /workspace` | `BLOCKED` (Daemon Offline) | Only the disposable candidate worktree directory is writable. |
| **Host Secrets Exclusion** | Zero `.env` / credentials mounted | `VERIFIED` (Code Level) | `run_safe_subprocess` strips cloud keys; no secret volumes mounted. |
| **Docker Socket Exclusion** | `/var/run/docker.sock` NEVER mounted | `VERIFIED` (Code Level) | Candidate code has zero access to host container daemon. |
| **Timeout & Tree Kill** | `--rm` + `taskkill /F /T /PID` | `VERIFIED` (Code Level) | Container automatically destroyed on exit; process tree killed on timeout. |

---

## 4. Fallback Mode: Restricted Local Subprocess

When `REQUIRE_CONTAINER_SANDBOX = False` (local developer workstation mode):
1. **Prominent UI Diagnostic:**
   - Sandbox status reports: `"Docker offline. Restricted local subprocess worktree sandbox active."`
   - Warnings displayed on Dashboard, Health, and Settings consoles.
2. **Local Guardrails Active:**
   - Git worktree filesystem boundary isolation (`worktrees/ouro-...`).
   - Static AST screen (`ASTSecurityVisitor`) blocks `os.system`, `subprocess.*`, `socket`, `ctypes`, `importlib`.
   - Bounded execution timeouts (`SUBPROCESS_TIMEOUT_SECONDS=45`).
   - Single concurrency mutex (`asyncio.Lock()`) prevents resource exhaustion.

---

## 5. Conclusion & Actionable Operator Steps

1. **Host State:** Container execution is currently **BLOCKED** as expected under fail-closed security rules.
2. **No Unsafe Fallback:** The system safely refuses to execute untrusted code without container isolation when `REQUIRE_CONTAINER_SANDBOX=True`.
3. **To Enable Live Container Sandboxing:**
   ```powershell
   # 1. Start Docker Desktop on Windows
   Start-Process "C:\Program Files\Docker\Docker\Docker Desktop.exe"

   # 2. Wait for daemon initialization
   docker info

   # 3. Pull required base execution image
   docker pull python:3.12-slim
   ```
4. **Current Recommendation:** Retain `REQUIRE_CONTAINER_SANDBOX=True` for untrusted public code evaluation.
