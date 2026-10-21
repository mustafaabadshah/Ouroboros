from pathlib import Path
from typing import Dict, List, Any, Optional, Tuple
from app.core.logging import logger
from app.core.security import validate_safe_path
from app.integrations.git.diff_parser import UnifiedDiffParser
from app.evaluation.ast_analyzer import ASTChangeAnalyzer
from app.evaluation.runner import pytest_runner
from app.evaluation.failure_context import FailureContextNormalizer

class DeterministicJudge:
    """
    Ordinary deterministic application code (NOT an LLM).
    Authority of truth for candidate evaluation.
    Enforces regression gates, acceptance tests, and AST safety policies.
    """

    @staticmethod
    def _simulate_patched_content(original_content: str, diff_text: str, rel_file: str) -> str:
        """
        Simulates the post-patch content of rel_file in memory using unified diff hunks.
        Ensures that AST syntax checks evaluate the candidate code after changes,
        preventing false rejections when a patch is fixing an existing baseline syntax error.
        """
        import re
        norm_rel = rel_file.replace("\\", "/").lower()

        hunk_blocks = re.split(r"(^@@\s+-\d+(?:,\d+)?\s+\+\d+(?:,\d+)?\s+@@.*$)", diff_text, flags=re.MULTILINE)
        modified_content = original_content

        for i in range(1, len(hunk_blocks), 2):
            hunk_body = hunk_blocks[i + 1] if i + 1 < len(hunk_blocks) else ""
            hunk_lines = [l for l in hunk_body.splitlines() if not l.startswith("---") and not l.startswith("+++")]
            old_lines = [l[1:] for l in hunk_lines if l.startswith(" ") or l.startswith("-")]
            new_lines = [l[1:] for l in hunk_lines if l.startswith(" ") or l.startswith("+")]

            old_block = "\n".join(old_lines)
            new_block = "\n".join(new_lines)

            if old_block and old_block in modified_content:
                modified_content = modified_content.replace(old_block, new_block, 1)

        # If file is brand new, assemble from added lines
        if not original_content.strip() and not modified_content.strip():
            added_lines = [l[1:] for l in diff_text.splitlines() if l.startswith("+") and not l.startswith("+++")]
            if added_lines:
                modified_content = "\n".join(added_lines)

        return modified_content

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
            f_ctx = FailureContextNormalizer.from_patch_error(diff_meta["error"])
            return {
                "verdict": "BLOCKED",
                "reason": f"Malformed patch: {diff_meta['error']}",
                "ast_analysis": {},
                "failure_context": f_ctx.to_dict()
            }

        # Check allowed files scope
        if allowed_files:
            allowed_normalized = [f.replace("\\", "/").lower() for f in allowed_files]
            for modified in diff_meta["changed_files"]:
                mod_clean = modified.lower()
                if not any(mod_clean.endswith(allow) or allow.endswith(mod_clean) for allow in allowed_normalized):
                    reason_msg = f"Out-of-scope modification: '{modified}' is not in allowed files {allowed_files}."
                    f_ctx = FailureContextNormalizer.from_static_policy(
                        rule_id="boundary_scope",
                        reason=reason_msg,
                        allowed_requirement=f"Modify only files in {allowed_files}.",
                        target_file=modified
                    )
                    return {
                        "verdict": "BLOCKED",
                        "reason": reason_msg,
                        "ast_analysis": {},
                        "failure_context": f_ctx.to_dict(),
                        "policy_rule_id": "boundary_scope",
                        "policy_requirement": f"Modify only files in {allowed_files}."
                    }

        if diff_meta["protected_files_touched"]:
            reason_msg = f"Patch touches protected engine files: {diff_meta['protected_files_touched']}"
            f_ctx = FailureContextNormalizer.from_static_policy(
                rule_id="protected_path",
                reason=reason_msg,
                allowed_requirement="Protected engine files may not be modified by automated repair.",
                target_file=str(diff_meta["protected_files_touched"])
            )
            return {
                "verdict": "NEEDS_HUMAN_REVIEW",
                "reason": reason_msg,
                "ast_analysis": {},
                "failure_context": f_ctx.to_dict(),
                "policy_rule_id": "protected_path",
                "policy_requirement": "Protected engine files may not be modified by automated repair."
            }
        from app.sandbox.security import analyze_code_security

        # 2. Check AST syntax, security violations, and symbol safety on changed files
        ast_results = {}
        for rel_file in diff_meta["changed_files"]:
            try:
                file_path = validate_safe_path(worktree_path, rel_file)
            except ValueError as ve:
                f_ctx = FailureContextNormalizer.from_static_policy(
                    rule_id="path_traversal",
                    reason=str(ve),
                    allowed_requirement="Paths must remain strictly within workspace boundary.",
                    target_file=rel_file
                )
                return {
                    "verdict": "BLOCKED",
                    "reason": f"Path Security Violation: {ve}",
                    "ast_analysis": {},
                    "failure_context": f_ctx.to_dict(),
                    "policy_rule_id": "path_traversal",
                    "policy_requirement": "Paths must remain strictly within workspace boundary."
                }
            if file_path.suffix == ".py":
                try:
                    original_content = ""
                    if file_path.exists():
                        with open(file_path, "r", encoding="utf-8") as f:
                            original_content = f.read()

                    # Simulate applying diff hunks to original_content to validate post-patch syntax
                    code_content = DeterministicJudge._simulate_patched_content(original_content, diff_text, rel_file)

                    # A. Static AST Syntax Check
                    tree, syntax_err = ASTChangeAnalyzer.parse_python_ast(code_content, rel_file)
                    if syntax_err:
                        f_ctx = FailureContextNormalizer.from_patch_error(
                            error_msg=f"Syntax error introduced in {rel_file}: {syntax_err}",
                            target_file=rel_file
                        )
                        return {
                            "verdict": "FAIL",
                            "reason": f"Syntax error introduced in {rel_file}: {syntax_err}",
                            "ast_analysis": {rel_file: {"syntax_valid": False, "error": syntax_err}},
                            "failure_context": f_ctx.to_dict()
                        }

                    # B. Static AST Security Analysis
                    sec_res = analyze_code_security(code_content, filename=rel_file)
                    if not sec_res["is_safe"]:
                        p_calls = sec_res.get("details", {}).get("prohibited_calls", [])
                        p_imps = sec_res.get("details", {}).get("prohibited_imports", [])
                        rule_id = "security_policy"
                        requirement = "Use standard algorithms and higher-level libraries without prohibited calls or imports."
                        if p_calls:
                            rule_id = p_calls[0].get("rule_id", "prohibited_primitive")
                            requirement = p_calls[0].get("requirement", requirement)
                        elif p_imps:
                            rule_id = p_imps[0].get("rule_id", "prohibited_module")
                            requirement = p_imps[0].get("requirement", requirement)

                        sec_reason = f"Security Policy Violation in {rel_file}: {'; '.join(sec_res['violations'])}"
                        f_ctx = FailureContextNormalizer.from_static_policy(
                            rule_id=rule_id,
                            reason=sec_reason,
                            allowed_requirement=requirement,
                            target_file=rel_file
                        )
                        return {
                            "verdict": "BLOCKED",
                            "reason": sec_reason,
                            "ast_analysis": {rel_file: {"security_violations": sec_res["violations"]}},
                            "failure_context": f_ctx.to_dict(),
                            "policy_rule_id": rule_id,
                            "policy_requirement": requirement
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
        impact_test_files: Optional[List[str]] = None,
        regression_test_dir: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Runs AST-directed impact tests first (fail-fast within 2-3s), then full regression suite.
        Compares outcomes against baseline to prevent any collateral regressions.
        """
        logger.info(f"DeterministicJudge evaluating candidate in {worktree_path}")

        # 1. AST-Directed Impact Tests (Fail-Fast Priority)
        impact_tests_to_run = list(impact_test_files or [])
        if acceptance_test_file and acceptance_test_file not in impact_tests_to_run:
            impact_tests_to_run.insert(0, acceptance_test_file)

        acceptance_res = None
        for impact_file in impact_tests_to_run:
            test_path_obj = worktree_path / impact_file
            if test_path_obj.exists():
                logger.info(f"[Fail-Fast Gate] Executing AST-directed impact test: {impact_file}")
                impact_res = await pytest_runner.run_tests(
                    working_dir=worktree_path,
                    test_path=impact_file
                )
                if not impact_res["passed"]:
                    logger.warning(f"[Fail-Fast Gate] Impact test {impact_file} failed in {impact_res.get('duration_ms', 0)}ms. Aborting early.")
                    return {
                        "verdict": "FAIL",
                        "is_fail_fast": True,
                        "fail_fast_test": impact_file,
                        "duration_ms": impact_res.get("duration_ms", 0),
                        "reason": f"Acceptance tests failed (⚡ Fail-Fast Gate Triggered: {impact_file} failed in {impact_res.get('duration_ms', 0)}ms with {impact_res['failed_count']} failed, {impact_res['error_count']} errors). Aborted regression suite to trigger repair in 3s.",
                        "acceptance": impact_res,
                        "regression": impact_res,
                        "impact_failure_file": impact_file
                    }
                if not acceptance_res:
                    acceptance_res = impact_res

        # 2. Run Full Regression Suite (Zero Collateral Breakage Verification)
        regression_target = regression_test_dir or "backend/tests"
        logger.info(f"[Regression Gate] Executing full regression suite across {regression_target}...")
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
