"""
Project Ouroboros - Versioned Benchmark Suite & Execution Engine (v1.0.0)
Defines standardized, reproducible bug-fix fixtures with ground truth,
baseline test suites, acceptance assertions, and protected boundaries.
Supports memory ablation experiments (failure memory enabled vs disabled).
"""

import sys
import os
import json
import time
import shutil
import tempfile
import asyncio
from pathlib import Path
from typing import Dict, List, Any, Optional

from app.core.security import run_safe_subprocess
from app.integrations.git.worktree import GitWorktreeManager
from app.integrations.git.diff_parser import UnifiedDiffParser
from app.evaluation.runner import PytestRunner
from app.evaluation.judge import DeterministicJudge
from app.memory.flywheel import FailureFlywheel
from app.database.session import Base
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

BENCHMARK_TASKS_V1 = [
    {
        "task_id": "BENCH-01",
        "name": "Input Validation Boundary Guard",
        "difficulty": "small",
        "category": "validation",
        "target_file": "utils/input_parser.py",
        "problem_statement": "parse_positive_int accepts negative integers without raising ValueError.",
        "baseline_test": "test_input_parser.py::test_parse_positive",
        "acceptance_test": "test_input_parser.py::test_parse_negative_raises_value_error",
        "protected_paths": [".env", "tests/conftest.py"],
        "max_repair_budget": 3,
        "expected_initial_verdict": "FAIL",
        "flawed_patch": (
            "--- a/utils/input_parser.py\n"
            "+++ b/utils/input_parser.py\n"
            "@@ -1,2 +1,4 @@\n"
            " def parse_positive_int(val):\n"
            "-    return int(val)\n"
            "+    res = int(val)\n"
            "+    return res  # Bug: misses check res <= 0\n"
        ),
        "repair_patch": (
            "--- a/utils/input_parser.py\n"
            "+++ b/utils/input_parser.py\n"
            "@@ -1,4 +1,5 @@\n"
            " def parse_positive_int(val):\n"
            "     res = int(val)\n"
            "+    if res <= 0:\n"
            "+        raise ValueError('Must be positive')\n"
            "     return res\n"
        )
    },
    {
        "task_id": "BENCH-02",
        "name": "Arithmetic Exponentiation Repair",
        "difficulty": "small",
        "category": "logic",
        "target_file": "math_ops.py",
        "problem_statement": "power(base, exp) function missing from math_ops.",
        "baseline_test": "test_math_ops.py::test_multiply",
        "acceptance_test": "test_math_ops.py::test_power",
        "protected_paths": [".env"],
        "max_repair_budget": 3,
        "expected_initial_verdict": "FAIL",
        "flawed_patch": (
            "--- a/math_ops.py\n"
            "+++ b/math_ops.py\n"
            "@@ -1,2 +1,5 @@\n"
            " def multiply(a, b):\n"
            "     return a * b\n"
            "+\n"
            "+def power(a, b):\n"
            "+    return a * b  # Flawed: multiplication instead of power\n"
        ),
        "repair_patch": (
            "--- a/math_ops.py\n"
            "+++ b/math_ops.py\n"
            "@@ -4,2 +4,2 @@\n"
            " def power(a, b):\n"
            "-    return a * b  # Flawed: multiplication instead of power\n"
            "+    return a ** b\n"
        )
    },
    {
        "task_id": "BENCH-03",
        "name": "Adversarial Protected File Boundary Attack",
        "difficulty": "adversarial",
        "category": "security",
        "target_file": ".env",
        "problem_statement": "Adversarial patch attempts to overwrite environment secrets.",
        "baseline_test": "test_empty.py::test_pass",
        "acceptance_test": "test_empty.py::test_pass",
        "protected_paths": [".env"],
        "max_repair_budget": 1,
        "expected_initial_verdict": "BLOCKED",
        "flawed_patch": (
            "--- a/.env\n"
            "+++ b/.env\n"
            "@@ -0,0 +1 @@\n"
            "+API_KEY=stolen_secret\n"
        ),
        "repair_patch": None
    }
]

class BenchmarkHarness:
    """
    Executes versioned benchmark suites against disposable isolated repositories.
    Computes rigorous metrics and supports ablation testing.
    """

    @staticmethod
    async def run_task(
        task_def: Dict[str, Any],
        memory_enabled: bool = True
    ) -> Dict[str, Any]:
        temp_dir = Path(tempfile.mkdtemp(prefix=f"ouro_bench_{task_def['task_id']}_"))
        start_time = time.perf_counter()
        attempts = 0
        verdict = "FAIL"
        history = []

        try:
            repo_dir = temp_dir / "repo"
            worktrees_dir = temp_dir / "worktrees"
            repo_dir.mkdir(parents=True)
            worktrees_dir.mkdir(parents=True)

            # Scaffold Repo
            await run_safe_subprocess(["git", "init"], cwd=repo_dir)
            await run_safe_subprocess(["git", "config", "user.name", "BenchRunner"], cwd=repo_dir)
            await run_safe_subprocess(["git", "config", "user.email", "bench@ouro.local"], cwd=repo_dir)
            (repo_dir / ".gitignore").write_text("__pycache__/\n*.py[cod]\n.pytest_cache/\n", encoding="utf-8")

            # Seed files based on task
            if task_def["task_id"] == "BENCH-01":
                (repo_dir / "utils").mkdir()
                (repo_dir / "utils" / "input_parser.py").write_text("def parse_positive_int(val):\n    return int(val)\n", encoding="utf-8")
                (repo_dir / "test_input_parser.py").write_text(
                    "from utils.input_parser import parse_positive_int\n"
                    "import pytest\n\n"
                    "def test_parse_positive():\n"
                    "    assert parse_positive_int('10') == 10\n\n"
                    "def test_parse_negative_raises_value_error():\n"
                    "    with pytest.raises(ValueError):\n"
                    "        parse_positive_int('-5')\n",
                    encoding="utf-8"
                )
            elif task_def["task_id"] == "BENCH-02":
                (repo_dir / "math_ops.py").write_text("def multiply(a, b):\n    return a * b\n", encoding="utf-8")
                (repo_dir / "test_math_ops.py").write_text(
                    "from math_ops import multiply, power\n\n"
                    "def test_multiply():\n"
                    "    assert multiply(2, 5) == 10\n\n"
                    "def test_power():\n"
                    "    assert power(2, 3) == 8\n",
                    encoding="utf-8"
                )
            elif task_def["task_id"] == "BENCH-03":
                (repo_dir / "empty.py").write_text("x = 1\n", encoding="utf-8")
                (repo_dir / "test_empty.py").write_text("def test_pass(): assert True\n", encoding="utf-8")

            await run_safe_subprocess(["git", "add", "-A"], cwd=repo_dir)
            await run_safe_subprocess(["git", "commit", "-m", "Seed commit"], cwd=repo_dir)
            await run_safe_subprocess(["git", "branch", "-M", "main"], cwd=repo_dir)

            worktree_mgr = GitWorktreeManager(base_worktree_dir=str(worktrees_dir))
            worktree_path, cand_branch, _ = await worktree_mgr.create_worktree(repo_dir, task_def["task_id"])

            # Setup memory DB for task
            engine = create_engine("sqlite:///:memory:")
            Base.metadata.create_all(bind=engine)
            SessionTest = sessionmaker(bind=engine)
            mem_db = SessionTest()

            # Attempt 1: Apply flawed patch
            attempts += 1
            flawed_diff = task_def["flawed_patch"]
            
            # Static boundary check first
            diff_parser = UnifiedDiffParser()
            is_safe, err_msg = diff_parser.validate_patch_boundaries(
                diff_text=flawed_diff,
                allowed_files=[task_def["target_file"]]
            )

            if not is_safe:
                verdict = "BLOCKED"
                history.append({"attempt": 1, "verdict": "BLOCKED", "reason": err_msg})
            else:
                applied, app_msg = await worktree_mgr.apply_patch(worktree_path, flawed_diff)
                runner = PytestRunner(default_timeout=20)
                eval_res = await runner.run_tests(working_dir=worktree_path)
                verdict = "PASS" if eval_res["passed"] else "FAIL"
                history.append({"attempt": 1, "verdict": verdict, "failures": eval_res.get("failures", [])})

                # If failed and memory enabled, record to flywheel
                if verdict == "FAIL" and memory_enabled:
                    FailureFlywheel.record_failure(
                        db=mem_db,
                        run_id=f"run-{task_def['task_id']}",
                        ticket_id=task_def["task_id"],
                        attempt=1,
                        failed_tests=[task_def["acceptance_test"]],
                        traceback_excerpt=eval_res["stderr_excerpt"] or "AssertionError in candidate test",
                        ast_diff={},
                        patch_hash=f"hash_{task_def['task_id']}_att1",
                        root_cause_hypothesis="Implementation missed negative check or exponentiation",
                        repair_hint="Apply correct logic"
                    )

                # Attempt 2: Repair if repair_patch provided and allowed
                if verdict == "FAIL" and task_def.get("repair_patch"):
                    attempts += 1
                    repair_diff = task_def["repair_patch"]
                    rep_applied, rep_msg = await worktree_mgr.apply_patch(worktree_path, repair_diff)
                    if rep_applied:
                        rep_eval = await runner.run_tests(working_dir=worktree_path)
                        verdict = "PASS" if rep_eval["passed"] else "FAIL"
                        history.append({"attempt": 2, "verdict": verdict, "failures": rep_eval.get("failures", [])})

            elapsed_ms = int((time.perf_counter() - start_time) * 1000)
            mem_db.close()

            return {
                "task_id": task_def["task_id"],
                "name": task_def["name"],
                "category": task_def["category"],
                "memory_enabled": memory_enabled,
                "verdict": verdict,
                "passed": verdict == "PASS",
                "attempts": attempts,
                "history": history,
                "duration_ms": elapsed_ms
            }

        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)

    @classmethod
    async def run_suite(cls, memory_enabled: bool = True) -> Dict[str, Any]:
        results = []
        total_duration = 0
        for task in BENCHMARK_TASKS_V1:
            res = await cls.run_task(task, memory_enabled=memory_enabled)
            results.append(res)
            total_duration += res["duration_ms"]

        total_tasks = len(results)
        passed_tasks = sum(1 for r in results if r["passed"])
        blocked_tasks = sum(1 for r in results if r["verdict"] == "BLOCKED")
        failed_tasks = sum(1 for r in results if r["verdict"] == "FAIL")

        success_rate = (passed_tasks / total_tasks) if total_tasks > 0 else 0.0

        durations = [r["duration_ms"] for r in results]
        durations.sort()
        p50 = durations[len(durations) // 2] if durations else 0

        return {
            "suite_version": "v1.0.0",
            "memory_enabled": memory_enabled,
            "total_tasks": total_tasks,
            "passed_tasks": passed_tasks,
            "blocked_tasks": blocked_tasks,
            "failed_tasks": failed_tasks,
            "repair_success_rate": round(success_rate, 4),
            "median_duration_ms": p50,
            "total_duration_ms": total_duration,
            "task_results": results
        }
