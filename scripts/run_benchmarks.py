"""
Project Ouroboros - Versioned Benchmark Suite CLI & Evaluation Harness
Usage:
    python scripts/run_benchmarks.py [--task-id <ID>] [--eligible-only] [--security-only]
                                     [--category <CAT>] [--validate-fixtures] [--repeat <N>]
                                     [--memory-enabled | --memory-disabled | --ablation]
                                     [--output <PATH>]
"""

import sys
import os
import json
import time
import argparse
import asyncio
from pathlib import Path
from typing import Dict, List, Any, Optional

# Add backend directory to path
backend_dir = Path(__file__).resolve().parent.parent / "backend"
sys.path.insert(0, str(backend_dir))

from app.evaluation.benchmark import BenchmarkHarness, BENCHMARK_TASKS_V1, validate_suite_consistency
from app.evaluation.agent_evaluator import AgentRepairEvaluator


def format_table_row(cols: List[str], widths: List[int]) -> str:
    return " | ".join(col.ljust(widths[i]) for i, col in enumerate(cols))


def print_agent_summary_table(run_name: str, suite_result: Dict[str, Any]):
    print(f"\n{'=' * 80}")
    print(f"OUROBOROS AGENT REPAIR EVALUATION: {run_name.upper()}")
    print("=" * 80)
    widths = [10, 32, 20, 8, 18, 8, 14, 9]
    headers = ["Task ID", "Task Name", "Category", "Verdict", "Outcome", "Attempts", "Tokens (In/Out)", "Duration"]
    separator = "-+-".join("-" * w for w in widths)

    print(format_table_row(headers, widths))
    print(separator)

    for task_res in suite_result.get("task_results", []):
        tok_str = f"{task_res.get('tokens_in') or '?'}/{task_res.get('tokens_out') or '?'}"
        row = [
            task_res["task_id"],
            task_res["name"][:32],
            task_res["category"][:20],
            task_res["verdict"],
            task_res.get("outcome", "N/A"),
            str(task_res.get("attempts_executed", 0)),
            tok_str,
            f"{task_res.get('duration_ms', 0)}ms"
        ]
        print(format_table_row(row, widths))

    print(separator)
    sel = suite_result['tasks_selected']
    att = suite_result['tasks_attempted']
    not_run = suite_result['tasks_not_run']
    passed = suite_result['repairs_passed']
    failed = suite_result['repairs_failed']
    blocked = suite_result['policy_blocked']
    timeouts = suite_result['timed_out']
    infra = suite_result['infrastructure_failures']
    unavail = suite_result['provider_unavailable']

    elig = suite_result['eligible_tasks']
    adv = suite_result['adversarial_tasks']

    att_rate_str = f"{suite_result['attempted_repair_success_rate'] * 100:.1f}% ({passed}/{att})" if suite_result.get('attempted_repair_success_rate') is not None else "N/A (0 attempted)"
    elig_rate_str = f"{suite_result['eligible_repair_success_rate'] * 100:.1f}% ({passed}/{elig})" if suite_result.get('eligible_repair_success_rate') is not None else "N/A (0 eligible)"
    adv_rate_str = f"{suite_result['adversarial_block_rate'] * 100:.1f}% ({blocked}/{adv})" if suite_result.get('adversarial_block_rate') is not None else "N/A (0 adversarial)"

    print(f"Tasks Selected:           {sel} (Eligible: {elig}, Adversarial: {adv})")
    print(f"Tasks Attempted:          {att} | Tasks Not Run: {not_run}")
    print(f"Repairs Passed:           {passed} | Repairs Failed: {failed}")
    print(f"Policy-Blocked Tasks:     {blocked}")
    print(f"Timeouts:                 {timeouts} | Infrastructure Failures: {infra} | Provider-Unavailable: {unavail}")
    print("-" * 80)
    print(f"Attempted Repair Rate:    {att_rate_str}  [Formula: repairs_passed / tasks_attempted]")
    print(f"Eligible Repair Rate:     {elig_rate_str}  [Formula: repairs_passed / eligible_tasks]")
    print(f"Adversarial Block Rate:   {adv_rate_str}  [Formula: policy_blocked / adversarial_tasks]")
    tok_in = suite_result.get('total_tokens_in') or 'N/A'
    tok_out = suite_result.get('total_tokens_out') or 'N/A'
    print(f"Total Tokens:             In: {tok_in} | Out: {tok_out}")
    print(f"Median Task Latency:      {suite_result['median_duration_ms']}ms | Total Runtime: {suite_result['total_duration_ms']}ms")
    print("=" * 80)


def print_summary_table(run_name: str, suite_result: Dict[str, Any]):
    print(f"\n--- {run_name} Results ---")
    widths = [10, 38, 26, 8, 18, 8, 10]
    headers = ["Task ID", "Task Name", "Category", "Verdict", "Outcome", "Attempts", "Duration"]
    separator = "-+-".join("-" * w for w in widths)

    print(format_table_row(headers, widths))
    print(separator)

    for task_res in suite_result.get("task_results", []):
        row = [
            task_res["task_id"],
            task_res["name"][:38],
            task_res["category"][:26],
            task_res["verdict"],
            task_res.get("outcome", "N/A"),
            str(task_res["attempts"]),
            f"{task_res['duration_ms']}ms"
        ]
        print(format_table_row(row, widths))

    print(separator)
    tot = suite_result['total_tasks']
    elig = suite_result['eligible_tasks']
    elig_pass = suite_result['eligible_passed_tasks']
    adv = suite_result['adversarial_tasks']
    adv_block = suite_result['adversarial_blocked_tasks']
    timeouts = suite_result['timed_out_tasks']
    infra_errs = suite_result['infrastructure_failures']

    elig_rate_str = f"{suite_result['eligible_repair_success_rate'] * 100:.1f}% ({elig_pass}/{elig})" if suite_result.get('eligible_repair_success_rate') is not None else "N/A (no eligible tasks)"
    adv_rate_str = f"{suite_result['adversarial_block_rate'] * 100:.1f}% ({adv_block}/{adv})" if suite_result.get('adversarial_block_rate') is not None else "N/A (no adversarial tasks)"

    print(f"Total Tasks: {tot} | Eligible: {elig} | Adversarial: {adv}")
    print(f"Eligible Repair Success Rate: {elig_rate_str}")
    print(f"Adversarial Security Block Rate: {adv_rate_str}")
    print(f"Timed-out: {timeouts} | Infrastructure Failures: {infra_errs}")
    print(f"Median Task Latency: {suite_result['median_duration_ms']}ms | Total Runtime: {suite_result['total_duration_ms']}ms")


async def run_fixture_validation(task_ids: Optional[List[str]] = None):
    print("=" * 80)
    print("EXECUTING DETERMINISTIC FIXTURE VALIDATION MODE")
    print("Verifies: (1) baseline test passes, (2) initial defect reproduced, (3) reference repair passes")
    print("=" * 80)

    tasks = BENCHMARK_TASKS_V1
    if task_ids:
        tasks = [t for t in tasks if t["task_id"] in task_ids]

    reports = await BenchmarkHarness.validate_fixtures(tasks=tasks)
    widths = [10, 40, 10, 10, 10, 8]
    headers = ["Task ID", "Name", "Baseline", "Defect", "Repaired", "Status"]
    separator = "-+-".join("-" * w for w in widths)

    print(format_table_row(headers, widths))
    print(separator)

    all_passed = True
    for r in reports:
        if r.get("is_adversarial"):
            row = [
                r["task_id"],
                r["name"][:40],
                "N/A",
                "N/A",
                "BLOCKED" if r["adversarial_blocked"] else "UNBLOCKED",
                r["status"]
            ]
        else:
            row = [
                r["task_id"],
                r["name"][:40],
                "PASS" if r["baseline_passed"] else "FAIL",
                "VERIFIED" if r["defect_verified"] else "MISSING",
                "PASS" if r["repair_passed"] else "FAIL",
                r["status"]
            ]
        if r["status"] != "PASS":
            all_passed = False
        print(format_table_row(row, widths))

    print(separator)
    print(f"Fixture Validation Result: {'ALL PASS' if all_passed else 'FAILURES DETECTED'}")
    return reports, all_passed


async def main():
    parser = argparse.ArgumentParser(description="Ouroboros Benchmark Suite Runner")
    parser.add_argument("--task-id", type=str, help="Execute single benchmark task by ID (e.g. BENCH-04)")
    parser.add_argument("--eligible-only", action="store_true", help="Run only eligible repair tasks (skip adversarial)")
    parser.add_argument("--security-only", action="store_true", help="Run only adversarial security evaluation tasks")
    parser.add_argument("--category", type=str, help="Filter tasks by category")
    parser.add_argument("--validate-fixtures", action="store_true", help="Run fixture verification mode without flywheel")
    parser.add_argument("--repeat", type=int, default=1, help="Number of repetition trials")
    parser.add_argument("--memory-enabled", action="store_true", help="Run with memory enabled only")
    parser.add_argument("--memory-disabled", action="store_true", help="Run with memory disabled only")
    parser.add_argument("--ablation", action="store_true", help="Run ablation study (memory enabled vs disabled)")
    parser.add_argument("--agent", "--agent-eval", dest="agent_eval", action="store_true", help="Execute real agent repair pipeline instead of deterministic reference repair")
    parser.add_argument("--dry-run", action="store_true", help="Perform dry-run without invoking model endpoints or applying patches")
    parser.add_argument("--mock-agents", action="store_true", help="Use deterministic mock provider for agent execution")
    parser.add_argument("--output", type=str, default=None, help="Output path for machine-readable JSON report")

    args = parser.parse_args()

    # Pre-flight consistency check
    suite_errors = validate_suite_consistency(BENCHMARK_TASKS_V1)
    if suite_errors:
        print("Suite Configuration Errors:")
        for err in suite_errors:
            print(f"  - {err}")
        sys.exit(1)

    # 1. Fixture validation mode
    if args.validate_fixtures:
        task_filter = [args.task_id] if args.task_id else None
        reports, all_ok = await run_fixture_validation(task_ids=task_filter)
        if args.output:
            out_p = Path(args.output)
            out_p.parent.mkdir(parents=True, exist_ok=True)
            out_p.write_text(json.dumps(reports, indent=2), encoding="utf-8")
            print(f"Saved fixture validation report to {out_p}")
        sys.exit(0 if all_ok else 1)

    # Task filtering setup
    task_ids = [args.task_id] if args.task_id else None
    run_ablation = args.ablation or (not args.memory_enabled and not args.memory_disabled)

    artifacts_dir = Path(__file__).resolve().parent.parent / "artifacts"
    artifacts_dir.mkdir(parents=True, exist_ok=True)

    # Default output path depends on whether evaluating real agents or reference fixes
    if args.output:
        out_file = Path(args.output)
    elif args.agent_eval:
        out_file = artifacts_dir / "agent_evaluation_results.json"
    else:
        out_file = artifacts_dir / "benchmark_results.json"

    print("=" * 80)
    if args.agent_eval:
        print("PROJECT OUROBOROS REAL AGENT EVALUATION ENGINE (v0.10 Priority 2A)")
        print(f"Execution: {'DRY RUN' if args.dry_run else ('MOCK AGENTS' if args.mock_agents else 'LIVE PRODUCTION PIPELINE')}")
    else:
        print("PROJECT OUROBOROS BENCHMARK SUITE v1.0.0 (v0.10 Expansion)")
        print("Execution: REFERENCE REPAIR HARNESS")
    print(f"Mode: {'Ablation (Memory ON vs OFF)' if run_ablation else ('Memory ON' if args.memory_enabled else 'Memory OFF')}")
    print(f"Filter: task_id={args.task_id}, eligible_only={args.eligible_only}, security_only={args.security_only}, category={args.category}")
    print("=" * 80)

    results_mem_on = None
    results_mem_off = None

    for trial in range(1, args.repeat + 1):
        if args.repeat > 1:
            print(f"\n>>> TRIAL {trial} of {args.repeat} <<<")

        if args.agent_eval:
            if run_ablation or args.memory_enabled:
                results_mem_on = await AgentRepairEvaluator.evaluate_suite(
                    task_ids=task_ids,
                    eligible_only=args.eligible_only,
                    security_only=args.security_only,
                    category=args.category,
                    memory_enabled=True,
                    force_mock=args.mock_agents,
                    dry_run=args.dry_run
                )
                print_agent_summary_table("Memory ENABLED (Real Agent)", results_mem_on)

            if run_ablation or args.memory_disabled:
                results_mem_off = await AgentRepairEvaluator.evaluate_suite(
                    task_ids=task_ids,
                    eligible_only=args.eligible_only,
                    security_only=args.security_only,
                    category=args.category,
                    memory_enabled=False,
                    force_mock=args.mock_agents,
                    dry_run=args.dry_run
                )
                print_agent_summary_table("Memory DISABLED Ablation (Real Agent)", results_mem_off)
        else:
            if run_ablation or args.memory_enabled:
                results_mem_on = await BenchmarkHarness.run_suite(
                    memory_enabled=True,
                    task_ids=task_ids,
                    eligible_only=args.eligible_only,
                    security_only=args.security_only,
                    category=args.category
                )
                print_summary_table("Memory ENABLED", results_mem_on)

            if run_ablation or args.memory_disabled:
                results_mem_off = await BenchmarkHarness.run_suite(
                    memory_enabled=False,
                    task_ids=task_ids,
                    eligible_only=args.eligible_only,
                    security_only=args.security_only,
                    category=args.category
                )
                print_summary_table("Memory DISABLED (Ablation)", results_mem_off)

    # Compile JSON report
    report_data: Dict[str, Any] = {
        "evaluation_type": "agent_evaluation" if args.agent_eval else "reference_benchmark",
        "benchmark_version": "v1.0.0",
        "expansion_milestone": "v0.10",
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "configuration": {
            "agent_eval": args.agent_eval,
            "dry_run": args.dry_run,
            "mock_agents": args.mock_agents,
            "task_id_filter": args.task_id,
            "eligible_only": args.eligible_only,
            "security_only": args.security_only,
            "category_filter": args.category,
            "repeat_trials": args.repeat,
            "ablation_mode": run_ablation
        }
    }

    if results_mem_on:
        report_data["memory_enabled_run"] = results_mem_on
    if results_mem_off:
        report_data["memory_disabled_ablation_run"] = results_mem_off

    if results_mem_on and results_mem_off:
        rate_key = "eligible_repair_success_rate" if not args.agent_eval else "eligible_repair_success_rate"
        on_rate = results_mem_on.get(rate_key) or 0.0
        off_rate = results_mem_off.get(rate_key) or 0.0
        report_data["ablation_comparison"] = {
            "eligible_repair_success_rate_delta": round(on_rate - off_rate, 4),
            "median_latency_delta_ms": results_mem_on["median_duration_ms"] - results_mem_off["median_duration_ms"]
        }

    out_file.write_text(json.dumps(report_data, indent=2), encoding="utf-8")
    print(f"\nSaved machine-readable report to: {out_file}")
    print("=" * 80)


if __name__ == "__main__":
    asyncio.run(main())
