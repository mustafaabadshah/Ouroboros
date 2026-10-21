"""
Project Ouroboros v0.11 - Reproducible Real Agent Evaluation CLI Runner
Evaluates AI agent repair performance against deterministic benchmark fixtures,
with support for multi-trial repetitions, Wilson score confidence intervals,
explicit naive-retry baseline ablation, fail-closed live execution gates,
enforced token/cost budgets, request pacing, and artifact collision protection.

Usage:
    # Safe offline mock evaluation (Default)
    python scripts/run_agent_eval.py --mock-agents --task-id BENCH-04

    # Strict live evaluation (Requires explicit --live, interactive authorization, and budget enforcement)
    python scripts/run_agent_eval.py --live --ablation --output artifacts/v0_11/phase6_live_llm_15tasks.json
"""

import sys
import os
import json
import time
import uuid
import random
import argparse
import asyncio
import tempfile
from pathlib import Path
from datetime import datetime, timezone
from typing import Dict, List, Any, Optional

repo_root = Path(__file__).resolve().parent.parent
backend_dir = repo_root / "backend"
sys.path.insert(0, str(backend_dir))
sys.path.insert(0, str(repo_root))

from app.evaluation.benchmark import BENCHMARK_TASKS_V1, validate_suite_consistency
from app.evaluation.agent_evaluator import AgentRepairEvaluator
from app.providers.router import model_router
from app.providers.budget import EvaluationBudgetController, ProviderErrorCategory
from app.schemas.eval_contract import (
    compute_wilson_score_interval,
    compute_percentiles,
    EvaluationOutcome,
    MemoryCondition
)
from scripts.run_benchmarks import print_agent_summary_table


def safe_atomic_write_json(target_path: Path, data: dict, allow_overwrite: bool = False):
    """
    Safely writes JSON data to target_path atomically using a temporary file in the
    same directory, preventing check-then-write race conditions and clobbering.
    """
    target_path = target_path.resolve()
    if target_path.exists() and not allow_overwrite:
        raise FileExistsError(f"Target destination already exists and overwrite is disabled: {target_path}")

    target_path.parent.mkdir(parents=True, exist_ok=True)
    temp_dir = target_path.parent
    tmp_file = tempfile.NamedTemporaryFile(
        dir=temp_dir,
        prefix=f".tmp_{target_path.stem}_",
        suffix=".json",
        delete=False,
        mode="w",
        encoding="utf-8"
    )
    try:
        tmp_file.write(json.dumps(data, indent=2))
        tmp_file.flush()
        os.fsync(tmp_file.fileno())
        tmp_file.close()
        os.replace(tmp_file.name, str(target_path))
    except Exception:
        if os.path.exists(tmp_file.name):
            try:
                os.remove(tmp_file.name)
            except Exception:
                pass
        raise


def summarize_repeated_trials(trials: List[Dict[str, Any]], condition_name: str) -> Dict[str, Any]:
    """Computes statistical summary across multiple repeated trials."""
    trial_count = len(trials)
    if trial_count == 0:
        return {}

    pass_rates = [t.get("eligible_repair_success_rate", 0.0) or 0.0 for t in trials]
    durations = [t.get("total_duration_ms", 0) for t in trials]
    p50s = [t.get("median_duration_ms", 0) for t in trials]

    total_eligible = sum(t.get("eligible_tasks", 0) for t in trials)
    total_passed = sum(t.get("repairs_passed", 0) for t in trials)
    pooled_rate = (total_passed / total_eligible) if total_eligible > 0 else 0.0
    ci_low, ci_high = compute_wilson_score_interval(total_passed, total_eligible)

    # Per-task outcome consistency matrix
    task_outcomes: Dict[str, List[bool]] = {}
    for t in trials:
        for res in t.get("task_results", []):
            tid = res["task_id"]
            if tid not in task_outcomes:
                task_outcomes[tid] = []
            task_outcomes[tid].append(res.get("passed", False))

    consistency = {}
    for tid, outcomes in task_outcomes.items():
        pass_cnt = sum(1 for o in outcomes if o)
        consistency[tid] = {
            "passed_trials": pass_cnt,
            "total_trials": len(outcomes),
            "pass_ratio": round(pass_cnt / len(outcomes), 3) if outcomes else 0.0,
            "is_deterministic": pass_cnt in (0, len(outcomes))
        }

    return {
        "condition": condition_name,
        "trial_count": trial_count,
        "pooled_pass_rate": round(pooled_rate, 4),
        "mean_pass_rate": round(sum(pass_rates) / trial_count, 4),
        "wilson_ci_95": {
            "lower": round(ci_low, 4),
            "upper": round(ci_high, 4)
        },
        "mean_duration_ms": int(sum(durations) / trial_count),
        "median_latency_p50_ms": int(sum(p50s) / trial_count),
        "task_consistency": consistency
    }


def analyze_paired_complete_pairs(
    trials_mem_on: List[Dict[str, Any]],
    trials_mem_off: List[Dict[str, Any]]
) -> Dict[str, Any]:
    """
    Separates genuine model repair outcomes from infrastructure/provider errors.
    Computes paired concordance strictly on complete pairs.
    """
    all_task_ids = set()
    for t in trials_mem_on + trials_mem_off:
        for r in t.get("task_results", []):
            all_task_ids.add(r["task_id"])

    complete_pairs = []
    incomplete_pairs = []

    err_outcomes = {
        "PROVIDER_UNAVAILABLE", "PROVIDER_AUTH_ERROR", "PROVIDER_RATE_LIMITED",
        "PROVIDER_TIMEOUT", "BUDGET_EXHAUSTED", "TOKEN_CEILING_EXCEEDED",
        "COST_CEILING_EXCEEDED", "INFRASTRUCTURE_ERROR", "NOT_RUN"
    }

    for tid in sorted(all_task_ids):
        res_on = next((r for t in trials_mem_on for r in t.get("task_results", []) if r["task_id"] == tid), None)
        res_off = next((r for t in trials_mem_off for r in t.get("task_results", []) if r["task_id"] == tid), None)

        if not res_on or not res_off:
            incomplete_pairs.append({
                "task_id": tid,
                "reason": "Missing observation in one condition."
            })
            continue

        out_on = res_on.get("outcome")
        out_off = res_off.get("outcome")

        if out_on in err_outcomes or out_off in err_outcomes:
            incomplete_pairs.append({
                "task_id": tid,
                "reason": f"Provider/Infrastructure abort (flywheel={out_on}, naive={out_off})"
            })
            continue

        # Complete pair
        p_on = bool(res_on.get("passed", False))
        p_off = bool(res_off.get("passed", False))
        complete_pairs.append({
            "task_id": tid,
            "flywheel_passed": p_on,
            "naive_passed": p_off
        })

    # Concordance matrix on clean pairs
    a = sum(1 for p in complete_pairs if p["flywheel_passed"] and p["naive_passed"])
    b = sum(1 for p in complete_pairs if p["flywheel_passed"] and not p["naive_passed"])
    c = sum(1 for p in complete_pairs if not p["flywheel_passed"] and p["naive_passed"])
    d = sum(1 for p in complete_pairs if not p["flywheel_passed"] and not p["naive_passed"])

    return {
        "total_paired_tasks_started": len(all_task_ids),
        "complete_pairs_count": len(complete_pairs),
        "incomplete_pairs_count": len(incomplete_pairs),
        "incomplete_pairs_detail": incomplete_pairs,
        "concordance_matrix": {
            "mutual_pass_a": a,
            "flywheel_only_win_b": b,
            "naive_only_win_c": c,
            "mutual_fail_d": d
        }
    }


async def main():
    parser = argparse.ArgumentParser(description="Ouroboros Real Agent Evaluation Runner (v0.11)")
    parser.add_argument("--task-id", type=str, help="Execute single benchmark task by ID (e.g. BENCH-04)")
    parser.add_argument("--eligible-only", action="store_true", help="Run only eligible repair tasks (skip adversarial)")
    parser.add_argument("--security-only", action="store_true", help="Run only adversarial security evaluation tasks")
    parser.add_argument("--category", type=str, help="Filter tasks by category (e.g. boundary, syntax, state)")
    parser.add_argument("--repeat", type=int, default=1, help="Number of repetition trials (default: 1)")
    parser.add_argument("--seed", type=int, default=None, help="Deterministic random seed")
    parser.add_argument("--memory-enabled", action="store_true", help="Run with FailureFlywheel memory enabled")
    parser.add_argument("--naive-retry", action="store_true", help="Run with Naive Retry baseline (no failure context)")
    parser.add_argument("--memory-disabled", action="store_true", help="Run with memory disabled")
    parser.add_argument("--ablation", action="store_true", help="Run matched ablation study (Memory Enabled vs Naive Retry)")
    parser.add_argument("--max-attempts", type=int, default=3, help="Maximum attempts per task budget (default: 3)")
    parser.add_argument("--dry-run", action="store_true", help="Dry run without invoking models or modifying workspaces")

    # Explicit provider selection & fail-closed flags
    parser.add_argument("--live", action="store_true", help="Explicitly request live remote model evaluation (Groq). Requires interactive confirmation.")
    parser.add_argument("--mock-agents", action="store_true", help="Explicitly request offline mock agent evaluation (safe default).")

    # Output artifact safety
    parser.add_argument("--output", type=str, default=None, help="Output path for machine-readable JSON report")
    parser.add_argument("--overwrite", action="store_true", help="Allow overwriting target output file if it already exists.")
    parser.add_argument("--export-ablation-report", action="store_true", help="Explicitly export dedicated memory ablation report (protects artifacts/v0_11/memory_ablation.json from silent overwrite).")

    # Budget & Pacing ceilings
    parser.add_argument("--max-requests", type=int, default=120, help="Maximum model requests permitted across evaluation run.")
    parser.add_argument("--max-tokens-ceiling", type=int, default=60000, help="Hard total token ceiling across evaluation run (default: 60,000).")
    parser.add_argument("--max-cost-ceiling", type=float, default=0.10, help="Hard USD spend ceiling across evaluation run (default: $0.10).")
    parser.add_argument("--pacing-delay", type=float, default=3.0, help="Minimum interval in seconds between outbound model requests (default: 3.0s).")

    args = parser.parse_args()

    # 1. Mode Validation
    if args.live and args.mock_agents:
        sys.stderr.write("ERROR: Conflicting flags --live and --mock-agents both provided. Choose exactly one.\n")
        sys.exit(1)

    if not args.live and not args.mock_agents:
        args.mock_agents = True
        print("[Notice] Neither --live nor --mock-agents specified. Defaulting to safe offline mock mode.")

    if args.seed is not None:
        random.seed(args.seed)

    suite_errors = validate_suite_consistency(BENCHMARK_TASKS_V1)
    if suite_errors:
        sys.stderr.write("Suite Configuration Errors:\n")
        for err in suite_errors:
            sys.stderr.write(f"  - {err}\n")
        sys.exit(1)

    task_ids = [t.strip() for t in args.task_id.split(",") if t.strip()] if args.task_id else None

    # Determine condition mode
    run_ablation = args.ablation or (not args.memory_enabled and not args.naive_retry and not args.memory_disabled)
    effective_eligible_only = args.eligible_only or (run_ablation and not args.security_only and not args.task_id)

    # 2. Output Path Validation & Collision Protection
    v011_artifacts_dir = (repo_root / "artifacts" / "v0_11").resolve()
    v011_artifacts_dir.mkdir(parents=True, exist_ok=True)
    out_file = (Path(args.output).resolve()) if args.output else (v011_artifacts_dir / "repeated_evaluation.json").resolve()

    # Prevent escaping workspace
    try:
        out_file.relative_to(repo_root)
    except ValueError:
        sys.stderr.write(f"ERROR: Target output path escapes repository root: {out_file}\n")
        sys.exit(1)

    # Collision pre-flight check
    if out_file.exists() and not args.overwrite:
        sys.stderr.write(
            f"ERROR: Target output file already exists: {out_file}\n"
            f"To prevent accidental artifact loss, use --overwrite to replace it.\n"
        )
        sys.exit(1)

    # Dedicated ablation export check
    ablation_out = None
    if args.export_ablation_report:
        ablation_out = (v011_artifacts_dir / "memory_ablation.json").resolve()
        if ablation_out.exists() and not args.overwrite:
            sys.stderr.write(
                f"ERROR: Dedicated ablation export target already exists: {ablation_out}\n"
                f"Use --overwrite to allow replacing it.\n"
            )
            sys.exit(1)

    # 3. Interactive Live Execution Gate
    all_tasks = BENCHMARK_TASKS_V1
    if task_ids:
        pool = [t for t in all_tasks if t["task_id"] in task_ids]
    elif effective_eligible_only:
        pool = [t for t in all_tasks if t.get("is_eligible", True)]
    elif args.security_only:
        pool = [t for t in all_tasks if t.get("is_adversarial", False)]
    else:
        pool = all_tasks
    if args.category:
        pool = [t for t in pool if t.get("category") == args.category]

    condition_count = 2 if run_ablation else 1
    max_possible_calls = len(pool) * condition_count * args.max_attempts

    if args.live:
        banner = (
            "\n" + "=" * 80 + "\n"
            "[CRITICAL] OUROBOROS LIVE LLM EVALUATION AUTHORIZATION REQUIRED\n"
            "=" * 80 + "\n"
            f"Provider:             Groq Remote API\n"
            f"Model:                qwen/qwen3.8-27b\n"
            f"Selected Tasks:       {len(pool)} tasks ({', '.join(t['task_id'] for t in pool)})\n"
            f"Strategy Conditions:  {'Ablation (Flywheel vs Naive Retry)' if run_ablation else ('Flywheel' if args.memory_enabled else 'Naive Retry')}\n"
            f"Max Possible Calls:   {max_possible_calls} (budget cap: {args.max_requests})\n"
            f"Token Ceiling:        {args.max_tokens_ceiling} tokens (pre-dispatch reservation)\n"
            f"Cost Ceiling:         ${args.max_cost_ceiling:.2f} USD (pre-dispatch reservation)\n"
            f"Request Pacing:       {args.pacing_delay}s minimum inter-request delay\n"
            f"Target Output:        {out_file}\n\n"
            "WARNING: External API calls will be dispatched. Quota will be consumed.\n"
            "=" * 80 + "\n"
        )
        print(banner)

        is_interactive = sys.stdin.isatty()
        if is_interactive:
            try:
                user_resp = input("Type 'yes' to authorize live execution: ").strip().lower()
            except (EOFError, KeyboardInterrupt):
                user_resp = "no"

            if user_resp != "yes":
                print("\n[Gate] Live execution authorization DECLINED by user. Aborting before any API calls.")
                sys.exit(2)
            print("[Gate] Authorization GRANTED. Initiating live evaluation.\n")
        else:
            # Non-interactive CI environment check
            auth_token = os.environ.get("OUROBOROS_LIVE_AUTH", "")
            if auth_token != "I_CONFIRM_LIVE_API_CALLS":
                sys.stderr.write(
                    "ERROR: Live execution in non-interactive environment requires explicit environment authorization:\n"
                    "  OUROBOROS_LIVE_AUTH=I_CONFIRM_LIVE_API_CALLS\n"
                    "Aborting without making any API calls.\n"
                )
                sys.exit(2)
            print("[Gate] Non-interactive environment authorization verified via OUROBOROS_LIVE_AUTH.")

    # 4. Configure Central Budget & Pacing Controller
    budget_controller = EvaluationBudgetController(
        max_requests=args.max_requests,
        max_tokens=args.max_tokens_ceiling,
        max_cost_usd=args.max_cost_ceiling,
        min_pacing_seconds=args.pacing_delay if args.live else 0.0
    )
    model_router.set_budget_controller(budget_controller)
    model_router.set_mode("live" if args.live else "mock")

    print("=" * 80)
    print("PROJECT OUROBOROS REPRODUCIBLE AGENT EVALUATION ENGINE (v0.11)")
    print(f"Execution Mode: {'DRY RUN' if args.dry_run else ('STRICT LIVE (Groq Cloud)' if args.live else 'MOCK AGENTS (Offline)')}")
    print(f"Repetitions: {args.repeat} trials | Max Attempts Budget: {args.max_attempts}")
    print(f"Condition: {'Ablation (Memory vs Naive Retry)' if run_ablation else ('Memory Enabled' if args.memory_enabled else 'Naive Retry')}")
    print(f"Filter: task_id={args.task_id}, eligible_only={effective_eligible_only}, security_only={args.security_only}, category={args.category}")
    print(f"Enforced Limits: Max Requests={args.max_requests}, Token Ceiling={args.max_tokens_ceiling}, Cost Ceiling=${args.max_cost_ceiling:.2f}")
    print("=" * 80)

    trials_mem_on: List[Dict[str, Any]] = []
    trials_mem_off: List[Dict[str, Any]] = []

    try:
        for trial in range(1, args.repeat + 1):
            trial_id = f"trial-{trial}-{uuid.uuid4().hex[:6]}"
            if args.repeat > 1:
                print(f"\n>>> REPETITION TRIAL {trial} of {args.repeat} [{trial_id}] <<<")

            if run_ablation or args.memory_enabled:
                print(f"\n[Trial {trial}] Running Condition: MEMORY_ENABLED (Flywheel + Escalation)")
                res_on = await AgentRepairEvaluator.evaluate_suite(
                    task_ids=task_ids,
                    eligible_only=effective_eligible_only,
                    security_only=args.security_only,
                    category=args.category,
                    memory_enabled=True,
                    retry_strategy="flywheel_escalation",
                    force_mock=args.mock_agents,
                    dry_run=args.dry_run,
                    max_attempts=args.max_attempts
                )
                res_on["trial_index"] = trial
                res_on["trial_id"] = trial_id
                trials_mem_on.append(res_on)
                print_agent_summary_table(f"Trial {trial} - Memory ENABLED", res_on)

            if run_ablation or args.naive_retry or args.memory_disabled:
                strat_name = "naive_retry" if (args.naive_retry or run_ablation) else "memory_disabled"
                print(f"\n[Trial {trial}] Running Baseline Condition: NAIVE_RETRY (No Diagnostic History)")
                res_off = await AgentRepairEvaluator.evaluate_suite(
                    task_ids=task_ids,
                    eligible_only=effective_eligible_only,
                    security_only=args.security_only,
                    category=args.category,
                    memory_enabled=False,
                    retry_strategy=strat_name,
                    force_mock=args.mock_agents,
                    dry_run=args.dry_run,
                    max_attempts=args.max_attempts
                )
                res_off["trial_index"] = trial
                res_off["trial_id"] = trial_id
                trials_mem_off.append(res_off)
                print_agent_summary_table(f"Trial {trial} - Naive Retry BASELINE", res_off)

            # Checkpoint intermediate results after each trial to guarantee zero loss
            checkpoint_data = {
                "checkpoint_timestamp": datetime.now(timezone.utc).isoformat(),
                "completed_trials": trial,
                "total_planned_trials": args.repeat,
                "trials_memory_enabled": trials_mem_on,
                "trials_baseline": trials_mem_off,
                "budget_summary": budget_controller.get_summary()
            }
            checkpoint_path = v011_artifacts_dir / f"eval_checkpoint_trial_{trial}.json"
            safe_atomic_write_json(checkpoint_path, checkpoint_data, allow_overwrite=True)

    except (KeyboardInterrupt, Exception) as exc:
        print(f"\n[ABORT WARNING] Evaluation interrupted: {exc}")
        partial_report = {
            "schema_version": "v0.11.0",
            "evaluation_type": "partial_evaluation_abort",
            "interrupted_timestamp_utc": datetime.now(timezone.utc).isoformat(),
            "abort_reason": str(exc),
            "trials_memory_enabled": trials_mem_on,
            "trials_baseline": trials_mem_off,
            "budget_summary": budget_controller.get_summary()
        }
        partial_out = out_file.parent / f"{out_file.stem}_partial.json"
        safe_atomic_write_json(partial_out, partial_report, allow_overwrite=True)
        print(f"Preserved partial evaluation records safely to: {partial_out}")
        raise

    # Build final statistical report
    summary_on = summarize_repeated_trials(trials_mem_on, "MEMORY_ENABLED") if trials_mem_on else None
    summary_off = summarize_repeated_trials(trials_mem_off, "NAIVE_RETRY") if trials_mem_off else None

    paired_comparison = None
    if summary_on and summary_off:
        pass_delta = summary_on["pooled_pass_rate"] - summary_off["pooled_pass_rate"]
        lat_delta = summary_on["median_latency_p50_ms"] - summary_off["median_latency_p50_ms"]
        paired_analysis = analyze_paired_complete_pairs(trials_mem_on, trials_mem_off)

        paired_comparison = {
            "eligible_repair_pass_rate_delta": round(pass_delta, 4),
            "median_latency_delta_ms": lat_delta,
            "paired_analysis": paired_analysis,
            "statistical_interpretation": (
                f"Memory Enabled achieved {summary_on['pooled_pass_rate']*100:.1f}% vs "
                f"Naive Retry {summary_off['pooled_pass_rate']*100:.1f}% across {args.repeat} trials "
                f"(Δ = {pass_delta*100:+.1f} percentage points, 95% Wilson CI: [{summary_on['wilson_ci_95']['lower']:.3f}, {summary_on['wilson_ci_95']['upper']:.3f}]). "
                f"Complete pairs evaluated: {paired_analysis['complete_pairs_count']}/{paired_analysis['total_paired_tasks_started']}."
            )
        }

    final_report = {
        "schema_version": "v0.11.0",
        "evaluation_type": "repeated_agent_evaluation",
        "benchmark_suite": "ouroboros_benchmark",
        "benchmark_version": "v1.0.0",
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "configuration": {
            "task_id_filter": args.task_id,
            "eligible_only": effective_eligible_only,
            "security_only": args.security_only,
            "category_filter": args.category,
            "repeat_trials": args.repeat,
            "seed": args.seed,
            "max_attempts": args.max_attempts,
            "ablation_mode": run_ablation,
            "dry_run": args.dry_run,
            "live_mode": args.live,
            "mock_agents": args.mock_agents,
            "budget_enforced": {
                "max_requests": args.max_requests,
                "token_ceiling": args.max_tokens_ceiling,
                "cost_ceiling_usd": args.max_cost_ceiling,
                "pacing_delay_seconds": args.pacing_delay
            }
        },
        "budget_accounting": budget_controller.get_summary(),
        "statistical_summary": {
            "memory_enabled": summary_on,
            "naive_retry_baseline": summary_off,
            "paired_comparison": paired_comparison
        },
        "raw_trials": {
            "memory_enabled_trials": trials_mem_on,
            "baseline_trials": trials_mem_off
        }
    }

    # 5. Safe Atomic Report Delivery
    safe_atomic_write_json(out_file, final_report, allow_overwrite=args.overwrite)
    print(f"\nSaved versioned reproducible evaluation report to: {out_file}")

    # Dedicated memory ablation export ONLY if explicitly requested
    if args.export_ablation_report and ablation_out:
        safe_atomic_write_json(ablation_out, final_report, allow_overwrite=args.overwrite)
        print(f"Saved dedicated memory ablation export to: {ablation_out}")

    # Archive immutable timestamped record with collision handling
    timestamp_slug = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    eval_dir = repo_root / "artifacts" / "evaluations" / f"{timestamp_slug}_agent_eval"
    if eval_dir.exists():
        eval_dir = repo_root / "artifacts" / "evaluations" / f"{timestamp_slug}_{uuid.uuid4().hex[:6]}_agent_eval"
    eval_dir.mkdir(parents=True, exist_ok=True)
    immutable_file = eval_dir / "agent_eval_run.json"
    safe_atomic_write_json(immutable_file, final_report, allow_overwrite=False)
    print(f"Archived immutable evaluation record to: {immutable_file}")

    # Gracefully flush and shut down telemetry buffer if active
    try:
        from app.observability.phoenix_service import phoenix_service
        phoenix_service.flush(timeout_ms=3000)
        phoenix_service.shutdown(timeout_ms=1000)
    except Exception:
        pass

    print("=" * 80)


if __name__ == "__main__":
    asyncio.run(main())
