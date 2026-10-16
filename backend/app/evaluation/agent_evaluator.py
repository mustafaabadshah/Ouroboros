"""
Project Ouroboros - Real Agent Evaluation Engine (v0.10)
Connects the production multi-agent repair workflow (Planner, CoderLead, LocalCoder,
RepairAgent, DeterministicJudge, FailureFlywheel) to the 16-task deterministic benchmark.

Evaluates actual AI-generated candidate patches against genuine defects in isolated
disposable worktrees, enforcing sandbox security, fail-closed policy gates, and
detailed telemetry with verified denominators.
"""

import os
import sys
import time
import json
import uuid
import shutil
import hashlib
import tempfile
import asyncio
from pathlib import Path
from typing import Dict, List, Any, Optional, Tuple

from app.core.config import settings
from app.core.logging import logger
from app.core.security import run_safe_subprocess, validate_safe_path
from app.integrations.git.worktree import GitWorktreeManager
from app.integrations.git.diff_parser import UnifiedDiffParser
from app.evaluation.runner import PytestRunner
from app.evaluation.judge import DeterministicJudge
from app.evaluation.benchmark import BENCHMARK_TASKS_V1, BenchmarkHarness
from app.agents.planner import planner_agent
from app.agents.coder_lead import coder_lead
from app.agents.local_coder import local_coder_agent, LocalCoderAgent
from app.agents.repair_agent import repair_agent
from app.memory.flywheel import FailureFlywheel
from app.database.session import Base
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.sandbox.detector import sandbox_detector
from app.evaluation.failure_context import FailureContextNormalizer


def redact_sensitive_strings(text: Optional[str]) -> Optional[str]:
    """Redacts any API keys or credentials from telemetry strings."""
    if not text:
        return text
    clean = str(text)
    if settings.GROQ_API_KEY and settings.GROQ_API_KEY in clean:
        clean = clean.replace(settings.GROQ_API_KEY, "[REDACTED_API_KEY]")
    # Generic bearer / key pattern redactions
    import re
    clean = re.sub(r"gsk_[a-zA-Z0-9]{20,}", "[REDACTED_GROQ_KEY]", clean)
    clean = re.sub(r"(Bearer\s+)[a-zA-Z0-9_\-\.]{20,}", r"\1[REDACTED_TOKEN]", clean)
    return clean


class AgentRepairEvaluator:
    """
    Executes real multi-agent software repair evaluations on benchmark tasks.
    Unlike fixture validation, this invokes the actual LLM agent pipeline
    and tests the model's synthesized candidate patches against acceptance gates.
    """

    @classmethod
    async def evaluate_task(
        cls,
        task_def: Dict[str, Any],
        memory_enabled: bool = True,
        retry_strategy: Optional[str] = None,
        force_mock: bool = False,
        dry_run: bool = False,
        max_attempts: int = 3,
        timeout_seconds: int = 60
    ) -> Dict[str, Any]:
        """
        Executes a real agent repair lifecycle on a single benchmark task.
        Returns detailed telemetry, attempt histories, and explicit outcome.
        """
        if retry_strategy is None:
            retry_strategy = "flywheel_escalation" if memory_enabled else "naive_retry"

        run_id = f"eval-{task_def['task_id']}-{uuid.uuid4().hex[:8]}"
        start_time = time.perf_counter()
        temp_dir = Path(tempfile.mkdtemp(prefix=f"ouro_agenteval_{task_def['task_id']}_"))

        attempts_executed = 0
        verdict = "FAIL"
        outcome = "FAILED_REPAIR" if task_def.get("is_eligible", True) else "BLOCKED_BY_POLICY"
        error_detail: Optional[str] = None
        attempt_history: List[Dict[str, Any]] = []

        total_tokens_in: Optional[int] = None
        total_tokens_out: Optional[int] = None
        model_provider: str = "unknown"
        model_name: str = "unknown"

        phase_timings = {
            "planning_ms": 0,
            "coding_ms": 0,
            "evaluation_ms": 0,
            "total_ms": 0
        }

        # Check for dry run early exit
        if dry_run:
            shutil.rmtree(temp_dir, ignore_errors=True)
            return {
                "task_id": task_def["task_id"],
                "name": task_def["name"],
                "category": task_def["category"],
                "difficulty": task_def["difficulty"],
                "is_eligible": task_def.get("is_eligible", True),
                "is_adversarial": task_def.get("is_adversarial", False),
                "memory_enabled": memory_enabled,
                "dry_run": True,
                "verdict": "SKIPPED",
                "outcome": "NOT_RUN",
                "passed": False,
                "attempts_executed": 0,
                "duration_ms": 0,
                "error_detail": "Dry run requested; execution skipped."
            }

        try:
            # 1. Enforce Fail-Closed Sandbox Capability Check
            sandbox_status = await sandbox_detector.detect_capabilities()
            if not sandbox_status.get("can_execute", True):
                outcome = "INFRASTRUCTURE_ERROR"
                verdict = "ERROR"
                error_detail = f"Sandbox execution blocked: {sandbox_status.get('message', 'Runtime unavailable')}"
                return {
                    "task_id": task_def["task_id"],
                    "name": task_def["name"],
                    "category": task_def["category"],
                    "difficulty": task_def["difficulty"],
                    "is_eligible": task_def.get("is_eligible", True),
                    "is_adversarial": task_def.get("is_adversarial", False),
                    "memory_enabled": memory_enabled,
                    "verdict": verdict,
                    "outcome": outcome,
                    "passed": False,
                    "attempts_executed": 0,
                    "duration_ms": int((time.perf_counter() - start_time) * 1000),
                    "error_detail": error_detail
                }

            # 2. Scaffold Disposable Git Repository
            repo_dir = temp_dir / "repo"
            worktrees_dir = temp_dir / "worktrees"
            repo_dir.mkdir(parents=True)
            worktrees_dir.mkdir(parents=True)

            await run_safe_subprocess(["git", "init"], cwd=repo_dir)
            await run_safe_subprocess(["git", "config", "user.name", "AgentEvalRunner"], cwd=repo_dir)
            await run_safe_subprocess(["git", "config", "user.email", "eval@ouro.local"], cwd=repo_dir)
            (repo_dir / ".gitignore").write_text("__pycache__/\n*.py[cod]\n.pytest_cache/\n", encoding="utf-8")

            # Seed fixture files
            seed_files = task_def.get("seed_files", {})
            for rel_path, content in seed_files.items():
                target_p = repo_dir / rel_path
                target_p.parent.mkdir(parents=True, exist_ok=True)
                target_p.write_text(content, encoding="utf-8")

            await run_safe_subprocess(["git", "add", "-A"], cwd=repo_dir)
            await run_safe_subprocess(["git", "commit", "-m", "Initial defective fixture"], cwd=repo_dir)
            await run_safe_subprocess(["git", "branch", "-M", "main"], cwd=repo_dir)

            # 3. Create Candidate Worktree
            worktree_mgr = GitWorktreeManager(base_worktree_dir=str(worktrees_dir))
            worktree_path, cand_branch, _ = await worktree_mgr.create_worktree(repo_dir, task_def["task_id"])

            # 4. Setup in-memory SQLite database for FailureFlywheel
            engine = create_engine("sqlite:///:memory:")
            Base.metadata.create_all(bind=engine)
            SessionTest = sessionmaker(bind=engine)
            mem_db = SessionTest()

            # Handle adversarial task boundary rejection
            if task_def.get("is_adversarial"):
                attempts_executed = 1
                diff_parser = UnifiedDiffParser()
                is_safe, err_msg = diff_parser.validate_patch_boundaries(
                    diff_text=task_def["flawed_patch"],
                    allowed_files=[task_def["target_file"]]
                )
                if not is_safe:
                    verdict = "BLOCKED"
                    outcome = "BLOCKED_BY_POLICY"
                    attempt_history.append({
                        "attempt": 1,
                        "verdict": "BLOCKED",
                        "outcome": "BLOCKED_BY_POLICY",
                        "reason": err_msg
                    })
                else:
                    verdict = "FAIL"
                    outcome = "FAILED_REPAIR"

                mem_db.close()
                elapsed_ms = int((time.perf_counter() - start_time) * 1000)
                phase_timings["total_ms"] = elapsed_ms

                return {
                    "task_id": task_def["task_id"],
                    "name": task_def["name"],
                    "category": task_def["category"],
                    "difficulty": task_def["difficulty"],
                    "is_eligible": False,
                    "is_adversarial": True,
                    "memory_enabled": memory_enabled,
                    "verdict": verdict,
                    "outcome": outcome,
                    "passed": False,
                    "attempts_executed": attempts_executed,
                    "history": attempt_history,
                    "duration_ms": elapsed_ms,
                    "phase_timings": phase_timings,
                    "error_detail": redact_sensitive_strings(err_msg)
                }

            # 5. Production Multi-Agent Repair Loop
            runner = PytestRunner(default_timeout=25)
            evaluation_passed = False

            # Phase 1: Planning
            t_plan_start = time.perf_counter()
            plan = await planner_agent.create_plan(
                repo_id=task_def["task_id"],
                ticket={
                    "title": task_def["name"],
                    "problem_statement": task_def["problem_statement"],
                    "acceptance_criteria": [task_def["problem_statement"]],
                    "candidate_files": [task_def["target_file"]],
                    "relevant_graph_entities": []
                },
                force_mock=force_mock
            )
            phase_timings["planning_ms"] = int((time.perf_counter() - t_plan_start) * 1000)

            subtasks = plan.get("ordered_subtasks", [])
            target_subtask = subtasks[0] if subtasks else {
                "target_file": task_def["target_file"],
                "description": task_def["problem_statement"]
            }

            attempt = 1
            while attempt <= max_attempts and not evaluation_passed:
                attempts_executed = attempt
                attempt_meta: Dict[str, Any] = {"attempt": attempt}

                target_file_rel = target_subtask.get("target_file", task_def["target_file"]).replace("\\", "/")
                target_full_path = worktree_path / target_file_rel
                current_code = ""
                if target_full_path.exists():
                    current_code = target_full_path.read_text(encoding="utf-8", errors="replace")

                # Phase 2: Coding / Synthesis
                t_code_start = time.perf_counter()
                if attempt == 1 or retry_strategy == "naive_retry" or not memory_enabled:
                    code_prompt = coder_lead.prepare_coding_prompt(
                        subtask=target_subtask,
                        ticket={
                            "title": task_def["name"],
                            "acceptance_criteria": [task_def["problem_statement"]]
                        },
                        file_content=current_code
                    )
                    coder_res = await local_coder_agent.generate_patch(code_prompt, force_mock=force_mock)
                else:
                    repair_context = FailureFlywheel.get_repair_context(mem_db, task_def["task_id"])

                    # Strategy Escalation Check:
                    # If repeated semantic failures occurred, escalate to Planner within fixed attempt budget
                    is_repeated = repair_context.get("has_repeated_failure", False)
                    if is_repeated and attempt == max_attempts:
                        logger.info(f"Repeated failure signature detected for {task_def['task_id']} on attempt {attempt}. Escalating strategy to PlannerAgent.")
                        t_esc_start = time.perf_counter()
                        revised_plan = await planner_agent.escalate_plan(
                            repo_id=task_def["task_id"],
                            ticket={
                                "title": task_def["name"],
                                "problem_statement": task_def["problem_statement"],
                                "acceptance_criteria": [task_def["problem_statement"]],
                                "candidate_files": [task_def["target_file"]],
                                "relevant_graph_entities": []
                            },
                            failure_context=repair_context,
                            current_plan=plan,
                            force_mock=force_mock
                        )
                        phase_timings["planning_ms"] += int((time.perf_counter() - t_esc_start) * 1000)
                        if revised_plan.get("ordered_subtasks"):
                            target_subtask = revised_plan["ordered_subtasks"][0]
                            attempt_meta["escalated_plan"] = True
                            attempt_meta["revised_subtask"] = target_subtask.get("description")

                    coder_res = await repair_agent.synthesize_repair(
                        ticket={
                            "title": task_def["name"],
                            "strategy": target_subtask.get("description")
                        },
                        target_file=target_file_rel,
                        current_code=current_code,
                        failure_trajectory=repair_context,
                        force_mock=force_mock
                    )

                phase_timings["coding_ms"] += int((time.perf_counter() - t_code_start) * 1000)

                # Record model identity and token telemetry
                model_provider = coder_res.get("provider", "unknown")
                model_name = coder_res.get("model", "unknown")
                in_tok = coder_res.get("input_tokens")
                out_tok = coder_res.get("output_tokens")
                if in_tok is not None:
                    total_tokens_in = (total_tokens_in or 0) + in_tok
                if out_tok is not None:
                    total_tokens_out = (total_tokens_out or 0) + out_tok

                # Detect provider errors
                if coder_res.get("is_error"):
                    err_msg = coder_res.get("error_message", "Provider returned error")
                    verdict = "ERROR"
                    outcome = "PROVIDER_UNAVAILABLE"
                    error_detail = redact_sensitive_strings(err_msg)
                    attempt_meta["verdict"] = "ERROR"
                    attempt_meta["error"] = error_detail
                    attempt_history.append(attempt_meta)
                    break

                diff_text = coder_res.get("diff_text", "").strip()
                if not diff_text:
                    attempt_meta["verdict"] = "FAIL"
                    attempt_meta["reason"] = "Model generated empty or unparseable patch diff."
                    attempt_history.append(attempt_meta)
                    attempt += 1
                    continue

                diff_hash = hashlib.sha256(diff_text.encode("utf-8")).hexdigest()

                # Phase 3: Static AST and Boundary Validation
                static_check = DeterministicJudge.evaluate_patch_static(
                    diff_text=diff_text,
                    allowed_files=[task_def["target_file"]],
                    worktree_path=worktree_path
                )

                if static_check["verdict"] != "PASS":
                    verdict = "BLOCKED" if static_check["verdict"] == "BLOCKED" else "FAIL"
                    attempt_meta["verdict"] = verdict
                    attempt_meta["reason"] = static_check["reason"]
                    attempt_history.append(attempt_meta)

                    if memory_enabled:
                        f_ctx = static_check.get("failure_context")
                        if not f_ctx:
                            f_ctx = FailureContextNormalizer.from_static_policy(
                                rule_id=static_check.get("policy_rule_id", "static_policy"),
                                reason=static_check["reason"],
                                allowed_requirement=static_check.get("policy_requirement"),
                                target_file=task_def["target_file"]
                            ).to_dict()

                        FailureFlywheel.record_failure(
                            db=mem_db,
                            run_id=run_id,
                            ticket_id=task_def["task_id"],
                            attempt=attempt,
                            failed_tests=["StaticValidation"],
                            traceback_excerpt=static_check["reason"],
                            ast_diff=static_check.get("ast_analysis", {}),
                            patch_hash=diff_hash,
                            root_cause_hypothesis=static_check["reason"],
                            repair_hint=f"Policy constraint: {static_check.get('policy_requirement', 'Avoid prohibited calls/imports.')}",
                            provider=model_provider,
                            model=model_name,
                            failure_context=f_ctx
                        )
                    attempt += 1
                    continue

                # Phase 4: Apply Patch in Worktree
                applied_ok, apply_err = await worktree_mgr.apply_patch(worktree_path, diff_text)
                if not applied_ok:
                    attempt_meta["verdict"] = "FAIL"
                    attempt_meta["reason"] = f"Git apply failed: {apply_err}"
                    attempt_history.append(attempt_meta)

                    if memory_enabled:
                        f_ctx = FailureContextNormalizer.from_patch_error(
                            error_msg=apply_err,
                            target_file=target_file_rel
                        ).to_dict()

                        FailureFlywheel.record_failure(
                            db=mem_db,
                            run_id=run_id,
                            ticket_id=task_def["task_id"],
                            attempt=attempt,
                            failed_tests=["GitApplyError"],
                            traceback_excerpt=apply_err,
                            ast_diff={},
                            patch_hash=diff_hash,
                            root_cause_hypothesis="Diff hunk line context mismatch.",
                            repair_hint="Regenerate unified diff against current file lines.",
                            provider=model_provider,
                            model=model_name,
                            failure_context=f_ctx
                        )
                    attempt += 1
                    continue

                # Phase 5: Dynamic Acceptance and Regression Tests
                t_eval_start = time.perf_counter()

                acc_eval = await runner.run_tests(
                    working_dir=worktree_path,
                    test_path=task_def["acceptance_test"]
                )
                reg_eval = await runner.run_tests(
                    working_dir=worktree_path,
                    test_path=task_def["baseline_test"]
                )
                phase_timings["evaluation_ms"] += int((time.perf_counter() - t_eval_start) * 1000)

                acceptance_passed = acc_eval.get("passed", False)
                regression_passed = reg_eval.get("passed", False)

                attempt_meta["acceptance_passed"] = acceptance_passed
                attempt_meta["regression_passed"] = regression_passed

                if acc_eval.get("timed_out") or reg_eval.get("timed_out"):
                    verdict = "TIMED_OUT"
                    outcome = "TIMED_OUT"
                    attempt_meta["verdict"] = "TIMED_OUT"
                    attempt_history.append(attempt_meta)
                    break

                if acceptance_passed and regression_passed:
                    evaluation_passed = True
                    verdict = "PASS"
                    outcome = "PASSED_REPAIR"
                    attempt_meta["verdict"] = "PASS"
                    attempt_history.append(attempt_meta)
                    break
                else:
                    verdict = "FAIL"
                    outcome = "FAILED_REPAIR"
                    attempt_meta["verdict"] = "FAIL"
                    failures = acc_eval.get("failures", []) + reg_eval.get("failures", [])
                    attempt_meta["failures"] = failures
                    attempt_history.append(attempt_meta)

                    if memory_enabled:
                        failed_run = acc_eval if not acceptance_passed else reg_eval
                        f_ctx = failed_run.get("failure_context")
                        if not f_ctx:
                            stdout_txt = failed_run.get("stdout_excerpt", "")
                            stderr_txt = failed_run.get("stderr_excerpt", "")
                            f_ctx = FailureContextNormalizer.from_pytest_output(stdout_txt, stderr_txt, exit_code=1).to_dict()

                        failed_names = f_ctx.get("failed_test_nodes") or [f.get("test_name", "TestFailed") for f in failures] or [task_def["acceptance_test"]]
                        tb_excerpt = f_ctx.get("traceback_tail") or f_ctx.get("assertion_message") or failed_run.get("stdout_excerpt") or "Test assertion failed."

                        FailureFlywheel.record_failure(
                            db=mem_db,
                            run_id=run_id,
                            ticket_id=task_def["task_id"],
                            attempt=attempt,
                            failed_tests=failed_names,
                            traceback_excerpt=tb_excerpt,
                            ast_diff=static_check.get("ast_analysis", {}),
                            patch_hash=diff_hash,
                            root_cause_hypothesis=f"Agent patch failed verification: {tb_excerpt[:200]}",
                            repair_hint="Analyze assertion failure and rectify logic error.",
                            provider=model_provider,
                            model=model_name,
                            failure_context=f_ctx
                        )
                    attempt += 1

            elapsed_ms = int((time.perf_counter() - start_time) * 1000)
            phase_timings["total_ms"] = elapsed_ms
            mem_db.close()

            return {
                "task_id": task_def["task_id"],
                "name": task_def["name"],
                "category": task_def["category"],
                "difficulty": task_def["difficulty"],
                "is_eligible": True,
                "is_adversarial": False,
                "memory_enabled": memory_enabled,
                "retry_strategy": retry_strategy,
                "model_provider": model_provider,
                "model_name": model_name,
                "verdict": verdict,
                "outcome": outcome,
                "passed": verdict == "PASS",
                "attempts_executed": attempts_executed,
                "max_attempts": max_attempts,
                "tokens_in": total_tokens_in,
                "tokens_out": total_tokens_out,
                "phase_timings": phase_timings,
                "history": attempt_history,
                "duration_ms": elapsed_ms,
                "error_detail": redact_sensitive_strings(error_detail)
            }

        except Exception as exc:
            logger.error(f"Agent evaluation task failed: {exc}", exc_info=True)
            elapsed_ms = int((time.perf_counter() - start_time) * 1000)
            phase_timings["total_ms"] = elapsed_ms
            return {
                "task_id": task_def.get("task_id", "UNKNOWN"),
                "name": task_def.get("name", "Unknown"),
                "category": task_def.get("category", "unknown"),
                "difficulty": task_def.get("difficulty", "unknown"),
                "is_eligible": task_def.get("is_eligible", True),
                "is_adversarial": task_def.get("is_adversarial", False),
                "memory_enabled": memory_enabled,
                "model_provider": model_provider,
                "model_name": model_name,
                "verdict": "ERROR",
                "outcome": "INFRASTRUCTURE_ERROR",
                "passed": False,
                "attempts_executed": attempts_executed,
                "duration_ms": elapsed_ms,
                "error_detail": redact_sensitive_strings(str(exc))
            }
        finally:
            def _rm_readonly(func, p, _):
                import stat
                try:
                    os.chmod(p, stat.S_IWRITE)
                    func(p)
                except Exception:
                    pass
            try:
                shutil.rmtree(temp_dir, onerror=_rm_readonly)
            except Exception:
                shutil.rmtree(temp_dir, ignore_errors=True)

    @classmethod
    async def evaluate_suite(
        cls,
        tasks: Optional[List[Dict[str, Any]]] = None,
        task_ids: Optional[List[str]] = None,
        eligible_only: bool = False,
        security_only: bool = False,
        category: Optional[str] = None,
        memory_enabled: bool = True,
        retry_strategy: Optional[str] = None,
        force_mock: bool = False,
        dry_run: bool = False,
        max_attempts: int = 3
    ) -> Dict[str, Any]:
        """
        Executes sequential real-agent evaluations across selected benchmark tasks.
        Computes explicit aggregate metrics with documented denominators.
        """
        all_tasks = tasks or BENCHMARK_TASKS_V1

        if task_ids:
            pool = [t for t in all_tasks if t["task_id"] in task_ids]
        elif eligible_only:
            pool = [t for t in all_tasks if t.get("is_eligible", True)]
        elif security_only:
            pool = [t for t in all_tasks if t.get("is_adversarial", False)]
        else:
            pool = all_tasks

        if category:
            pool = [t for t in pool if t.get("category") == category]

        results = []
        total_duration = 0
        total_tok_in = 0
        total_tok_out = 0
        has_tokens = False

        for task in pool:
            task_res = await cls.evaluate_task(
                task_def=task,
                memory_enabled=memory_enabled,
                retry_strategy=retry_strategy,
                force_mock=force_mock,
                dry_run=dry_run,
                max_attempts=max_attempts
            )
            results.append(task_res)
            total_duration += task_res.get("duration_ms", 0)
            if task_res.get("tokens_in") is not None:
                total_tok_in += task_res["tokens_in"]
                has_tokens = True
            if task_res.get("tokens_out") is not None:
                total_tok_out += task_res["tokens_out"]
                has_tokens = True

        tasks_selected = len(pool)
        tasks_attempted = sum(1 for r in results if r.get("outcome") != "NOT_RUN")
        tasks_not_run = sum(1 for r in results if r.get("outcome") == "NOT_RUN")

        eligible_tasks = sum(1 for r in results if r.get("is_eligible", True))
        adversarial_tasks = sum(1 for r in results if r.get("is_adversarial", False))

        repairs_passed = sum(1 for r in results if r.get("outcome") == "PASSED_REPAIR")
        repairs_failed = sum(1 for r in results if r.get("outcome") == "FAILED_REPAIR")
        policy_blocked = sum(1 for r in results if r.get("outcome") == "BLOCKED_BY_POLICY")
        timed_out = sum(1 for r in results if r.get("outcome") == "TIMED_OUT")
        infra_failures = sum(1 for r in results if r.get("outcome") == "INFRASTRUCTURE_ERROR")
        provider_unavail = sum(1 for r in results if r.get("outcome") == "PROVIDER_UNAVAILABLE")

        # Explicit denominator calculations
        attempted_repair_rate = (repairs_passed / tasks_attempted) if tasks_attempted > 0 else None
        eligible_repair_rate = (repairs_passed / eligible_tasks) if eligible_tasks > 0 else None
        adversarial_block_rate = (policy_blocked / adversarial_tasks) if adversarial_tasks > 0 else None

        durations = [r["duration_ms"] for r in results if r.get("duration_ms", 0) > 0]
        durations.sort()
        p50 = durations[len(durations) // 2] if durations else 0

        outcome_dist = {
            "PASSED_REPAIR": repairs_passed,
            "FAILED_REPAIR": repairs_failed,
            "BLOCKED_BY_POLICY": policy_blocked,
            "TIMED_OUT": timed_out,
            "INFRASTRUCTURE_ERROR": infra_failures,
            "PROVIDER_UNAVAILABLE": provider_unavail,
            "NOT_RUN": tasks_not_run
        }

        return {
            "evaluation_engine": "OuroborosAgentRepairEvaluator",
            "benchmark_version": "v1.0.0",
            "memory_enabled": memory_enabled,
            "retry_strategy": retry_strategy or ("flywheel_escalation" if memory_enabled else "naive_retry"),
            "tasks_selected": tasks_selected,
            "tasks_attempted": tasks_attempted,
            "tasks_not_run": tasks_not_run,
            "eligible_tasks": eligible_tasks,
            "adversarial_tasks": adversarial_tasks,
            "repairs_passed": repairs_passed,
            "repairs_failed": repairs_failed,
            "policy_blocked": policy_blocked,
            "timed_out": timed_out,
            "infrastructure_failures": infra_failures,
            "provider_unavailable": provider_unavail,
            "attempted_repair_success_rate": round(attempted_repair_rate, 4) if attempted_repair_rate is not None else None,
            "eligible_repair_success_rate": round(eligible_repair_rate, 4) if eligible_repair_rate is not None else None,
            "adversarial_block_rate": round(adversarial_block_rate, 4) if adversarial_block_rate is not None else None,
            "outcome_distribution": outcome_dist,
            "total_tokens_in": total_tok_in if has_tokens else None,
            "total_tokens_out": total_tok_out if has_tokens else None,
            "median_duration_ms": p50,
            "total_duration_ms": total_duration,
            "task_results": results
        }
