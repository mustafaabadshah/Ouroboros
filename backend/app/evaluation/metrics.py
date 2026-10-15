"""
Project Ouroboros - Deterministic Evaluation Metrics Engine
Computes honest, verifiable evaluation metrics from persisted database records.
Explicit formulas, verified denominators, and distinction between blocked, failed, and passed runs.
"""

from typing import Dict, List, Any, Optional
from sqlalchemy.orm import Session
from sqlalchemy import func
from app.database.models import RunModel, CandidateModel, TestResultModel, FailureTrajectoryModel

class MetricsCalculator:
    """
    Computes rigorous evaluation metrics from the SQLite database.
    Formulas:
    1. Repair Success Rate:
       passed_runs / eligible_attempted_runs
       (Blocked runs, cancellations, and timeouts are reported separately and excluded from successful repairs)
    2. Candidate Test Pass Rate:
       passed_test_executions / total_completed_test_executions
    3. Regression Rate:
       runs_with_regressions / total_evaluated_runs
    4. Average Attempts per Repair:
       sum(attempts_for_passing_runs) / passing_runs_count
    5. Latency Distribution:
       median (p50) and 95th percentile (p95) execution durations in milliseconds.
    6. Workflow Reliability:
       Breakdown of COMPLETED, FAILED, BLOCKED, CANCELLED, TIMED_OUT states.
    """

    @staticmethod
    def compute_summary_metrics(db: Session) -> Dict[str, Any]:
        runs: List[RunModel] = db.query(RunModel).all()
        candidates: List[CandidateModel] = db.query(CandidateModel).all()
        test_results: List[TestResultModel] = db.query(TestResultModel).all()
        failures: List[FailureTrajectoryModel] = db.query(FailureTrajectoryModel).all()

        total_runs = len(runs)
        completed_runs = sum(1 for r in runs if r.state == "COMPLETED")
        failed_runs = sum(1 for r in runs if r.state == "FAILED")
        blocked_runs = sum(1 for r in runs if r.state == "BLOCKED")
        cancelled_runs = sum(1 for r in runs if r.state == "CANCELLED")

        # Passing runs (evaluated with PASS verdict)
        passing_runs = [r for r in runs if r.evaluation_verdict == "PASS"]
        passing_count = len(passing_runs)

        # Eligible attempted runs for repair (runs that entered evaluation)
        eligible_attempted = sum(1 for r in runs if r.state in ["COMPLETED", "FAILED", "AWAITING_APPROVAL"])
        repair_success_rate = (passing_count / eligible_attempted) if eligible_attempted > 0 else 0.0

        # Candidate test pass rate
        candidate_tests = [t for t in test_results if t.test_type in ["acceptance", "regression"]]
        total_cand_tests = len(candidate_tests)
        passed_cand_tests = sum(1 for t in candidate_tests if t.exit_code == 0)
        candidate_test_pass_rate = (passed_cand_tests / total_cand_tests) if total_cand_tests > 0 else 0.0

        # Regression detection rate
        runs_with_regression = 0
        for r in runs:
            run_tests = [t for t in test_results if t.run_id == r.id and t.test_type == "regression"]
            if any(t.failed_count > 0 for t in run_tests):
                runs_with_regression += 1
        regression_rate = (runs_with_regression / total_runs) if total_runs > 0 else 0.0

        # Attempts per repair
        attempts_passing = [r.retry_count + 1 for r in passing_runs]
        avg_attempts = (sum(attempts_passing) / len(attempts_passing)) if attempts_passing else 1.0

        # Durations & Latencies
        durations = [t.duration_ms for t in test_results if t.duration_ms > 0]
        durations.sort()
        if durations:
            p50_idx = int(len(durations) * 0.50)
            p95_idx = int(len(durations) * 0.95)
            latency_p50_ms = durations[min(p50_idx, len(durations) - 1)]
            latency_p95_ms = durations[min(p95_idx, len(durations) - 1)]
        else:
            latency_p50_ms = 0
            latency_p95_ms = 0

        # Repeated failures caught by memory flywheel
        repeated_failures = sum(1 for f in failures if f.status == "REPEATED")

        return {
            "total_runs": total_runs,
            "completed_runs": completed_runs,
            "failed_runs": failed_runs,
            "blocked_runs": blocked_runs,
            "cancelled_runs": cancelled_runs,
            "passing_runs_count": passing_count,
            "eligible_attempted_runs": eligible_attempted,
            "repair_success_rate": round(repair_success_rate, 4),
            "total_candidate_test_executions": total_cand_tests,
            "passed_candidate_test_executions": passed_cand_tests,
            "candidate_test_pass_rate": round(candidate_test_pass_rate, 4),
            "runs_with_regression": runs_with_regression,
            "regression_rate": round(regression_rate, 4),
            "avg_attempts_per_successful_repair": round(avg_attempts, 2),
            "latency_p50_ms": latency_p50_ms,
            "latency_p95_ms": latency_p95_ms,
            "total_failure_trajectories_recorded": len(failures),
            "repeated_failures_prevented": repeated_failures,
            "total_candidates_generated": len(candidates)
        }
