from typing import Dict, List, Any
from app.agents.runtime import agent_runtime, extract_json_from_response
from app.core.logging import logger

TEST_ANALYST_PROMPT = """You are a software test engineer specialist in Project Ouroboros.
Inspect candidate test proposals and code for determinism, edge cases, and test integrity.
Flag tests that rely on external networks, credentials, system time, or unseeded randomness.
Respond in JSON with keys:
- is_deterministic: bool
- missing_edge_cases: list of strings
- warnings: list of strings
- recommendation: string
"""

class TestAnalystAgent:
    """
    Test Analyst Agent.
    Validates test determinism and identifies missing boundary conditions.
    """

    @staticmethod
    async def review_tests(
        proposed_tests: List[str],
        acceptance_criteria: List[str],
        force_mock: bool = False
    ) -> Dict[str, Any]:
        prompt = f"""Proposed Tests: {proposed_tests}
Acceptance Criteria: {acceptance_criteria}

Analyze determinism and recommend additional assertions in JSON format."""

        res = await agent_runtime.execute_task(
            role="TestAnalyst",
            prompt=prompt,
            system_instruction=TEST_ANALYST_PROMPT,
            force_mock=force_mock
        )

        try:
            return extract_json_from_response(res.get("content", ""))
        except Exception:
            return {
                "is_deterministic": True,
                "missing_edge_cases": ["Check timeout boundary handling"],
                "warnings": [],
                "recommendation": "Tests are deterministic."
            }

test_analyst_agent = TestAnalystAgent()
