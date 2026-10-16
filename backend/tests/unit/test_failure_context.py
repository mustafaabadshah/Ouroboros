import pytest
from app.evaluation.failure_context import (
    FailureClass,
    FailureContext,
    FailureContextNormalizer,
    sanitize_diagnostic_text
)

SAMPLE_PYTEST_ASSERTION_OUTPUT = """
============================= test session starts =============================
platform win32 -- Python 3.12.3, pytest-9.1.1, pluggy-1.6.0
rootdir: E:\\MM Office\\Ouroboros
collected 2 items

test_paginator.py::test_paginate_boundaries_and_validation FAILED        [ 50%]
test_paginator.py::test_paginate_empty PASSED                            [100%]

================================== FAILURES ===================================
_________________ test_paginate_boundaries_and_validation _____________________

    def test_paginate_boundaries_and_validation():
        items = list(range(10))
>       res = paginate(items, page=1, page_size=3)
E       AssertionError: assert [0, 1] == [0, 1, 2]
E         Right contains one more item: 2
E         Use -v to get more diff

test_paginator.py:25: AssertionError
=========================== short test summary info ===========================
FAILED test_paginator.py::test_paginate_boundaries_and_validation - AssertionError: assert [0, 1] == [0, 1, 2]
========================= 1 failed, 1 passed in 0.15s =========================
"""

def test_pytest_output_extracts_clean_node_ids_and_assertions():
    ctx = FailureContextNormalizer.from_pytest_output(stdout=SAMPLE_PYTEST_ASSERTION_OUTPUT, stderr="", exit_code=1)

    assert ctx.failure_class == FailureClass.TEST_ASSERTION
    assert ctx.failed_test_nodes == ["test_paginator.py::test_paginate_boundaries_and_validation"]
    assert "[100%]" not in ctx.failed_test_nodes
    assert "[ 50%]" not in ctx.failed_test_nodes
    assert "assert [0, 1] == [0, 1, 2]" in ctx.assertion_message
    assert ctx.actual_value == "[0, 1]"
    assert ctx.expected_value == "[0, 1, 2]"
    assert ctx.source_location == "test_paginator.py:25"
    assert len(ctx.failure_signature) == 16


def test_sanitize_diagnostic_redacts_secrets_and_bounds_length():
    leaked = "Error connecting with gsk_abcdef1234567890abcdef123456 and Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.xyz and password='super_secret_password_123'"
    sanitized = sanitize_diagnostic_text(leaked, max_len=50)

    assert "gsk_abcdef1234567890abcdef123456" not in sanitized
    assert "super_secret_password_123" not in sanitized
    assert "[REDACTED" in sanitized
    assert len(sanitized) <= 70
    assert "[TRUNCATED]" in sanitized


def test_syntax_error_normalization():
    syntax_out = """
  File "semver/parser.py", line 12
    return { 'major':
                    ^
SyntaxError: invalid syntax
"""
    ctx = FailureContextNormalizer.from_pytest_output(stdout="", stderr=syntax_out, exit_code=1)

    assert ctx.failure_class == FailureClass.SYNTAX_ERROR
    assert "semver/parser.py:12" in (ctx.source_location or "")
    assert "invalid syntax" in ctx.assertion_message


def test_static_policy_normalization():
    ctx = FailureContextNormalizer.from_static_policy(
        rule_id="prohibited_call",
        reason="Execution of dangerous primitive 'compile' is forbidden.",
        prohibited_item="compile",
        allowed_requirement="Use standard string methods or non-compiled regexes.",
        target_file="semver/parser.py"
    )

    assert ctx.failure_class == FailureClass.STATIC_POLICY_VIOLATION
    assert ctx.policy_rule_id == "prohibited_call"
    assert "forbidden" in ctx.policy_reason
    assert "standard string methods" in ctx.policy_requirement
    assert ctx.source_location == "semver/parser.py"
    assert len(ctx.failure_signature) == 16


def test_malformed_and_empty_output_safety():
    ctx = FailureContextNormalizer.from_pytest_output(stdout="", stderr="", exit_code=1)

    assert ctx.failure_class == FailureClass.TEST_ASSERTION
    assert ctx.failed_test_nodes == ["UnknownTestNode"]
    assert ctx.raw_output_length == 1
    assert len(ctx.failure_signature) == 16


def test_failure_signature_stability():
    ctx1 = FailureContextNormalizer.from_pytest_output(stdout=SAMPLE_PYTEST_ASSERTION_OUTPUT, stderr="", exit_code=1)
    # Slightly different timestamp or runtime
    modified_output = SAMPLE_PYTEST_ASSERTION_OUTPUT.replace("in 0.15s", "in 0.42s")
    ctx2 = FailureContextNormalizer.from_pytest_output(stdout=modified_output, stderr="", exit_code=1)

    assert ctx1.failure_signature == ctx2.failure_signature


def test_serialization_roundtrip():
    ctx = FailureContextNormalizer.from_pytest_output(stdout=SAMPLE_PYTEST_ASSERTION_OUTPUT, stderr="", exit_code=1)
    d = ctx.to_dict()
    restored = FailureContext.from_dict(d)

    assert restored.failure_class == ctx.failure_class
    assert restored.failed_test_nodes == ctx.failed_test_nodes
    assert restored.assertion_message == ctx.assertion_message
    assert restored.failure_signature == ctx.failure_signature
