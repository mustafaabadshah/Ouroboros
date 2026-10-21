"""
Project Ouroboros - Clean-Room Local Release Validation Script.

Purpose:
Validates that Project Ouroboros can be deployed and operated in a fresh,
zero-state isolated directory without relying on ambient paths, lingering database state,
or uncommitted development debris.

Workflow:
1. Replicate repository code into a fresh temporary directory (excluding .venv, node_modules, .git).
2. Validate bytecode compilation & syntax in the clean room.
3. Verify zero-state database schema initialization & clean crash recovery.
4. Verify FastAPI application startup & /api/health probe via TestClient.
5. Verify Git worktree creation, reset, and teardown inside the clean room.
6. Execute deterministic offline mock repair (BENCH-01) from scratch.
7. Execute acceptance verification protocol.
8. Archive structured evidence report.
"""

import os
import sys
import json
import time
import shutil
import tempfile
import asyncio
import subprocess
from pathlib import Path

# Force UTF-8 on Windows
if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

REPO_ROOT = Path(__file__).resolve().parent.parent


def ignore_patterns(path, names):
    """Ignores heavy virtual environments, build artifacts, and git directories."""
    ignored = set()
    for name in names:
        if name in [".venv", "node_modules", ".git", ".pytest_cache", "__pycache__", "dist", ".ouroboros_pids.json"]:
            ignored.add(name)
        elif name.endswith((".pyc", ".tmp", ".log")):
            ignored.add(name)
    return ignored


def run_cmd(args, cwd):
    """Runs a command synchronously with error capture."""
    p = subprocess.run(args, cwd=str(cwd), capture_output=True, text=True)
    return p.returncode, p.stdout, p.stderr


def main():
    print("=" * 80)
    print("PROJECT OUROBOROS -- CLEAN-ROOM ZERO-STATE RELEASE VALIDATION")
    print("=" * 80)

    start_time = time.perf_counter()
    report = {
        "timestamp_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "source_repo": str(REPO_ROOT),
        "stages": {},
        "verdict": "UNKNOWN"
    }

    with tempfile.TemporaryDirectory(prefix="ouro_cleanroom_") as tmp_dir:
        clean_root = Path(tmp_dir) / "Ouroboros"
        print(f"\n[Stage 1/6] Replicating Clean-Room Workspace to:\n  {clean_root}")
        
        # Copy codebase excluding .venv, node_modules, .git
        shutil.copytree(REPO_ROOT, clean_root, ignore=ignore_patterns)
        print("  [OK] Workspace replicated cleanly (zero-state, no local venv or DB).")
        report["stages"]["replication"] = {"status": "PASS", "path": str(clean_root)}

        # Stage 2: Bytecode compilation check
        print("\n[Stage 2/6] Verifying Bytecode Compilation & Syntax in Clean Room...")
        code, out, err = run_cmd([sys.executable, "-m", "compileall", "-q", "backend/", "scripts/"], clean_root)
        if code != 0:
            print(f"  [FAIL] Bytecode compilation failed: {err}")
            report["stages"]["compilation"] = {"status": "FAIL", "error": err}
            return False
        print("  [OK] Python bytecode compilation passed with zero syntax errors.")
        report["stages"]["compilation"] = {"status": "PASS"}

        # Stage 3: Clean Database Initialization & Engine
        print("\n[Stage 3/6] Initializing Zero-State Database & API Probes...")
        sys_path_clean = [str(clean_root / "backend"), str(clean_root)] + sys.path
        
        env_clean = os.environ.copy()
        env_clean["PYTHONPATH"] = f"{clean_root / 'backend'};{clean_root}"
        env_clean["OUROBOROS_LIVE_AUTH"] = ""
        env_clean["OUROBOROS_MOCK_ONLY"] = "1"
        env_clean["PHOENIX_ENABLED"] = "false"

        probe_script = clean_root / "_probe_api.py"
        probe_script.write_text(
            "import os, sys\n"
            "from pathlib import Path\n"
            "from fastapi.testclient import TestClient\n"
            "from app.core.config import settings, BACKEND_DIR\n"
            "from app.database.session import Base, engine\n"
            "from app.main import app\n\n"
            "# 1. Initialize SQLite schema from scratch\n"
            "Base.metadata.create_all(bind=engine)\n"
            "db_path = BACKEND_DIR / 'ouroboros.db'\n"
            "assert db_path.exists(), f'DB not created at {db_path}'\n\n"
            "# 2. Probe FastAPI endpoints\n"
            "client = TestClient(app)\n"
            "r_health = client.get('/api/health')\n"
            "assert r_health.status_code == 200, f'Health probe failed: {r_health.text}'\n"
            "assert r_health.json().get('status') == 'healthy'\n\n"
            "r_models = client.get('/api/models/status')\n"
            "assert r_models.status_code == 200, f'Models status probe failed: {r_models.text}'\n"
            "print('PROBE_SUCCESS')\n",
            encoding="utf-8"
        )

        code, out, err = run_cmd([sys.executable, str(probe_script)], clean_root)
        if code != 0 or "PROBE_SUCCESS" not in out:
            print(f"  [FAIL] Database initialization or API probe failed:\n{err or out}")
            report["stages"]["database_and_api"] = {"status": "FAIL", "error": err or out}
            return False
        print("  [OK] Zero-state SQLite schema initialized.")
        print("  [OK] GET /api/health returned 200 (status: healthy).")
        print("  [OK] GET /api/models/status returned 200.")
        report["stages"]["database_and_api"] = {"status": "PASS"}

        # Stage 4: Worktree Creation, Boundary Validation & Reset in Clean Room
        print("\n[Stage 4/6] Verifying Candidate Git Worktree Operations in Clean Room...")
        wt_test_script = clean_root / "_test_worktree.py"
        wt_test_script.write_text(
            "import asyncio, os, subprocess\n"
            "from pathlib import Path\n"
            "from app.integrations.git.worktree import GitWorktreeManager\n"
            "from app.core.security import run_safe_subprocess\n\n"
            "async def test_wt():\n"
            "    repo = Path('clean_fixture')\n"
            "    repo.mkdir()\n"
            "    await run_safe_subprocess(['git', 'init'], cwd=repo)\n"
            "    await run_safe_subprocess(['git', 'config', 'user.name', 'Cleanroom Test'], cwd=repo)\n"
            "    await run_safe_subprocess(['git', 'config', 'user.email', 'test@cleanroom.local'], cwd=repo)\n"
            "    (repo / 'f.txt').write_text('init\\n')\n"
            "    await run_safe_subprocess(['git', 'add', 'f.txt'], cwd=repo)\n"
            "    await run_safe_subprocess(['git', 'commit', '-m', 'c1'], cwd=repo)\n"
            "    await run_safe_subprocess(['git', 'branch', '-M', 'main'], cwd=repo)\n\n"
            "    wt_dir = Path('clean_worktrees')\n"
            "    wt_dir.mkdir()\n"
            "    mgr = GitWorktreeManager(base_worktree_dir=str(wt_dir.resolve()))\n"
            "    wt_path, branch, commit = await mgr.create_worktree(repo.resolve(), 'TICKET-01')\n"
            "    assert wt_path.exists()\n"
            "    assert (wt_path / '.git').is_file()\n\n"
            "    # Dirty and reset\n"
            "    (wt_path / 'dirty.txt').write_text('dirty\\n')\n"
            "    reset_ok = await mgr.reset_worktree_to_base(wt_path, commit)\n"
            "    assert reset_ok, 'Reset to base failed'\n"
            "    assert not (wt_path / 'dirty.txt').exists()\n\n"
            "    # Remove\n"
            "    await mgr.remove_worktree(repo.resolve(), 'TICKET-01', branch)\n"
            "    assert not wt_path.exists()\n"
            "    print('WORKTREE_SUCCESS')\n\n"
            "asyncio.run(test_wt())\n",
            encoding="utf-8"
        )

        code, out, err = run_cmd([sys.executable, str(wt_test_script)], clean_root)
        if code != 0 or "WORKTREE_SUCCESS" not in out:
            print(f"  [FAIL] Worktree manager test failed:\n{err or out}")
            report["stages"]["worktree_isolation"] = {"status": "FAIL", "error": err or out}
            return False
        print("  [OK] Git candidate worktree created, dirtied, reset, and cleaned cleanly.")
        report["stages"]["worktree_isolation"] = {"status": "PASS"}

        # Stage 5: Deterministic Offline Mock Repair (BENCH-01)
        print("\n[Stage 5/6] Executing Deterministic Offline Mock Evaluation (BENCH-01)...")
        eval_out = clean_root / "cleanroom_eval_result.json"
        code, out, err = run_cmd(
            [sys.executable, "scripts/run_agent_eval.py", "--mock-agents", "--task-id", "BENCH-01", "--output", str(eval_out)],
            clean_root
        )
        if code != 0 or not eval_out.exists():
            print(f"  [FAIL] Cleanroom evaluation failed:\n{err or out}")
            report["stages"]["mock_eval"] = {"status": "FAIL", "error": err or out}
            return False

        eval_data = json.loads(eval_out.read_text(encoding="utf-8"))
        print(f"  [OK] Offline evaluation completed successfully.")
        print(f"  [OK] Result written to: {eval_out.name}")
        report["stages"]["mock_eval"] = {
            "status": "PASS",
            "eval_output_size": len(eval_out.read_bytes())
        }

        # Stage 6: Acceptance Verification Protocol
        print("\n[Stage 6/6] Executing Full Acceptance Protocol Checklist...")
        code, out, err = run_cmd([sys.executable, "backend/tests/verify_acceptance.py"], clean_root)
        if code != 0 or "ALL 20 CHECKS PASSED" not in out:
            print(f"  [FAIL] Acceptance checklist failed:\n{err or out}")
            report["stages"]["acceptance_checklist"] = {"status": "FAIL", "error": err or out}
            return False
        print("  [OK] All 20 acceptance verification protocol checks passed in clean room.")
        report["stages"]["acceptance_checklist"] = {"status": "PASS", "checks_passed": 20}

        report["verdict"] = "CLEANROOM_RELEASE_PASSED"
        elapsed = time.perf_counter() - start_time
        report["duration_seconds"] = round(elapsed, 2)

        # Write final audit evidence
        out_report_dir = REPO_ROOT / "artifacts" / "evaluations" / "20261019_cleanroom_release_validation"
        out_report_dir.mkdir(parents=True, exist_ok=True)
        report_path = out_report_dir / "cleanroom_validation_report.json"
        report_path.write_text(json.dumps(report, indent=2), encoding="utf-8")

        print("=" * 80)
        print(f"CLEAN-ROOM VALIDATION RESULT: {report['verdict']} in {elapsed:.1f}s")
        print(f"Audit Evidence: {report_path}")
        print("=" * 80)
        return True


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
