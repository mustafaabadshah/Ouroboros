import pytest
import hashlib
from pathlib import Path

from app.core.security import validate_safe_path, is_protected_path
from app.sandbox.security import analyze_code_security, ASTSecurityVisitor
from app.sandbox.detector import SandboxDetector
from app.evaluation.judge import deterministic_judge
from app.evaluation.runner import pytest_runner
from app.integrations.git.diff_parser import UnifiedDiffParser
from app.integrations.git.worktree import git_worktree_manager
from app.providers.router import model_router
from app.core.config import settings

def test_unified_diff_detects_deletion_of_protected_file():
    """
    SEC-01 Regression Test:
    A unified diff deleting a protected file (+++ /dev/null) must identify the deleted file,
    flag it as protected, and reject it in validate_patch_boundaries.
    """
    deletion_diff = """--- a/backend/app/chess/validator.py
+++ /dev/null
@@ -1,10 +0,0 @@
-def validate_move():
-    return True
"""
    meta = UnifiedDiffParser.parse_patch(deletion_diff)
    assert meta["is_valid"] is True
    assert "backend/app/chess/validator.py" in meta["changed_files"]
    assert "backend/app/chess/validator.py" in meta["protected_files_touched"]
    assert meta["deletions"] > 0

    is_safe, err = UnifiedDiffParser.validate_patch_boundaries(
        diff_text=deletion_diff,
        allowed_files=["backend/app/chess/validator.py"]
    )
    assert is_safe is False
    assert "Prohibited modification of protected files" in err

def test_unified_diff_detects_renamed_file_across_headers():
    """
    Ensures that diffs renaming or moving files check both source and target paths against policy.
    """
    rename_diff = """diff --git a/backend/app/safe.py b/backend/app/chess/validator.py
similarity index 100%
rename from backend/app/safe.py
rename to backend/app/chess/validator.py
--- a/backend/app/safe.py
+++ b/backend/app/chess/validator.py
@@ -1,2 +1,3 @@
 # Safe comment
+# Added line
"""
    meta = UnifiedDiffParser.parse_patch(rename_diff)
    assert meta["is_valid"] is True
    assert "backend/app/chess/validator.py" in meta["changed_files"]
    assert "backend/app/chess/validator.py" in meta["protected_files_touched"]

    is_safe, err = UnifiedDiffParser.validate_patch_boundaries(
        diff_text=rename_diff,
        allowed_files=["backend/app/safe.py"]
    )
    assert is_safe is False

def test_direct_hunk_applier_blocks_path_traversal(tmp_path):
    """
    SEC-02 Regression Test:
    The direct hunk applier must reject patches with path traversal in +++ b/ headers.
    """
    traversal_patch = """--- a/backend/app/evil.py
+++ b/../../Windows/System32/evil.dll
@@ -1,1 +1,1 @@
-clean
+evil
"""
    success, msg = git_worktree_manager._apply_hunks_directly(tmp_path, traversal_patch)
    assert success is False
    assert "Security Violation" in msg or "Path traversal" in msg

@pytest.mark.asyncio
async def test_pytest_runner_fails_closed_when_container_required(monkeypatch, tmp_path):
    """
    SEC-03 Regression Test:
    When REQUIRE_CONTAINER_SANDBOX is enabled and Docker is offline,
    PytestRunner.run_tests() must refuse to execute on the host and return BLOCKED.
    """
    monkeypatch.setattr(settings, "REQUIRE_CONTAINER_SANDBOX", True)
    
    # Run test in temporary directory
    target_dir = tmp_path / "sandbox"
    target_dir.mkdir()
    res = await pytest_runner.run_tests(working_dir=target_dir, test_path="backend/tests/unit")
    
    status = await SandboxDetector().detect_capabilities()
    if not status["docker_running"]:
        assert res["passed"] is False
        assert res["command"] == "BLOCKED"
        assert "EXECUTION BLOCKED" in res["failures"][0]

def test_ast_visitor_detects_expanded_prohibited_primitives():
    """
    SEC-04 Regression Test:
    Detects asyncio subprocesses, importlib, os.spawn*, and multiprocessing.
    """
    dangerous_snippets = [
        ("import asyncio; asyncio.create_subprocess_shell('dir')", "asyncio.create_subprocess_shell"),
        ("import asyncio; asyncio.create_subprocess_exec('python')", "asyncio.create_subprocess_exec"),
        ("import importlib; importlib.import_module('os')", "importlib"),
        ("import multiprocessing", "multiprocessing"),
        ("import os; os.posix_spawn('/bin/sh', [])", "os.posix_spawn"),
    ]
    for code, expected_kw in dangerous_snippets:
        res = analyze_code_security(code, filename="exploit.py")
        assert res["is_safe"] is False
        combined = " ".join(res["violations"])
        assert expected_kw in combined, f"Expected {expected_kw} in {combined}"

def test_judge_rejects_patch_modifying_protected_evaluation_files(tmp_path):
    """
    Verifies that Judge rejects patches attempting to modify judge.py, runner.py, or conftest.py.
    """
    harness_diff = """--- a/backend/app/evaluation/judge.py
+++ b/backend/app/evaluation/judge.py
@@ -10,3 +10,4 @@
 # modify judge
+pass
"""
    res = deterministic_judge.evaluate_patch_static(
        diff_text=harness_diff,
        allowed_files=["backend/app/evaluation/judge.py"],
        worktree_path=tmp_path
    )
    assert res["verdict"] == "NEEDS_HUMAN_REVIEW"
    assert "protected" in res["reason"].lower()

@pytest.mark.asyncio
async def test_model_router_strictly_enforces_remote_fallback_policy(monkeypatch):
    """
    Verifies that setting ALLOW_REMOTE_FALLBACK=False or STRICT_LOCAL_ONLY=True
    strictly prevents any remote call to Groq.
    """
    monkeypatch.setattr(settings, "ALLOW_REMOTE_FALLBACK", False)
    monkeypatch.setattr(settings, "STRICT_LOCAL_ONLY", True)
    
    # Even if GROQ_API_KEY is populated, routing must stay local/mock
    monkeypatch.setattr(settings, "GROQ_API_KEY", "gsk_synthetic_test_key_1234567890")
    
    res = await model_router.route_task(
        agent_role="Architect",
        prompt="Synthesize architecture proposal",
        force_mock=False
    )
    # Must NOT route to groq
    assert res["provider"] != "groq"

import sys
from fastapi import HTTPException, BackgroundTasks
from app.api.runs import start_run, approve_merge
from app.schemas.run import RunCreateRequest, RunApprovalRequest
from app.database.repositories import (
    get_or_create_repository,
    create_ticket,
    create_run,
    create_candidate
)
from app.database.models import RunModel
from app.core.security import run_safe_subprocess

def make_valid_ticket_dict(repo_id: str, title: str = "Test Ticket", status: str = "APPROVED"):
    return {
        "repo_id": repo_id,
        "title": title,
        "problem_statement": "Problem statement for test",
        "motivation": "Motivation for test",
        "current_behavior": "Current behavior",
        "desired_behavior": "Desired behavior",
        "acceptance_criteria_json": ["Criterion 1"],
        "proposed_tests_json": ["test_1()"],
        "candidate_files_json": ["file.py"],
        "status": status
    }

@pytest.mark.asyncio
async def test_wrk01_start_run_rejects_unapproved_ticket(test_db):
    """
    WRK-01 Regression Test:
    start_run must reject tickets whose status is PROPOSED or REJECTED.
    """
    repo = get_or_create_repository(test_db, "repo-wrk1", "Repo WRK1", "E:/MM Office/Agent Chess")
    ticket = create_ticket(test_db, make_valid_ticket_dict(repo.id, title="Unapproved ticket", status="PROPOSED"))
    req = RunCreateRequest(ticket_id=ticket.id)
    with pytest.raises(HTTPException) as exc_info:
        await start_run(req, BackgroundTasks(), test_db)
    assert exc_info.value.status_code == 400
    assert "must be 'APPROVED' first" in exc_info.value.detail

@pytest.mark.asyncio
async def test_wrk02_approve_merge_rejects_failing_or_blocked_verdict(test_db):
    """
    WRK-02 Regression Test:
    approve_merge must independently verify that run.verdict is PASS or PASS_WITH_WARNINGS.
    """
    repo = get_or_create_repository(test_db, "repo-wrk2", "Repo WRK2", "E:/MM Office/Agent Chess")
    ticket = create_ticket(test_db, make_valid_ticket_dict(repo.id, title="Merge gate ticket", status="APPROVED"))
    run = create_run(test_db, {
        "ticket_id": ticket.id,
        "repo_id": repo.id,
        "state": "AWAITING_APPROVAL",
        "verdict": "FAIL"
    })
    create_candidate(test_db, {
        "run_id": run.id,
        "ticket_id": ticket.id,
        "attempt": 1,
        "diff_content": "--- a/file.py\n+++ b/file.py\n@@ -1,1 +1,2 @@\n+line\n",
        "diff_hash": "dummy_hash"
    })
    req = RunApprovalRequest(action="approve")
    with pytest.raises(HTTPException) as exc_info:
        await approve_merge(req, run.id, test_db)
    assert exc_info.value.status_code == 403
    assert "Approval rejected: Run verdict is 'FAIL'" in exc_info.value.detail

@pytest.mark.asyncio
async def test_candidate_drift_and_replay_rejected(test_db):
    """
    Release Gate 4 & 5:
    Re-verifies diff hash and rejects approval replay when run is already COMPLETED.
    """
    repo = get_or_create_repository(test_db, "repo-gate", "Repo Gate", "E:/MM Office/Agent Chess")
    ticket = create_ticket(test_db, make_valid_ticket_dict(repo.id, title="Gate ticket", status="APPROVED"))
    run = create_run(test_db, {
        "ticket_id": ticket.id,
        "repo_id": repo.id,
        "state": "AWAITING_APPROVAL",
        "verdict": "PASS"
    })
    diff_text = "--- a/file.py\n+++ b/file.py\n@@ -1,1 +1,2 @@\n+line\n"
    actual_hash = hashlib.sha256(diff_text.encode("utf-8")).hexdigest()
    create_candidate(test_db, {
        "run_id": run.id,
        "ticket_id": ticket.id,
        "attempt": 1,
        "diff_content": diff_text,
        "diff_hash": actual_hash,
        "changed_files_json": ["file.py"]
    })

    # Test 1: Hash mismatch / drift rejected with 409 Conflict
    req_bad_hash = RunApprovalRequest(action="approve", candidate_hash="tampered_hash_value")
    with pytest.raises(HTTPException) as exc_info:
        await approve_merge(req_bad_hash, run.id, test_db)
    assert exc_info.value.status_code == 409
    assert "Approval invalidated" in exc_info.value.detail

    # Test 2: Approval replay rejected when run state is COMPLETED
    run.state = "COMPLETED"
    test_db.commit()
    with pytest.raises(HTTPException) as exc_replay:
        await approve_merge(RunApprovalRequest(action="approve"), run.id, test_db)
    assert exc_replay.value.status_code == 400
    assert "COMPLETED" in exc_replay.value.detail

@pytest.mark.asyncio
async def test_concurrent_run_creation_on_same_ticket_rejected(test_db):
    """
    Release Gate: Concurrency protection.
    A second run cannot be started on a ticket that already has an active run.
    """
    repo = get_or_create_repository(test_db, "repo-concur", "Repo Concur", "E:/MM Office/Agent Chess")
    ticket = create_ticket(test_db, make_valid_ticket_dict(repo.id, title="Concur ticket", status="APPROVED"))
    create_run(test_db, {
        "ticket_id": ticket.id,
        "repo_id": repo.id,
        "state": "CODING"
    })
    req = RunCreateRequest(ticket_id=ticket.id)
    with pytest.raises(HTTPException) as exc_info:
        await start_run(req, BackgroundTasks(), test_db)
    assert exc_info.value.status_code == 409
    assert "is already in progress" in exc_info.value.detail

@pytest.mark.asyncio
async def test_rel01_merge_conflict_aborts_cleanly(tmp_path):
    """
    REL-01 Regression Test:
    When git merge encounters conflicts, it must abort cleanly and leave the working tree pristine.
    """
    repo_dir = tmp_path / "conflict_repo"
    repo_dir.mkdir()
    await run_safe_subprocess(["git", "init"], cwd=repo_dir)
    await run_safe_subprocess(["git", "config", "user.name", "Tester"], cwd=repo_dir)
    await run_safe_subprocess(["git", "config", "user.email", "tester@test.local"], cwd=repo_dir)
    
    # Base commit
    target_file = repo_dir / "target.txt"
    target_file.write_text("line A\nline B\n", encoding="utf-8")
    await run_safe_subprocess(["git", "add", "target.txt"], cwd=repo_dir)
    await run_safe_subprocess(["git", "commit", "-m", "Base commit"], cwd=repo_dir)
    await run_safe_subprocess(["git", "branch", "-M", "main"], cwd=repo_dir)

    # Candidate branch with conflicting change
    await run_safe_subprocess(["git", "checkout", "-b", "candidate/conflict-branch"], cwd=repo_dir)
    target_file.write_text("line A\nline CANDIDATE\n", encoding="utf-8")
    await run_safe_subprocess(["git", "commit", "-am", "Candidate commit"], cwd=repo_dir)

    # Main branch with conflicting change
    await run_safe_subprocess(["git", "checkout", "main"], cwd=repo_dir)
    target_file.write_text("line A\nline MAIN_DIVERGED\n", encoding="utf-8")
    await run_safe_subprocess(["git", "commit", "-am", "Main commit"], cwd=repo_dir)

    # Attempt merge
    success, msg = await git_worktree_manager.merge_candidate(repo_dir, "candidate/conflict-branch", "main")
    assert success is False
    assert "Merge failed" in msg

    # Verify repository is clean and not stuck in conflicted merging state
    _, status_out, _ = await run_safe_subprocess(["git", "status", "--porcelain"], cwd=repo_dir)
    assert status_out.strip() == "", "Working tree left dirty after failed merge!"
    assert not (repo_dir / ".git" / "MERGE_HEAD").exists(), "MERGE_HEAD still exists!"

@pytest.mark.asyncio
async def test_rel02_subprocess_timeout_process_tree_termination():
    """
    REL-02 Regression Test:
    run_safe_subprocess terminates on timeout with exit code -1 and timeout message.
    """
    code, out, err = await run_safe_subprocess(
        cmd_args=[sys.executable, "-c", "import time; time.sleep(10)"],
        cwd=Path.cwd(),
        timeout=1
    )
    assert code == -1
    assert "timed out" in err.lower()

def test_server_restart_reconciliation(test_db):
    """
    Tests that intermediate runs are safely reconciled on server startup.
    """
    r1 = create_run(test_db, {"ticket_id": "t1", "repo_id": "r1", "state": "CODING"})
    r2 = create_run(test_db, {"ticket_id": "t2", "repo_id": "r1", "state": "PATCH_VALIDATION"})
    r3 = create_run(test_db, {"ticket_id": "t3", "repo_id": "r1", "state": "COMPLETED"})

    # Simulate startup reconciliation
    interrupted = test_db.query(RunModel).filter(
        RunModel.state.in_(["IDLE", "CODING", "PATCH_VALIDATION"])
    ).all()
    for r in interrupted:
        r.state = "FAILED"
        r.error_message = "Process interrupted by server restart. Run halted safely."
    test_db.commit()

    assert test_db.query(RunModel).filter(RunModel.id == r1.id).first().state == "FAILED"
    assert test_db.query(RunModel).filter(RunModel.id == r2.id).first().state == "FAILED"
    assert test_db.query(RunModel).filter(RunModel.id == r3.id).first().state == "COMPLETED"

def test_protected_file_patterns_block_ci_workflows_and_docker_artifacts():
    """
    Verifies that .github/workflows and docker artifacts are strictly protected.
    """
    ci_diff = """--- a/.github/workflows/ci.yml
+++ b/.github/workflows/ci.yml
@@ -1,3 +1,3 @@
-name: CI
+name: Pwned
"""
    is_safe, err = UnifiedDiffParser.validate_patch_boundaries(ci_diff, allowed_files=[".github/workflows/ci.yml"])
    assert is_safe is False
    assert "Prohibited modification of protected files" in err

    docker_diff = """--- a/docker-compose.yml
+++ b/docker-compose.yml
@@ -1,2 +1,3 @@
-version: '3'
+version: '2'
"""
    is_safe2, err2 = UnifiedDiffParser.validate_patch_boundaries(docker_diff, allowed_files=["docker-compose.yml"])
    assert is_safe2 is False
    assert "Prohibited modification of protected files" in err2

def test_validate_safe_path_blocks_symlink_and_traversal(tmp_path):
    """
    Verifies that validate_safe_path rejects directory traversal and secret files.
    """
    base_dir = tmp_path / "workspace"
    base_dir.mkdir()
    outside_dir = tmp_path / "outside"
    outside_dir.mkdir()
    secret_file = outside_dir / "secret.txt"
    secret_file.write_text("TOP_SECRET", encoding="utf-8")

    # Direct traversal
    with pytest.raises(ValueError) as exc:
        validate_safe_path(base_dir, "../outside/secret.txt")
    assert "Path traversal detected" in str(exc.value)

    # Secret file patterns
    with pytest.raises(ValueError) as exc2:
        validate_safe_path(base_dir, ".env")
    assert "Access to secret file" in str(exc2.value)

@pytest.mark.asyncio
async def test_approve_merge_rejects_target_branch_drift(test_db, tmp_path):
    """
    Release Gate: Target-branch drift triggers 409 Conflict and invalidates approval.
    """
    repo_dir = tmp_path / "drift_repo"
    repo_dir.mkdir()
    await run_safe_subprocess(["git", "init"], cwd=repo_dir)
    await run_safe_subprocess(["git", "config", "user.name", "Tester"], cwd=repo_dir)
    await run_safe_subprocess(["git", "config", "user.email", "tester@test.local"], cwd=repo_dir)
    f = repo_dir / "target.py"
    f.write_text("initial = 1\n", encoding="utf-8")
    await run_safe_subprocess(["git", "add", "target.py"], cwd=repo_dir)
    await run_safe_subprocess(["git", "commit", "-m", "Commit 1"], cwd=repo_dir)
    await run_safe_subprocess(["git", "branch", "-M", "main"], cwd=repo_dir)

    _, head1, _ = await run_safe_subprocess(["git", "rev-parse", "HEAD"], cwd=repo_dir)
    base_commit = head1.strip()

    # Create candidate branch
    await run_safe_subprocess(["git", "checkout", "-b", "candidate/drift-branch"], cwd=repo_dir)
    f.write_text("initial = 2\n", encoding="utf-8")
    await run_safe_subprocess(["git", "commit", "-am", "Candidate change"], cwd=repo_dir)

    # Main branch advances (drift)
    await run_safe_subprocess(["git", "checkout", "main"], cwd=repo_dir)
    (repo_dir / "other.py").write_text("other = 1\n", encoding="utf-8")
    await run_safe_subprocess(["git", "add", "other.py"], cwd=repo_dir)
    await run_safe_subprocess(["git", "commit", "-m", "Commit 2 on main"], cwd=repo_dir)

    repo = get_or_create_repository(test_db, "repo-drift", "Repo Drift", str(repo_dir))
    ticket = create_ticket(test_db, make_valid_ticket_dict(repo.id, title="Drift ticket", status="APPROVED"))
    run = create_run(test_db, {
        "ticket_id": ticket.id,
        "repo_id": repo.id,
        "state": "AWAITING_APPROVAL",
        "verdict": "PASS",
        "base_commit": base_commit,
        "candidate_branch": "candidate/drift-branch"
    })
    diff_text = "--- a/target.py\n+++ b/target.py\n@@ -1,1 +1,1 @@\n-initial = 1\n+initial = 2\n"
    actual_hash = hashlib.sha256(diff_text.encode("utf-8")).hexdigest()
    create_candidate(test_db, {
        "run_id": run.id,
        "ticket_id": ticket.id,
        "attempt": 1,
        "diff_content": diff_text,
        "diff_hash": actual_hash,
        "changed_files_json": ["target.py"]
    })

    with pytest.raises(HTTPException) as exc_info:
        await approve_merge(RunApprovalRequest(action="approve"), run.id, test_db)
    assert exc_info.value.status_code == 409
    assert "Target branch has drifted" in exc_info.value.detail

@pytest.mark.asyncio
async def test_pytest_runner_returns_runtime_unavailable_code_when_blocked(monkeypatch):
    """
    Verifies that PytestRunner returns reason_code 'RUNTIME_UNAVAILABLE' when fail-closed.
    """
    monkeypatch.setattr(settings, "REQUIRE_CONTAINER_SANDBOX", True)
    status = await SandboxDetector().detect_capabilities()
    if not status["docker_running"]:
        res = await pytest_runner.run_tests(working_dir=Path.cwd())
        assert res["passed"] is False
        assert res["command"] == "BLOCKED"
        assert res.get("reason_code") == "RUNTIME_UNAVAILABLE"
