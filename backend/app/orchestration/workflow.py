import asyncio
import hashlib
from pathlib import Path
from typing import Dict, Any, Optional
from datetime import datetime, timezone
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.logging import logger
from app.core.events import event_bus
from app.database.session import SessionLocal
from app.database.repositories import (
    get_run,
    get_ticket,
    get_repository,
    update_run_state,
    create_candidate,
    record_test_result,
    record_audit_event
)
from app.orchestration.state_machine import workflow_sm
from app.integrations.git.worktree import git_worktree_manager
from app.integrations.git.diff_parser import UnifiedDiffParser
from app.integrations.graph.adapter import meta_graph_adapter
from app.agents.planner import planner_agent
from app.agents.coder_lead import coder_lead
from app.agents.local_coder import local_coder_agent
from app.agents.repair_agent import repair_agent
from app.evaluation.judge import deterministic_judge
from app.evaluation.runner import pytest_runner
from app.memory.flywheel import failure_flywheel

class WorkflowController:
    """
    Autonomous Swarm Workflow Controller.
    Orchestrates the complete deterministic ticket-to-patch-to-test lifecycle.
    Guarantees:
    - Deterministic state machine enforcement
    - Non-destructive Git worktree isolation
    - Persistent failure memory flywheel
    - Zero merges without explicit human approval
    """

    def __init__(self):
        self._cancelled_runs = set()

    def cancel_run(self, run_id: str):
        self._cancelled_runs.add(run_id)
        logger.warning(f"Cancellation requested for run {run_id}")

    def is_cancelled(self, run_id: str) -> bool:
        return run_id in self._cancelled_runs

    async def execute_run_lifecycle(self, run_id: str, use_mock_agents: bool = False):
        """Asynchronously runs the full state machine pipeline."""
        db: Session = SessionLocal()
        try:
            run = get_run(db, run_id)
            if not run:
                logger.error(f"Run {run_id} not found.")
                return

            ticket = get_ticket(db, run.ticket_id)
            repo = get_repository(db, run.repo_id)
            if not ticket or not repo:
                logger.error(f"Missing ticket or repository for run {run_id}.")
                return

            repo_path = Path(repo.path)

            # -------------------------------------------------------------
            # Stage 1: BASELINE_VALIDATION
            # -------------------------------------------------------------
            await self._transition(db, run_id, "BASELINE_VALIDATION", active_agent="Judge")
            if self.is_cancelled(run_id):
                return await self._terminate(db, run_id, "CANCELLED", "User cancelled run.")

            # Run existing tests against the clean baseline repository
            baseline_res = await pytest_runner.run_tests(
                working_dir=repo_path,
                test_path="backend/tests"
            )
            record_test_result(db, {
                "run_id": run_id,
                "test_type": "baseline",
                "test_command": baseline_res["command"],
                "exit_code": baseline_res["exit_code"],
                "duration_ms": baseline_res["duration_ms"],
                "passed_count": baseline_res["passed_count"],
                "failed_count": baseline_res["failed_count"],
                "error_count": baseline_res["error_count"],
                "failures_json": baseline_res["failures"],
                "stdout_excerpt": baseline_res["stdout_excerpt"],
                "stderr_excerpt": baseline_res["stderr_excerpt"]
            })
            logger.info(f"Baseline validation complete: {baseline_res['passed_count']} passed, {baseline_res['failed_count']} failed.")

            # -------------------------------------------------------------
            # Stage 2: PLANNING
            # -------------------------------------------------------------
            await self._transition(db, run_id, "PLANNING", active_agent="Planner")
            if self.is_cancelled(run_id):
                return await self._terminate(db, run_id, "CANCELLED", "User cancelled run.")

            plan = await planner_agent.create_plan(
                repo_id=repo.id,
                ticket={
                    "title": ticket.title,
                    "problem_statement": ticket.problem_statement,
                    "acceptance_criteria": ticket.acceptance_criteria_json,
                    "candidate_files": ticket.candidate_files_json,
                    "relevant_graph_entities": ticket.relevant_graph_entities_json
                },
                force_mock=use_mock_agents
            )
            subtasks = plan.get("ordered_subtasks", [])
            target_subtask = subtasks[0] if subtasks else {
                "target_file": ticket.candidate_files_json[0] if ticket.candidate_files_json else "backend/app/agents/groq_agent.py",
                "description": ticket.problem_statement
            }

            # -------------------------------------------------------------
            # Stage 3: ISOLATED WORKTREE CREATION
            # -------------------------------------------------------------
            try:
                worktree_path, cand_branch, base_commit = await git_worktree_manager.create_worktree(
                    repo_path=repo_path,
                    ticket_id=ticket.id
                )
                run.worktree_path = str(worktree_path)
                run.candidate_branch = cand_branch
                run.base_commit = base_commit
                db.commit()
            except Exception as wt_err:
                return await self._terminate(db, run_id, "BLOCKED", f"Worktree creation failed: {wt_err}")

            # -------------------------------------------------------------
            # Stage 4: CODING & REPAIR LOOP
            # -------------------------------------------------------------
            attempt = 1
            max_attempts = run.max_retries or settings.MAX_REPAIR_ATTEMPTS
            evaluation_passed = False

            while attempt <= max_attempts and not evaluation_passed:
                if self.is_cancelled(run_id):
                    return await self._terminate(db, run_id, "CANCELLED", "User cancelled run.")

                await self._transition(
                    db,
                    run_id,
                    "CODING",
                    active_agent="RepairAgent" if attempt > 1 else "LocalCoder"
                )

                target_file_rel = target_subtask.get("target_file", "").replace("\\", "/")
                target_full_path = worktree_path / target_file_rel
                current_file_content = ""
                if target_full_path.exists():
                    with open(target_full_path, "r", encoding="utf-8", errors="replace") as f:
                        current_file_content = f.read()

                # Generate or repair patch
                if attempt == 1:
                    code_prompt = coder_lead.prepare_coding_prompt(
                        subtask=target_subtask,
                        ticket={
                            "title": ticket.title,
                            "acceptance_criteria": ticket.acceptance_criteria_json
                        },
                        file_content=current_file_content
                    )
                    coder_res = await local_coder_agent.generate_patch(code_prompt, force_mock=use_mock_agents)
                else:
                    # Repair step
                    repair_context = failure_flywheel.get_repair_context(db, ticket.id)
                    coder_res = await repair_agent.synthesize_repair(
                        ticket={"title": ticket.title},
                        target_file=target_file_rel,
                        current_code=current_file_content,
                        failure_trajectory=repair_context,
                        force_mock=use_mock_agents
                    )

                diff_text = coder_res.get("diff_text", "")
                diff_hash = hashlib.sha256(diff_text.encode("utf-8")).hexdigest()

                # -------------------------------------------------------------
                # Stage 5: PATCH_VALIDATION (Static AST + Bounds)
                # -------------------------------------------------------------
                await self._transition(db, run_id, "PATCH_VALIDATION", active_agent="Judge")

                static_check = deterministic_judge.evaluate_patch_static(
                    diff_text=diff_text,
                    allowed_files=ticket.candidate_files_json,
                    worktree_path=worktree_path
                )

                # Record candidate in DB
                cand_record = create_candidate(db, {
                    "run_id": run_id,
                    "ticket_id": ticket.id,
                    "attempt": attempt,
                    "diff_content": diff_text,
                    "diff_hash": diff_hash,
                    "patch_explanation": coder_res.get("explanation"),
                    "changed_files_json": list(static_check.get("ast_analysis", {}).keys()),
                    "ast_changes_json": static_check.get("ast_analysis", {}),
                    "status": "APPLIED" if static_check["verdict"] == "PASS" else static_check["verdict"]
                })

                if static_check["verdict"] != "PASS":
                    logger.warning(f"Static validation failed: {static_check['reason']}")
                    failure_flywheel.record_failure(
                        db=db,
                        run_id=run_id,
                        ticket_id=ticket.id,
                        attempt=attempt,
                        failed_tests=["StaticASTValidation"],
                        traceback_excerpt=static_check["reason"],
                        ast_diff=static_check.get("ast_analysis", {}),
                        patch_hash=diff_hash,
                        root_cause_hypothesis="Patch violates static constraints or contains syntax errors.",
                        repair_hint="Correct syntax and verify diff headers.",
                        provider=coder_res.get("provider"),
                        model=coder_res.get("model")
                    )
                    attempt += 1
                    continue

                # Apply patch into isolated worktree
                applied_ok, apply_err = await git_worktree_manager.apply_patch(worktree_path, diff_text)
                if not applied_ok:
                    logger.warning(f"Git apply failed: {apply_err}")
                    failure_flywheel.record_failure(
                        db=db,
                        run_id=run_id,
                        ticket_id=ticket.id,
                        attempt=attempt,
                        failed_tests=["GitApplyError"],
                        traceback_excerpt=apply_err,
                        ast_diff={},
                        patch_hash=diff_hash,
                        root_cause_hypothesis="Diff hunk line numbers or context mismatch.",
                        repair_hint="Regenerate unified diff against current file content.",
                        provider=coder_res.get("provider"),
                        model=coder_res.get("model")
                    )
                    attempt += 1
                    continue

                # Commit candidate inside isolated worktree
                await git_worktree_manager.commit_candidate(
                    worktree_path=worktree_path,
                    message=f"feat({ticket.id}): {ticket.title}\n\nCandidate patch attempt {attempt} evaluated by DeterministicJudge."
                )

                # -------------------------------------------------------------
                # Stage 6: ACCEPTANCE_TESTS & REGRESSION_TESTS
                # -------------------------------------------------------------
                await self._transition(db, run_id, "ACCEPTANCE_TESTS", active_agent="Judge")

                judge_eval = await deterministic_judge.evaluate_candidate(
                    worktree_path=worktree_path,
                    baseline_results=baseline_res,
                    acceptance_test_file=None,
                    regression_test_dir="backend/tests"
                )

                verdict = judge_eval["verdict"]
                reg_res = judge_eval.get("regression")
                if reg_res:
                    record_test_result(db, {
                        "run_id": run_id,
                        "candidate_id": cand_record.id,
                        "test_type": "regression",
                        "test_command": reg_res["command"],
                        "exit_code": reg_res["exit_code"],
                        "duration_ms": reg_res["duration_ms"],
                        "passed_count": reg_res["passed_count"],
                        "failed_count": reg_res["failed_count"],
                        "error_count": reg_res["error_count"],
                        "failures_json": reg_res["failures"],
                        "stdout_excerpt": reg_res["stdout_excerpt"],
                        "stderr_excerpt": reg_res["stderr_excerpt"]
                    })

                if verdict == "PASS":
                    evaluation_passed = True
                    logger.info(f"Candidate passed evaluation on attempt {attempt}!")
                    break
                else:
                    logger.warning(f"Candidate evaluation failed on attempt {attempt}: {judge_eval['reason']}")
                    # Record failure trajectory
                    failure_flywheel.record_failure(
                        db=db,
                        run_id=run_id,
                        ticket_id=ticket.id,
                        attempt=attempt,
                        failed_tests=[f["test_name"] for f in reg_res.get("failures", [])] if reg_res else ["TestFailure"],
                        traceback_excerpt=reg_res.get("failures", [{}])[0].get("traceback", judge_eval["reason"]) if reg_res else judge_eval["reason"],
                        ast_diff=static_check.get("ast_analysis", {}),
                        patch_hash=diff_hash,
                        root_cause_hypothesis=judge_eval["reason"],
                        repair_hint="Fix assertions and avoid regressions in existing tests.",
                        provider=coder_res.get("provider"),
                        model=coder_res.get("model")
                    )
                    attempt += 1

            # -------------------------------------------------------------
            # Stage 7: FINAL VERDICT & AWAITING APPROVAL
            # -------------------------------------------------------------
            if evaluation_passed:
                await self._transition(db, run_id, "AWAITING_APPROVAL", verdict="PASS", active_agent="HumanReviewer")
                record_audit_event(db, "CANDIDATE_READY_FOR_REVIEW", details={"run_id": run_id, "ticket_id": ticket.id})
            else:
                await self._terminate(db, run_id, "FAILED", f"All {max_attempts} repair attempts exhausted.")

        except Exception as e:
            logger.error(f"Fatal error during run execution: {e}", exc_info=True)
            await self._terminate(db, run_id, "FAILED", str(e))
        finally:
            db.close()

    async def _transition(
        self,
        db: Session,
        run_id: str,
        new_state: str,
        active_agent: Optional[str] = None,
        verdict: Optional[str] = None
    ):
        run = get_run(db, run_id)
        if run:
            workflow_sm.validate_transition(run.state, new_state)
            update_run_state(db, run_id, new_state, active_agent=active_agent, verdict=verdict)
            logger.info(f"Run {run_id} transitioned to {new_state} [agent: {active_agent}]")
            await event_bus.publish(run_id, "STATE_CHANGED", {
                "state": new_state,
                "active_agent": active_agent,
                "verdict": verdict
            })

    async def _terminate(self, db: Session, run_id: str, final_state: str, message: str):
        update_run_state(db, run_id, final_state, error_message=message)
        logger.info(f"Run {run_id} terminated with state {final_state}: {message}")
        await event_bus.publish(run_id, "RUN_TERMINATED", {
            "state": final_state,
            "error_message": message
        })

workflow_controller = WorkflowController()
