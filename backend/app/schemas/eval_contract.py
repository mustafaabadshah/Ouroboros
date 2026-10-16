"""
Project Ouroboros v0.11 - Evaluation Data Contract & Schema
Defines versioned, strongly-typed contracts for reproducible agent evaluations,
distinguishing terminal outcomes, intermediate attempt verdicts, honest denominators,
and backward-compatible adapters for v0.10 artifacts.
"""

from enum import Enum
from typing import List, Optional, Dict, Any, Tuple
from datetime import datetime, timezone
import math
from pydantic import BaseModel, Field


class EvaluationOutcome(str, Enum):
    """Explicit terminal and attempt evaluation outcomes."""
    PASS = "PASS"
    FAILED_REPAIR = "FAILED_REPAIR"
    BLOCKED_BY_POLICY = "BLOCKED_BY_POLICY"
    RUNTIME_UNAVAILABLE = "RUNTIME_UNAVAILABLE"
    PROVIDER_ERROR = "PROVIDER_ERROR"
    TIMEOUT = "TIMEOUT"
    CANCELLED = "CANCELLED"
    INVALID_RESULT = "INVALID_RESULT"


class MemoryCondition(str, Enum):
    """Evaluation memory baseline condition."""
    MEMORY_ENABLED = "MEMORY_ENABLED"
    NAIVE_RETRY = "NAIVE_RETRY"
    MEMORY_DISABLED = "MEMORY_DISABLED"


class AttemptRecord(BaseModel):
    """Fine-grained telemetry and outcome for a single repair attempt."""
    attempt_number: int = Field(..., ge=1)
    repair_outcome: EvaluationOutcome
    patch_diff: Optional[str] = None
    patch_hash: Optional[str] = None
    tests_passed: int = 0
    tests_failed: int = 0
    tests_errored: int = 0
    failure_signature: Optional[str] = None
    escalation_level: Optional[str] = None
    duration_ms: int = 0
    tokens_in: Optional[int] = None
    tokens_out: Optional[int] = None
    cost_estimate_usd: Optional[float] = None
    timestamp_utc: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class EvaluationTaskRecord(BaseModel):
    """Versioned, strongly-typed record for a single evaluated task."""
    schema_version: str = "v0.11.0"
    run_id: str
    task_id: str
    task_name: str
    category: str
    benchmark_suite: str = "ouroboros_benchmark"
    benchmark_version: str = "v1.0.0"
    is_eligible: bool = True
    eligibility_reason: Optional[str] = None
    memory_condition: MemoryCondition = MemoryCondition.MEMORY_ENABLED
    retry_strategy: str = "flywheel_escalation"
    provider: str = "groq"
    model: str = "qwen/qwen3.8-27b"
    started_at_utc: datetime
    completed_at_utc: datetime
    duration_ms: int
    git_commit: str
    git_tree_fingerprint: str
    attempt_count: int = Field(..., ge=0)
    attempts: List[AttemptRecord] = []
    terminal_outcome: EvaluationOutcome
    policy_blocked: bool = False
    infrastructure_failure: bool = False
    tests_passed_count: int = 0
    tests_failed_count: int = 0
    regression_test_passed: bool = True
    token_usage: Optional[Dict[str, Optional[int]]] = None
    cost_estimate_usd: Optional[float] = None
    failure_signature: Optional[str] = None
    escalation_events: List[str] = []
    sandbox_runtime: str = "local_subprocess"
    cleanup_verified: bool = True
    artifact_paths: List[str] = []
    integrity_hashes: Dict[str, str] = {}


class SummaryStatistics(BaseModel):
    """Statistical summary metrics with confidence intervals."""
    total_tasks_selected: int
    total_tasks_attempted: int
    eligible_tasks_count: int
    adversarial_tasks_count: int
    repairs_passed: int
    repairs_failed: int
    policy_blocked: int
    timeouts: int
    infrastructure_failures: int
    provider_unavailable: int
    invalid_results: int
    eligible_repair_success_rate: float
    raw_success_rate: float
    adversarial_block_rate: float
    mean_attempts_eligible: float
    p50_latency_ms: float
    p95_latency_ms: float
    total_duration_ms: int
    total_tokens_in: Optional[int] = None
    total_tokens_out: Optional[int] = None
    total_tokens: Optional[int] = None
    total_cost_usd: Optional[float] = None
    # 95% Wilson Score Confidence Interval for eligible repair success rate
    wilson_ci_lower: float
    wilson_ci_upper: float


class EvaluationSweepRun(BaseModel):
    """Complete evaluation sweep result containing typed records and summary."""
    schema_version: str = "v0.11.0"
    sweep_id: str
    benchmark_suite: str
    benchmark_version: str
    memory_condition: MemoryCondition
    repetition_index: int = 1
    total_repetitions: int = 1
    started_at_utc: datetime
    completed_at_utc: datetime
    git_commit: str
    git_tree_fingerprint: str
    summary: SummaryStatistics
    task_results: List[EvaluationTaskRecord]


def compute_wilson_score_interval(successes: int, total: int, z: float = 1.96) -> Tuple[float, float]:
    """
    Computes the 95% Wilson score confidence interval for a binomial proportion.
    Accurate and well-behaved even near 0% and 100% or small sample sizes.
    """
    if total <= 0:
        return 0.0, 0.0
    p = successes / total
    denominator = 1 + (z ** 2) / total
    centre_adjusted_probability = p + (z ** 2) / (2 * total)
    adjusted_std_dev = math.sqrt((p * (1 - p) + (z ** 2) / (4 * total)) / total)
    lower = (centre_adjusted_probability - z * adjusted_std_dev) / denominator
    upper = (centre_adjusted_probability + z * adjusted_std_dev) / denominator
    return max(0.0, lower), min(1.0, upper)


def compute_percentiles(values: List[float], percentiles: List[float]) -> Dict[float, float]:
    """Calculates nearest-rank or linear interpolated percentiles."""
    if not values:
        return {p: 0.0 for p in percentiles}
    sorted_v = sorted(values)
    results = {}
    for p in percentiles:
        k = (len(sorted_v) - 1) * (p / 100.0)
        f = math.floor(k)
        c = math.ceil(k)
        if f == c:
            results[p] = float(sorted_v[int(k)])
        else:
            d0 = sorted_v[int(f)] * (c - k)
            d1 = sorted_v[int(c)] * (k - f)
            results[p] = float(d0 + d1)
    return results


class EvaluationContractAdapter:
    """
    Backward-compatible adapter that parses legacy v0.10 evaluation sweeps
    into validated v0.11 EvaluationSweepRun instances.
    """

    @classmethod
    def from_v010_json(cls, data: Dict[str, Any], git_commit: str = "549608c") -> EvaluationSweepRun:
        mem_run = data.get("memory_enabled_run") or data.get("memory_disabled_run") or {}
        raw_tasks = mem_run.get("task_results", [])
        is_mem_enabled = mem_run.get("memory_enabled", True)
        condition = MemoryCondition.MEMORY_ENABLED if is_mem_enabled else MemoryCondition.MEMORY_DISABLED

        records: List[EvaluationTaskRecord] = []
        for t in raw_tasks:
            # map legacy outcome
            leg_outcome = t.get("outcome") or t.get("verdict")
            if leg_outcome in ["PASSED_REPAIR", "PASS"]:
                outcome = EvaluationOutcome.PASS
            elif leg_outcome in ["BLOCKED_BY_POLICY", "BLOCKED"]:
                outcome = EvaluationOutcome.BLOCKED_BY_POLICY
            elif leg_outcome in ["TIMED_OUT", "TIMEOUT"]:
                outcome = EvaluationOutcome.TIMEOUT
            elif leg_outcome in ["INFRASTRUCTURE_ERROR", "RUNTIME_UNAVAILABLE"]:
                outcome = EvaluationOutcome.RUNTIME_UNAVAILABLE
            else:
                outcome = EvaluationOutcome.FAILED_REPAIR

            # build attempts
            attempts_list = []
            for idx, att in enumerate(t.get("attempt_history", [])):
                att_outcome = EvaluationOutcome.PASS if att.get("passed") else EvaluationOutcome.FAILED_REPAIR
                attempts_list.append(AttemptRecord(
                    attempt_number=idx + 1,
                    repair_outcome=att_outcome,
                    tests_passed=att.get("tests_passed", 0),
                    tests_failed=att.get("tests_failed", 0),
                    duration_ms=att.get("duration_ms", 0),
                    failure_signature=att.get("failure_signature"),
                    escalation_level=att.get("strategy_escalation")
                ))

            rec = EvaluationTaskRecord(
                run_id=f"legacy-{t.get('task_id')}",
                task_id=t.get("task_id", "UNKNOWN"),
                task_name=t.get("name", ""),
                category=t.get("category", "general"),
                benchmark_suite="ouroboros_benchmark",
                benchmark_version="v1.0.0",
                is_eligible=t.get("is_eligible", True),
                memory_condition=condition,
                retry_strategy="flywheel_escalation" if is_mem_enabled else "naive_retry",
                provider=t.get("model_provider", "groq"),
                model=t.get("model_name", "qwen/qwen3.8-27b"),
                started_at_utc=datetime.now(timezone.utc),
                completed_at_utc=datetime.now(timezone.utc),
                duration_ms=t.get("duration_ms", 0),
                git_commit=git_commit,
                git_tree_fingerprint="v0.10-baseline-fingerprint",
                attempt_count=t.get("attempts", 1),
                attempts=attempts_list,
                terminal_outcome=outcome,
                policy_blocked=(outcome == EvaluationOutcome.BLOCKED_BY_POLICY),
                infrastructure_failure=False,
                tests_passed_count=t.get("tests_passed", 0),
                tests_failed_count=t.get("tests_failed", 0),
                regression_test_passed=True,
                token_usage={
                    "tokens_in": t.get("tokens_in"),
                    "tokens_out": t.get("tokens_out"),
                    "total_tokens": (t.get("tokens_in", 0) + t.get("tokens_out", 0)) if t.get("tokens_in") is not None else None
                },
                failure_signature=t.get("failure_signature"),
                escalation_events=[t.get("strategy_escalation")] if t.get("strategy_escalation") else [],
                sandbox_runtime="local_subprocess",
                cleanup_verified=True
            )
            records.append(rec)

        # Compute summary
        eligible_records = [r for r in records if r.is_eligible and not r.policy_blocked]
        passed_records = [r for r in eligible_records if r.terminal_outcome == EvaluationOutcome.PASS]
        blocked_records = [r for r in records if r.terminal_outcome == EvaluationOutcome.BLOCKED_BY_POLICY]

        success_rate = (len(passed_records) / len(eligible_records)) if eligible_records else 0.0
        ci_low, ci_high = compute_wilson_score_interval(len(passed_records), len(eligible_records))

        durations = [r.duration_ms for r in records]
        percentiles = compute_percentiles(durations, [50.0, 95.0])

        summary = SummaryStatistics(
            total_tasks_selected=len(records),
            total_tasks_attempted=len(records),
            eligible_tasks_count=len(eligible_records),
            adversarial_tasks_count=len(blocked_records),
            repairs_passed=len(passed_records),
            repairs_failed=len(eligible_records) - len(passed_records),
            policy_blocked=len(blocked_records),
            timeouts=0,
            infrastructure_failures=0,
            provider_unavailable=0,
            invalid_results=0,
            eligible_repair_success_rate=success_rate,
            raw_success_rate=len(passed_records) / len(records) if records else 0.0,
            adversarial_block_rate=1.0 if blocked_records else 0.0,
            mean_attempts_eligible=(sum(r.attempt_count for r in eligible_records) / len(eligible_records)) if eligible_records else 0.0,
            p50_latency_ms=percentiles[50.0],
            p95_latency_ms=percentiles[95.0],
            total_duration_ms=sum(durations),
            total_tokens_in=mem_run.get("total_tokens_in"),
            total_tokens_out=mem_run.get("total_tokens_out"),
            total_tokens=(mem_run.get("total_tokens_in", 0) + mem_run.get("total_tokens_out", 0)),
            wilson_ci_lower=ci_low,
            wilson_ci_upper=ci_high
        )

        return EvaluationSweepRun(
            sweep_id=f"v010-adapter-{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}",
            benchmark_suite="ouroboros_benchmark",
            benchmark_version="v1.0.0",
            memory_condition=condition,
            repetition_index=1,
            total_repetitions=1,
            started_at_utc=datetime.now(timezone.utc),
            completed_at_utc=datetime.now(timezone.utc),
            git_commit=git_commit,
            git_tree_fingerprint="v0.10-baseline-fingerprint",
            summary=summary,
            task_results=records
        )
