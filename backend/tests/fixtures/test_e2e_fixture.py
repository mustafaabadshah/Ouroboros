import os
import shutil
import tempfile
import asyncio
from pathlib import Path
import pytest

from app.core.security import run_safe_subprocess
from app.integrations.git.worktree import GitWorktreeManager
from app.integrations.git.diff_parser import UnifiedDiffParser
from app.evaluation.runner import PytestRunner
from app.evaluation.judge import DeterministicJudge
from app.memory.flywheel import FailureFlywheel
from app.database.session import Base
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

@pytest.mark.asyncio
async def test_deterministic_e2e_fixture_repair_lifecycle():
    """
    DETERMINISTIC END-TO-END DEMONSTRATION
    Executes the complete evolution lifecycle against an isolated fixture repository:
    1. Scaffold tiny fixture repository with git and pytest
    2. Run baseline tests -> PASS
    3. Define feature ticket
    4. Create candidate worktree
    5. Apply flawed patch (Attempt 1)
    6. Run candidate tests -> FAILS deliberately
    7. Persist failure trajectory to FailureFlywheel
    8. Synthesize and apply targeted repair patch (Attempt 2)
    9. Rerun candidate tests -> PASS
    10. DeterministicJudge delivers PASS verdict
    11. Verify original repository remains completely unchanged!
    """
    temp_dir = Path(tempfile.mkdtemp(prefix="ouro_e2e_"))
    try:
        repo_dir = temp_dir / "target_fixture_repo"
        worktrees_dir = temp_dir / "worktrees"
        repo_dir.mkdir(parents=True)
        worktrees_dir.mkdir(parents=True)

        # 1. Initialize Git Repo
        await run_safe_subprocess(["git", "init"], cwd=repo_dir)
        await run_safe_subprocess(["git", "config", "user.name", "Ouroboros"], cwd=repo_dir)
        await run_safe_subprocess(["git", "config", "user.email", "ouro@local"], cwd=repo_dir)

        # .gitignore
        (repo_dir / ".gitignore").write_text("__pycache__/\n*.py[cod]\n.pytest_cache/\n", encoding="utf-8")

        # Source Code: calculator.py
        src_file = repo_dir / "calculator.py"
        src_file.write_text("""def add(a, b):
    return a + b
""", encoding="utf-8")

        # Test Code: test_calculator.py
        test_file = repo_dir / "test_calculator.py"
        test_file.write_text("""from calculator import add

def test_add():
    assert add(2, 3) == 5
""", encoding="utf-8")

        await run_safe_subprocess(["git", "add", "-A"], cwd=repo_dir)
        await run_safe_subprocess(["git", "commit", "-m", "Initial commit"], cwd=repo_dir)
        await run_safe_subprocess(["git", "branch", "-M", "main"], cwd=repo_dir)

        # 2. Baseline Test Run
        runner = PytestRunner(default_timeout=20)
        baseline_res = await runner.run_tests(working_dir=repo_dir)
        assert baseline_res["passed"] is True
        assert baseline_res["passed_count"] == 1
        assert baseline_res["failed_count"] == 0

        # Snapshot of original code
        original_src_content = src_file.read_text(encoding="utf-8")

        # 3. Create Candidate Worktree
        worktree_mgr = GitWorktreeManager(base_worktree_dir=str(worktrees_dir))
        ticket_id = "ouro-fixture-001"
        worktree_path, cand_branch, base_commit = await worktree_mgr.create_worktree(
            repo_path=repo_dir,
            ticket_id=ticket_id
        )
        assert worktree_path.exists()

        # Add acceptance test for new function: multiply(a, b)
        wt_test_file = worktree_path / "test_calculator.py"
        wt_test_file.write_text("""from calculator import add, multiply

def test_add():
    assert add(2, 3) == 5

def test_multiply_acceptance():
    assert multiply(3, 4) == 12
""", encoding="utf-8")

        # 4. Attempt 1: Apply Flawed Patch (deliberate bug: multiply returns a + b instead of a * b)
        flawed_patch = """--- a/calculator.py
+++ b/calculator.py
@@ -1,2 +1,5 @@
 def add(a, b):
     return a + b
+
+def multiply(a, b):
+    return a + b
"""
        applied_ok, apply_msg = await worktree_mgr.apply_patch(worktree_path, flawed_patch)
        assert applied_ok is True

        # 5. Run Candidate Tests on Attempt 1 -> Must Fail!
        attempt1_eval = await DeterministicJudge.evaluate_candidate(
            worktree_path=worktree_path,
            baseline_results=baseline_res,
            acceptance_test_file=None,
            regression_test_dir="test_calculator.py"
        )
        assert attempt1_eval["verdict"] == "FAIL"
        assert attempt1_eval["regression"]["failed_count"] == 1

        # 6. Persist Failure Trajectory in Memory
        engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(bind=engine)
        SessionLocalTest = sessionmaker(bind=engine)
        test_db = SessionLocalTest()

        failure_record = FailureFlywheel.record_failure(
            db=test_db,
            run_id="run-fixture-1",
            ticket_id=ticket_id,
            attempt=1,
            failed_tests=["test_multiply_acceptance"],
            traceback_excerpt=attempt1_eval["regression"]["failures"][0]["traceback"],
            ast_diff={},
            patch_hash="flawed_hash_001",
            root_cause_hypothesis="multiply returns addition instead of multiplication",
            repair_hint="Use * operator instead of + in multiply",
            provider="mock",
            model="mock-v1"
        )
        assert failure_record.status == "UNRESOLVED"

        # 7. Attempt 2: Apply Repair Patch (fixes the bug to return a * b)
        repair_patch = """--- a/calculator.py
+++ b/calculator.py
@@ -4,2 +4,2 @@
 def multiply(a, b):
-    return a + b
+    return a * b
"""
        repair_ok, repair_msg = await worktree_mgr.apply_patch(worktree_path, repair_patch)
        assert repair_ok is True, f"Repair patch failed to apply: {repair_msg}"

        # 8. Rerun Tests on Attempt 2 -> Must Pass!
        attempt2_eval = await DeterministicJudge.evaluate_candidate(
            worktree_path=worktree_path,
            baseline_results=baseline_res,
            acceptance_test_file=None,
            regression_test_dir="test_calculator.py"
        )
        assert attempt2_eval["verdict"] == "PASS"
        assert attempt2_eval["regression"]["passed_count"] == 2
        assert attempt2_eval["regression"]["failed_count"] == 0

        # 9. Verify Original Repository Remains Completely Unchanged
        current_original_src = src_file.read_text(encoding="utf-8")
        assert current_original_src == original_src_content, "CRITICAL: Original repository was mutated!"

        # Check git status of original repository
        code, out, _ = await run_safe_subprocess(["git", "status", "--porcelain"], cwd=repo_dir)
        assert out.strip() == "", "Original repository has uncommitted changes!"

        # Cleanup worktree
        await worktree_mgr.remove_worktree(repo_dir, ticket_id, cand_branch)
        assert not worktree_path.exists()
        test_db.close()

    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)
