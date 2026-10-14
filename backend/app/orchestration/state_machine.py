from typing import Set, Dict, Optional
from app.core.logging import logger

VALID_STATES = {
    "IDLE",
    "REPOSITORY_ANALYSIS",
    "TICKET_GENERATION",
    "TICKET_REVIEW",
    "TEST_GENERATION",
    "BASELINE_VALIDATION",
    "PLANNING",
    "CODING",
    "PATCH_VALIDATION",
    "ACCEPTANCE_TESTS",
    "REGRESSION_TESTS",
    "REVIEW",
    "AWAITING_APPROVAL",
    "COMPLETED",
    "FAILED",
    "BLOCKED",
    "CANCELLED",
    "TIMED_OUT",
    "REPAIR_REQUIRED"
}

ALLOWED_TRANSITIONS: Dict[str, Set[str]] = {
    "IDLE": {"REPOSITORY_ANALYSIS", "TICKET_GENERATION", "BASELINE_VALIDATION", "PLANNING", "CANCELLED"},
    "REPOSITORY_ANALYSIS": {"TICKET_GENERATION", "FAILED", "CANCELLED"},
    "TICKET_GENERATION": {"TICKET_REVIEW", "FAILED", "CANCELLED"},
    "TICKET_REVIEW": {"BASELINE_VALIDATION", "PLANNING", "BLOCKED", "CANCELLED"},
    "BASELINE_VALIDATION": {"PLANNING", "BLOCKED", "FAILED", "CANCELLED"},
    "PLANNING": {"CODING", "BLOCKED", "FAILED", "CANCELLED"},
    "CODING": {"PATCH_VALIDATION", "FAILED", "CANCELLED"},
    "PATCH_VALIDATION": {"ACCEPTANCE_TESTS", "REPAIR_REQUIRED", "CODING", "BLOCKED", "FAILED", "CANCELLED"},
    "ACCEPTANCE_TESTS": {"REGRESSION_TESTS", "AWAITING_APPROVAL", "REPAIR_REQUIRED", "CODING", "FAILED", "CANCELLED"},
    "REGRESSION_TESTS": {"REVIEW", "AWAITING_APPROVAL", "REPAIR_REQUIRED", "CODING", "FAILED", "CANCELLED"},
    "REPAIR_REQUIRED": {"CODING", "FAILED", "BLOCKED", "CANCELLED"},
    "REVIEW": {"AWAITING_APPROVAL", "FAILED", "CANCELLED"},
    "AWAITING_APPROVAL": {"COMPLETED", "FAILED", "CANCELLED"},
    "COMPLETED": set(),
    "FAILED": set(),
    "BLOCKED": set(),
    "CANCELLED": set(),
    "TIMED_OUT": set(),
}

class WorkflowStateMachine:
    """
    Deterministic Python state machine.
    Enforces that valid lifecycle state transitions occur strictly in order.
    The controller, not an LLM, decides valid state transitions.
    """

    @staticmethod
    def validate_transition(current_state: str, new_state: str) -> bool:
        if new_state not in VALID_STATES:
            raise ValueError(f"Invalid workflow state: '{new_state}'. Valid states: {VALID_STATES}")

        allowed = ALLOWED_TRANSITIONS.get(current_state, set())
        if new_state not in allowed:
            # Allow terminal transitions (CANCELLED, FAILED) from any active state
            if new_state in ("CANCELLED", "FAILED", "TIMED_OUT"):
                return True
            raise ValueError(f"Invalid state transition: Cannot transition from '{current_state}' to '{new_state}'. Allowed: {allowed}")

        return True

workflow_sm = WorkflowStateMachine()
