"""
Project Ouroboros v0.11 - Reproducible Real Agent Evaluation CLI Runner
Evaluates actual AI agent repair performance against deterministic benchmark fixtures,
with support for multi-trial repetitions, Wilson score confidence intervals,
explicit naive-retry baseline ablation, and intermediate trial checkpointing.

Usage:
    python scripts/run_agent_eval.py [--task-id <ID>] [--eligible-only] [--category <CAT>]
                                     [--repeat <N>] [--memory-enabled | --naive-retry | --memory-disabled | --ablation]
                                     [--dry-run] [--mock-agents] [--output <PATH>] [--seed <INT>]
"""

import sys
import os
import json
import time
import uuid
import random
import argparse
import asyncio
from pathlib import Path
from datetime import datetime, timezone
from typing import Dict, List, Any, Optional

repo_root = Path(__file__).resolve().parent.parent
backend_dir = repo_root / "backend"
sys.path.insert(0, str(backend_dir))
sys.path.insert(0, str(repo_root))

from app.evaluation.benchmark import BENCHMARK_TASKS_V1, validate_suite_consistency
from app.evaluation.agent_evaluator import AgentRepairEvaluator
from app.schemas.eval_contract import (
    compute_wilson_score_interval,
    compute_percentiles,
    EvaluationOutcome,
    MemoryCondition
)
from scripts.run_benchmarks import print_agent_summary_table


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

    consistency: Dict[str, Dict[str, Any]] = {}
    for tid, passes in task_outcomes.items():
        consistency[tid] = {
            "trials_passed": sum(1 for p in passes if p),
            "total_trials": len(passes),
            "pass_ratio": sum(1 for p in passes if p) / len(passes) if passes else 0.0,
            "consistent": len(set(passes)) <= 1
        }

    return {
        "condition": condition_name,
        "trials_count": trial_count,
        "trial_pass_rates": pass_rates,
        "mean_pass_rate": sum(pass_rates) / trial_count,
        "pooled_pass_rate": round(pooled_rate, 4),
        "wilson_ci_95": {
            "lower": round(ci_low, 4),
            "upper": round(ci_high, 4)
        },
        "mean_duration_ms": int(sum(durations) / trial_count),
        "median_latency_p50_ms": int(sum(p50s) / trial_count),
        "task_consistency": consistency
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
    parser.add_argument("--mock-agents", action="store_true", help="Use deterministic mock provider for testing")
    parser.add_argument("--output", type=str, default=None, help="Output path for machine-readable JSON report")

    args = parser.parse_args()

    if args.seed is not None:
        random.seed(args.seed)

    suite_errors = validate_suite_consistency(BENCHMARK_TASKS_V1)
    if suite_errors:
        print("Suite Configuration Errors:")
        for err in suite_errors:
            print(f"  - {err}")
        sys.exit(1)

    task_ids = [args.task_id] if args.task_id else None

    # Determine mode
    run_ablation = args.ablation or (not args.memory_enabled and not args.naive_retry and not args.memory_disabled)

    v011_artifacts_dir = repo_root / "artifacts" / "v0_11"
    v011_artifacts_dir.mkdir(parents=True, exist_ok=True)
    out_file = Path(args.output) if args.output else v011_artifacts_dir / "repeated_evaluation.json"

    print("=" * 80)
    print("PROJECT OUROBOROS REPRODUCIBLE AGENT EVALUATION ENGINE (v0.11)")
    print(f"Execution Mode: {'DRY RUN' if args.dry_run else ('MOCK AGENTS' if args.mock_agents else 'LIVE PRODUCTION PIPELINE')}")
    print(f"Repetitions: {args.repeat} trials | Max Attempts Budget: {args.max_attempts}")
    print(f"Condition: {'Ablation (Memory vs Naive Retry)' if run_ablation else ('Memory Enabled' if args.memory_enabled else 'Naive Retry')}")
    print(f"Filter: task_id={args.task_id}, eligible_only={args.eligible_only}, security_only={args.security_only}, category={args.category}")
    print("=" * 80)

    trials_mem_on: List[Dict[str, Any]] = []
    trials_mem_off: List[Dict[str, Any]] = []

    for trial in range(1, args.repeat + 1):
        trial_id = f"trial-{trial}-{uuid.uuid4().hex[:6]}"
        if args.repeat > 1:
            print(f"\n>>> REPETITION TRIAL {trial} of {args.repeat} [{trial_id}] <<<")

        if run_ablation or args.memory_enabled:
            print(f"\n[Trial {trial}] Running Condition: MEMORY_ENABLED (Flywheel + Escalation)")
            res_on = await AgentRepairEvaluator.evaluate_suite(
                task_ids=task_ids,
                eligible_only=args.eligible_only,
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
            strat_name = "naive_retry" if args.naive_retry else "memory_disabled"
            print(f"\n[Trial {trial}] Running Baseline Condition: NAIVE_RETRY (No Diagnostic History)")
            res_off = await AgentRepairEvaluator.evaluate_suite(
                task_ids=task_ids,
                eligible_only=args.eligible_only,
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
            "trials_baseline": trials_mem_off
        }
        checkpoint_path = v011_artifacts_dir / f"eval_checkpoint_trial_{trial}.json"
        checkpoint_path.write_text(json.dumps(checkpoint_data, indent=2), encoding="utf-8")

    # Build final statistical report
    summary_on = summarize_repeated_trials(trials_mem_on, "MEMORY_ENABLED") if trials_mem_on else None
    summary_off = summarize_repeated_trials(trials_mem_off, "NAIVE_RETRY") if trials_mem_off else None

    paired_comparison = None
    if summary_on and summary_off:
        pass_delta = summary_on["pooled_pass_rate"] - summary_off["pooled_pass_rate"]
        lat_delta = summary_on["median_latency_p50_ms"] - summary_off["median_latency_p50_ms"]
        paired_comparison = {
            "eligible_repair_pass_rate_delta": round(pass_delta, 4),
            "median_latency_delta_ms": lat_delta,
            "statistical_interpretation": (
                f"Memory Enabled achieved {summary_on['pooled_pass_rate']*100:.1f}% vs "
                f"Naive Retry {summary_off['pooled_pass_rate']*100:.1f}% across {args.repeat} trials "
                f"(Δ = {pass_delta*100:+.1f} percentage points, 95% Wilson CI: [{summary_on['wilson_ci_95']['lower']:.3f}, {summary_on['wilson_ci_95']['upper']:.3f}])."
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
            "eligible_only": args.eligible_only,
            "security_only": args.security_only,
            "category_filter": args.category,
            "repeat_trials": args.repeat,
            "seed": args.seed,
            "max_attempts": args.max_attempts,
            "ablation_mode": run_ablation,
            "dry_run": args.dry_run,
            "mock_agents": args.mock_agents
        },
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

    out_file.write_text(json.dumps(final_report, indent=2), encoding="utf-8")
    print(f"\nSaved versioned reproducible evaluation report to: {out_file}")

    # Also save dedicated memory ablation report if run in ablation mode
    if run_ablation:
        ablation_out = v011_artifacts_dir / "memory_ablation.json"
        ablation_out.write_text(json.dumps(final_report, indent=2), encoding="utf-8")
        print(f"Saved memory ablation report to: {ablation_out}")

    print("=" * 80)


if __name__ == "__main__":
    asyncio.run(main())
