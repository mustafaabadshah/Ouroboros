# PROJECT OUROBOROS: LOCAL DEVELOPMENT GUIDE
**Target Machine:** Windows 10/11 x64 (8 GB RAM Limit, Intel HD 620 iGPU)  
**Python Runtime:** Python 3.12.3 in virtual environment `.venv`  
**Node.js Runtime:** Node.js v24.14.1 (npm v11.11.0)  

---

## 1. Prerequisites Setup

1. **Python Virtual Environment:**
   ```powershell
   python -m venv .venv
   .\.venv\Scripts\Activate.ps1
   pip install -r backend/requirements.txt
   ```
2. **Frontend Dependencies:**
   ```powershell
   cd frontend
   npm install
   cd ..
   ```
3. **Configuration:**
   ```powershell
   Copy-Item .env.example .env
   # Edit .env to add your GROQ_API_KEY if cloud reasoning is desired
   ```

---

## 2. Windows Lifecycle Scripts

We provide dedicated PowerShell scripts to start, stop, test, and diagnose the application:

* **Diagnose Host System & Hardware:**
  ```powershell
  powershell -ExecutionPolicy Bypass scripts/check-environment.ps1
  ```
* **Start All Services (Backend, Phoenix Tracing, Frontend):**
  ```powershell
  powershell -ExecutionPolicy Bypass scripts/start.ps1
  ```
  * Frontend: `http://localhost:5173/`
  * Backend API: `http://127.0.0.1:8000/docs`
  * Arize Phoenix UI: `http://127.0.0.1:6006/`
* **Stop All Running Services Gracefully:**
  ```powershell
  powershell -ExecutionPolicy Bypass scripts/stop.ps1
  ```
* **Execute the Automated Test Suite:**
  ```powershell
  powershell -ExecutionPolicy Bypass scripts/test.ps1
  ```

---

## 3. Sandboxing & Memory Guardrails

* **8 GB RAM Guardrail:** Because host physical RAM is limited, Ouroboros restricts local model concurrency to `1` generation worker. If free RAM falls below `1500 MB`, `ram_warning=True` triggers backpressure.
* **Fail-Closed Mode:** To require strict Docker container execution, set `REQUIRE_CONTAINER_SANDBOX=true` in `.env`.
