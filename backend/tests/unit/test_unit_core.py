import pytest
from pathlib import Path
from pydantic import ValidationError

from app.schemas.ticket import TicketBase
from app.orchestration.state_machine import workflow_sm
from app.core.security import mask_secret, validate_safe_path, is_protected_path
from app.evaluation.ast_analyzer import ASTChangeAnalyzer
from app.integrations.git.diff_parser import UnifiedDiffParser
from app.observability.telemetry import telemetry
from app.providers.router import model_router

def test_ticket_schema_validation():
    # Valid Ticket
    valid_data = {
        "title": "Add latency telemetry to GroqChessAgent",
        "problem_statement": "Move latency is currently unrecorded.",
        "motivation": "Observability.",
        "current_behavior": "latency_ms is None.",
        "desired_behavior": "latency_ms is recorded.",
        "acceptance_criteria": ["latency_ms is positive integer"],
        "proposed_tests": ["test_latency()"],
        "relevant_graph_entities": ["GroqChessAgent"],
        "candidate_files": ["backend/app/agents/groq_agent.py"],
        "risk_level": "low",
        "expected_complexity": "small",
        "estimated_resources": "1 LLM call",
        "evidence": ["groq_agent.py:187"],
        "out_of_scope": "validator.py"
    }
    ticket = TicketBase.model_validate(valid_data)
    assert ticket.title == "Add latency telemetry to GroqChessAgent"
    assert ticket.risk_level == "low"

    # Missing mandatory title -> should raise ValidationError
    invalid_data = dict(valid_data)
    del invalid_data["title"]
    with pytest.raises(ValidationError):
        TicketBase.model_validate(invalid_data)

def test_workflow_state_transitions():
    # Valid transitions
    assert workflow_sm.validate_transition("IDLE", "BASELINE_VALIDATION") is True
    assert workflow_sm.validate_transition("BASELINE_VALIDATION", "PLANNING") is True
    assert workflow_sm.validate_transition("PLANNING", "CODING") is True
    assert workflow_sm.validate_transition("CODING", "PATCH_VALIDATION") is True
    assert workflow_sm.validate_transition("PATCH_VALIDATION", "ACCEPTANCE_TESTS") is True
    assert workflow_sm.validate_transition("ACCEPTANCE_TESTS", "REGRESSION_TESTS") is True
    assert workflow_sm.validate_transition("REGRESSION_TESTS", "AWAITING_APPROVAL") is True
    assert workflow_sm.validate_transition("AWAITING_APPROVAL", "COMPLETED") is True

    # Cancellation permitted from active states
    assert workflow_sm.validate_transition("CODING", "CANCELLED") is True
    assert workflow_sm.validate_transition("PLANNING", "FAILED") is True

    # Invalid jump: IDLE directly to COMPLETED or AWAITING_APPROVAL
    with pytest.raises(ValueError):
        workflow_sm.validate_transition("IDLE", "COMPLETED")

    with pytest.raises(ValueError):
        workflow_sm.validate_transition("BASELINE_VALIDATION", "COMPLETED")

def test_security_controls(tmp_path):
    # Secret Masking
    assert mask_secret("gsk_1234567890abcdef") == "gsk_...cdef"
    assert mask_secret("") == "NONE"
    assert mask_secret(None) == "NONE"
    assert mask_secret("short") == "********"

    # Protected file check
    assert is_protected_path("backend/app/chess/validator.py") is True
    assert is_protected_path("backend/app/chess/stockfish.py") is True
    assert is_protected_path("backend/app/config.py") is True
    assert is_protected_path("backend/app/agents/groq_agent.py") is False

    # Path traversal validation
    base_dir = tmp_path / "agent_chess"
    base_dir.mkdir()
    with pytest.raises(ValueError, match="Path traversal detected"):
        validate_safe_path(base_dir, "../../../Windows/System32")

    with pytest.raises(ValueError, match="secret file"):
        validate_safe_path(base_dir, ".env")

def test_ast_change_analyzer():
    code_before = """
def calculate_score(a, b):
    return a + b
"""
    code_after = """
def calculate_score(a, b, multiplier=1):
    return (a + b) * multiplier

def new_telemetry_helper():
    return True
"""
    res = ASTChangeAnalyzer.compare_files_ast(code_before, code_after, "sample.py")
    assert res["syntax_valid"] is True
    assert "new_telemetry_helper" in res["added_symbols"]
    assert "calculate_score" in res["modified_symbols"]
    assert len(res["protected_violations"]) == 0

    # Protected symbol modification detection
    code_protected = """
def validate_move(board, move_str):
    return True, None, None
"""
    res_prot = ASTChangeAnalyzer.compare_files_ast(code_protected, code_protected.replace("validate_move", "validate_move_mod"), "validator.py")
    assert any("validate_move" in v for v in res_prot["protected_violations"])

def test_unified_diff_parser():
    diff_sample = """--- a/backend/app/agents/groq_agent.py
+++ b/backend/app/agents/groq_agent.py
@@ -10,3 +10,4 @@
 import time
+import asyncio
 import json
"""
    meta = UnifiedDiffParser.parse_patch(diff_sample)
    assert meta["is_valid"] is True
    assert "backend/app/agents/groq_agent.py" in meta["changed_files"]
    assert meta["additions"] == 1
    assert meta["deletions"] == 0

    # Boundary validation
    is_safe, err = UnifiedDiffParser.validate_patch_boundaries(
        diff_sample,
        allowed_files=["backend/app/agents/groq_agent.py"]
    )
    assert is_safe is True
    assert err is None

    # Rejection of out-of-scope files
    is_safe_bad, err_bad = UnifiedDiffParser.validate_patch_boundaries(
        diff_sample,
        allowed_files=["backend/app/chess/board_manager.py"]
    )
    assert is_safe_bad is False
    assert "Out-of-scope" in err_bad

def test_telemetry_cost_and_resources():
    # Cost calculation for Llama-3.3-70b
    cost_70b = telemetry.estimate_model_cost("llama-3.3-70b-versatile", 1000, 500)
    assert cost_70b is not None
    assert cost_70b > 0

    # Local Qwen -> 0.0 compute cost
    cost_local = telemetry.estimate_model_cost("qwen2.5-coder:1.5b", 1000, 500)
    assert cost_local == 0.0

    # System metrics inspection
    metrics = telemetry.get_system_metrics()
    assert "total_ram_mb" in metrics
    assert "free_ram_mb" in metrics
    assert metrics["total_ram_mb"] > 0

@pytest.mark.asyncio
async def test_model_router_mock_fallback():
    # Forced mock routing
    res = await model_router.route_task(
        agent_role="Architect",
        prompt="Generate ticket for testing",
        force_mock=True
    )
    assert res["is_error"] is False
    assert res["provider"] == "mock"
    assert "title" in res["content"].lower()
