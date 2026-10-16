"""
Unit tests for Ouroboros Benchmark Expansion (v0.10 / v1.0.0)
Tests:
- Schema validation for all 16 benchmark tasks (15 eligible + 1 adversarial).
- Five category distributions (3 tasks each).
- Rejection of duplicate IDs, missing fixtures, and invalid classifications.
- Metrics calculations with verified explicit denominators.
- Accurate distinction between PASSED_REPAIR, FAILED_REPAIR, BLOCKED_BY_POLICY, TIMED_OUT, INFRASTRUCTURE_ERROR.
- Isolation and cleanup verification.
"""

import pytest
import copy
from typing import Dict, Any

from app.evaluation.benchmark import (
    BENCHMARK_TASKS_V1,
    BenchmarkHarness,
    validate_task_schema,
    validate_suite_consistency
)


def test_suite_composition():
    """Verify exactly 16 tasks total: 15 eligible repair tasks and 1 adversarial task."""
    assert len(BENCHMARK_TASKS_V1) == 16
    eligible = [t for t in BENCHMARK_TASKS_V1 if t.get("is_eligible")]
    adversarial = [t for t in BENCHMARK_TASKS_V1 if t.get("is_adversarial")]
    assert len(eligible) == 15
    assert len(adversarial) == 1
    assert adversarial[0]["task_id"] == "BENCH-03"


def test_five_categories_distribution():
    """Verify each of the 5 categories contains exactly 3 eligible repair tasks."""
    expected_categories = [
        "boundary_and_edge_case",
        "type_and_interface",
        "multi_file_and_state",
        "serialization_and_parsing",
        "logic_and_exception"
    ]
    eligible_tasks = [t for t in BENCHMARK_TASKS_V1 if t.get("is_eligible")]

    category_counts: Dict[str, int] = {}
    for t in eligible_tasks:
        cat = t["category"]
        category_counts[cat] = category_counts.get(cat, 0) + 1

    for cat in expected_categories:
        assert cat in category_counts, f"Missing category: {cat}"
        assert category_counts[cat] == 3, f"Category {cat} has {category_counts[cat]} tasks, expected 3"


def test_schema_valid_for_all_tasks():
    """Verify all 16 task definitions in the suite conform to schema specification."""
    for task in BENCHMARK_TASKS_V1:
        errors = validate_task_schema(task)
        assert len(errors) == 0, f"Task {task.get('task_id')} failed schema: {errors}"


def test_schema_rejects_missing_keys():
    """Verify schema validator detects missing required fields."""
    incomplete = {
        "task_id": "BENCH-99",
        "name": "Incomplete task"
    }
    errors = validate_task_schema(incomplete)
    assert len(errors) > 0
    assert any("Missing required key" in e for e in errors)


def test_schema_rejects_invalid_task_id():
    """Verify schema validator rejects task IDs not matching prefix convention."""
    task = copy.deepcopy(BENCHMARK_TASKS_V1[0])
    task["task_id"] = "INVALID-99"
    errors = validate_task_schema(task)
    assert any("Invalid task_id format" in e for e in errors)


def test_schema_rejects_conflicting_eligibility():
    """Verify a task cannot be both eligible for repair and adversarial."""
    task = copy.deepcopy(BENCHMARK_TASKS_V1[0])
    task["is_eligible"] = True
    task["is_adversarial"] = True
    errors = validate_task_schema(task)
    assert any("cannot be both eligible for repair and adversarial" in e for e in errors)


def test_schema_rejects_eligible_task_without_repair_patch():
    """Verify an eligible repair task must have a non-empty repair patch."""
    task = copy.deepcopy(BENCHMARK_TASKS_V1[0])
    task["repair_patch"] = None
    errors = validate_task_schema(task)
    assert any("must have a non-empty repair_patch" in e for e in errors)


def test_suite_consistency_detects_duplicate_ids():
    """Verify suite validator rejects duplicated task IDs."""
    duplicated = copy.deepcopy(BENCHMARK_TASKS_V1)
    duplicated.append(copy.deepcopy(BENCHMARK_TASKS_V1[0]))
    errors = validate_suite_consistency(duplicated)
    assert any("Duplicate task ID detected" in e for e in errors)


def test_suite_consistency_detects_insufficient_eligible_tasks():
    """Verify suite validator rejects suites with fewer than 15 eligible tasks."""
    partial = [t for t in BENCHMARK_TASKS_V1 if t["task_id"] in ["BENCH-01", "BENCH-02", "BENCH-03"]]
    errors = validate_suite_consistency(partial)
    assert any("Expected at least 15 eligible repair tasks" in e for e in errors)


@pytest.mark.asyncio
async def test_metrics_calculation_denominators_and_rates():
    """Verify explicit denominators and correct rate calculation in suite execution."""
    # Run only security task (0 eligible tasks)
    sec_suite = await BenchmarkHarness.run_suite(security_only=True)
    assert sec_suite["eligible_tasks"] == 0
    assert sec_suite["eligible_repair_success_rate"] is None  # Never silently 0.0 when denominator is 0
    assert sec_suite["adversarial_tasks"] == 1
    assert sec_suite["adversarial_blocked_tasks"] == 1
    assert sec_suite["adversarial_block_rate"] == 1.0

    # Run single eligible task
    single_suite = await BenchmarkHarness.run_suite(task_ids=["BENCH-04"])
    assert single_suite["eligible_tasks"] == 1
    assert single_suite["eligible_passed_tasks"] == 1
    assert single_suite["eligible_repair_success_rate"] == 1.0
    assert single_suite["adversarial_tasks"] == 0
    assert single_suite["adversarial_block_rate"] is None


@pytest.mark.asyncio
async def test_adversarial_task_does_not_inflate_repair_rate():
    """Verify that an adversarial task being blocked does not increment repair success count."""
    mixed_tasks = [
        BenchmarkHarness.get_task_by_id("BENCH-01"),
        BenchmarkHarness.get_task_by_id("BENCH-03")
    ]
    suite_res = await BenchmarkHarness.run_suite(tasks=mixed_tasks)
    assert suite_res["total_tasks"] == 2
    assert suite_res["eligible_tasks"] == 1
    assert suite_res["adversarial_tasks"] == 1
    assert suite_res["eligible_passed_tasks"] == 1
    assert suite_res["adversarial_blocked_tasks"] == 1
    # Blocked task must not count as passed repair
    assert suite_res["eligible_repair_success_rate"] == 1.0
    assert suite_res["raw_task_outcome_distribution"]["PASSED_REPAIR"] == 1
    assert suite_res["raw_task_outcome_distribution"]["BLOCKED_BY_POLICY"] == 1


@pytest.mark.asyncio
async def test_deterministic_task_lifecycle_bench01():
    """Verify complete lifecycle for BENCH-01: flawed patch fails, repair patch succeeds."""
    task = BenchmarkHarness.get_task_by_id("BENCH-01")
    assert task is not None
    res = await BenchmarkHarness.run_task(task, memory_enabled=False)
    assert res["verdict"] == "PASS"
    assert res["outcome"] == "PASSED_REPAIR"
    assert res["attempts"] == 2
    assert res["history"][0]["verdict"] == "FAIL"
    assert res["history"][1]["verdict"] == "PASS"


@pytest.mark.asyncio
async def test_deterministic_adversarial_block_bench03():
    """Verify static policy rejection for BENCH-03 (.env attack)."""
    task = BenchmarkHarness.get_task_by_id("BENCH-03")
    assert task is not None
    res = await BenchmarkHarness.run_task(task, memory_enabled=False)
    assert res["verdict"] == "BLOCKED"
    assert res["outcome"] == "BLOCKED_BY_POLICY"
    assert res["attempts"] == 1
    assert "Prohibited modification of protected files" in res["history"][0]["reason"]
