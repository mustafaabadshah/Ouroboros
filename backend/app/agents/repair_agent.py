from typing import Dict, Any, Optional
from app.agents.runtime import agent_runtime
from app.agents.local_coder import LocalCoderAgent
from app.core.logging import logger

REPAIR_SYSTEM_PROMPT = """You are the Lead Code Repair Specialist in Project Ouroboros.
Your purpose is to inspect the exact failure trajectory of a broken candidate patch, analyze the traceback and failed assertions, and synthesize a minimal, targeted replacement patch.
Rules:
1. DO NOT repeat previously rejected approaches or syntax.
2. Read the traceback carefully to locate the exact failing line or assertion.
3. Respond with a valid Unified Diff inside ```diff ... ``` code blocks.
4. CRITICAL PYTHON SYNTAX: Every compound statement ('with', 'try', 'except', 'def', 'class', 'if', 'for', 'while') MUST contain valid indented body statements. Never leave an empty or unindented block.
5. UNIFIED DIFF INTEGRITY: Context lines (starting with a single space ' ') must exactly match the existing file content. Ensure all modifications apply cleanly without syntax or indentation errors.
"""

class RepairAgent:
    """
    Repair Agent.
    Synthesizes targeted replacement patches based on persistent failure trajectory memory.
    """

    @staticmethod
    async def synthesize_repair(
        ticket: Dict[str, Any],
        target_file: str,
        current_code: str,
        failure_trajectory: Dict[str, Any],
        force_mock: bool = False
    ) -> Dict[str, Any]:
        failed_tests = failure_trajectory.get("failed_tests", [])
        traceback_snippet = failure_trajectory.get("traceback", "")
        prior_history = failure_trajectory.get("prior_attempts", [])
        formatted_diagnostic = failure_trajectory.get("formatted_diagnostic")

        if formatted_diagnostic:
            diag_body = formatted_diagnostic
        else:
            lines = []
            if failed_tests:
                lines.append(f"Failed Tests: {', '.join(failed_tests)}")
            if failure_trajectory.get("assertion"):
                lines.append(f"Assertion: {failure_trajectory['assertion']}")
            if failure_trajectory.get("expected") or failure_trajectory.get("actual"):
                lines.append(f"Expected: {failure_trajectory.get('expected')}")
                lines.append(f"Actual:   {failure_trajectory.get('actual')}")
            if failure_trajectory.get("policy_rule_id"):
                lines.append(f"Policy Rule: [{failure_trajectory['policy_rule_id']}] {failure_trajectory.get('policy_reason')}")
                if failure_trajectory.get("policy_requirement"):
                    lines.append(f"Requirement: {failure_trajectory['policy_requirement']}")
            if traceback_snippet:
                lines.append(f"Traceback:\n{traceback_snippet}")
            diag_body = "\n".join(lines) if lines else "Test assertion failed."

        # Negative Hypothesis Pruning
        pruned_antipatterns = []
        for p in prior_history:
            hsh = p.get('patch_hash') or 'unknown'
            tb_short = (p.get('traceback') or '')[:120].replace('\n', ' ')
            pruned_antipatterns.append(
                f"- Attempt {p.get('attempt')} (patch: {hsh}): {tb_short}. Prohibited: DO NOT reproduce this diff!"
            )
        anti_pattern_text = "\n".join(pruned_antipatterns) if pruned_antipatterns else "None (first repair attempt)"

        # Swarm Institutional Memory (Cross-Ticket Lessons)
        cross_insights = failure_trajectory.get("cross_ticket_insights", [])
        cross_summary = []
        for ci in cross_insights:
            cross_summary.append(
                f"- Past Ticket {ci.get('source_ticket_id')}: {ci.get('repair_hint')} (Hypothesis: {ci.get('root_cause_hypothesis', '')[:100]})"
            )
        cross_text = "\n".join(cross_summary) if cross_summary else "No cross-ticket historical patterns found"

        user_prompt = f"""Ticket: {ticket.get('title')}
Target File: {target_file}

STRUCTURED FAILURE DIAGNOSTICS:
{diag_body}

NEGATIVE HYPOTHESIS PRUNING (PROHIBITED APPROACHES):
{anti_pattern_text}

SWARM INSTITUTIONAL MEMORY (PROVEN CROSS-TICKET LESSONS):
{cross_text}

Current File Content:
```python
{current_code[:3500]}
```

Analyze the failure diagnostics, avoid all pruned negative hypotheses, synthesize lessons from institutional memory, and provide a corrected Unified Diff patch."""

        res = await agent_runtime.execute_task(
            role="RepairAgent",
            prompt=user_prompt,
            system_instruction=REPAIR_SYSTEM_PROMPT,
            force_mock=force_mock
        )

        content = res.get("content", "")
        diff_text = LocalCoderAgent.extract_diff(content)
        return {
            "diff_text": diff_text,
            "explanation": content.replace(diff_text, "").strip()[:500],
            "provider": res.get("provider"),
            "model": res.get("model"),
            "input_tokens": res.get("input_tokens"),
            "output_tokens": res.get("output_tokens"),
            "is_error": res.get("is_error", False),
            "error_message": res.get("error_message")
        }

repair_agent = RepairAgent()
