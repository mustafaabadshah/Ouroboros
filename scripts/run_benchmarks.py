"""
Script to execute Project Ouroboros Versioned Benchmark Suite v1.0.0
Generates artifacts/benchmark_results.json and conducts memory ablation experiments.
"""

import sys
import os
import json
import asyncio
from pathlib import Path

# Add backend directory to path
backend_dir = Path(__file__).resolve().parent.parent / "backend"
sys.path.insert(0, str(backend_dir))

from app.evaluation.benchmark import BenchmarkHarness

async def main():
    print("=" * 80)
    print("EXECUTING PROJECT OUROBOROS BENCHMARK SUITE v1.0.0")
    print("=" * 80)

    # 1. Run with Failure Memory ENABLED
    print("\n[EXPERIMENT 1] Running Benchmark with Memory ENABLED...")
    results_mem_on = await BenchmarkHarness.run_suite(memory_enabled=True)
    print(f"  -> Total tasks: {results_mem_on['total_tasks']} (Eligible repair tasks: {results_mem_on['eligible_tasks']})")
    print(f"  -> Passed: {results_mem_on['passed_tasks']}, Blocked (Adversarial): {results_mem_on['blocked_tasks']}, Failed: {results_mem_on['failed_tasks']}")
    print(f"  -> Raw Success Rate (all tasks): {results_mem_on['raw_success_rate'] * 100:.1f}% ({results_mem_on['passed_tasks']}/{results_mem_on['total_tasks']})")
    print(f"  -> Eligible Repair Success Rate: {results_mem_on['eligible_success_rate'] * 100:.1f}% ({results_mem_on['passed_tasks']}/{results_mem_on['eligible_tasks']})")
    print(f"  -> Median Latency: {results_mem_on['median_duration_ms']}ms")

    # 2. Run with Failure Memory DISABLED (Ablation)
    print("\n[EXPERIMENT 2] Running Benchmark with Memory DISABLED (Ablation)...")
    results_mem_off = await BenchmarkHarness.run_suite(memory_enabled=False)
    print(f"  -> Total tasks: {results_mem_off['total_tasks']} (Eligible repair tasks: {results_mem_off['eligible_tasks']})")
    print(f"  -> Passed: {results_mem_off['passed_tasks']}, Blocked (Adversarial): {results_mem_off['blocked_tasks']}, Failed: {results_mem_off['failed_tasks']}")
    print(f"  -> Raw Success Rate (all tasks): {results_mem_off['raw_success_rate'] * 100:.1f}% ({results_mem_off['passed_tasks']}/{results_mem_off['total_tasks']})")
    print(f"  -> Eligible Repair Success Rate: {results_mem_off['eligible_success_rate'] * 100:.1f}% ({results_mem_off['passed_tasks']}/{results_mem_off['eligible_tasks']})")
    print(f"  -> Median Latency: {results_mem_off['median_duration_ms']}ms")

    # Save to artifacts
    artifacts_dir = Path(__file__).resolve().parent.parent / "artifacts"
    artifacts_dir.mkdir(parents=True, exist_ok=True)
    out_file = artifacts_dir / "benchmark_results.json"

    combined = {
        "benchmark_version": "v1.0.0",
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "memory_enabled_run": results_mem_on,
        "memory_disabled_ablation_run": results_mem_off,
        "ablation_comparison": {
            "raw_success_rate_delta": round(results_mem_on['raw_success_rate'] - results_mem_off['raw_success_rate'], 4),
            "eligible_success_rate_delta": round(results_mem_on['eligible_success_rate'] - results_mem_off['eligible_success_rate'], 4),
            "median_latency_delta_ms": results_mem_on['median_duration_ms'] - results_mem_off['median_duration_ms']
        }
    }

    out_file.write_text(json.dumps(combined, indent=2), encoding="utf-8")
    print(f"\nSaved machine-readable benchmark report to: {out_file}")
    print("=" * 80)

if __name__ == "__main__":
    import time
    asyncio.run(main())
