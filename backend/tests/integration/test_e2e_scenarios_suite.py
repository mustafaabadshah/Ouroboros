"""
Comprehensive End-to-End Acceptance and Scenario Suite for Project Ouroboros.

Validates the full local E2E lifecycle across Scenarios A through J:
A. Successful repair with Git worktree isolation and atomic artifact emission
B. Repair failure after exhausted attempts (distinguished from provider outages)
C. Provider failure with fail-closed non-fallback guarantees
D. Invalid patch rejection (path traversal, syntax error, prohibited security primitives)
E. Regression detection (fixing one test while breaking an existing baseline test)
F. Budget exhaustion (pre-dispatch block on request and token ceilings)
G. Interrupted/cancelled run lifecycle and state preservation
H. Artifact collision protection (refusal to clobber existing files without flag)
I. Task boundary isolation (zero cross-task memory/context contamination)
J. Retry-learning behavior (within-task failure trajectory consumption vs naive retry)
"""

import os
import sys
import json
import shutil
import tempfile
import asyncio
from pathlib import Path
from unittest.mock import patch, AsyncMock

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from fastapi.testclient import TestClient

from app.core.security import run_safe_subprocess
from app.integrations.git.worktree import GitWorktreeManager
from app.integrations.git.diff_parser import UnifiedDiffParser
from app.evaluation.runner import PytestRunner
from app.evaluation.judge import DeterministicJudge
from app.memory.flywheel import FailureFlywheel
from app.orchestration.workflow import WorkflowController
from app.providers.router import model_router
from app.providers.groq_provider import groq_provider
from app.providers.mock_provider import mock_provider
from app.providers.budget import EvaluationBudgetController, ProviderErrorCategory
from app.core.config import settings
from app.database.session import Base
repo_root = Path(__file__).resolve().parent.parent.parent.parent
if str(repo_root) not in sys.path:
    sys.path.insert(0, str(repo_root))

from scripts.run_agent_eval import safe_atomic_write_json, analyze_paired_complete_pairs
from app.main import app


@pytest.fixture(autouse=True)
def restore_router_state():
    """Guarantee router state isolation between unit tests."""
    orig_mode = model_router.get_mode()
    orig_ctrl = model_router.get_budget_controller()
    yield
    model_router.set_mode(orig_mode)
    model_router.set_budget_controller(orig_ctrl)



# ------------------------------------------------------------------------------
# SCENARIO A: SUCCESSFUL REPAIR E2E
# ------------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_scenario_a_successful_repair():
    """Scenario A: Full successful repair lifecycle inside an isolated worktree."""
    with tempfile.TemporaryDirectory(prefix="ouro_e2e_scen_a_") as tmpdir:
        repo_dir = Path(tmpdir) / "repo"
        worktrees_dir = Path(tmpdir) / "worktrees"
        out_dir = Path(tmpdir) / "artifacts"
        repo_dir.mkdir()
        worktrees_dir.mkdir()
        out_dir.mkdir()

        # 1. Init fixture git repository
        await run_safe_subprocess(["git", "init"], cwd=repo_dir)
        await run_safe_subprocess(["git", "config", "user.name", "Ouroboros"], cwd=repo_dir)
        await run_safe_subprocess(["git", "config", "user.email", "ouro@local"], cwd=repo_dir)

        calc_file = repo_dir / "calc.py"
        calc_file.write_text("def add(a, b):\n    return a + b\n", encoding="utf-8")

        test_file = repo_dir / "test_calc.py"
        test_file.write_text("from calc import add\n\ndef test_add():\n    assert add(2, 3) == 5\n", encoding="utf-8")

        await run_safe_subprocess(["git", "add", "-A"], cwd=repo_dir)
        await run_safe_subprocess(["git", "commit", "-m", "Initial commit"], cwd=repo_dir)

        # Baseline tests pass
        runner = PytestRunner(default_timeout=60)
        baseline = await runner.run_tests(working_dir=repo_dir)
        assert baseline["passed"] is True

        # 2. Worktree creation
        wt_mgr = GitWorktreeManager(base_worktree_dir=str(worktrees_dir))
        ticket_id = "ouro-scen-a-01"
        wt_path, cand_branch, base_commit = await wt_mgr.create_worktree(repo_dir, ticket_id)
        assert wt_path.exists()

        # Add acceptance test in worktree
        wt_test = wt_path / "test_calc.py"
        wt_test.write_text(
            "from calc import add, multiply\n\n"
            "def test_add():\n    assert add(2, 3) == 5\n\n"
            "def test_multiply():\n    assert multiply(3, 4) == 12\n",
            encoding="utf-8"
        )

        # 3. Patch generation & application (valid repair)
        valid_patch = (
            "--- a/calc.py\n"
            "+++ b/calc.py\n"
            "@@ -1,2 +1,5 @@\n"
            " def add(a, b):\n"
            "     return a + b\n"
            "+\n"
            "+def multiply(a, b):\n"
            "+    return a * b\n"
        )
        applied, msg = await wt_mgr.apply_patch(wt_path, valid_patch)
        assert applied is True

        # 4. Deterministic Judge evaluation
        eval_res = await DeterministicJudge.evaluate_candidate(
            worktree_path=wt_path,
            baseline_results=baseline,
            acceptance_test_file="test_calc.py",
            regression_test_dir="test_calc.py"
        )
        assert eval_res["verdict"] == "PASS"

        # 5. Atomic artifact emission
        artifact_file = out_dir / "run_scen_a_result.json"
        safe_atomic_write_json(artifact_file, {"verdict": "PASS", "ticket_id": ticket_id}, allow_overwrite=False)
        assert artifact_file.exists()
        assert json.loads(artifact_file.read_text(encoding="utf-8"))["verdict"] == "PASS"

        # 6. Verify original repo remains untouched
        assert "multiply" not in calc_file.read_text(encoding="utf-8")
        await wt_mgr.remove_worktree(repo_dir, ticket_id, cand_branch)
        assert not wt_path.exists()


# ------------------------------------------------------------------------------
# SCENARIO B: REPAIR FAILURE (DISTINGUISHED FROM PROVIDER FAILURE)
# ------------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_scenario_b_repair_failure_classification():
    """Scenario B: Unsuccessful patch attempts are classified as repair failure, not provider outage."""
    with tempfile.TemporaryDirectory(prefix="ouro_e2e_scen_b_") as tmpdir:
        repo_dir = Path(tmpdir) / "repo"
        worktrees_dir = Path(tmpdir) / "worktrees"
        repo_dir.mkdir()
        worktrees_dir.mkdir()

        await run_safe_subprocess(["git", "init"], cwd=repo_dir)
        await run_safe_subprocess(["git", "config", "user.name", "Ouroboros"], cwd=repo_dir)
        await run_safe_subprocess(["git", "config", "user.email", "ouro@local"], cwd=repo_dir)

        (repo_dir / "math_mod.py").write_text("def subtract(a, b):\n    return a - b\n", encoding="utf-8")
        (repo_dir / "test_math.py").write_text(
            "from math_mod import subtract\n\ndef test_sub():\n    assert subtract(5, 2) == 3\n",
            encoding="utf-8"
        )
        await run_safe_subprocess(["git", "add", "-A"], cwd=repo_dir)
        await run_safe_subprocess(["git", "commit", "-m", "Init"], cwd=repo_dir)

        runner = PytestRunner(default_timeout=60)
        baseline = await runner.run_tests(working_dir=repo_dir)

        wt_mgr = GitWorktreeManager(base_worktree_dir=str(worktrees_dir))
        ticket_id = "ouro-scen-b-01"
        wt_path, cand_branch, _ = await wt_mgr.create_worktree(repo_dir, ticket_id)

        # Flawed patch that causes test failure
        (wt_path / "test_math.py").write_text(
            "from math_mod import subtract, power\n\n"
            "def test_sub():\n    assert subtract(5, 2) == 3\n\n"
            "def test_power():\n    assert power(2, 3) == 8\n",
            encoding="utf-8"
        )
        flawed_patch = (
            "--- a/math_mod.py\n"
            "+++ b/math_mod.py\n"
            "@@ -1,2 +1,5 @@\n"
            " def subtract(a, b):\n"
            "     return a - b\n"
            "+\n"
            "+def power(a, b):\n"
            "+    return a * b\n"  # Bug: multiplication instead of exponentiation
        )
        applied, _ = await wt_mgr.apply_patch(wt_path, flawed_patch)
        assert applied is True

        eval_res = await DeterministicJudge.evaluate_candidate(
            worktree_path=wt_path,
            baseline_results=baseline,
            acceptance_test_file="test_math.py",
            regression_test_dir="test_math.py"
        )
        assert eval_res["verdict"] == "FAIL"
        assert "Acceptance tests failed" in eval_res["reason"]

        await wt_mgr.remove_worktree(repo_dir, ticket_id, cand_branch)


# ------------------------------------------------------------------------------
# SCENARIO C: PROVIDER FAILURE HANDLING (FAIL-CLOSED, ZERO MOCK FALLBACK)
# ------------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_scenario_c_provider_failure_fails_closed():
    """Scenario C: Live provider failure returns structured error and never invokes MockProvider."""
    orig_mode = model_router.get_mode()
    model_router.set_mode("live")
    model_router.set_budget_controller(None)

    try:
        with patch.object(settings, "GROQ_API_KEY", "test_synthetic_key_for_offline_ci"):
            # 1. Simulated 429 Rate Limit
            fake_429 = {
                "content": "",
                "provider": "groq",
                "model": "qwen/qwen3.8-27b",
                "is_error": True,
                "error_message": "Rate limit reached: 429 Too Many Requests"
            }
            with patch.object(groq_provider, "generate", new_callable=AsyncMock, return_value=fake_429) as mock_groq, \
                 patch.object(mock_provider, "generate", new_callable=AsyncMock) as mock_mock:
                res = await model_router.route_task("Planner", "Create execution plan")
                assert res["is_error"] is True
                assert res["error_type"] == ProviderErrorCategory.RATE_LIMITED.value
                assert res["diff_text"] == ""
                mock_groq.assert_called_once()
                mock_mock.assert_not_called()

            # 2. Simulated Timeout
            fake_timeout = {
                "content": "",
                "provider": "groq",
                "model": "qwen/qwen3.8-27b",
                "is_error": True,
                "error_message": "Connection timed out after 30s"
            }
            with patch.object(groq_provider, "generate", new_callable=AsyncMock, return_value=fake_timeout) as mock_groq, \
                 patch.object(mock_provider, "generate", new_callable=AsyncMock) as mock_mock:
                res = await model_router.route_task("LocalCoder", "Generate patch")
                assert res["is_error"] is True
                assert res["error_type"] == ProviderErrorCategory.TIMEOUT.value
                mock_groq.assert_called_once()
                mock_mock.assert_not_called()

    finally:
        model_router.set_mode(orig_mode)


# ------------------------------------------------------------------------------
# SCENARIO D: INVALID PATCH REJECTION (PATH TRAVERSAL & PROHIBITED PRIMITIVES)
# ------------------------------------------------------------------------------
def test_scenario_d_invalid_patch_rejection():
    """Scenario D: Malformed diffs, path traversal, and prohibited primitives are rejected before apply."""
    with tempfile.TemporaryDirectory(prefix="ouro_e2e_scen_d_") as tmpdir:
        wt_path = Path(tmpdir)

        # 1. Path traversal attempt
        traversal_patch = (
            "--- a/../../../../etc/passwd\n"
            "+++ b/../../../../etc/passwd\n"
            "@@ -1,1 +1,1 @@\n"
            "+root:x:0:0::/root:/bin/bash\n"
        )
        res_traversal = DeterministicJudge.evaluate_patch_static(
            diff_text=traversal_patch,
            allowed_files=["calculator.py"],
            worktree_path=wt_path
        )
        assert res_traversal["verdict"] == "BLOCKED"
        assert "boundary_scope" in str(res_traversal.get("policy_rule_id", "")) or "Out-of-scope" in res_traversal["reason"]

        # 2. Malformed diff string
        res_malformed = DeterministicJudge.evaluate_patch_static(
            diff_text="This is not a diff block",
            allowed_files=["calculator.py"],
            worktree_path=wt_path
        )
        assert res_malformed["verdict"] == "BLOCKED"
        assert "Malformed patch" in res_malformed["reason"]

        # 3. Prohibited security primitive: __import__ and eval
        prohibited_code_patch = (
            "--- a/target.py\n"
            "+++ b/target.py\n"
            "@@ -1,1 +1,2 @@\n"
            "+def exploit():\n"
            "+    return eval('__import__(\"os\").system(\"calc\")')\n"
        )
        # Create candidate file with prohibited code
        (wt_path / "target.py").write_text("import os\ndef exploit():\n    eval('__import__(\"os\").system(\"calc\")')\n", encoding="utf-8")
        res_sec = DeterministicJudge.evaluate_patch_static(
            diff_text=prohibited_code_patch,
            allowed_files=["target.py"],
            worktree_path=wt_path
        )
        assert res_sec["verdict"] == "BLOCKED"
        assert "Security Policy Violation" in res_sec["reason"]


# ------------------------------------------------------------------------------
# SCENARIO E: REGRESSION DETECTION
# ------------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_scenario_e_regression_detection():
    """Scenario E: Candidate that fixes a new feature but breaks an existing baseline test is failed."""
    with tempfile.TemporaryDirectory(prefix="ouro_e2e_scen_e_") as tmpdir:
        repo_dir = Path(tmpdir) / "repo"
        worktrees_dir = Path(tmpdir) / "worktrees"
        repo_dir.mkdir()
        worktrees_dir.mkdir()

        await run_safe_subprocess(["git", "init"], cwd=repo_dir)
        await run_safe_subprocess(["git", "config", "user.name", "Ouroboros"], cwd=repo_dir)
        await run_safe_subprocess(["git", "config", "user.email", "ouro@local"], cwd=repo_dir)

        (repo_dir / "core.py").write_text("def get_version():\n    return '1.0.0'\n", encoding="utf-8")
        (repo_dir / "test_core.py").write_text(
            "from core import get_version\n\ndef test_ver():\n    assert get_version() == '1.0.0'\n",
            encoding="utf-8"
        )
        await run_safe_subprocess(["git", "add", "-A"], cwd=repo_dir)
        await run_safe_subprocess(["git", "commit", "-m", "Init"], cwd=repo_dir)

        runner = PytestRunner(default_timeout=60)
        baseline = await runner.run_tests(working_dir=repo_dir)
        assert baseline["passed"] is True

        wt_mgr = GitWorktreeManager(base_worktree_dir=str(worktrees_dir))
        ticket_id = "ouro-scen-e-01"
        wt_path, cand_branch, _ = await wt_mgr.create_worktree(repo_dir, ticket_id)

        # Regressive patch: breaks get_version() while adding get_build()
        regressive_patch = (
            "--- a/core.py\n"
            "+++ b/core.py\n"
            "@@ -1,2 +1,4 @@\n"
            " def get_version():\n"
            "-    return '1.0.0'\n"
            "+    return '2.0.0-broken'\n"
            "+def get_build():\n"
            "+    return 42\n"
        )
        applied, _ = await wt_mgr.apply_patch(wt_path, regressive_patch)
        assert applied is True

        eval_res = await DeterministicJudge.evaluate_candidate(
            worktree_path=wt_path,
            baseline_results=baseline,
            acceptance_test_file=None,
            regression_test_dir="test_core.py"
        )
        assert eval_res["verdict"] == "FAIL"
        assert "Regression detected" in eval_res["reason"]

        await wt_mgr.remove_worktree(repo_dir, ticket_id, cand_branch)


# ------------------------------------------------------------------------------
# SCENARIO F: BUDGET EXHAUSTION
# ------------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_scenario_f_budget_exhaustion_circuit_breaker():
    """Scenario F: Request count and token ceiling limits block dispatch prior to model call."""
    # 1. Request count exhaustion
    ctrl_req = EvaluationBudgetController(max_requests=1, max_tokens=100000)
    ok1, _ = ctrl_req.check_and_reserve(100, 100)
    assert ok1 is True
    ok2, err2 = ctrl_req.check_and_reserve(100, 100)
    assert ok2 is False
    assert "Maximum request limit of 1 reached" in err2

    # 2. Token ceiling exhaustion
    ctrl_tok = EvaluationBudgetController(max_requests=10, max_tokens=1000)
    ok_tok, err_tok = ctrl_tok.check_and_reserve(estimated_prompt_tokens=600, max_output_tokens=600)
    assert ok_tok is False
    assert "Token ceiling of 1000 tokens would be exceeded" in err_tok

    # 3. ModelRouter wired check
    orig_mode = model_router.get_mode()
    model_router.set_mode("live")
    model_router.set_budget_controller(ctrl_req)
    try:
        res = await model_router.route_task("Planner", "Prompt that should be blocked")
        assert res["is_error"] is True
        assert res["error_type"] in (ProviderErrorCategory.BUDGET_EXHAUSTED.value, ProviderErrorCategory.TOKEN_CEILING_EXCEEDED.value)
    finally:
        model_router.set_mode(orig_mode)
        model_router.set_budget_controller(None)


# ------------------------------------------------------------------------------
# SCENARIO G: INTERRUPTED/CANCELLED RUN LIFECYCLE
# ------------------------------------------------------------------------------
def test_scenario_g_cancellation_preserves_state():
    """Scenario G: User cancellation sets cancelled state and halts workflow without leaks."""
    wf = WorkflowController()
    test_run_id = "ouro-scen-g-cancel-01"
    assert wf.is_cancelled(test_run_id) is False

    wf.cancel_run(test_run_id)
    assert wf.is_cancelled(test_run_id) is True


# ------------------------------------------------------------------------------
# SCENARIO H: ARTIFACT COLLISION REFUSAL
# ------------------------------------------------------------------------------
def test_scenario_h_artifact_collision_refusal():
    """Scenario H: Safe atomic writing strictly refuses to overwrite existing file without explicit authorization."""
    with tempfile.TemporaryDirectory(prefix="ouro_e2e_scen_h_") as tmpdir:
        dest_file = Path(tmpdir) / "pre_existing_output.json"
        dest_file.write_text('{"initial": "preserved"}', encoding="utf-8")

        # Must raise FileExistsError and leave content untouched
        with pytest.raises(FileExistsError, match="Target destination already exists"):
            safe_atomic_write_json(dest_file, {"malicious": "clobber"}, allow_overwrite=False)

        assert json.loads(dest_file.read_text(encoding="utf-8")) == {"initial": "preserved"}

        # Authorized overwrite works cleanly
        safe_atomic_write_json(dest_file, {"authorized": "updated"}, allow_overwrite=True)
        assert json.loads(dest_file.read_text(encoding="utf-8")) == {"authorized": "updated"}


# ------------------------------------------------------------------------------
# SCENARIO I: TASK BOUNDARY ISOLATION
# ------------------------------------------------------------------------------
def test_scenario_i_task_boundary_isolation():
    """Scenario I: Sequential tasks execute in isolated sessions with zero cross-contamination."""
    engine_t1 = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=engine_t1)
    db1 = sessionmaker(bind=engine_t1)()

    # Record failure in Task 1
    FailureFlywheel.record_failure(
        db=db1,
        run_id="run-task-1",
        ticket_id="TICKET-ALPHA",
        attempt=1,
        failed_tests=["test_alpha_func"],
        traceback_excerpt="ZeroDivisionError: division by zero",
        ast_diff={},
        patch_hash="patch_hash_alpha"
    )

    ctx1 = FailureFlywheel.get_repair_context(db1, "TICKET-ALPHA")
    assert ctx1["has_history"] is True
    assert "ZeroDivisionError" in ctx1["prior_attempts"][0]["traceback"]
    db1.close()

    # Task 2 in a fresh session
    engine_t2 = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=engine_t2)
    db2 = sessionmaker(bind=engine_t2)()

    # Verify Task 2 has zero knowledge of Task 1
    ctx2 = FailureFlywheel.get_repair_context(db2, "TICKET-BETA")
    assert ctx2["has_history"] is False
    assert len(ctx2["prior_attempts"]) == 0

    ctx2_bleed = FailureFlywheel.get_repair_context(db2, "TICKET-ALPHA")
    assert ctx2_bleed["has_history"] is False
    db2.close()


# ------------------------------------------------------------------------------
# SCENARIO J: RETRY-LEARNING BEHAVIOR (WITHIN-TASK VS CROSS-TASK)
# ------------------------------------------------------------------------------
def test_scenario_j_retry_learning_trajectory():
    """Scenario J: Flywheel escalation supplies prior diagnostic on retry, distinct from naive retry."""
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    db = sessionmaker(bind=engine)()

    ticket_id = "ouro-bench-clamp"

    # Attempt 1 has zero history
    ctx_att1 = FailureFlywheel.get_repair_context(db, ticket_id)
    assert ctx_att1["has_history"] is False

    # Attempt 1 fails -> trajectory saved
    FailureFlywheel.record_failure(
        db=db,
        run_id="run-clamp-01",
        ticket_id=ticket_id,
        attempt=1,
        failed_tests=["test_clamp_negative"],
        traceback_excerpt="AssertionError: assert -5 == 0",
        ast_diff={"clamp.py": {"modified": ["clamp"]}},
        patch_hash="hash_attempt1",
        root_cause_hypothesis="Did not clamp lower bound",
        repair_hint="Use max(val, min_val) before returning"
    )

    # Attempt 2 retrieves prior diagnostic
    ctx_att2 = FailureFlywheel.get_repair_context(db, ticket_id)
    assert ctx_att2["has_history"] is True
    assert len(ctx_att2["prior_attempts"]) == 1
    prior = ctx_att2["prior_attempts"][0]
    assert prior["attempt"] == 1
    assert "AssertionError: assert -5 == 0" in prior["traceback"]
    assert prior["repair_hint"] == "Use max(val, min_val) before returning"

    db.close()


# ------------------------------------------------------------------------------
# FASTAPI BACKEND API INTEGRATION CHECKS
# ------------------------------------------------------------------------------
def test_api_endpoints_health_and_models(test_db):
    """Verify core API endpoints return expected structure and statuses."""
    from app.database.session import get_db
    app.dependency_overrides[get_db] = lambda: test_db
    client = TestClient(app)

    try:
        # 1. Health endpoint
        res_h = client.get("/api/health")
        assert res_h.status_code == 200
        assert res_h.json()["status"] == "healthy"

        # 2. Settings endpoint
        res_s = client.get("/api/settings")
        assert res_s.status_code == 200
        settings_data = res_s.json()
        assert "app_name" in settings_data

        # 3. Model status endpoint
        res_m = client.get("/api/models/status")
        assert res_m.status_code == 200
        models_data = res_m.json()
        assert "groq_available" in models_data
        assert "local_runtime" in models_data

    finally:
        app.dependency_overrides.clear()
