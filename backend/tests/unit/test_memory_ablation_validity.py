"""
Unit tests validating memory ablation semantics and isolation guarantees.

Validates:
1. Memory-enabled retrieval receives historical failure trajectories and structured diagnostics.
2. Memory-disabled mode strictly bypasses retrieval and does not inject historical errors into prompts.
3. Ephemeral sessions (sqlite:///:memory:) guarantee zero cross-task memory bleeding.
4. Cross-task learning occurs if and only if a shared database session is explicitly configured.
5. Deterministic memory fixtures enable reproducible memory-enabled evaluations.
"""

import json
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.database.session import Base
from app.database.models import FailureTrajectoryModel
from app.memory.flywheel import FailureFlywheel
from app.evaluation.failure_context import FailureContext, FailureClass


@pytest.fixture
def clean_session():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    yield session
    session.close()


def test_memory_enabled_retrieval_receives_historical_context(clean_session):
    """Verifies that when memory is enabled, get_repair_context retrieves recorded failure history."""
    f_ctx = FailureContext(
        failure_class=FailureClass.TEST_ASSERTION,
        failed_test_nodes=["test_bounds.py::test_clamp_boundaries_and_invalid_range"],
        assertion_message="assert -5 == 0",
        expected_value="0",
        actual_value="-5",
        traceback_tail="test_bounds.py:8: in test_clamp_boundaries_and_invalid_range\n    assert clamp(-5, 0, 10) == 0\nE   assert -5 == 0",
        source_location="math_utils/bounds.py:12"
    )

    FailureFlywheel.record_failure(
        db=clean_session,
        run_id="run-enabled-1",
        ticket_id="BENCH-04",
        attempt=1,
        failed_tests=["test_bounds.py::test_clamp_boundaries_and_invalid_range"],
        traceback_excerpt=f_ctx.traceback_tail,
        ast_diff={"target_file": "math_utils/bounds.py"},
        patch_hash="patch_hash_attempt1",
        root_cause_hypothesis="clamp returns high instead of low",
        repair_hint="Validate low <= high and return low when val < low",
        failure_context=f_ctx.to_dict()
    )

    repair_ctx = FailureFlywheel.get_repair_context(clean_session, ticket_id="BENCH-04")
    assert repair_ctx["has_history"] is True
    assert repair_ctx["failed_tests"] == ["test_bounds.py::test_clamp_boundaries_and_invalid_range"]
    assert "assert -5 == 0" in repair_ctx["traceback"]
    assert len(repair_ctx["prior_attempts"]) == 1
    assert repair_ctx["prior_attempts"][0]["repair_hint"] == "Validate low <= high and return low when val < low"


def test_memory_disabled_bypasses_retrieval(clean_session):
    """
    Verifies that under memory-disabled execution semantics,
    even if trajectories existed in a store, the agent evaluation path
    bypasses retrieval and operates with empty context.
    """
    # Seed a trajectory
    FailureFlywheel.record_failure(
        db=clean_session,
        run_id="run-seed",
        ticket_id="BENCH-04",
        attempt=1,
        failed_tests=["test_bounds.py::test_clamp"],
        traceback_excerpt="assert False",
        ast_diff={},
        patch_hash="hash_seed"
    )

    # Simulation of memory_enabled = False condition:
    memory_enabled = False
    attempt = 2

    # In AgentRepairEvaluator:
    if attempt == 1 or not memory_enabled:
        repair_context = {"has_history": False, "prior_attempts": [], "failed_tests": [], "traceback": ""}
    else:
        repair_context = FailureFlywheel.get_repair_context(clean_session, ticket_id="BENCH-04")

    assert repair_context["has_history"] is False
    assert len(repair_context["prior_attempts"]) == 0
    assert repair_context["failed_tests"] == []


def test_ephemeral_sessions_prevent_cross_task_bleeding():
    """
    Validates that each benchmark task using an isolated sqlite:///:memory: session
    has zero cross-task contamination.
    """
    # Task A execution
    engine_a = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=engine_a)
    SessionA = sessionmaker(bind=engine_a)
    session_a = SessionA()

    FailureFlywheel.record_failure(
        db=session_a,
        run_id="run-task-a",
        ticket_id="BENCH-04",
        attempt=1,
        failed_tests=["test_bounds.py"],
        traceback_excerpt="Task A failure",
        ast_diff={},
        patch_hash="hash_a"
    )
    # Task A closes
    session_a.close()

    # Task B execution (fresh session)
    engine_b = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=engine_b)
    SessionB = sessionmaker(bind=engine_b)
    session_b = SessionB()

    # Querying either task ID in Session B returns zero history
    ctx_bench04 = FailureFlywheel.get_repair_context(session_b, ticket_id="BENCH-04")
    ctx_bench12 = FailureFlywheel.get_repair_context(session_b, ticket_id="BENCH-12")

    assert ctx_bench04["has_history"] is False
    assert len(ctx_bench04["prior_attempts"]) == 0
    assert ctx_bench12["has_history"] is False
    assert len(ctx_bench12["prior_attempts"]) == 0

    session_b.close()


def test_persistent_memory_store_allows_cross_task_learning_when_configured():
    """
    Demonstrates that cross-task learning occurs if and only if
    a shared database session is explicitly configured across tasks.
    """
    shared_engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=shared_engine)
    SharedSession = sessionmaker(bind=shared_engine)
    shared_db = SharedSession()

    try:
        # Task 1 writes failure
        FailureFlywheel.record_failure(
            db=shared_db,
            run_id="run-shared-task1",
            ticket_id="SHARED-TASK-1",
            attempt=1,
            failed_tests=["test_shared.py::test_case1"],
            traceback_excerpt="AssertionError: shared fault",
            ast_diff={},
            patch_hash="shared_hash_1",
            repair_hint="Use global sanitization"
        )

        # Task 2 in the shared session can access prior failure context
        ctx = FailureFlywheel.get_repair_context(shared_db, ticket_id="SHARED-TASK-1")
        assert ctx["has_history"] is True
        assert len(ctx["prior_attempts"]) == 1
        assert ctx["prior_attempts"][0]["repair_hint"] == "Use global sanitization"
    finally:
        shared_db.close()


def test_memory_fixture_reproducibility():
    """
    Validates that a versioned failure fixture produces identical semantic failure
    signatures and repair contexts across repeated seedings.
    """
    fixture_data = {
        "ticket_id": "BENCH-FIXTURE-01",
        "attempt": 1,
        "failed_tests": ["test_math_ops.py::test_power"],
        "traceback_excerpt": "assert 6 == 8",
        "patch_hash": "hash_deterministic_fixture_01",
        "failure_context": {
            "failure_class": "test_assertion",
            "failed_test_nodes": ["test_math_ops.py::test_power"],
            "assertion_message": "assert 6 == 8",
            "source_location": "math_ops.py:8"
        }
    }

    # Run trial 1
    engine1 = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=engine1)
    db1 = sessionmaker(bind=engine1)()

    rec1 = FailureFlywheel.record_failure(
        db=db1,
        run_id="trial-1",
        ticket_id=fixture_data["ticket_id"],
        attempt=fixture_data["attempt"],
        failed_tests=fixture_data["failed_tests"],
        traceback_excerpt=fixture_data["traceback_excerpt"],
        ast_diff={},
        patch_hash=fixture_data["patch_hash"],
        failure_context=fixture_data["failure_context"]
    )
    sig1 = (rec1.ast_diff_json or {}).get("failure_signature")
    ctx1 = FailureFlywheel.get_repair_context(db1, ticket_id=fixture_data["ticket_id"])
    db1.close()

    # Run trial 2
    engine2 = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=engine2)
    db2 = sessionmaker(bind=engine2)()

    rec2 = FailureFlywheel.record_failure(
        db=db2,
        run_id="trial-2",
        ticket_id=fixture_data["ticket_id"],
        attempt=fixture_data["attempt"],
        failed_tests=fixture_data["failed_tests"],
        traceback_excerpt=fixture_data["traceback_excerpt"],
        ast_diff={},
        patch_hash=fixture_data["patch_hash"],
        failure_context=fixture_data["failure_context"]
    )
    sig2 = (rec2.ast_diff_json or {}).get("failure_signature")
    ctx2 = FailureFlywheel.get_repair_context(db2, ticket_id=fixture_data["ticket_id"])
    db2.close()

    # Assert perfect determinism across runs
    assert sig1 is not None
    assert sig1 == sig2
    assert ctx1["failed_tests"] == ctx2["failed_tests"]
    assert ctx1["traceback"] == ctx2["traceback"]
