"""
Unit tests validating the Mock-Agent Isolation and Retry-Learning Ablation Contract.

Validates Stage Two requirements:
1. Mock-agent isolation:
   - Operates offline without external LLM API credentials or network requests.
   - Preserves deterministic mock provider identity and records mock mode in metadata.
2. Retry-learning behavior:
   - Attempt 1 operates with zero prior failure memory in both strategies.
   - Intermediate failures record structured diagnostics to FailureFlywheel.
   - Flywheel escalation consumes failure diagnostics on retry (Attempt 2+) and applies corrective repairs.
   - Naive retry baseline strictly bypasses failure memory, repeating baseline attempts without hints.
   - Task boundary isolation: ephemeral in-memory databases prevent cross-task memory contamination.
3. Reproducibility:
   - Deterministic execution produces identical attempt sequences.
"""

import pytest
import asyncio
from unittest.mock import patch, MagicMock

from app.core.config import settings
from app.providers.mock_provider import mock_provider, _find_benchmark_task
from app.evaluation.benchmark import BenchmarkHarness, BENCHMARK_TASKS_V1
from app.evaluation.agent_evaluator import AgentRepairEvaluator
from app.memory.flywheel import FailureFlywheel


def test_mock_mode_offline_no_api_key_required():
    """Verify mock provider operates completely offline without Groq or external keys."""
    with patch.object(settings, "GROQ_API_KEY", None):
        health = asyncio.run(mock_provider.check_health())
        assert health["available"] is True
        assert health["provider"] == "mock"

        res = asyncio.run(mock_provider.generate("Task: fix something\nTarget File: utils/test.py"))
        assert res["provider"] == "mock"
        assert res["model"] == "mock-deterministic-v1"
        assert res["is_error"] is False


def test_mock_provider_benchmark_task_dispatch():
    """Verify MockProvider correctly matches benchmark tasks and returns appropriate role outputs."""
    task = BenchmarkHarness.get_task_by_id("BENCH-04")
    assert task is not None

    # 1. Planner prompt dispatch
    plan_prompt = f"Approved Ticket:\nTitle: {task['name']}\nCandidate Files: ['{task['target_file']}']\nProduce a bounded execution plan in JSON."
    plan_res = asyncio.run(mock_provider.generate(plan_prompt))
    assert task["target_file"] in plan_res["content"]
    assert "ordered_subtasks" in plan_res["content"]

    # 2. LocalCoder prompt dispatch (Attempt 1 or Naive Retry - No diagnostics)
    coder_prompt = f"Task: {task['problem_statement']}\nTarget File: {task['target_file']}\nExisting File Content:\ndef clamp(): pass\nGenerate a concise Unified Diff."
    coder_res = asyncio.run(mock_provider.generate(coder_prompt))
    assert task["flawed_patch"].strip() in coder_res["content"]

    # 3. RepairAgent prompt dispatch (Flywheel Escalation - With failure diagnostics)
    repair_prompt = f"Ticket: {task['name']}\nTarget File: {task['target_file']}\n\nSTRUCTURED FAILURE DIAGNOSTICS:\nAssertion: assert -5 == 0\nTraceback:\nassert clamp(-5, 0, 10) == 0\n\nCurrent File Content:\ncode\nAnalyze the failure diagnostics and provide a corrected Unified Diff patch."
    repair_res = asyncio.run(mock_provider.generate(repair_prompt, system_instruction="You are the Lead Code Repair Specialist"))
    assert task["repair_patch"].strip() in repair_res["content"]


@pytest.mark.asyncio
async def test_retry_learning_contract_ablation_bench04():
    """
    Validates the core ablation contract on BENCH-04:
    - Attempt 1 in both conditions executes LocalCoder with zero prior history and fails.
    - Flywheel escalation Attempt 2 consumes FailureFlywheel diagnostics, synthesizes repair, and passes.
    - Naive retry Attempt 2 and 3 repeat LocalCoder without diagnostics and fail.
    """
    task = BenchmarkHarness.get_task_by_id("BENCH-04")
    assert task is not None

    # Condition A: Memory Enabled (Flywheel Escalation)
    res_enabled = await AgentRepairEvaluator.evaluate_task(
        task_def=task,
        memory_enabled=True,
        retry_strategy="flywheel_escalation",
        force_mock=True,
        max_attempts=3
    )

    assert res_enabled["verdict"] == "PASS"
    assert res_enabled["outcome"] == "PASSED_REPAIR"
    assert res_enabled["attempts_executed"] == 2
    assert len(res_enabled["history"]) == 2
    assert res_enabled["history"][0]["verdict"] == "FAIL"
    assert res_enabled["history"][1]["verdict"] == "PASS"
    assert res_enabled["model_provider"] == "mock"

    # Condition B: Memory Disabled (Naive Retry)
    res_disabled = await AgentRepairEvaluator.evaluate_task(
        task_def=task,
        memory_enabled=False,
        retry_strategy="naive_retry",
        force_mock=True,
        max_attempts=3
    )

    assert res_disabled["verdict"] == "FAIL"
    assert res_disabled["outcome"] == "FAILED_REPAIR"
    assert res_disabled["attempts_executed"] == 3
    assert len(res_disabled["history"]) == 3
    for attempt_record in res_disabled["history"]:
        assert attempt_record["verdict"] == "FAIL"


def test_task_boundary_memory_isolation_guarantee():
    """Verify that memory recorded for Task A cannot be retrieved during Task B execution."""
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker
    from app.database.session import Base

    # Task 1 in-memory session
    engine1 = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=engine1)
    Session1 = sessionmaker(bind=engine1)()

    FailureFlywheel.record_failure(
        db=Session1,
        run_id="run-bench04",
        ticket_id="BENCH-04",
        attempt=1,
        failed_tests=["test_bounds.py"],
        traceback_excerpt="assert -5 == 0",
        ast_diff={},
        patch_hash="h1"
    )

    ctx1 = FailureFlywheel.get_repair_context(Session1, "BENCH-04")
    assert ctx1["has_history"] is True
    Session1.close()

    # Task 2 fresh session
    engine2 = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=engine2)
    Session2 = sessionmaker(bind=engine2)()

    ctx2_b4 = FailureFlywheel.get_repair_context(Session2, "BENCH-04")
    ctx2_b5 = FailureFlywheel.get_repair_context(Session2, "BENCH-05")

    assert ctx2_b4["has_history"] is False
    assert ctx2_b5["has_history"] is False
    Session2.close()
