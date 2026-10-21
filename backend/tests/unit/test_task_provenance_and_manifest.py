"""
Unit tests validating benchmark task identity, manifest integrity, and provenance fingerprints.

Validates:
1. Strict uniqueness of task IDs across the entire reference benchmark manifest.
2. Canonical identity of BENCH-04 (Numeric Boundary Clamping in math_utils/bounds.py).
3. Exact partition of 15 eligible repair tasks and 1 isolated adversarial task.
4. Completeness of required task schema fields for reproducibility.
5. Deterministic fingerprinting of task definitions.
"""

import hashlib
import json
import pytest

from app.evaluation.benchmark import BENCHMARK_TASKS_V1, BenchmarkHarness


def test_manifest_unique_task_ids():
    """Validates that no task ID collisions exist in the benchmark manifest."""
    task_ids = [t["task_id"] for t in BENCHMARK_TASKS_V1]
    unique_ids = set(task_ids)
    assert len(task_ids) == len(unique_ids), f"Duplicate task IDs detected: {[x for x in task_ids if task_ids.count(x) > 1]}"
    assert len(task_ids) == 16, f"Expected exactly 16 tasks in reference suite, found {len(task_ids)}"


def test_manifest_canonical_partition_positive_vs_adversarial():
    """Validates that the suite contains exactly 15 eligible positive repair tasks and 1 adversarial task."""
    eligible = [t["task_id"] for t in BENCHMARK_TASKS_V1 if t.get("is_eligible") and not t.get("is_adversarial")]
    adversarial = [t["task_id"] for t in BENCHMARK_TASKS_V1 if t.get("is_adversarial")]

    assert len(eligible) == 15, f"Expected 15 eligible positive repair tasks, got {len(eligible)}"
    assert len(adversarial) == 1, f"Expected 1 adversarial task, got {len(adversarial)}"
    assert adversarial == ["BENCH-03"]
    assert "BENCH-04" in eligible


def test_bench04_canonical_identity():
    """
    Prevents historical reporting errors where BENCH-04 was erroneously described
    as 'Off-by-One Binary Search' or 'Concurrency Deadlock'.
    Asserts canonical truth from backend/app/evaluation/benchmark.py.
    """
    task = BenchmarkHarness.get_task_by_id("BENCH-04")
    assert task is not None
    assert task["task_id"] == "BENCH-04"
    assert task["name"] == "Numeric Boundary Clamping"
    assert task["category"] == "boundary_and_edge_case"
    assert task["target_file"] == "math_utils/bounds.py"
    assert task["acceptance_test"] == "test_bounds.py::test_clamp_boundaries_and_invalid_range"
    assert task["baseline_test"] == "test_bounds.py::test_clamp_in_range"
    assert task["is_eligible"] is True
    assert task["is_adversarial"] is False


def test_manifest_required_fields_present():
    """Validates that all tasks have the mandatory attributes required for deterministic execution."""
    required_fields = [
        "task_id",
        "name",
        "category",
        "difficulty",
        "is_eligible",
        "target_file",
        "problem_statement",
        "baseline_test",
        "acceptance_test",
        "flawed_patch"
    ]

    for t in BENCHMARK_TASKS_V1:
        tid = t.get("task_id", "UNKNOWN")
        for field in required_fields:
            assert field in t, f"Task {tid} is missing required field '{field}'"
            assert t[field] is not None, f"Task {tid} field '{field}' must not be None"


def test_task_definition_fingerprint_stability():
    """
    Validates that a cryptographic fingerprint computed on task definition fields
    is strictly deterministic and sensitive to specification changes.
    """
    def compute_task_fingerprint(t: dict) -> str:
        canonical_str = json.dumps({
            "task_id": t["task_id"],
            "name": t["name"],
            "target_file": t["target_file"],
            "problem_statement": t["problem_statement"],
            "acceptance_test": t["acceptance_test"]
        }, sort_keys=True)
        return hashlib.sha256(canonical_str.encode("utf-8")).hexdigest()

    task = BenchmarkHarness.get_task_by_id("BENCH-04")
    fp1 = compute_task_fingerprint(task)
    fp2 = compute_task_fingerprint(task)
    assert fp1 == fp2

    # Modified task must yield a different fingerprint
    modified_task = dict(task, name="Modified Name")
    fp_mod = compute_task_fingerprint(modified_task)
    assert fp1 != fp_mod
