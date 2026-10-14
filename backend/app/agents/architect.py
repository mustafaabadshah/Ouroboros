from typing import Dict, Any, Optional
from app.agents.runtime import agent_runtime, extract_json_from_response
from app.schemas.ticket import TicketBase
from app.core.logging import logger

ARCHITECT_SYSTEM_PROMPT = """You are the Lead Systems Architect in Project Ouroboros.
Your purpose is to inspect grounded codebase AST and graph metadata, identify bounded technical debt, missing telemetry, or missing deterministic test coverage, and generate a single Jira-style engineering ticket.
Rules:
1. You MUST respond with ONLY a single valid JSON object. No conversational filler.
2. The ticket MUST be small, bounded, and testable via pytest.
3. NEVER propose large refactors, architectural rewrites, or modifying protected core engine logic (e.g. validator.py, stockfish.py, legality checks).
4. Strictly adhere to the requested schema keys:
   - title
   - problem_statement
   - motivation
   - current_behavior
   - desired_behavior
   - acceptance_criteria (list of strings)
   - proposed_tests (list of strings)
   - relevant_graph_entities (list of strings)
   - candidate_files (list of file paths)
   - risk_level (low, medium, high)
   - expected_complexity (small, medium, large)
   - estimated_resources
   - evidence (list of strings)
   - out_of_scope
"""

class ArchitectAgent:
    """
    Architect Agent.
    Identifies high-value, bounded technical debt or missing tests and produces structured tickets.
    """

    @staticmethod
    async def generate_ticket(
        repo_id: str,
        repo_summary: Dict[str, Any],
        target_focus: Optional[str] = None,
        force_mock: bool = False
    ) -> TicketBase:
        user_prompt = f"""Target Repository: {repo_id}
Architectural Structure:
{repo_summary}

Target Focus / Direction: {target_focus or "Identify missing telemetry, unhandled edge-case test coverage, or telemetry counters."}

Generate one high-value, bounded, low-risk engineering ticket in strict JSON format."""

        res = await agent_runtime.execute_task(
            role="Architect",
            prompt=user_prompt,
            system_instruction=ARCHITECT_SYSTEM_PROMPT,
            force_mock=force_mock
        )

        content = res.get("content", "")
        try:
            data = extract_json_from_response(content)
            ticket = TicketBase.model_validate(data)
            logger.info(f"Architect generated ticket: '{ticket.title}'")
            return ticket
        except Exception as e:
            logger.error(f"Architect response failed schema validation: {e}. Raw content: {content[:200]}")
            # Fallback safe default ticket
            return TicketBase(
                title="Add telemetry and deterministic test for agent emergency fallback",
                problem_statement="GroqChessAgent falls back to emergency moves without recording error taxonomy counters in match summary telemetry.",
                motivation="Improve tournament observability and ensure fallback frequency is tracked accurately.",
                current_behavior="Emergency moves are tagged as 'fallback' but tournament summary statistics do not aggregate fallback rates.",
                desired_behavior="Expose fallback_count in tournament match telemetry.",
                acceptance_criteria=[
                    "MoveModel records move_source='fallback' on emergency triggers",
                    "A new deterministic unit test validates fallback move creation without network calls",
                    "Existing 19 baseline tests continue to pass with 0 regressions"
                ],
                proposed_tests=[
                    "backend/tests/test_agents.py::test_groq_agent_emergency_fallback_telemetry"
                ],
                relevant_graph_entities=[
                    "GroqChessAgent._select_emergency_move",
                    "MoveModel.move_source"
                ],
                candidate_files=[
                    "backend/app/agents/groq_agent.py"
                ],
                risk_level="low",
                expected_complexity="small",
                estimated_resources="1 LLM call, 1 pytest run",
                evidence=["backend/app/agents/groq_agent.py:225"],
                out_of_scope="Do not modify backend/app/chess/validator.py or legality rules."
            )

architect_agent = ArchitectAgent()
