"""
Project Ouroboros v0.11 - Real-Repository Repair Pilot Suite
Evaluates agent repair capabilities on isolated real-repository bug fixtures
with reproducible original defects, separate regression test suites,
strict patch-scope boundaries, and zero reference-leakage.
"""

import os
import sys
import time
import uuid
import shutil
import hashlib
import tempfile
import difflib
from pathlib import Path
from typing import Dict, List, Any, Optional

def generate_unified_diff(original: str, modified: str, file_path: str) -> str:
    orig_lines = original.splitlines(keepends=True)
    mod_lines = modified.splitlines(keepends=True)
    diff = difflib.unified_diff(
        orig_lines,
        mod_lines,
        fromfile=f"a/{file_path}",
        tofile=f"b/{file_path}"
    )
    return "".join(diff)

from app.core.security import run_safe_subprocess, validate_safe_path
from app.integrations.git.worktree import GitWorktreeManager
from app.integrations.git.diff_parser import UnifiedDiffParser
from app.evaluation.runner import PytestRunner
from app.evaluation.judge import DeterministicJudge
from app.schemas.eval_contract import EvaluationOutcome, EvaluationTaskRecord, AttemptRecord
from app.agents.local_coder import local_coder_agent
from app.agents.coder_lead import coder_lead
from app.agents.repair_agent import repair_agent
from app.memory.flywheel import FailureFlywheel
from app.database.session import Base
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker


REAL_REPO_FIXTURES: List[Dict[str, Any]] = [
    {
        "fixture_id": "REAL-REPO-01",
        "name": "fastapi_jwt_auth",
        "description": "JWT expiration boundary condition rejects valid token at exact boundary second",
        "defect_summary": "jwt_handler checks `now > exp` instead of `now >= exp` with leeway allowance, causing edge-case rejections at exact boundary.",
        "target_file": "auth/jwt_handler.py",
        "allowed_patch_scope": ["auth/jwt_handler.py"],
        "protected_paths": [".env", "config/keys.pem", ".git"],
        "seed_files": {
            "auth/__init__.py": "",
            "auth/jwt_handler.py": '''"""JWT validation handler with leeway allowance."""
import time

def verify_token(payload: dict, leeway_seconds: int = 0) -> bool:
    current_time = int(time.time())
    exp = payload.get("exp")
    if exp is None:
        return False
    # DEFECT: strictly rejects if current_time >= exp before applying leeway
    if current_time >= exp:
        return False
    if current_time > (exp + leeway_seconds):
        return False
    return True
''',
            "tests/__init__.py": "",
            "tests/test_auth.py": '''import time
from auth.jwt_handler import verify_token

def test_existing_valid_token_and_invalid():
    # Existing regression test
    now = int(time.time())
    assert verify_token({"exp": now + 3600}) is True
    assert verify_token({"exp": now - 3600}) is False

def test_token_exact_second_boundary():
    # Failing test reproducing the defect
    now = int(time.time())
    # A token with 5 seconds leeway should be valid when current_time == exp
    assert verify_token({"exp": now}, leeway_seconds=5) is True
    # At exact expiration without leeway, it should be expired
    assert verify_token({"exp": now}, leeway_seconds=0) is False
'''
        },
        "test_path": "tests/test_auth.py",
        "test_command": [sys.executable, "-m", "pytest", "tests/test_auth.py", "-v"]
    },
    {
        "fixture_id": "REAL-REPO-02",
        "name": "dataclass_csv_parser",
        "description": "Streaming CSV parser mishandles escaped quote delimiters inside quoted columns",
        "defect_summary": "csv_stream splitter splits on quotes naively without tracking escape sequences.",
        "target_file": "parser/csv_stream.py",
        "allowed_patch_scope": ["parser/csv_stream.py"],
        "protected_paths": [".env", ".git"],
        "seed_files": {
            "parser/__init__.py": "",
            "parser/csv_stream.py": '''"""CSV streaming record splitter."""
from typing import List

def parse_csv_line(line: str) -> List[str]:
    # DEFECT: naive split fails on quotes with escaped quotes
    if '""' in line:
        # flawed replacement
        return [col.strip() for col in line.split(",")]
    parts = []
    current = []
    in_quotes = False
    for char in line:
        if char == '"':
            in_quotes = not in_quotes
        elif char == ',' and not in_quotes:
            parts.append("".join(current).strip())
            current = []
            continue
        current.append(char)
    parts.append("".join(current).strip())
    return parts
''',
            "tests/__init__.py": "",
            "tests/test_parser.py": '''from parser.csv_stream import parse_csv_line

def test_standard_tabular_rows():
    # Regression test
    res = parse_csv_line("apple,banana,orange")
    assert res == ["apple", "banana", "orange"]

def test_multiline_escaped_quote_field():
    # Failing reproduction test
    line = '123,"Item with ""quoted"" word",45.67'
    res = parse_csv_line(line)
    assert len(res) == 3
    assert res[0] == "123"
    assert "quoted" in res[1]
    assert res[2] == "45.67"
'''
        },
        "test_path": "tests/test_parser.py",
        "test_command": [sys.executable, "-m", "pytest", "tests/test_parser.py", "-v"]
    },
    {
        "fixture_id": "REAL-REPO-03",
        "name": "lru_ttl_cache",
        "description": "TTL eviction fails to purge expired node from linked list leading to memory accumulation",
        "defect_summary": "Cache marks key expired in dict but leaves node in doubly linked list.",
        "target_file": "cache/lru_ttl.py",
        "allowed_patch_scope": ["cache/lru_ttl.py"],
        "protected_paths": [".env", ".git"],
        "seed_files": {
            "cache/__init__.py": "",
            "cache/lru_ttl.py": '''"""LRU TTL In-Memory Cache."""
import time
from typing import Any

class LRUTTLCache:
    def __init__(self, capacity: int = 10):
        self.capacity = capacity
        self.store = {}
        self.ttl = {}
        self.node_count = 0

    def set(self, key: str, value: Any, ttl_seconds: int = 60):
        self.store[key] = value
        self.ttl[key] = time.time() + ttl_seconds
        self.node_count += 1

    def get(self, key: str):
        if key not in self.store:
            return None
        if time.time() > self.ttl[key]:
            # DEFECT: deletes from dict but leaves node_count unincremented / list unpurged
            del self.store[key]
            del self.ttl[key]
            # Missing: self.node_count -= 1
            return None
        return self.store[key]

    def active_node_count(self) -> int:
        return self.node_count
''',
            "tests/__init__.py": "",
            "tests/test_cache.py": '''import time
from cache.lru_ttl import LRUTTLCache

def test_lru_capacity_order():
    # Regression test
    c = LRUTTLCache(capacity=5)
    c.set("a", 1, ttl_seconds=100)
    assert c.get("a") == 1

def test_ttl_eviction_purges_node():
    # Failing reproduction test
    c = LRUTTLCache(capacity=5)
    c.set("temp", 99, ttl_seconds=-1)  # expired immediately
    assert c.get("temp") is None
    assert c.active_node_count() == 0  # fails because node_count is not decremented
'''
        },
        "test_path": "tests/test_cache.py",
        "test_command": [sys.executable, "-m", "pytest", "tests/test_cache.py", "-v"]
    }
]


class RealRepoEvaluator:
    """
    Executes real-repository evaluations against isolated bug fixtures.
    Follows strict safety protocols:
    - Preflight defect confirmation
    - Disposable Git worktree isolation
    - Scope enforcement (zero modifications outside permitted files)
    - Regression prevention
    - Zero human checkout modification
    """

    @classmethod
    async def evaluate_fixture(
        cls,
        fixture: Dict[str, Any],
        force_mock: bool = False,
        dry_run: bool = False,
        max_attempts: int = 2
    ) -> Dict[str, Any]:
        """Runs the complete repair and qualification protocol on a real-repo fixture."""
        fixture_id = fixture["fixture_id"]
        start_time = time.perf_counter()
        temp_dir = Path(tempfile.mkdtemp(prefix=f"ouro_realrepo_{fixture_id}_"))

        try:
            repo_dir = temp_dir / "fixture_repo"
            worktrees_dir = temp_dir / "worktrees"
            repo_dir.mkdir(parents=True)
            worktrees_dir.mkdir(parents=True)

            # 1. Initialize Git repository
            await run_safe_subprocess(["git", "init"], cwd=repo_dir)
            await run_safe_subprocess(["git", "config", "user.name", "RealRepoEvaluator"], cwd=repo_dir)
            await run_safe_subprocess(["git", "config", "user.email", "eval@realrepo.local"], cwd=repo_dir)
            (repo_dir / ".gitignore").write_text("__pycache__/\n*.py[cod]\n.pytest_cache/\n", encoding="utf-8")

            # Seed fixture files
            for rel_p, content in fixture["seed_files"].items():
                p = repo_dir / rel_p
                p.parent.mkdir(parents=True, exist_ok=True)
                p.write_text(content, encoding="utf-8")

            await run_safe_subprocess(["git", "add", "."], cwd=repo_dir)
            await run_safe_subprocess(["git", "commit", "-m", "Initial fixture state with reproducible defect"], cwd=repo_dir)

            if dry_run:
                return {
                    "fixture_id": fixture_id,
                    "name": fixture["name"],
                    "verdict": "SKIPPED",
                    "outcome": EvaluationOutcome.CANCELLED,
                    "duration_ms": 0,
                    "message": "Dry-run execution requested."
                }

            # 2. Step 1: Preflight Defect Confirmation
            # The test must reproduce failure on initial checkout
            runner = PytestRunner()
            preflight_res = await runner.run_tests(
                working_dir=repo_dir,
                test_path=fixture.get("test_path", "tests")
            )

            if preflight_res.get("exit_code") == 0:
                # The fixture is invalid if the bug does not reproduce!
                return {
                    "fixture_id": fixture_id,
                    "name": fixture["name"],
                    "verdict": "INVALID",
                    "outcome": EvaluationOutcome.INVALID_RESULT,
                    "duration_ms": int((time.perf_counter() - start_time) * 1000),
                    "error_detail": "Fixture failed preflight check: original defect did not reproduce (tests passed on broken codebase)."
                }

            # 3. Create disposable Git worktree
            # 3. Create disposable Git worktree
            wt_manager = GitWorktreeManager(base_worktree_dir=str(worktrees_dir))
            worktree_path, candidate_branch, base_commit = await wt_manager.create_worktree(
                repo_path=repo_dir,
                ticket_id=f"cand-{fixture_id.lower()}"
            )

            # 4. Generate candidate patch
            target_file_rel = fixture["target_file"]
            target_full = worktree_path / target_file_rel
            current_code = target_full.read_text(encoding="utf-8")

            code_prompt = (
                f"Fix the defect in {target_file_rel}:\n"
                f"Problem: {fixture['defect_summary']}\n"
                f"Code:\n```python\n{current_code}\n```"
            )

            # In mock mode, supply targeted correction for deterministic tests
            if force_mock:
                # Generate accurate synthetic fix for the targeted fixture
                if fixture_id == "REAL-REPO-01":
                    repaired_code = current_code.replace(
                        "if current_time >= exp:\n        return False\n    if current_time > (exp + leeway_seconds):",
                        "if current_time >= (exp + leeway_seconds):"
                    )
                elif fixture_id == "REAL-REPO-02":
                    repaired_code = current_code.replace("return [col.strip() for col in line.split(\",\")]", "pass # proper quote parsing")
                elif fixture_id == "REAL-REPO-03":
                    repaired_code = current_code.replace("del self.ttl[key]", "del self.ttl[key]\n            self.node_count -= 1")
                else:
                    repaired_code = current_code

                # Create synthetic unified diff
                diff_text = generate_unified_diff(
                    original=current_code,
                    modified=repaired_code,
                    file_path=target_file_rel
                )
                coder_res = {"diff_text": diff_text, "provider": "mock", "model": "mock-v1"}
            else:
                coder_res = await local_coder_agent.generate_patch(code_prompt)

            diff_text = coder_res.get("diff_text", "").strip()
            if not diff_text:
                return {
                    "fixture_id": fixture_id,
                    "name": fixture["name"],
                    "verdict": "FAIL",
                    "outcome": EvaluationOutcome.FAILED_REPAIR,
                    "duration_ms": int((time.perf_counter() - start_time) * 1000),
                    "error_detail": "Model synthesized empty patch diff."
                }

            # 5. Scope Validation: Ensure patch touches ONLY permitted files
            scope_check = DeterministicJudge.evaluate_patch_static(
                diff_text=diff_text,
                allowed_files=fixture["allowed_patch_scope"],
                worktree_path=worktree_path
            )

            if scope_check["verdict"] != "PASS":
                return {
                    "fixture_id": fixture_id,
                    "name": fixture["name"],
                    "verdict": "BLOCKED",
                    "outcome": EvaluationOutcome.BLOCKED_BY_POLICY,
                    "duration_ms": int((time.perf_counter() - start_time) * 1000),
                    "error_detail": f"Patch-scope violation: {scope_check.get('reason')}"
                }

            # 6. Apply patch in disposable worktree
            applied_ok, apply_err = await wt_manager.apply_patch(worktree_path, diff_text)
            if not applied_ok:
                return {
                    "fixture_id": fixture_id,
                    "name": fixture["name"],
                    "verdict": "FAIL",
                    "outcome": EvaluationOutcome.FAILED_REPAIR,
                    "duration_ms": int((time.perf_counter() - start_time) * 1000),
                    "error_detail": f"Failed to apply patch: {apply_err}"
                }

            # 7. Run test suite to verify fix & regression prevention
            candidate_test_res = await runner.run_tests(
                working_dir=worktree_path,
                test_path=fixture.get("test_path", "tests")
            )

            elapsed_ms = int((time.perf_counter() - start_time) * 1000)

            if candidate_test_res.get("exit_code") == 0:
                return {
                    "fixture_id": fixture_id,
                    "name": fixture["name"],
                    "verdict": "PASS",
                    "outcome": EvaluationOutcome.PASS,
                    "duration_ms": elapsed_ms,
                    "patch_diff": diff_text,
                    "tests_passed": candidate_test_res.get("passed_count", 0),
                    "tests_failed": candidate_test_res.get("failed_count", 0),
                    "message": "Original defect resolved and all regression tests passed."
                }
            else:
                return {
                    "fixture_id": fixture_id,
                    "name": fixture["name"],
                    "verdict": "FAIL",
                    "outcome": EvaluationOutcome.FAILED_REPAIR,
                    "duration_ms": elapsed_ms,
                    "patch_diff": diff_text,
                    "tests_passed": candidate_test_res.get("passed_count", 0),
                    "tests_failed": candidate_test_res.get("failed_count", 0),
                    "error_detail": f"Regression or unresolved test failures: {candidate_test_res.get('stderr_excerpt')}"
                }

        finally:
            def _rm_readonly(func, p, _):
                import stat
                try:
                    os.chmod(p, stat.S_IWRITE)
                    func(p)
                except Exception:
                    pass
            try:
                shutil.rmtree(temp_dir, onerror=_rm_readonly)
            except Exception:
                shutil.rmtree(temp_dir, ignore_errors=True)

    @classmethod
    async def evaluate_all(cls, force_mock: bool = False, dry_run: bool = False) -> Dict[str, Any]:
        """Runs the entire real-repository pilot suite."""
        results = []
        for fix in REAL_REPO_FIXTURES:
            res = await cls.evaluate_fixture(fix, force_mock=force_mock, dry_run=dry_run)
            results.append(res)

        total = len(results)
        passed = sum(1 for r in results if r["outcome"] == EvaluationOutcome.PASS)
        failed = sum(1 for r in results if r["outcome"] == EvaluationOutcome.FAILED_REPAIR)
        blocked = sum(1 for r in results if r["outcome"] == EvaluationOutcome.BLOCKED_BY_POLICY)
        invalid = sum(1 for r in results if r["outcome"] == EvaluationOutcome.INVALID_RESULT)

        return {
            "suite": "real_repository_repair_pilot",
            "schema_version": "v0.11.0",
            "fixtures_count": total,
            "repairs_passed": passed,
            "repairs_failed": failed,
            "policy_blocked": blocked,
            "invalid_fixtures": invalid,
            "success_rate": (passed / total) if total > 0 else 0.0,
            "results": results
        }
