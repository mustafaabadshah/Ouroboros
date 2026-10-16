import json
import pytest
from pathlib import Path
from datetime import datetime, timezone
from app.schemas.eval_contract import (
    EvaluationOutcome,
    MemoryCondition,
    AttemptRecord,
    EvaluationTaskRecord,
    EvaluationSweepRun,
    compute_wilson_score_interval,
    compute_percentiles,
    EvaluationContractAdapter
)

def test_evaluation_outcome_enum():
    assert EvaluationOutcome.PASS == "PASS"
    assert EvaluationOutcome.FAILED_REPAIR == "FAILED_REPAIR"
    assert EvaluationOutcome.BLOCKED_BY_POLICY == "BLOCKED_BY_POLICY"
    assert EvaluationOutcome.RUNTIME_UNAVAILABLE == "RUNTIME_UNAVAILABLE"
    assert EvaluationOutcome.PROVIDER_ERROR == "PROVIDER_ERROR"
    assert EvaluationOutcome.TIMEOUT == "TIMEOUT"
    assert EvaluationOutcome.CANCELLED == "CANCELLED"
    assert EvaluationOutcome.INVALID_RESULT == "INVALID_RESULT"

def test_wilson_score_interval():
    # 15 out of 15 passes (100%)
    lower, upper = compute_wilson_score_interval(15, 15)
    assert upper == 1.0
    assert 0.75 < lower < 1.0  # Wilson lower bound for 15/15 is ~0.796

    # 0 out of 15 passes (0%)
    lower, upper = compute_wilson_score_interval(0, 15)
    assert lower == 0.0
    assert 0.0 < upper < 0.25

    # Empty total
    lower, upper = compute_wilson_score_interval(0, 0)
    assert (lower, upper) == (0.0, 0.0)

def test_percentile_computation():
    data = [10.0, 20.0, 30.0, 40.0, 50.0, 60.0, 70.0, 80.0, 90.0, 100.0]
    percentiles = compute_percentiles(data, [50.0, 95.0])
    assert percentiles[50.0] == 55.0
    assert percentiles[95.0] == 95.5

def test_legacy_v010_adapter():
    sweep_path = Path(r"E:\MM Office\Ouroboros\artifacts\agent_eval_p2c_sweep.json")
    if not sweep_path.exists():
        pytest.skip("Historical sweep artifact not present")

    with open(sweep_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    sweep_run = EvaluationContractAdapter.from_v010_json(data, git_commit="549608c")
    assert sweep_run.schema_version == "v0.11.0"
    assert len(sweep_run.task_results) == 16
    assert sweep_run.summary.eligible_tasks_count == 15
    assert sweep_run.summary.repairs_passed == 15
    assert sweep_run.summary.eligible_repair_success_rate == 1.0
    assert sweep_run.summary.policy_blocked == 1
    assert sweep_run.summary.total_tokens == 10687
    assert sweep_run.summary.wilson_ci_upper == 1.0
    assert sweep_run.summary.wilson_ci_lower > 0.75

def test_task_record_validation():
    task = EvaluationTaskRecord(
        run_id="run-test-01",
        task_id="BENCH-01",
        task_name="Boundary Check",
        category="boundary",
        is_eligible=True,
        memory_condition=MemoryCondition.MEMORY_ENABLED,
        retry_strategy="flywheel",
        started_at_utc=datetime.now(timezone.utc),
        completed_at_utc=datetime.now(timezone.utc),
        duration_ms=1500,
        git_commit="549608c",
        git_tree_fingerprint="test-fingerprint",
        attempt_count=1,
        terminal_outcome=EvaluationOutcome.PASS,
        policy_blocked=False,
        infrastructure_failure=False,
        tests_passed_count=5,
        tests_failed_count=0,
        token_usage={"tokens_in": 100, "tokens_out": 50, "total_tokens": 150}
    )
    assert task.terminal_outcome == EvaluationOutcome.PASS
    assert task.attempt_count == 1
    assert task.token_usage["total_tokens"] == 150
