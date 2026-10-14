# Project Ouroboros: Troubleshooting & Operations Guide
**Document ID:** OPS-OURO-001  

---

## 1. Memory Pressure & RAM Warning Alerts

### Symptom
Dashboard top navigation bar displays a yellow warning: `LOW RAM WARNING: < 1500 MB FREE`.

### Causes
Windows background processes, browser tabs, or Antigravity memory consumption pushing free physical RAM below 1.5 GB.

### Mitigations
1. **Unload Inactive Local Models:**
   Ollama automatically unloads models after 5 minutes of idle time. You can manually force an unload via the **Models & Providers** dashboard tab by clicking **Unload Model**.
2. **Enable Remote Fallback:**
   In **Settings > Models**, ensure **Allow Remote Fallback** is toggled ON. Complex reasoning will route to Groq API rather than loading large local models.
3. **Close Superfluous Browser Tabs:**
   Keep only one instance of `http://localhost:5173` open during active runs.

---

## 2. Git Worktree & Branch Conflicts

### Symptom
Run fails during worktree creation with:
`fatal: a branch named 'candidate/ouro-...' already exists` or `worktree already exists`.

### Mitigation
The backend includes automated pruning in `GitWorktreeManager`, but if an external process aborted uncleanly:
1. Open PowerShell in the target repository directory (e.g. `E:\MM Office\Agent Chess`):
   ```powershell
   git worktree prune
   git branch -D candidate/ouro-de9451
   ```
2. Delete the temporary worktree folder if it remains:
   ```powershell
   Remove-Item -Recurse -Force "E:\MM Office\Ouroboros\worktrees\ouro-de9451"
   ```

---

## 3. Windows Line Endings (CRLF vs LF) in Patches

### Symptom
Git apply dry-run reports `error: patch failed at line ...` or `corrupt patch at line ...`.

### Resolution
- Ouroboros automatically normalizes all incoming diff patches to binary UTF-8 with LF line endings (`\n`) and appends `--ignore-whitespace` to `git apply`.
- Ensure your Git global configuration handles line endings cleanly:
  ```powershell
  git config core.autocrlf false
  ```

---

## 4. Port Conflicts (8000 or 5173 Already in Use)

### Symptom
Backend fails to start with `[Errno 10048] error while attempting to bind on address ('127.0.0.1', 8000)`.

### Resolution
Run the provided stop script to terminate orphaned instances:
```powershell
powershell -ExecutionPolicy Bypass scripts/stop.ps1
```
Alternatively, identify and kill the process manually:
```powershell
netstat -ano | findstr :8000
taskkill /F /PID <PID>
```

---

## 5. Offline Demonstration & Testing

### Running Without External Services
To run the deterministic test suite without Ollama, Groq credentials, or network access:
```powershell
powershell -ExecutionPolicy Bypass scripts/test.ps1
```
All 11 unit and integration tests (including the deterministic end-to-end fixture test) pass completely offline using `MockProvider`.
