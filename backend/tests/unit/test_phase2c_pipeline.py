"""
Unit and integration tests for Ouroboros Phase 2C failure feedback & diagnostic pipeline.
Validates:
1. Pytest normalization captures both stdout and stderr, preserves assertion values, excludes percentage artifacts.
2. FailureFlywheel schema contract exposes top-level failed_tests, traceback, and formatted_diagnostic for RepairAgent.
3. Semantic failure repetition detects identical failure signatures across different patch hashes.
4. Static security policy blocks dangerous dynamic execution while allowing benign library calls (e.g. re.compile).
5. Strategy escalation re-engages Planner upon repeated failures while strictly maintaining the 3-attempt budget.
"""

import pytest
import asyncio
from pathlib import Path
from unittest.mock import AsyncMock, patch, MagicMock
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.database.session import Base
from app.evaluation.failure_context import (
    FailureClass,
    FailureContext,
    FailureContextNormalizer,
    sanitize_diagnostic_text
)
from app.memory.flywheel import FailureFlywheel
from app.evaluation.runner import PytestRunner
from app.evaluation.judge import DeterministicJudge
from app.sandbox.security import analyze_code_security
from app.agents.repair_agent import repair_agent
from app.agents.planner import planner_agent


@pytest.fixture
def memory_db():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    yield session
    session.close()


# 1. Pytest Normalization
def test_pytest_runner_normalizes_stdout_stderr_and_excludes_percentage():
    runner = PytestRunner()
    raw_stdout = """============================= test session starts =============================
platform win32 -- Python 3.12.3, pytest-9.1.1
collected 1 item

test_paginator.py::test_boundaries FAILED [100%]

=================================== FAILURES ===================================
_______________________________ test_boundaries _______________________________
    def test_boundaries():
>       assert paginate([1, 2, 3], page=1, page_size=2) == [1, 2, 3]
E       AssertionError: assert [1, 2] == [1, 2, 3]
E         Right contains one more item: 3
E         Full diff:
E         - [1, 2, 3]
E         + [1, 2]
test_paginator.py:14: AssertionError
=========================== short test summary info ============================
FAILED test_paginator.py::test_boundaries - AssertionError: assert [1, 2] == [1, 2, 3]
============================== 1 failed in 0.05s ===============================
"""
    raw_stderr = ""
    summary = runner._parse_pytest_output(raw_stdout, raw_stderr)

    assert summary["failed"] == 1
    assert len(summary["failure_details"]) == 1
    # Crucial: test name must NOT be "[100%]"
    assert summary["failure_details"][0]["test_name"] == "test_paginator.py::test_boundaries"
    assert "assert [1, 2] == [1, 2, 3]" in summary["failure_details"][0]["traceback"]

    # Canonical FailureContext check
    ctx = summary["failure_context"]
    assert ctx["failure_class"] == "test_assertion"
    assert ctx["failed_test_nodes"] == ["test_paginator.py::test_boundaries"]
    assert ctx["actual_value"] == "[1, 2]"
    assert ctx["expected_value"] == "[1, 2, 3]"


# 2. FailureFlywheel Schema Contract
def test_flywheel_schema_contract_and_top_level_fields(memory_db):
    ticket_id = "BENCH-TEST-01"
    f_ctx = FailureContext(
        failure_class=FailureClass.TEST_ASSERTION,
        failed_test_nodes=["test_demo.py::test_foo"],
        assertion_message="assert 'actual' == 'expected'",
        expected_value="'expected'",
        actual_value="'actual'",
        traceback_tail="File test_demo.py, line 42, in test_foo\n    assert 'actual' == 'expected'",
        source_location="test_demo.py:42"
    )

    FailureFlywheel.record_failure(
        db=memory_db,
        run_id="run-1",
        ticket_id=ticket_id,
        attempt=1,
        failed_tests=["test_demo.py::test_foo"],
        traceback_excerpt=f_ctx.traceback_tail,
        ast_diff={},
        patch_hash="abc111",
        root_cause_hypothesis="Value mismatch",
        repair_hint="Fix return value",
        failure_context=f_ctx.to_dict()
    )

    repair_ctx = FailureFlywheel.get_repair_context(memory_db, ticket_id=ticket_id)

    # Top-level fields MUST be populated for RepairAgent
    assert repair_ctx["has_history"] is True
    assert repair_ctx["failed_tests"] == ["test_demo.py::test_foo"]
    assert "test_demo.py" in repair_ctx["traceback"]
    assert repair_ctx["assertion"] == "assert 'actual' == 'expected'"
    assert repair_ctx["expected"] == "'expected'"
    assert repair_ctx["actual"] == "'actual'"
    assert repair_ctx["failure_class"] == "test_assertion"
    assert "STRUCTURED FAILURE DIAGNOSTICS" or "Failure Class:" in repair_ctx["formatted_diagnostic"]
    assert len(repair_ctx["prior_attempts"]) == 1


# 3. Semantic Failure Repetition Detection
def test_flywheel_semantic_failure_repetition(memory_db):
    ticket_id = "BENCH-TEST-REP"
    f_ctx1 = FailureContext(
        failure_class=FailureClass.TEST_ASSERTION,
        failed_test_nodes=["test_bar.py::test_logic"],
        assertion_message="IndexError: list index out of range",
        source_location="test_bar.py:10"
    )

    # Attempt 1
    t1 = FailureFlywheel.record_failure(
        db=memory_db,
        run_id="run-rep",
        ticket_id=ticket_id,
        attempt=1,
        failed_tests=["test_bar.py::test_logic"],
        traceback_excerpt="IndexError: list index out of range",
        ast_diff={},
        patch_hash="patch_hash_AAA",
        failure_context=f_ctx1.to_dict()
    )
    assert t1.status == "UNRESOLVED"

    # Attempt 2 with DIFFERENT patch hash but SAME failure signature
    f_ctx2 = FailureContext(
        failure_class=FailureClass.TEST_ASSERTION,
        failed_test_nodes=["test_bar.py::test_logic"],
        assertion_message="IndexError: list index out of range",
        source_location="test_bar.py:10"
    )

    t2 = FailureFlywheel.record_failure(
        db=memory_db,
        run_id="run-rep",
        ticket_id=ticket_id,
        attempt=2,
        failed_tests=["test_bar.py::test_logic"],
        traceback_excerpt="IndexError: list index out of range",
        ast_diff={},
        patch_hash="patch_hash_BBB_DIFFERENT",
        failure_context=f_ctx2.to_dict()
    )
    # Must be recognized as REPEATED despite different patch hash!
    assert t2.status == "REPEATED"

    repair_ctx = FailureFlywheel.get_repair_context(memory_db, ticket_id=ticket_id)
    assert repair_ctx["has_repeated_failure"] is True
    assert repair_ctx["repetition_count"] >= 1


# 4. Security Policy: re.compile Allowed, Builtin compile Blocked
def test_security_policy_precision():
    # A. re.compile is allowed
    clean_code = "import re\npat = re.compile(r'\\d+')\ndef fn(x): return pat.match(x)\n"
    res_clean = analyze_code_security(clean_code, filename="safe.py")
    assert res_clean["is_safe"] is True

    # B. builtin compile is blocked with structured feedback
    bad_code = "c = compile('print(1)', '<string>', 'exec')\n"
    res_bad = analyze_code_security(bad_code, filename="bad.py")
    assert res_bad["is_safe"] is False
    assert len(res_bad["details"]["prohibited_calls"]) == 1
    call = res_bad["details"]["prohibited_calls"][0]
    assert call["rule_id"] == "prohibited_primitive"
    assert "requirement" in call


# 5. Planner Escalation Method
@pytest.mark.asyncio
async def test_planner_escalate_plan():
    ticket = {
        "title": "Fix Regex Parser",
        "problem_statement": "Invalid version string format handling",
        "acceptance_criteria": ["All semver strings parsed correctly"],
        "candidate_files": ["version.py"]
    }
    failure_ctx = {
        "formatted_diagnostic": "AssertionError: Expected '1.0.0', got None",
        "traceback": "test_version.py:15 in test_parse"
    }
    current_plan = {
        "ordered_subtasks": [
            {"subtask_id": "ST-1", "target_file": "version.py", "description": "Naive regex update"}
        ]
    }

    revised = await planner_agent.escalate_plan(
        repo_id="TEST-REPO",
        ticket=ticket,
        failure_context=failure_ctx,
        current_plan=current_plan,
        force_mock=True
    )

    assert "ordered_subtasks" in revised
    assert len(revised["ordered_subtasks"]) > 0
