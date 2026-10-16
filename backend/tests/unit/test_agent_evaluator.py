"""
Unit tests for Ouroboros Real Agent Evaluation Engine (v0.10 Priority 2A)

Tests:
1. Agent pipeline invocation through intended integration point.
2. Missing provider configuration or provider unavailability.
3. Successful candidate patch flow using a controlled test double.
4. Invalid or empty candidate patches.
5. Protected-file modification attempts (adversarial isolation).
6. Patch application failure (git apply failure).
7. Acceptance-test failure.
8. Regression-test failure.
9. Sandbox unavailability / fail-closed enforcement.
10. Timeout handling.
11. Cleanup after exceptions (guaranteed finally cleanup).
12. Outcome taxonomy and aggregate metrics with explicit denominators.
13. Redaction of credentials and sensitive environment values.
14. Accurate serialization of missing telemetry.
"""

import pytest
import asyncio
from pathlib import Path
from unittest.mock import patch, AsyncMock, MagicMock

from app.evaluation.benchmark import BenchmarkHarness, BENCHMARK_TASKS_V1
from app.evaluation.agent_evaluator import (
    AgentRepairEvaluator,
    redact_sensitive_strings
)


@pytest.fixture
def sample_task():
    return BenchmarkHarness.get_task_by_id("BENCH-04")


@pytest.fixture
def adversarial_task():
    return BenchmarkHarness.get_task_by_id("BENCH-03")


VALID_BENCH04_FIX = (
    "--- a/math_utils/bounds.py\n"
    "+++ b/math_utils/bounds.py\n"
    "@@ -1,6 +1,6 @@\n"
    " def clamp(val, low, high):\n"
    "     if low > high:\n"
    "-        pass\n"
    "+        raise ValueError('low must be <= high')\n"
    "     if val < low:\n"
    "-        return high  # Bug: returns high instead of low\n"
    "+        return low\n"
    "     if val > high:\n"
)


# 1. Redaction of credentials and sensitive values
def test_credential_redaction():
    text_with_groq = "Request failed: gsk_12345678901234567890abcdef at https://api.groq.com"
    clean = redact_sensitive_strings(text_with_groq)
    assert "gsk_12345678901234567890abcdef" not in clean
    assert "[REDACTED_GROQ_KEY]" in clean

    text_with_bearer = "Authorization: Bearer my_secret_token_value_987654321012345"
    clean_bearer = redact_sensitive_strings(text_with_bearer)
    assert "my_secret_token_value_987654321012345" not in clean_bearer
    assert "[REDACTED_TOKEN]" in clean_bearer

    assert redact_sensitive_strings(None) is None


# 2. Dry run mode
@pytest.mark.asyncio
async def test_dry_run_mode(sample_task):
    res = await AgentRepairEvaluator.evaluate_task(sample_task, dry_run=True)
    assert res["verdict"] == "SKIPPED"
    assert res["outcome"] == "NOT_RUN"
    assert res["passed"] is False
    assert res["attempts_executed"] == 0
    assert res["dry_run"] is True


# 3. Successful candidate patch flow with controlled test double
@pytest.mark.asyncio
async def test_successful_candidate_patch_mock(sample_task):
    mock_plan = {
        "ordered_subtasks": [
            {
                "subtask_id": "ST-1",
                "description": "Fix boundary clamping in bounds.py",
                "target_file": sample_task["target_file"]
            }
        ]
    }
    # Provide the exact known fix as model output
    mock_patch = {
        "diff_text": VALID_BENCH04_FIX,
        "explanation": "Clamped values and validated lower <= upper.",
        "provider": "mock_groq",
        "model": "qwen-coder-test",
        "input_tokens": 350,
        "output_tokens": 120,
        "is_error": False,
        "error_message": None
    }

    with patch("app.agents.planner.planner_agent.create_plan", new_callable=AsyncMock) as m_plan, \
         patch("app.agents.local_coder.local_coder_agent.generate_patch", new_callable=AsyncMock) as m_coder:

        m_plan.return_value = mock_plan
        m_coder.return_value = mock_patch

        res = await AgentRepairEvaluator.evaluate_task(sample_task, memory_enabled=True)

        assert res["task_id"] == "BENCH-04"
        assert res["verdict"] == "PASS"
        assert res["outcome"] == "PASSED_REPAIR"
        assert res["passed"] is True
        assert res["attempts_executed"] == 1
        assert res["tokens_in"] == 350
        assert res["tokens_out"] == 120
        assert res["model_provider"] == "mock_groq"
        assert res["model_name"] == "qwen-coder-test"
        assert res["phase_timings"]["planning_ms"] >= 0
        assert res["phase_timings"]["coding_ms"] >= 0
        assert res["phase_timings"]["evaluation_ms"] >= 0


# 4. Empty or invalid candidate patch
@pytest.mark.asyncio
async def test_empty_candidate_patch(sample_task):
    mock_plan = {"ordered_subtasks": [{"target_file": sample_task["target_file"]}]}
    mock_empty_patch = {
        "diff_text": "",
        "explanation": "No changes made.",
        "provider": "mock",
        "model": "test-model",
        "input_tokens": 100,
        "output_tokens": 10,
        "is_error": False
    }

    with patch("app.agents.planner.planner_agent.create_plan", new_callable=AsyncMock) as m_plan, \
         patch("app.agents.local_coder.local_coder_agent.generate_patch", new_callable=AsyncMock) as m_coder, \
         patch("app.agents.repair_agent.repair_agent.synthesize_repair", new_callable=AsyncMock) as m_repair:

        m_plan.return_value = mock_plan
        m_coder.return_value = mock_empty_patch
        m_repair.return_value = mock_empty_patch

        res = await AgentRepairEvaluator.evaluate_task(sample_task, max_attempts=2)

        assert res["verdict"] == "FAIL"
        assert res["outcome"] == "FAILED_REPAIR"
        assert res["passed"] is False
        assert res["attempts_executed"] == 2


# 5. Protected-file modification attempt (adversarial policy enforcement)
@pytest.mark.asyncio
async def test_adversarial_task_blocked_by_policy(adversarial_task):
    res = await AgentRepairEvaluator.evaluate_task(adversarial_task)

    assert res["task_id"] == "BENCH-03"
    assert res["verdict"] == "BLOCKED"
    assert res["outcome"] == "BLOCKED_BY_POLICY"
    assert res["passed"] is False
    assert res["is_adversarial"] is True
    assert "protected files" in (res.get("error_detail") or "").lower()


# 6. Out-of-bounds patch generated by model on eligible task
@pytest.mark.asyncio
async def test_model_generated_out_of_bounds_patch(sample_task):
    mock_plan = {"ordered_subtasks": [{"target_file": sample_task["target_file"]}]}
    out_of_bounds_patch = {
        "diff_text": """--- a/backend/app/core/security.py
+++ b/backend/app/core/security.py
@@ -10,3 +10,4 @@
 def bypass():
+    pass
""",
        "explanation": "Tampering with core security.",
        "provider": "mock",
        "model": "test-model"
    }

    with patch("app.agents.planner.planner_agent.create_plan", new_callable=AsyncMock) as m_plan, \
         patch("app.agents.local_coder.local_coder_agent.generate_patch", new_callable=AsyncMock) as m_coder, \
         patch("app.agents.repair_agent.repair_agent.synthesize_repair", new_callable=AsyncMock) as m_repair:

        m_plan.return_value = mock_plan
        m_coder.return_value = out_of_bounds_patch
        m_repair.return_value = out_of_bounds_patch

        res = await AgentRepairEvaluator.evaluate_task(sample_task, max_attempts=1)

        assert res["verdict"] in ("BLOCKED", "FAIL")
        assert res["outcome"] in ("BLOCKED_BY_POLICY", "FAILED_REPAIR")
        assert res["passed"] is False


# 7. Git apply failure (malformed hunk line numbers)
@pytest.mark.asyncio
async def test_git_apply_failure(sample_task):
    mock_plan = {"ordered_subtasks": [{"target_file": sample_task["target_file"]}]}
    malformed_hunk_patch = {
        "diff_text": f"""--- a/{sample_task['target_file']}
+++ b/{sample_task['target_file']}
@@ -999,5 +999,5 @@
-nonexistent line
+replacement line
""",
        "explanation": "Hunk pointing to nonexistent lines.",
        "provider": "mock",
        "model": "test-model"
    }

    with patch("app.agents.planner.planner_agent.create_plan", new_callable=AsyncMock) as m_plan, \
         patch("app.agents.local_coder.local_coder_agent.generate_patch", new_callable=AsyncMock) as m_coder, \
         patch("app.agents.repair_agent.repair_agent.synthesize_repair", new_callable=AsyncMock) as m_repair:

        m_plan.return_value = mock_plan
        m_coder.return_value = malformed_hunk_patch
        m_repair.return_value = malformed_hunk_patch

        res = await AgentRepairEvaluator.evaluate_task(sample_task, max_attempts=1)

        assert res["verdict"] == "FAIL"
        assert res["outcome"] == "FAILED_REPAIR"
        assert res["passed"] is False
        assert any("Git apply failed" in h.get("reason", "") for h in res["history"])


# 8. Dynamic acceptance test failure
@pytest.mark.asyncio
async def test_acceptance_test_failure(sample_task):
    mock_plan = {"ordered_subtasks": [{"target_file": sample_task["target_file"]}]}
    # A patch that applies cleanly but implements the wrong logic
    wrong_logic_patch = {
        "diff_text": (
            f"--- a/{sample_task['target_file']}\n"
            f"+++ b/{sample_task['target_file']}\n"
            "@@ -1,6 +1,6 @@\n"
            " def clamp(val, low, high):\n"
            "     if low > high:\n"
            "-        pass\n"
            "+        return 999.0\n"
            "     if val < low:\n"
            "-        return high  # Bug: returns high instead of low\n"
            "+        return low\n"
            "     if val > high:\n"
        ),
        "explanation": "Returns 999 instead of raising ValueError.",
        "provider": "mock",
        "model": "test-model"
    }

    with patch("app.agents.planner.planner_agent.create_plan", new_callable=AsyncMock) as m_plan, \
         patch("app.agents.local_coder.local_coder_agent.generate_patch", new_callable=AsyncMock) as m_coder, \
         patch("app.agents.repair_agent.repair_agent.synthesize_repair", new_callable=AsyncMock) as m_repair:

        m_plan.return_value = mock_plan
        m_coder.return_value = wrong_logic_patch
        m_repair.return_value = wrong_logic_patch

        res = await AgentRepairEvaluator.evaluate_task(sample_task, max_attempts=1)

        assert res["verdict"] == "FAIL"
        assert res["outcome"] == "FAILED_REPAIR"
        assert res["passed"] is False
        assert res["history"][0]["acceptance_passed"] is False


# 9. Dynamic regression test failure
@pytest.mark.asyncio
async def test_regression_test_failure(sample_task):
    mock_plan = {"ordered_subtasks": [{"target_file": sample_task["target_file"]}]}
    mock_patch = {
        "diff_text": VALID_BENCH04_FIX,
        "provider": "mock",
        "model": "test-model"
    }

    # Simulate acceptance passing, but baseline regression failing
    with patch("app.agents.planner.planner_agent.create_plan", new_callable=AsyncMock) as m_plan, \
         patch("app.agents.local_coder.local_coder_agent.generate_patch", new_callable=AsyncMock) as m_coder, \
         patch("app.evaluation.runner.PytestRunner.run_tests", new_callable=AsyncMock) as m_runner:

        m_plan.return_value = mock_plan
        m_coder.return_value = mock_patch
        # 1st call = acceptance test (passed), 2nd call = baseline test (failed)
        m_runner.side_effect = [
            {"passed": True, "timed_out": False, "failures": []},
            {"passed": False, "timed_out": False, "failures": [{"test_name": "test_clamp_in_range"}]}
        ]

        res = await AgentRepairEvaluator.evaluate_task(sample_task, max_attempts=1)

        assert res["verdict"] == "FAIL"
        assert res["outcome"] == "FAILED_REPAIR"
        assert res["passed"] is False
        assert res["history"][0]["acceptance_passed"] is True
        assert res["history"][0]["regression_passed"] is False


# 10. Timeout handling
@pytest.mark.asyncio
async def test_timeout_handling(sample_task):
    mock_plan = {"ordered_subtasks": [{"target_file": sample_task["target_file"]}]}
    mock_patch = {
        "diff_text": VALID_BENCH04_FIX,
        "provider": "mock",
        "model": "test-model"
    }

    with patch("app.agents.planner.planner_agent.create_plan", new_callable=AsyncMock) as m_plan, \
         patch("app.agents.local_coder.local_coder_agent.generate_patch", new_callable=AsyncMock) as m_coder, \
         patch("app.evaluation.runner.PytestRunner.run_tests", new_callable=AsyncMock) as m_runner:

        m_plan.return_value = mock_plan
        m_coder.return_value = mock_patch
        m_runner.return_value = {"passed": False, "timed_out": True, "failures": []}

        res = await AgentRepairEvaluator.evaluate_task(sample_task, max_attempts=1)

        assert res["verdict"] == "TIMED_OUT"
        assert res["outcome"] == "TIMED_OUT"
        assert res["passed"] is False


# 11. Fail-closed sandbox unavailability
@pytest.mark.asyncio
async def test_sandbox_unavailability(sample_task):
    with patch("app.sandbox.detector.sandbox_detector.detect_capabilities", new_callable=AsyncMock) as m_det:
        m_det.return_value = {
            "can_execute": False,
            "message": "Docker runtime blocked by isolation security policy"
        }

        res = await AgentRepairEvaluator.evaluate_task(sample_task)

        assert res["verdict"] == "ERROR"
        assert res["outcome"] == "INFRASTRUCTURE_ERROR"
        assert res["passed"] is False
        assert "Sandbox execution blocked" in (res.get("error_detail") or "")


# 12. Provider configuration error / unavailability
@pytest.mark.asyncio
async def test_provider_unavailability_handling(sample_task):
    mock_plan = {"ordered_subtasks": [{"target_file": sample_task["target_file"]}]}
    mock_error_patch = {
        "diff_text": "",
        "explanation": "Provider error",
        "provider": "groq",
        "model": "qwen",
        "is_error": True,
        "error_message": "Invalid API Key or Provider Unavailable"
    }

    with patch("app.agents.planner.planner_agent.create_plan", new_callable=AsyncMock) as m_plan, \
         patch("app.agents.local_coder.local_coder_agent.generate_patch", new_callable=AsyncMock) as m_coder:

        m_plan.return_value = mock_plan
        m_coder.return_value = mock_error_patch

        res = await AgentRepairEvaluator.evaluate_task(sample_task, max_attempts=1)

        assert res["outcome"] == "PROVIDER_UNAVAILABLE"
        assert res["verdict"] == "ERROR"
        assert res["passed"] is False
        assert "provider unavailable" in (res.get("error_detail") or "").lower()


# 13. Aggregate metrics calculations and explicit denominators
@pytest.mark.asyncio
async def test_suite_aggregate_metrics_denominators():
    mock_tasks = [
        {"task_id": "T1", "name": "Task 1", "category": "boundary", "difficulty": "easy", "is_eligible": True, "is_adversarial": False},
        {"task_id": "T2", "name": "Task 2", "category": "boundary", "difficulty": "easy", "is_eligible": True, "is_adversarial": False},
        {"task_id": "T3", "name": "Task 3", "category": "boundary", "difficulty": "easy", "is_eligible": False, "is_adversarial": True}
    ]

    mock_results = [
        {"task_id": "T1", "outcome": "PASSED_REPAIR", "verdict": "PASS", "is_eligible": True, "is_adversarial": False, "duration_ms": 100, "tokens_in": 50, "tokens_out": 20},
        {"task_id": "T2", "outcome": "FAILED_REPAIR", "verdict": "FAIL", "is_eligible": True, "is_adversarial": False, "duration_ms": 120, "tokens_in": 60, "tokens_out": 30},
        {"task_id": "T3", "outcome": "BLOCKED_BY_POLICY", "verdict": "BLOCKED", "is_eligible": False, "is_adversarial": True, "duration_ms": 10, "tokens_in": None, "tokens_out": None}
    ]

    with patch.object(AgentRepairEvaluator, "evaluate_task", side_effect=mock_results):
        suite = await AgentRepairEvaluator.evaluate_suite(tasks=mock_tasks)

        assert suite["tasks_selected"] == 3
        assert suite["tasks_attempted"] == 3
        assert suite["tasks_not_run"] == 0
        assert suite["eligible_tasks"] == 2
        assert suite["adversarial_tasks"] == 1
        assert suite["repairs_passed"] == 1
        assert suite["repairs_failed"] == 1
        assert suite["policy_blocked"] == 1

        # Denominator assertions
        assert suite["attempted_repair_success_rate"] == 0.3333  # 1 / 3
        assert suite["eligible_repair_success_rate"] == 0.5       # 1 / 2
        assert suite["adversarial_block_rate"] == 1.0            # 1 / 1
        assert suite["total_tokens_in"] == 110
        assert suite["total_tokens_out"] == 50


# 14. Zero-denominator safety (never divide by zero)
@pytest.mark.asyncio
async def test_zero_denominator_safety():
    mock_tasks = [
        {"task_id": "T1", "name": "Dry Task", "category": "boundary", "difficulty": "easy", "is_eligible": True, "is_adversarial": False}
    ]
    # Simulate dry run where task is NOT_RUN
    mock_results = [
        {"task_id": "T1", "outcome": "NOT_RUN", "verdict": "SKIPPED", "is_eligible": True, "is_adversarial": False, "duration_ms": 0}
    ]

    with patch.object(AgentRepairEvaluator, "evaluate_task", side_effect=mock_results):
        suite = await AgentRepairEvaluator.evaluate_suite(tasks=mock_tasks, dry_run=True)

        assert suite["tasks_selected"] == 1
        assert suite["tasks_attempted"] == 0
        assert suite["tasks_not_run"] == 1
        assert suite["attempted_repair_success_rate"] is None  # explicit None, not 0.0 or ZeroDivisionError
