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
    update_ticket_status,
    get_repository,
    get_verified_repo_path,
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
from app.core.security import is_protected_path

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

            from app.observability.phoenix_service import phoenix_service, set_current_run_context
            from app.sandbox.detector import sandbox_detector
            import json

            set_current_run_context(run.id, run.ticket_id)

            with phoenix_service.trace_workflow(run.id, run.ticket_id, name="ouroboros.workflow"):
                # Fail-Closed Sandbox Gate
                sandbox_status = await sandbox_detector.detect_capabilities()
                if not sandbox_status.get("can_execute", True):
                    logger.warning(f"Run {run_id} blocked: {sandbox_status['message']}")
                    return await self._terminate(db, run_id, "BLOCKED", sandbox_status["message"])

                # Cryptographically freeze acceptance criteria
                criteria_payload = json.dumps({
                    "title": ticket.title,
                    "acceptance_criteria": ticket.acceptance_criteria_json,
                    "candidate_files": ticket.candidate_files_json
                }, sort_keys=True)
                frozen_criteria_hash = hashlib.sha256(criteria_payload.encode("utf-8")).hexdigest()
                logger.info(f"Frozen acceptance criteria hash for run {run_id}: {frozen_criteria_hash[:12]}")

                repo_path = get_verified_repo_path(repo)

                # -------------------------------------------------------------
                # Stage 1: BASELINE_VALIDATION
                # -------------------------------------------------------------
                await self._transition(db, run_id, "BASELINE_VALIDATION", active_agent="Judge")
                if self.is_cancelled(run_id):
                    return await self._terminate(db, run_id, "CANCELLED", "User cancelled run.")

                with phoenix_service.trace_step("tests.baseline", stage="BASELINE_VALIDATION"):
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

                with phoenix_service.trace_step("planner.run", agent="Planner"):
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
                    with phoenix_service.trace_step("worktree.isolate", repo=repo.id):
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

                    if attempt > 1 and run.base_commit:
                        logger.info(f"Resetting worktree {worktree_path} cleanly to base_commit {run.base_commit[:8]} for attempt {attempt}")
                        await git_worktree_manager.reset_worktree_to_base(worktree_path, run.base_commit)

                    await self._transition(
                        db,
                        run_id,
                        "CODING",
                        active_agent="RepairAgent" if attempt > 1 else "LocalCoder"
                    )

                    execution_dag = plan.get("execution_dag", {})
                    is_parallel = execution_dag.get("is_parallelizable", False) and len(subtasks) > 1

                    # Generate or repair patch
                    with phoenix_service.trace_step("coder.run", attempt=attempt, agent="RepairAgent" if attempt > 1 else "LocalCoder"):
                        if attempt == 1 and is_parallel:
                            logger.info(f"Executing DAG parallel patch synthesis across {len(subtasks)} disjoint subtasks with concurrent worktrees.")
                            subtask_keys = [st.get("subtask_id", f"ST-{i}") for i, st in enumerate(subtasks)]
                            sub_wts = await git_worktree_manager.create_parallel_subtask_worktrees(
                                repo_path=repo_path,
                                ticket_id=ticket.id,
                                subtask_keys=subtask_keys
                            )

                            async def _synthesize_in_worktree(st):
                                sid = st.get("subtask_id", "ST-1")
                                wt_info = sub_wts.get(sid)
                                wt_p = wt_info[0] if wt_info else worktree_path
                                rel_path = st.get("target_file", "").replace("\\", "/")
                                full_p = wt_p / rel_path
                                f_content = ""
                                if full_p.exists():
                                    with open(full_p, "r", encoding="utf-8", errors="replace") as f:
                                        f_content = f.read()
                                inst_seed = failure_flywheel.get_institutional_coder_seed(
                                    db=db,
                                    target_file=rel_path,
                                    problem_statement=ticket.problem_statement
                                )
                                pmt = coder_lead.prepare_coding_prompt(
                                    subtask=st,
                                    ticket={"title": ticket.title, "acceptance_criteria": ticket.acceptance_criteria_json},
                                    file_content=f_content,
                                    failure_hint=inst_seed
                                )
                                res = await local_coder_agent.generate_patch(pmt, force_mock=use_mock_agents)
                                if res.get("diff_text"):
                                    await git_worktree_manager.apply_patch(wt_p, res.get("diff_text"))
                                return res

                            coder_results = await asyncio.gather(*[_synthesize_in_worktree(st) for st in subtasks])
                            await git_worktree_manager.cleanup_parallel_subtask_worktrees(repo_path, ticket.id, subtask_keys)

                            merged_diffs = [r.get("diff_text", "").strip() for r in coder_results if r.get("diff_text", "").strip()]
                            combined_diff = "\n\n".join(merged_diffs)
                            coder_res = {
                                "diff_text": combined_diff,
                                "explanation": f"Parallel DAG dual-worktree synthesis ({len(subtasks)} subtasks): " + "; ".join(r.get("explanation", "")[:100] for r in coder_results),
                                "provider": coder_results[0].get("provider"),
                                "model": coder_results[0].get("model"),
                                "is_error": any(r.get("is_error") for r in coder_results)
                            }
                        elif attempt == 1:
                            target_file_rel = target_subtask.get("target_file", "").replace("\\", "/")
                            target_full_path = worktree_path / target_file_rel
                            current_file_content = ""
                            if target_full_path.exists():
                                with open(target_full_path, "r", encoding="utf-8", errors="replace") as f:
                                    current_file_content = f.read()

                            institutional_seed = failure_flywheel.get_institutional_coder_seed(
                                db=db,
                                target_file=target_file_rel,
                                problem_statement=ticket.problem_statement
                            )
                            code_prompt = coder_lead.prepare_coding_prompt(
                                subtask=target_subtask,
                                ticket={
                                    "title": ticket.title,
                                    "acceptance_criteria": ticket.acceptance_criteria_json
                                },
                                file_content=current_file_content,
                                failure_hint=institutional_seed
                            )
                            coder_res = await local_coder_agent.generate_patch(code_prompt, force_mock=use_mock_agents)
                        else:
                            # Repair step
                            repair_context = failure_flywheel.get_repair_context(db, ticket.id)
                            target_file_rel = target_subtask.get("target_file", "").replace("\\", "/")
                            if repair_context.get("target_file") and not is_protected_path(repair_context["target_file"]):
                                target_file_rel = str(repair_context["target_file"]).replace("\\", "/")

                            target_full_path = worktree_path / target_file_rel
                            current_file_content = ""
                            if target_full_path.exists():
                                with open(target_full_path, "r", encoding="utf-8", errors="replace") as f:
                                    current_file_content = f.read()

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

                    with phoenix_service.trace_step("patch.validate", attempt=attempt):
                        # Construct comprehensive allowed files:
                        # 1. Candidate files
                        # 2. Planner's subtasks target files
                        # 3. Relevant graph entities
                        # Exclude any protected file patterns
                        allowed_scope = set()
                        for f in (ticket.candidate_files_json or []):
                            if not is_protected_path(f):
                                allowed_scope.add(f)
                        for st in subtasks:
                            tf = st.get("target_file")
                            if tf and not is_protected_path(tf):
                                allowed_scope.add(tf)
                        for rge in (ticket.relevant_graph_entities_json or []):
                            if isinstance(rge, str) and ("/" in rge or "." in rge) and not is_protected_path(rge):
                                allowed_scope.add(rge)

                        effective_allowed = list(allowed_scope) if allowed_scope else ticket.candidate_files_json
                        static_check = deterministic_judge.evaluate_patch_static(
                            diff_text=diff_text,
                            allowed_files=effective_allowed,
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
                        rule_id = static_check.get("policy_rule_id", "StaticASTValidation")
                        req_hint = static_check.get("policy_requirement")
                        reason = static_check.get("reason", "Static syntax or policy violation.")
                        if req_hint:
                            repair_hint = f"POLICY VIOLATION [{rule_id}]: {reason}. Requirement: {req_hint}. Do NOT use dynamic __import__, eval, exec, or prohibited modules. Use standard top-level imports."
                        else:
                            repair_hint = f"STATIC VALIDATION FAILED: {reason}. Correct Python syntax, remove invalid hunks, and ensure valid unified diff headers."

                        failure_flywheel.record_failure(
                            db=db,
                            run_id=run_id,
                            ticket_id=ticket.id,
                            attempt=attempt,
                            failed_tests=["StaticASTValidation", rule_id] if rule_id != "StaticASTValidation" else ["StaticASTValidation"],
                            traceback_excerpt=reason,
                            ast_diff=static_check.get("ast_analysis", {}),
                            patch_hash=diff_hash,
                            root_cause_hypothesis=f"Patch violates static constraints: {reason}",
                            repair_hint=repair_hint,
                            provider=coder_res.get("provider"),
                            model=coder_res.get("model"),
                            failure_context=static_check.get("failure_context")
                        )
                        attempt += 1
                        run.retry_count = attempt - 1
                        db.commit()
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
                        run.retry_count = attempt - 1
                        db.commit()
                        continue

                    # Commit candidate inside isolated worktree
                    await git_worktree_manager.commit_candidate(
                        worktree_path=worktree_path,
                        message=f"feat({ticket.id}): {ticket.title}\n\nCandidate patch attempt {attempt} evaluated by DeterministicJudge."
                    )

                    # -------------------------------------------------------------
                    # Stage 6: ACCEPTANCE_TESTS & REGRESSION_TESTS (AST-Directed Fail-Fast)
                    # -------------------------------------------------------------
                    await self._transition(db, run_id, "ACCEPTANCE_TESTS", active_agent="Judge")

                    candidate_files = ticket.candidate_files_json or list(static_check.get("ast_analysis", {}).keys())
                    impact_test_files = meta_graph_adapter.get_impacted_tests_from_callgraph(
                        ticket.repo_id,
                        candidate_files,
                        target_symbols=ticket.relevant_graph_entities_json or []
                    )
                    if impact_test_files:
                        logger.info(f"Identified {len(impact_test_files)} AST call-graph impact test file(s) for {ticket.id}: {impact_test_files}")

                    with phoenix_service.trace_step("tests.execute", attempt=attempt):
                        judge_eval = await deterministic_judge.evaluate_candidate(
                            worktree_path=worktree_path,
                            baseline_results=baseline_res,
                            acceptance_test_file=impact_test_files[0] if impact_test_files else None,
                            impact_test_files=impact_test_files,
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
                        if judge_eval.get("is_fail_fast"):
                            logger.info(f"Publishing FAIL_FAST_TRIGGERED event: {judge_eval.get('reason')}")
                            try:
                                await event_bus.publish(run_id, "FAIL_FAST_TRIGGERED", {
                                    "test_file": judge_eval.get("fail_fast_test"),
                                    "duration_ms": judge_eval.get("duration_ms"),
                                    "message": judge_eval.get("reason")
                                })
                            except Exception as pub_err:
                                logger.warning(f"Failed to publish FAIL_FAST_TRIGGERED event: {pub_err}")
                        # Safely extract failure details
                        reg_failures = reg_res.get("failures") if (reg_res and isinstance(reg_res.get("failures"), list)) else []
                        if reg_failures and len(reg_failures) > 0 and isinstance(reg_failures[0], dict):
                            first_tb = reg_failures[0].get("traceback", judge_eval.get("reason", "Test regression failed"))
                            failed_test_names = [f.get("test_name", "TestFailure") for f in reg_failures if isinstance(f, dict)]
                        else:
                            first_tb = (reg_res.get("stderr_excerpt") if reg_res else None) or judge_eval.get("reason", "Regression test failure or timeout")
                            failed_test_names = ["TestTimeoutOrFailure"]

                        # Record failure trajectory
                        failure_context = reg_res.get("failure_context") if reg_res else None
                        failure_flywheel.record_failure(
                            db=db,
                            run_id=run_id,
                            ticket_id=ticket.id,
                            attempt=attempt,
                            failed_tests=failed_test_names,
                            traceback_excerpt=first_tb,
                            ast_diff=static_check.get("ast_analysis", {}),
                            patch_hash=diff_hash,
                            root_cause_hypothesis=judge_eval.get("reason", "Candidate failed acceptance or regression testing."),
                            repair_hint="Fix assertions, avoid regressions in existing tests, and adhere to strict Python syntax.",
                            provider=coder_res.get("provider"),
                            model=coder_res.get("model"),
                            failure_context=failure_context
                        )
                        attempt += 1
                        run.retry_count = attempt - 1
                        db.commit()

                # -------------------------------------------------------------
                # Stage 7: FINAL VERDICT & AWAITING APPROVAL
                # -------------------------------------------------------------
                with phoenix_service.trace_step("approval.evaluate", verdict="PASS" if evaluation_passed else "FAIL"):
                    if evaluation_passed:
                        await self._transition(db, run_id, "AWAITING_APPROVAL", verdict="PASS", active_agent="HumanReviewer")
                        record_audit_event(db, "CANDIDATE_READY_FOR_REVIEW", details={"run_id": run_id, "ticket_id": ticket.id})
                    else:
                        await self._terminate(db, run_id, "FAILED", f"All {max_attempts} repair attempts exhausted.")

        except Exception as e:
            logger.error(f"Fatal error during run execution: {e}", exc_info=True)
            await self._terminate(db, run_id, "FAILED", str(e))
        finally:
            from app.observability.phoenix_service import phoenix_service
            phoenix_service.flush()
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
            try:
                await event_bus.publish(run_id, "STATE_CHANGED", {
                    "state": new_state,
                    "active_agent": active_agent,
                    "verdict": verdict
                })
            except Exception as pe:
                logger.warning(f"Failed to broadcast STATE_CHANGED: {pe}")

    async def _terminate(self, db: Session, run_id: str, final_state: str, message: str):
        run = update_run_state(db, run_id, final_state, error_message=message)
        logger.info(f"Run {run_id} terminated with state {final_state}: {message}")
        if run and run.ticket_id:
            if final_state == "FAILED":
                update_ticket_status(db, run.ticket_id, "FAILED")
                record_audit_event(db, "TICKET_RUN_FAILED", details={"run_id": run_id, "ticket_id": run.ticket_id, "error": message})
            elif final_state == "COMPLETED":
                update_ticket_status(db, run.ticket_id, "ACCEPTED")
                record_audit_event(db, "TICKET_RUN_COMPLETED", details={"run_id": run_id, "ticket_id": run.ticket_id})
        try:
            await event_bus.publish(run_id, "RUN_TERMINATED", {
                "state": final_state,
                "error_message": message
            })
        except Exception as pe:
            logger.warning(f"Failed to broadcast RUN_TERMINATED: {pe}")

workflow_controller = WorkflowController()
