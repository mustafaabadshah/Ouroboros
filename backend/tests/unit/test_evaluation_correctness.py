"""
Unit and regression tests for Ouroboros Evaluation Correctness & Reproducibility.
Verifies:
1. SandboxDetector caching: eliminates 5.5s Windows named pipe hangs.
2. MetricsCalculator honesty: regression rate denominator is evaluated_runs, not total_runs.
3. Zero-attempt defaults: avg_attempts is 0.0 when 0 passing runs.
4. Truthful suite metrics: repair_success_rate is None (not 0.0) when eligible_tasks == 0.
5. Statistical bounds: Wilson score confidence intervals and small sample behavior.
"""

import pytest
import asyncio
from unittest.mock import MagicMock
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.database.session import Base
from app.database.models import RunModel, CandidateModel, TestResultModel as DBTestResultModel, FailureTrajectoryModel
from app.sandbox.detector import SandboxDetector
from app.evaluation.metrics import MetricsCalculator
from app.evaluation.benchmark import BenchmarkHarness, BENCHMARK_TASKS_V1
from app.schemas.eval_contract import compute_wilson_score_interval, compute_percentiles


def test_sandbox_detector_caching():
    """Verify SandboxDetector caches capability check and reset_cache clears it."""
    SandboxDetector.reset_cache()
    assert SandboxDetector._cache is None

    # First call sets cache
    res1 = asyncio.run(SandboxDetector.detect_capabilities())
    assert res1 is not None
    assert "preferred_mode" in res1
    assert SandboxDetector._cache is not None

    # Second call returns cached result immediately
    res2 = asyncio.run(SandboxDetector.detect_capabilities())
    assert res2 == res1

    # Reset cache
    SandboxDetector.reset_cache()
    assert SandboxDetector._cache is None


def test_metrics_calculator_evaluated_runs_denominator():
    """
    Verify regression rate uses evaluated runs (runs executing regression tests)
    rather than total_runs, preventing deflation from blocked/cancelled runs.
    """
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    SessionTest = sessionmaker(bind=engine)
    db = SessionTest()

    try:
        # Create 4 runs:
        # Run 1: Completed, ran regression tests, no regressions
        # Run 2: Completed, ran regression tests, had 1 regression
        # Run 3: Blocked by static policy before test evaluation
        # Run 4: Cancelled before test evaluation
        r1 = RunModel(id="run-1", repo_id="test-repo", ticket_id="T-1", state="COMPLETED", verdict="PASS", retry_count=0)
        r2 = RunModel(id="run-2", repo_id="test-repo", ticket_id="T-2", state="FAILED", verdict="FAIL", retry_count=1)
        r3 = RunModel(id="run-3", repo_id="test-repo", ticket_id="T-3", state="BLOCKED", verdict="BLOCKED", retry_count=0)
        r4 = RunModel(id="run-4", repo_id="test-repo", ticket_id="T-4", state="CANCELLED", verdict="CANCELLED", retry_count=0)
        db.add_all([r1, r2, r3, r4])

        # Test results for r1 and r2 only
        t1 = DBTestResultModel(id="t-1", run_id="run-1", test_type="regression", test_command="pytest tests/", exit_code=0, passed_count=5, failed_count=0)
        t2 = DBTestResultModel(id="t-2", run_id="run-2", test_type="regression", test_command="pytest tests/", exit_code=1, passed_count=4, failed_count=1)
        db.add_all([t1, t2])
        db.commit()

        metrics = MetricsCalculator.compute_summary_metrics(db)

        assert metrics["total_runs"] == 4
        assert metrics["evaluated_runs_for_regression"] == 2
        assert metrics["runs_with_regression"] == 1
        # Regression rate must be 1 / 2 = 0.5 (50%), NOT 1 / 4 = 0.25 (25%)!
        assert metrics["regression_rate"] == 0.50
        assert metrics["repair_success_rate"] == 0.50  # 1 pass out of 2 eligible attempted (r1, r2)
        assert metrics["avg_attempts_per_successful_repair"] == 1.0  # r1 took 1 attempt
    finally:
        db.close()


def test_metrics_calculator_zero_passing_runs_defaults():
    """Verify avg_attempts is None (not 1.0 or 0.0) when no runs pass, and regression_rate is None when un-evaluated."""
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    SessionTest = sessionmaker(bind=engine)
    db = SessionTest()

    try:
        r1 = RunModel(id="run-fail-1", repo_id="test-repo", ticket_id="T-1", state="FAILED", verdict="FAIL", retry_count=2)
        db.add(r1)
        db.commit()

        metrics = MetricsCalculator.compute_summary_metrics(db)
        assert metrics["total_runs"] == 1
        assert metrics["passing_runs_count"] == 0
        # Average attempts for zero successful repairs is mathematically undefined (None)
        assert metrics["avg_attempts_per_successful_repair"] is None
        # 1 run attempted, 0 passed -> 0.0
        assert metrics["repair_success_rate"] == 0.0
        assert metrics["evaluated_runs_for_regression"] == 0
        # No regression tests evaluated -> regression_rate is None (not estimable, not 0.0)
        assert metrics["regression_rate"] is None
        assert metrics["candidate_test_pass_rate"] is None
    finally:
        db.close()


@pytest.mark.asyncio
async def test_suite_zero_eligible_denominator_returns_none():
    """Verify BenchmarkHarness.run_suite returns None (not 0.0) when eligible_tasks == 0."""
    sec_suite = await BenchmarkHarness.run_suite(security_only=True)
    assert sec_suite["total_tasks"] == 1
    assert sec_suite["eligible_tasks"] == 0
    assert sec_suite["adversarial_tasks"] == 1
    assert sec_suite["adversarial_block_rate"] == 1.0
    assert sec_suite["eligible_repair_success_rate"] is None
    assert sec_suite["repair_success_rate"] is None


def test_wilson_score_interval_bounds_and_zero_denominator():
    """Verify Wilson score confidence interval handles edge cases correctly."""
    # Zero denominator
    low, high = compute_wilson_score_interval(0, 0)
    assert low == 0.0
    assert high == 0.0

    # 100% success on small sample (15/15)
    low, high = compute_wilson_score_interval(15, 15)
    assert 0.75 < low < 1.0
    assert high == 1.0

    # 0% success on small sample (0/15)
    low, high = compute_wilson_score_interval(0, 15)
    assert low == 0.0
    assert 0.0 < high < 0.25

    # 50% success
    low, high = compute_wilson_score_interval(10, 20)
    assert low < 0.5 < high
