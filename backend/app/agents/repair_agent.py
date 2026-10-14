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

        user_prompt = f"""Ticket: {ticket.get('title')}
Target File: {target_file}

FAILURE DIAGNOSTIC:
Failed Tests: {failed_tests}
Traceback Excerpt:
{traceback_snippet}

Prior Rejected Attempts:
{prior_history}

Current File Content:
```python
{current_code[:3000]}
```

Analyze why the previous patch failed and provide a corrected Unified Diff patch."""

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
            "model": res.get("model")
        }

repair_agent = RepairAgent()
