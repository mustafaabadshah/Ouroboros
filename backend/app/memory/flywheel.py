import json
from pathlib import Path
from datetime import datetime, timezone
from typing import Dict, List, Any, Optional
from sqlalchemy.orm import Session

from app.database.models import FailureTrajectoryModel
from app.database.repositories import (
    create_failure_trajectory,
    list_failure_trajectories
)
from app.evaluation.failure_context import FailureContext
from app.core.logging import logger

class FailureFlywheel:
    """
    Persistent failure memory engine.
    Stores exact failure trajectories, tracebacks, AST diffs, and hypotheses.
    Detects repeated failure patterns and arms the Repair Agent with grounded historical lessons.
    """

    @staticmethod
    def record_failure(
        db: Session,
        run_id: str,
        ticket_id: str,
        attempt: int,
        failed_tests: List[str],
        traceback_excerpt: str,
        ast_diff: Dict[str, Any],
        patch_hash: str,
        root_cause_hypothesis: Optional[str] = None,
        repair_hint: Optional[str] = None,
        provider: Optional[str] = None,
        model: Optional[str] = None,
        failure_context: Optional[Dict[str, Any]] = None
    ) -> FailureTrajectoryModel:
        """Records a new failure trajectory and tags repeated semantic failures."""
        status = "UNRESOLVED"
        sig = ""
        if failure_context:
            try:
                ctx_obj = FailureContext.from_dict(failure_context)
                sig = ctx_obj.compute_signature()
            except Exception as e:
                logger.warning(f"Could not compute failure signature: {e}")

        # Check if an identical failure was recorded previously (semantic signature or exact patch)
        past_failures = list_failure_trajectories(db, ticket_id=ticket_id)
        for prev in past_failures:
            prev_sig = (prev.ast_diff_json or {}).get("failure_signature")
            if (sig and prev_sig and prev_sig == sig) or (prev.patch_hash == patch_hash and prev.failed_tests_json == failed_tests):
                status = "REPEATED"
                logger.warning(f"Repeated failure detected for ticket {ticket_id} (sig: {sig}, patch hash: {patch_hash[:8]})")
                break

        combined_ast = dict(ast_diff or {})
        if failure_context:
            combined_ast["failure_context"] = failure_context
            if sig:
                combined_ast["failure_signature"] = sig

        traj_data = {
            "run_id": run_id,
            "ticket_id": ticket_id,
            "attempt": attempt,
            "provider": provider,
            "model": model,
            "failed_tests_json": failed_tests,
            "traceback_excerpt": traceback_excerpt[:2000] if traceback_excerpt else None,
            "ast_diff_json": combined_ast,
            "patch_hash": patch_hash,
            "root_cause_hypothesis": root_cause_hypothesis,
            "repair_hint": repair_hint,
            "status": status,
        }

        record = create_failure_trajectory(db, traj_data)
        logger.info(f"Recorded failure trajectory {record.id} for ticket {ticket_id} (attempt {attempt}, status={status})")
        return record

    @staticmethod
    def get_repair_context(db: Session, ticket_id: str, max_history: int = 3) -> Dict[str, Any]:
        """
        Extracts bounded, formatted failure trajectory context for the Repair Agent.
        Provides both legacy list representation and canonical structured diagnostic fields.
        """
        trajectories = list_failure_trajectories(db, ticket_id=ticket_id)
        if not trajectories:
            return {
                "has_history": False,
                "has_repeated_failure": False,
                "repetition_count": 0,
                "failed_tests": [],
                "traceback": "",
                "prior_attempts": []
            }

        latest = trajectories[0] if trajectories else None
        latest_ctx_dict = (latest.ast_diff_json or {}).get("failure_context") if latest else None

        has_repeated = any(t.status == "REPEATED" for t in trajectories)
        rep_count = sum(1 for t in trajectories if t.status == "REPEATED")

        latest_ctx = None
        if latest_ctx_dict:
            try:
                latest_ctx = FailureContext.from_dict(latest_ctx_dict)
                if has_repeated:
                    latest_ctx.is_repeated = True
                    latest_ctx.repetition_count = rep_count
            except Exception as e:
                logger.warning(f"Failed to deserialize FailureContext from trajectory: {e}")

        history_items = []
        for t in trajectories[:max_history]:
            t_ctx = (t.ast_diff_json or {}).get("failure_context", {})
            history_items.append({
                "attempt": t.attempt,
                "failed_tests": t.failed_tests_json,
                "traceback": t.traceback_excerpt,
                "repair_hint": t.repair_hint,
                "status": t.status,
                "patch_hash": t.patch_hash[:8] if t.patch_hash else None,
                "failure_signature": (t.ast_diff_json or {}).get("failure_signature"),
                "failure_class": t_ctx.get("failure_class"),
                "assertion_message": t_ctx.get("assertion_message"),
                "policy_rule_id": t_ctx.get("policy_rule_id")
            })

        # Resolved top-level fields
        resolved_failed_tests = (
            latest_ctx.failed_test_nodes if (latest_ctx and latest_ctx.failed_test_nodes)
            else (latest.failed_tests_json if latest else [])
        )
        resolved_traceback = (
            latest_ctx.traceback_tail if (latest_ctx and latest_ctx.traceback_tail)
            else (latest.traceback_excerpt if latest else "")
        )

        res: Dict[str, Any] = {
            "has_history": True,
            "has_repeated_failure": has_repeated,
            "repetition_count": rep_count,
            "latest_attempt": latest.attempt if latest else 1,
            # Top-level fields expected by RepairAgent.synthesize_repair
            "failed_tests": resolved_failed_tests,
            "traceback": resolved_traceback,
            "prior_attempts": history_items,
        }

        if latest_ctx:
            res.update({
                "failure_class": latest_ctx.failure_class.value,
                "assertion": latest_ctx.assertion_message,
                "expected": latest_ctx.expected_value,
                "actual": latest_ctx.actual_value,
                "source_location": latest_ctx.source_location,
                "policy_rule_id": latest_ctx.policy_rule_id,
                "policy_reason": latest_ctx.policy_reason,
                "policy_requirement": latest_ctx.policy_requirement,
                "failure_signature": latest_ctx.failure_signature,
                "formatted_diagnostic": latest_ctx.format_for_repair_prompt(),
            })
        elif latest and latest.traceback_excerpt:
            res["formatted_diagnostic"] = f"Failed Tests: {', '.join(latest.failed_tests_json or [])}\nTraceback:\n{latest.traceback_excerpt}"

        return res

    @staticmethod
    def export_trajectories_json(db: Session, ticket_id: Optional[str] = None) -> str:
        """Exports failure trajectories as structured JSON."""
        records = list_failure_trajectories(db, ticket_id=ticket_id)
        data = []
        for r in records:
            data.append({
                "id": r.id,
                "run_id": r.run_id,
                "ticket_id": r.ticket_id,
                "attempt": r.attempt,
                "provider": r.provider,
                "model": r.model,
                "failed_tests": r.failed_tests_json,
                "traceback": r.traceback_excerpt,
                "ast_diff": r.ast_diff_json,
                "patch_hash": r.patch_hash,
                "root_cause_hypothesis": r.root_cause_hypothesis,
                "repair_hint": r.repair_hint,
                "status": r.status,
                "created_at": r.created_at.isoformat() if r.created_at else None
            })
        return json.dumps(data, indent=2)

failure_flywheel = FailureFlywheel()
