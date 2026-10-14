# Project Ouroboros: Security & Isolation Architecture
**Document ID:** SEC-OURO-001  
**Classification:** Engineering Security Controls  

---

## 1. Threat Model & Design Assumptions

Project Ouroboros operates under the assumption that **all model-generated outputs, proposed tickets, unified diff patches, and generated test cases are untrusted input**.

### Threat Vectors Addressed
1. **Arbitrary Code Execution via Patches:** Candidate diffs attempting to execute malware, open network sockets, or delete files during pytest runs.
2. **Path Traversal Attacks:** Diff headers or subtask paths attempting to escape repository roots (e.g., `--- a/../../Windows/System32/...`).
3. **Protected Engine Tampering:** LLMs attempting to bypass chess legality rules, Stockfish safety checks, or authentication boundaries to make a failing test pass artificially.
4. **Credential Leakage:** Accidental exposure of API keys (Groq, Anthropic, OpenAI) to the browser, logs, or SQLite database.
5. **Unauthorized Repository Mutation:** Autonomous agents committing or merging directly into production branches without human sign-off.

---

## 2. Path Traversal & Repository Boundary Controls

All filesystem interactions are mediated through `app.core.security.validate_safe_path`:
```python
def validate_safe_path(target_path: Path, allowed_root: Path) -> Path:
    resolved_target = target_path.resolve()
    resolved_root = allowed_root.resolve()
    if not str(resolved_target).startswith(str(resolved_root)):
        raise PermissionError(f"Access denied: Path '{target_path}' escapes root '{allowed_root}'.")
    return resolved_target
```
- Reject absolute paths attempting to access non-registered workspaces.
- Disallow symlinks pointing outside the repository boundary.
- Prohibit modifications to `.git/`, `.env`, and virtual environment directories.

---

## 3. Secret Isolation & API Key Management

### Backend-Only Secret Storage
- API keys (e.g., `GROQ_API_KEY`) are read strictly on the backend from `Ouroboros/.env` or OS environment variables.
- **Never sent to frontend:** REST API models and schemas exclude the actual secret key.
- **Masking:** When provider status is queried, secrets are masked (`gsk_...Uctb`).
- **Log Sanitation:** All HTTP client errors and process tracebacks sanitize `Authorization` and `Bearer` headers prior to writing to console or disk logs.

---

## 4. Protected Files & AST Symbol Modification Policy

The following paths in target repositories are designated as **Protected Files**:
- `backend/app/chess/validator.py` (Chess legality and move verification)
- `backend/app/chess/stockfish.py` (Engine process management and safety)
- `backend/app/core/config.py` (Core security settings and environment configurations)
- `backend/app/main.py` (CORS policies and root middleware)

### Enforcement Mechanism
1. **Static Diff Boundary Inspection:** `UnifiedDiffParser` rejects any patch that includes a header referencing a protected file.
2. **AST Change Analyzer:** `ASTChangeAnalyzer` scans the AST before and after patching. Any alteration to protected function definitions (`is_legal_move`, `validate_fen`, etc.) results in an immediate `FAIL` verdict by `DeterministicJudge`.

---

## 5. Execution Sandboxing & Subprocess Isolation

### Process Invocation Controls
- Subprocesses are spawned using explicit argument lists (`["python", "-m", "pytest", ...]`), **never raw shell string concatenation**.
- Environment variables are scrubbed: child processes inherit only necessary runtime paths; credentials not explicitly required by the test runner are stripped.
- Strict execution timeouts (default: 45–60s) terminate hung processes or infinite loops.
- Standard output and error streams are bounded to 64 KB to prevent memory exhaustion attacks.

### Git Worktree Isolation
- Every candidate patch executes in a dedicated disposable worktree (`worktrees/<ticket_id>`).
- Original repository branches are never modified or checked out during evaluation.
- Merge operations are blocked until a human operator clicks **Approve & Merge** in the dashboard.
