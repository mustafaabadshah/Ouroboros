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
        model: Optional[str] = None
    ) -> FailureTrajectoryModel:
        """Records a new failure trajectory and tags repeated failures."""
        # Check if an identical failure was recorded previously
        status = "UNRESOLVED"
        past_failures = list_failure_trajectories(db, ticket_id=ticket_id)
        for prev in past_failures:
            if prev.patch_hash == patch_hash and prev.failed_tests_json == failed_tests:
                status = "REPEATED"
                logger.warning(f"Repeated failure detected for ticket {ticket_id} (patch hash: {patch_hash[:8]})")
                break

        traj_data = {
            "run_id": run_id,
            "ticket_id": ticket_id,
            "attempt": attempt,
            "provider": provider,
            "model": model,
            "failed_tests_json": failed_tests,
            "traceback_excerpt": traceback_excerpt[:2000] if traceback_excerpt else None,
            "ast_diff_json": ast_diff,
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
        Does NOT dump the entire database - passes only relevant diagnostic excerpts.
        """
        trajectories = list_failure_trajectories(db, ticket_id=ticket_id)
        if not trajectories:
            return {"has_history": False, "prior_attempts": []}

        history_items = []
        for t in trajectories[:max_history]:
            history_items.append({
                "attempt": t.attempt,
                "failed_tests": t.failed_tests_json,
                "traceback": t.traceback_excerpt,
                "repair_hint": t.repair_hint,
                "status": t.status,
                "patch_hash": t.patch_hash[:8] if t.patch_hash else None
            })

        return {
            "has_history": True,
            "prior_attempts": history_items,
            "has_repeated_failure": any(t.status == "REPEATED" for t in trajectories)
        }

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
