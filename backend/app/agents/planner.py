from typing import Dict, List, Any
from app.agents.runtime import agent_runtime, extract_json_from_response
from app.integrations.graph.adapter import meta_graph_adapter
from app.core.logging import logger

PLANNER_SYSTEM_PROMPT = """You are the Lead Planning Engineer in Project Ouroboros.
Your purpose is to read an approved feature ticket, query graph dependencies, map requirements to specific files and symbols, and produce a bounded execution plan with subtasks, file ownership, and completion conditions.
Rules:
1. Respond with ONLY valid JSON.
2. Structure:
   - ordered_subtasks: list of objects {subtask_id, description, target_file, relevant_symbols, completion_condition}
   - file_ownership: dict mapping target_file to agent owner
   - protected_files: list of files that must NOT be modified
   - risk_warnings: list of cautionary notes
3. Never fabricate nonexistent dependencies or files.
"""

class PlannerAgent:
    """
    Planner Agent.
    Deconstructs approved tickets into dependency-aware subtasks with clear file ownership.
    """

    @staticmethod
    async def create_plan(
        repo_id: str,
        ticket: Dict[str, Any],
        force_mock: bool = False
    ) -> Dict[str, Any]:
        candidate_files = ticket.get("candidate_files", [])
        graph_context = {}
        for f in candidate_files[:3]:
            deps = meta_graph_adapter.get_file_dependencies(repo_id, f)
            if deps.get("found"):
                graph_context[f] = {
                    "symbols": [s["name"] for s in deps.get("symbols", [])][:10],
                    "callers": [c["caller_name"] for c in deps.get("callers", [])][:5]
                }

        user_prompt = f"""Approved Ticket:
Title: {ticket.get('title')}
Problem: {ticket.get('problem_statement')}
Acceptance Criteria: {ticket.get('acceptance_criteria')}
Candidate Files: {candidate_files}

Graph Context from Meta-Graph:
{graph_context}

Produce a bounded execution plan in JSON."""

        res = await agent_runtime.execute_task(
            role="Planner",
            prompt=user_prompt,
            system_instruction=PLANNER_SYSTEM_PROMPT,
            force_mock=force_mock
        )

        content = res.get("content", "")
        try:
            plan = extract_json_from_response(content)
            logger.info(f"Planner generated {len(plan.get('ordered_subtasks', []))} subtasks.")
            return plan
        except Exception as e:
            logger.warning(f"Planner response fallback: {e}")
            target_f = candidate_files[0] if candidate_files else "backend/app/agents/groq_agent.py"
            return {
                "ordered_subtasks": [
                    {
                        "subtask_id": "ST-1",
                        "description": f"Implement changes specified in acceptance criteria in {target_f}",
                        "target_file": target_f,
                        "relevant_symbols": ticket.get("relevant_graph_entities", []),
                        "completion_condition": "Acceptance criteria satisfied."
                    }
                ],
                "file_ownership": {target_f: "LocalCoder"},
                "protected_files": ["backend/app/chess/validator.py", "backend/app/chess/stockfish.py"],
                "risk_warnings": ["Avoid changing chess legality checks."]
            }

planner_agent = PlannerAgent()
