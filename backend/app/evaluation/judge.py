from pathlib import Path
from typing import Dict, List, Any, Optional, Tuple
from app.core.logging import logger
from app.core.security import validate_safe_path
from app.integrations.git.diff_parser import UnifiedDiffParser
from app.evaluation.ast_analyzer import ASTChangeAnalyzer
from app.evaluation.runner import pytest_runner

class DeterministicJudge:
    """
    Ordinary deterministic application code (NOT an LLM).
    Authority of truth for candidate evaluation.
    Enforces regression gates, acceptance tests, and AST safety policies.
    """

    @staticmethod
    def evaluate_patch_static(
        diff_text: str,
        allowed_files: List[str],
        worktree_path: Path
    ) -> Dict[str, Any]:
        """
        Runs static syntax, patch size, and protected file policies.
        """
        # 1. Parse and validate diff
        diff_meta = UnifiedDiffParser.parse_patch(diff_text)
        if not diff_meta["is_valid"]:
            return {
                "verdict": "BLOCKED",
                "reason": f"Malformed patch: {diff_meta['error']}",
                "ast_analysis": {}
            }

        # Check allowed files scope
        if allowed_files:
            allowed_normalized = [f.replace("\\", "/").lower() for f in allowed_files]
            for modified in diff_meta["changed_files"]:
                mod_clean = modified.lower()
                if not any(mod_clean.endswith(allow) or allow.endswith(mod_clean) for allow in allowed_normalized):
                    return {
                        "verdict": "BLOCKED",
                        "reason": f"Out-of-scope modification: '{modified}' is not in allowed files {allowed_files}.",
                        "ast_analysis": {}
                    }

        if diff_meta["protected_files_touched"]:
            return {
                "verdict": "NEEDS_HUMAN_REVIEW",
                "reason": f"Patch touches protected engine files: {diff_meta['protected_files_touched']}",
                "ast_analysis": {}
            }
        from app.sandbox.security import analyze_code_security

        # 2. Check AST syntax, security violations, and symbol safety on changed files
        ast_results = {}
        for rel_file in diff_meta["changed_files"]:
            try:
                file_path = validate_safe_path(worktree_path, rel_file)
            except ValueError as ve:
                return {
                    "verdict": "BLOCKED",
                    "reason": f"Path Security Violation: {ve}",
                    "ast_analysis": {}
                }
            if file_path.exists() and file_path.suffix == ".py":
                try:
                    with open(file_path, "r", encoding="utf-8") as f:
                        code_content = f.read()

                    # A. Static AST Syntax Check
                    tree, syntax_err = ASTChangeAnalyzer.parse_python_ast(code_content, rel_file)
                    if syntax_err:
                        return {
                            "verdict": "FAIL",
                            "reason": f"Syntax error introduced in {rel_file}: {syntax_err}",
                            "ast_analysis": {rel_file: {"syntax_valid": False, "error": syntax_err}}
                        }

                    # B. Static AST Security Analysis
                    sec_res = analyze_code_security(code_content, filename=rel_file)
                    if not sec_res["is_safe"]:
                        return {
                            "verdict": "BLOCKED",
                            "reason": f"Security Policy Violation in {rel_file}: {'; '.join(sec_res['violations'])}",
                            "ast_analysis": {rel_file: {"security_violations": sec_res["violations"]}}
                        }

                    symbols = ASTChangeAnalyzer.extract_symbols(tree)
                    ast_results[rel_file] = {"syntax_valid": True, "symbols_count": len(symbols)}
                except Exception as e:
                    logger.warning(f"Failed to read file for AST analysis {file_path}: {e}")

        return {
            "verdict": "PASS",
            "reason": "Static syntax, security policy, and diff checks passed.",
            "ast_analysis": ast_results
        }

    @staticmethod
    async def evaluate_candidate(
        worktree_path: Path,
        baseline_results: Dict[str, Any],
        acceptance_test_file: Optional[str] = None,
        regression_test_dir: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Runs acceptance and regression test suites and compares outcomes against baseline.
        """
        logger.info(f"DeterministicJudge evaluating candidate in {worktree_path}")

        # 1. Run Candidate Acceptance Tests
        acceptance_res = None
        if acceptance_test_file and (worktree_path / acceptance_test_file).exists():
            acceptance_res = await pytest_runner.run_tests(
                working_dir=worktree_path,
                test_path=acceptance_test_file
            )
            if not acceptance_res["passed"]:
                return {
                    "verdict": "FAIL",
                    "reason": f"Acceptance tests failed ({acceptance_res['failed_count']} failed, {acceptance_res['error_count']} errors).",
                    "acceptance": acceptance_res,
                    "regression": None
                }

        # 2. Run Regression Suite
        regression_target = regression_test_dir or "backend/tests"
        regression_res = await pytest_runner.run_tests(
            working_dir=worktree_path,
            test_path=regression_target
        )

        # 3. Compare Regression against Baseline
        baseline_failed = baseline_results.get("failed_count", 0) + baseline_results.get("error_count", 0)
        candidate_failed = regression_res["failed_count"] + regression_res["error_count"]

        # If candidate introduced NEW failures not present in baseline -> REGRESSION!
        if candidate_failed > baseline_failed:
            return {
                "verdict": "FAIL",
                "reason": f"Regression detected: Candidate failed {candidate_failed} tests compared to baseline {baseline_failed}.",
                "acceptance": acceptance_res,
                "regression": regression_res
            }

        verdict = "PASS" if regression_res["passed"] else ("FAIL" if candidate_failed > baseline_failed else "NEEDS_HUMAN_REVIEW")
        from app.observability.phoenix_service import phoenix_service
        try:
            phoenix_service.record_evaluator_span(
                name="deterministic_harness",
                run_id=str(worktree_path.name),
                ticket_id=str(worktree_path.name),
                verdict=verdict,
                tests_passed=regression_res.get("passed_count", 0),
                tests_failed=regression_res.get("failed_count", 0),
                duration_ms=float(regression_res.get("duration_ms", 0)),
                ast_changes=[]
            )
        except Exception as ex:
            logger.debug(f"Phoenix evaluator span recording skipped: {ex}")

        # If regression suite passed completely
        if regression_res["passed"]:
            return {
                "verdict": "PASS",
                "reason": "All acceptance and regression gates passed with 0 regressions.",
                "acceptance": acceptance_res,
                "regression": regression_res
            }

        # Ambiguous baseline failure carrying over
        return {
            "verdict": "NEEDS_HUMAN_REVIEW",
            "reason": f"Baseline had failures ({baseline_failed}) and candidate matched without new regressions.",
            "acceptance": acceptance_res,
            "regression": regression_res
        }

deterministic_judge = DeterministicJudge()
