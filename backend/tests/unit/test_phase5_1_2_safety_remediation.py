"""
Comprehensive Unit Tests for Phase 5.1.2 Safety Remediation.
Verifies all 4 remediated execution blockers:
1. Fail-closed provider routing (zero silent fallback to MockProvider on errors).
2. Artifact output safety (atomic writes, collision handling, memory_ablation protection).
3. Explicit live-execution authorization gate (interactive & non-interactive).
4. Enforced budgets, pacing, token/cost ceilings, and complete-pair accounting.
"""

import os
import sys
import json
import pytest
import tempfile
import asyncio
from pathlib import Path
from unittest.mock import AsyncMock, patch, MagicMock

repo_root = Path(__file__).resolve().parent.parent.parent.parent
if str(repo_root) not in sys.path:
    sys.path.insert(0, str(repo_root))

from app.core.config import settings
from app.providers.router import model_router, ProviderErrorCategory
from app.providers.budget import EvaluationBudgetController
from app.providers.mock_provider import mock_provider
from app.providers.groq_provider import groq_provider
from scripts.run_agent_eval import safe_atomic_write_json, analyze_paired_complete_pairs



@pytest.fixture(autouse=True)
def restore_router_state():
    """Guarantee router state isolation between unit tests."""
    orig_mode = model_router.get_mode()
    orig_ctrl = model_router.get_budget_controller()
    yield
    model_router.set_mode(orig_mode)
    model_router.set_budget_controller(orig_ctrl)


# ==============================================================================
# BLOCKER 1: FAIL-CLOSED PROVIDER ROUTING TESTS
# ==============================================================================

@pytest.mark.asyncio
async def test_mock_mode_uses_mock_provider_and_requires_no_key():
    """Verify that mock mode directly uses MockProvider without needing GROQ_API_KEY."""
    model_router.set_mode("mock")
    with patch.object(groq_provider, "generate", new_callable=AsyncMock) as mock_groq:
        res = await model_router.route_task("LocalCoder", "Generate test patch")
        assert res.get("provider") == "mock"
        mock_groq.assert_not_called()


@pytest.mark.asyncio
async def test_live_mode_uses_configured_live_provider():
    """Verify that live mode invokes the configured live provider."""
    model_router.set_mode("live")
    model_router.set_budget_controller(None)

    fake_live_response = {
        "content": "```diff\n--- a/file.py\n+++ b/file.py\n@@ -1 +1 @@\n-old\n+new\n```",
        "provider": "groq",
        "model": "qwen/qwen3.8-27b",
        "input_tokens": 100,
        "output_tokens": 50,
        "latency_ms": 120,
        "is_error": False,
        "error_message": None
    }

    with patch.object(groq_provider, "generate", new_callable=AsyncMock, return_value=fake_live_response) as mock_groq, \
         patch.object(mock_provider, "generate", new_callable=AsyncMock) as mock_mock:
        with patch.object(settings, "GROQ_API_KEY", "gsk_testkey1234567890abcdef1234"):
            res = await model_router.route_task("LocalCoder", "Generate test patch")
            assert res.get("provider") == "groq"
            assert res.get("is_error") is False
            mock_groq.assert_called_once()
            mock_mock.assert_not_called()


@pytest.mark.asyncio
async def test_live_mode_auth_error_fails_closed_without_mock_fallback():
    """Verify that a simulated 401/auth error fails closed with PROVIDER_AUTH_ERROR and never calls mock."""
    model_router.set_mode("live")
    model_router.set_budget_controller(None)

    fake_auth_error = {
        "content": "",
        "provider": "groq",
        "model": "qwen/qwen3.8-27b",
        "is_error": True,
        "error_message": "Invalid API Key (401 Unauthorized)"
    }

    with patch.object(groq_provider, "generate", new_callable=AsyncMock, return_value=fake_auth_error) as mock_groq, \
         patch.object(mock_provider, "generate", new_callable=AsyncMock) as mock_mock:
        with patch.object(settings, "GROQ_API_KEY", "gsk_testkey1234567890abcdef1234"):
            res = await model_router.route_task("LocalCoder", "Generate test patch")
            assert res.get("is_error") is True
            assert res.get("error_type") == ProviderErrorCategory.AUTH_ERROR.value
            assert res.get("diff_text") == ""
            mock_groq.assert_called_once()
            mock_mock.assert_not_called()


@pytest.mark.asyncio
async def test_live_mode_rate_limit_fails_closed_without_mock_fallback():
    """Verify that a simulated HTTP 429 fails closed with PROVIDER_RATE_LIMITED and never calls mock."""
    model_router.set_mode("live")
    model_router.set_budget_controller(None)

    fake_rate_limit = {
        "content": "",
        "provider": "groq",
        "model": "qwen/qwen3.8-27b",
        "is_error": True,
        "error_message": "Rate limit exceeded (HTTP 429)"
    }

    with patch.object(groq_provider, "generate", new_callable=AsyncMock, return_value=fake_rate_limit) as mock_groq, \
         patch.object(mock_provider, "generate", new_callable=AsyncMock) as mock_mock:
        with patch.object(settings, "GROQ_API_KEY", "gsk_testkey1234567890abcdef1234"):
            res = await model_router.route_task("LocalCoder", "Generate test patch")
            assert res.get("is_error") is True
            assert res.get("error_type") == ProviderErrorCategory.RATE_LIMITED.value
            mock_groq.assert_called_once()
            mock_mock.assert_not_called()


@pytest.mark.asyncio
async def test_live_mode_timeout_fails_closed_without_mock_fallback():
    """Verify that a simulated connection/read timeout fails closed with PROVIDER_TIMEOUT."""
    model_router.set_mode("live")
    model_router.set_budget_controller(None)

    fake_timeout = {
        "content": "",
        "provider": "groq",
        "model": "qwen/qwen3.8-27b",
        "is_error": True,
        "error_message": "Request timed out after 30.0 seconds."
    }

    with patch.object(groq_provider, "generate", new_callable=AsyncMock, return_value=fake_timeout) as mock_groq, \
         patch.object(mock_provider, "generate", new_callable=AsyncMock) as mock_mock:
        with patch.object(settings, "GROQ_API_KEY", "gsk_testkey1234567890abcdef1234"):
            res = await model_router.route_task("Planner", "Create execution plan")
            assert res.get("is_error") is True
            assert res.get("error_type") == ProviderErrorCategory.TIMEOUT.value
            mock_groq.assert_called_once()
            mock_mock.assert_not_called()


@pytest.mark.asyncio
async def test_live_mode_conflicting_force_mock_raises_error():
    """Verify that passing force_mock=True while router is in strict live mode raises a ValueError."""
    model_router.set_mode("live")
    with pytest.raises(ValueError, match="Conflicting configuration"):
        await model_router.route_task("LocalCoder", "Generate patch", force_mock=True)


# ==============================================================================
# BLOCKER 2: ARTIFACT OUTPUT SAFETY TESTS
# ==============================================================================

def test_atomic_write_prevents_unauthorized_overwrite():
    """Verify that safe_atomic_write_json refuses to overwrite existing file unless allow_overwrite=True."""
    with tempfile.TemporaryDirectory() as tmpdir:
        dest = Path(tmpdir) / "output.json"
        dest.write_text('{"existing": true}', encoding="utf-8")

        # Refusal without flag
        with pytest.raises(FileExistsError, match="Target destination already exists"):
            safe_atomic_write_json(dest, {"new": 1}, allow_overwrite=False)

        assert json.loads(dest.read_text(encoding="utf-8")) == {"existing": True}

        # Success with flag
        safe_atomic_write_json(dest, {"new": 2}, allow_overwrite=True)
        assert json.loads(dest.read_text(encoding="utf-8")) == {"new": 2}


def test_atomic_write_leaves_file_intact_on_failure():
    """Verify that an abort during write leaves existing artifact unharmed."""
    with tempfile.TemporaryDirectory() as tmpdir:
        dest = Path(tmpdir) / "stable.json"
        dest.write_text('{"intact": true}', encoding="utf-8")

        # Unserializable payload
        with pytest.raises(TypeError):
            safe_atomic_write_json(dest, {"bad_object": object()}, allow_overwrite=True)

        assert json.loads(dest.read_text(encoding="utf-8")) == {"intact": True}


def test_custom_output_does_not_touch_memory_ablation():
    """Verify that running with custom output never touches memory_ablation.json."""
    from scripts.run_agent_eval import safe_atomic_write_json
    with tempfile.TemporaryDirectory() as tmpdir:
        custom_out = Path(tmpdir) / "custom_phase6.json"
        memory_ablation_file = Path(tmpdir) / "memory_ablation.json"
        memory_ablation_file.write_text('{"historical": "intact"}', encoding="utf-8")

        # Write to custom output
        safe_atomic_write_json(custom_out, {"phase6": "done"}, allow_overwrite=False)

        # Confirm memory_ablation was untouched
        assert memory_ablation_file.exists()
        assert json.loads(memory_ablation_file.read_text(encoding="utf-8")) == {"historical": "intact"}


# ==============================================================================
# BLOCKER 3: LIVE AUTHORIZATION GATE TESTS
# ==============================================================================

def test_conflicting_live_and_mock_flags_rejected():
    """Verify that specifying both --live and --mock-agents aborts immediately."""
    from scripts.run_agent_eval import main
    test_args = ["run_agent_eval.py", "--live", "--mock-agents"]
    with patch.object(sys, "argv", test_args):
        with pytest.raises(SystemExit) as exc_info:
            asyncio.run(main())
        assert exc_info.value.code == 1


def test_non_interactive_live_aborts_without_auth_env():
    """Verify that running in non-interactive environment without OUROBOROS_LIVE_AUTH aborts."""
    from scripts.run_agent_eval import main
    test_args = ["run_agent_eval.py", "--live", "--task-id", "BENCH-05", "--output", "artifacts/scratch/test_out.json"]
    with patch.object(sys, "argv", test_args):
        with patch.object(sys.stdin, "isatty", return_value=False):
            with patch.dict(os.environ, {}, clear=True):
                with pytest.raises(SystemExit) as exc_info:
                    asyncio.run(main())
                assert exc_info.value.code == 2


# ==============================================================================
# BLOCKER 4: BUDGETS, PACING, TOKEN/COST CEILINGS & COMPLETE PAIRS TESTS
# ==============================================================================

@pytest.mark.asyncio
async def test_budget_controller_request_limit_enforced():
    """Verify that request count is strictly tracked and blocks once limit is reached."""
    ctrl = EvaluationBudgetController(max_requests=2, max_tokens=100000, max_cost_usd=1.0)

    ok1, err1 = ctrl.check_and_reserve(100, 100, role="Planner")
    assert ok1 is True
    assert ctrl.total_requests == 1

    ok2, err2 = ctrl.check_and_reserve(100, 100, role="LocalCoder")
    assert ok2 is True
    assert ctrl.total_requests == 2

    # Third call must be denied
    ok3, err3 = ctrl.check_and_reserve(100, 100, role="RepairAgent")
    assert ok3 is False
    assert "Maximum request limit of 2 reached" in err3


@pytest.mark.asyncio
async def test_budget_controller_token_ceiling_enforced():
    """Verify that pre-dispatch token reservations strictly enforce total ceiling (60,000 tokens)."""
    ctrl = EvaluationBudgetController(max_requests=100, max_tokens=60000, max_cost_usd=1.0)

    # First call: 30,000 tokens
    ok1, _ = ctrl.check_and_reserve(estimated_prompt_tokens=10000, max_output_tokens=20000)
    assert ok1 is True
    ctrl.reconcile_usage(actual_tokens_in=10000, actual_tokens_out=20000, estimated_prompt_tokens=10000, max_output_tokens=20000)
    assert ctrl.total_tokens == 30000

    # Second call: 25,000 tokens (total 55,000)
    ok2, _ = ctrl.check_and_reserve(estimated_prompt_tokens=5000, max_output_tokens=20000)
    assert ok2 is True
    ctrl.reconcile_usage(actual_tokens_in=5000, actual_tokens_out=20000, estimated_prompt_tokens=5000, max_output_tokens=20000)
    assert ctrl.total_tokens == 55000

    # Third call: requesting 10,000 tokens (would project to 65,000 > 60,000)
    ok3, err3 = ctrl.check_and_reserve(estimated_prompt_tokens=5000, max_output_tokens=5000)
    assert ok3 is False
    assert "Token ceiling of 60000 tokens would be exceeded" in err3


@pytest.mark.asyncio
async def test_budget_controller_cost_ceiling_enforced():
    """Verify that dollar cost reservations enforce the $0.10 ceiling and fail closed."""
    # Pricing: $0.20 per 1M tokens = $0.0000002 per token
    # Max cost: $0.001 (1,000 tokens = $0.0002)
    ctrl = EvaluationBudgetController(max_requests=100, max_tokens=100000, max_cost_usd=0.0005)

    # First call: 1,000 tokens in, 1,000 tokens out = 2,000 * 0.0000002 = $0.0004
    ok1, _ = ctrl.check_and_reserve(estimated_prompt_tokens=1000, max_output_tokens=1000)
    assert ok1 is True
    ctrl.reconcile_usage(actual_tokens_in=1000, actual_tokens_out=1000, estimated_prompt_tokens=1000, max_output_tokens=1000)

    # Second call: would add another $0.0004 -> projected $0.0008 > $0.0005
    ok2, err2 = ctrl.check_and_reserve(estimated_prompt_tokens=1000, max_output_tokens=1000)
    assert ok2 is False
    assert "Cost ceiling of $0.0005 USD would be exceeded" in err2


@pytest.mark.asyncio
async def test_budget_controller_fails_closed_when_pricing_unknown():
    """Verify that cost enforcement fails closed if pricing is unknown."""
    ctrl = EvaluationBudgetController(max_requests=100, max_tokens=100000, max_cost_usd=0.10, pricing_known=False)
    ok, err = ctrl.check_and_reserve(100, 100)
    assert ok is False
    assert "pricing data is marked unknown. Failing closed" in err


@pytest.mark.asyncio
async def test_budget_controller_fails_closed_when_model_unrecognized():
    """Verify that an unrecognized model with unknown pricing fails closed."""
    ctrl = EvaluationBudgetController(max_requests=100, max_tokens=100000, max_cost_usd=0.10, pricing_known=True)
    ok, err = ctrl.check_and_reserve(100, 100, model_name="unverified-random-model")
    assert ok is False
    assert "Pricing data not available for model 'unverified-random-model'. Failing closed" in err


@pytest.mark.asyncio
async def test_budget_controller_shared_pacing_with_fake_clock():
    """Verify that minimum 3.0s interval is enforced across calls using a fake clock."""
    current_time = 100.0

    def fake_clock():
        return current_time

    waited_seconds = []

    async def fake_sleeper(seconds: float):
        nonlocal current_time
        waited_seconds.append(seconds)
        current_time += seconds

    ctrl = EvaluationBudgetController(
        max_requests=10,
        min_pacing_seconds=3.0,
        clock=fake_clock,
        sleeper=fake_sleeper
    )

    # First call: no prior timestamp -> 0 wait
    w1 = await ctrl.wait_pacing()
    assert w1 == 0.0
    ctrl.check_and_reserve(100, 100)

    # Immediately attempt second call (0 elapsed): must wait 3.0 seconds
    w2 = await ctrl.wait_pacing()
    assert w2 == 3.0
    assert len(waited_seconds) == 1
    assert waited_seconds[0] == 3.0


def test_complete_pair_analysis_isolates_infrastructure_errors():
    """Verify that incomplete pairs due to provider/infrastructure aborts are separated from clean pairs."""
    trials_on = [{
        "task_results": [
            {"task_id": "BENCH-01", "passed": True, "outcome": "PASSED_REPAIR"},
            {"task_id": "BENCH-02", "passed": False, "outcome": "PROVIDER_RATE_LIMITED"}
        ]
    }]
    trials_off = [{
        "task_results": [
            {"task_id": "BENCH-01", "passed": False, "outcome": "FAILED_REPAIR"},
            {"task_id": "BENCH-02", "passed": True, "outcome": "PASSED_REPAIR"}
        ]
    }]

    analysis = analyze_paired_complete_pairs(trials_on, trials_off)
    assert analysis["total_paired_tasks_started"] == 2
    assert analysis["complete_pairs_count"] == 1
    assert analysis["incomplete_pairs_count"] == 1
    assert analysis["incomplete_pairs_detail"][0]["task_id"] == "BENCH-02"

    # Concordance is strictly on complete pair BENCH-01
    matrix = analysis["concordance_matrix"]
    assert matrix["flywheel_only_win_b"] == 1
    assert matrix["naive_only_win_c"] == 0
