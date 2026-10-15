from fastapi import APIRouter, Depends, Query, Response
from sqlalchemy.orm import Session
from typing import Dict, Any, List
import json

from app.database.session import get_db
from app.evaluation.metrics import MetricsCalculator
from app.evaluation.benchmark import BenchmarkHarness, BENCHMARK_TASKS_V1

router = APIRouter(prefix="/api/evaluation", tags=["Evaluation & Benchmarks"])

@router.get("/metrics", response_model=Dict[str, Any])
def get_evaluation_metrics(db: Session = Depends(get_db)):
    """Computes and returns honest summary metrics from persisted runs and test executions."""
    return MetricsCalculator.compute_summary_metrics(db)

@router.get("/benchmark/tasks", response_model=List[Dict[str, Any]])
def get_benchmark_tasks():
    """Lists all versioned benchmark tasks in suite v1.0.0."""
    return [
        {
            "task_id": t["task_id"],
            "name": t["name"],
            "difficulty": t["difficulty"],
            "category": t["category"],
            "target_file": t["target_file"],
            "problem_statement": t["problem_statement"],
            "baseline_test": t["baseline_test"],
            "acceptance_test": t["acceptance_test"],
            "max_repair_budget": t["max_repair_budget"],
            "expected_initial_verdict": t["expected_initial_verdict"]
        }
        for t in BENCHMARK_TASKS_V1
    ]

@router.post("/benchmark/run", response_model=Dict[str, Any])
async def run_benchmark_suite(
    memory_enabled: bool = Query(True, description="Enable FailureFlywheel persistent memory retrieval")
):
    """Executes the complete versioned benchmark suite and returns task-level outcomes and metrics."""
    results = await BenchmarkHarness.run_suite(memory_enabled=memory_enabled)
    return results

@router.get("/benchmark/export")
async def export_benchmark_report(
    memory_enabled: bool = Query(True, description="Filter export by memory setting")
):
    """Exports benchmark suite results as a downloadable formatted JSON report."""
    results = await BenchmarkHarness.run_suite(memory_enabled=memory_enabled)
    json_bytes = json.dumps(results, indent=2).encode("utf-8")
    return Response(
        content=json_bytes,
        media_type="application/json",
        headers={"Content-Disposition": "attachment; filename=ouroboros_benchmark_results.json"}
    )
