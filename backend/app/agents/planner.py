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
   - execution_dag: object describing dependency relationships and parallelizable stages
3. Never fabricate nonexistent dependencies or files.
"""

class PlannerAgent:
    """
    Planner Agent.
    Deconstructs approved tickets into dependency-aware subtasks with clear file ownership
    and DAG task parallelization for disjoint modules.
    """

    @staticmethod
    def compute_execution_dag(ordered_subtasks: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        DAG Task Parallelization:
        Analyzes subtask target files. When subtasks modify independent, non-overlapping modules,
        groups them into parallel execution stages to allow asynchronous multi-subtask synthesis.
        """
        if not ordered_subtasks:
            return {"is_parallelizable": False, "parallel_groups": [], "stages": []}

        all_files = [str(st.get("target_file", "")).replace("\\", "/").strip() for st in ordered_subtasks]
        unique_files = set(f for f in all_files if f)

        is_parallel = len(ordered_subtasks) > 1 and len(unique_files) == len(all_files)

        if is_parallel:
            parallel_groups = [[st.get("subtask_id") for st in ordered_subtasks]]
        else:
            parallel_groups = [[st.get("subtask_id")] for st in ordered_subtasks]

        return {
            "is_parallelizable": is_parallel,
            "parallel_groups": parallel_groups,
            "disjoint_files": list(unique_files),
            "stages": [
                {
                    "stage_id": f"STAGE-{idx+1}",
                    "subtasks": grp,
                    "mode": "PARALLEL" if len(grp) > 1 else "SEQUENTIAL"
                }
                for idx, grp in enumerate(parallel_groups)
            ]
        }

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
            subtasks = plan.get("ordered_subtasks", [])
            plan["execution_dag"] = PlannerAgent.compute_execution_dag(subtasks)
            logger.info(f"Planner generated {len(subtasks)} subtasks (Parallelizable: {plan['execution_dag']['is_parallelizable']}).")
            return plan
        except Exception as e:
            logger.warning(f"Planner response fallback: {e}")
            target_f = candidate_files[0] if candidate_files else "backend/app/agents/groq_agent.py"
            subtasks = [
                {
                    "subtask_id": "ST-1",
                    "description": f"Implement changes specified in acceptance criteria in {target_f}",
                    "target_file": target_f,
                    "relevant_symbols": ticket.get("relevant_graph_entities", []),
                    "completion_condition": "Acceptance criteria satisfied."
                }
            ]
            return {
                "ordered_subtasks": subtasks,
                "execution_dag": PlannerAgent.compute_execution_dag(subtasks),
                "file_ownership": {target_f: "LocalCoder"},
                "protected_files": ["backend/app/chess/validator.py", "backend/app/chess/stockfish.py"],
                "risk_warnings": ["Avoid changing chess legality checks."]
            }

    @staticmethod
    async def escalate_plan(
        repo_id: str,
        ticket: Dict[str, Any],
        failure_context: Dict[str, Any],
        current_plan: Dict[str, Any],
        force_mock: bool = False
    ) -> Dict[str, Any]:
        """
        Escalates repeated or stubborn failure trajectory to the Planner.
        Reconsiders the problem decomposition, subtasks, and algorithmic strategy using concrete failure diagnostics.
        """
        diag_body = failure_context.get("formatted_diagnostic") or failure_context.get("traceback") or "Repeated failure signature encountered."
        prior_subtasks = current_plan.get("ordered_subtasks", [])
        candidate_files = ticket.get("candidate_files", [])

        user_prompt = f"""Approved Ticket:
Title: {ticket.get('title')}
Problem: {ticket.get('problem_statement')}
Acceptance Criteria: {ticket.get('acceptance_criteria')}
Candidate Files: {candidate_files}

FAILURE ESCALATION:
The previous implementation strategy failed repeatedly.
Diagnostic Evidence:
{diag_body}

Previous Subtasks:
{prior_subtasks}

Produce a revised, alternative execution plan with a different algorithmic approach or refined subtask breakdown in JSON."""

        res = await agent_runtime.execute_task(
            role="Planner",
            prompt=user_prompt,
            system_instruction=PLANNER_SYSTEM_PROMPT,
            force_mock=force_mock
        )

        content = res.get("content", "")
        try:
            plan = extract_json_from_response(content)
            subtasks = plan.get("ordered_subtasks", [])
            plan["execution_dag"] = PlannerAgent.compute_execution_dag(subtasks)
            logger.info(f"Planner generated revised plan with {len(subtasks)} subtasks upon escalation.")
            return plan
        except Exception as e:
            logger.warning(f"Planner escalation fallback: {e}")
            target_f = candidate_files[0] if candidate_files else (prior_subtasks[0].get("target_file") if prior_subtasks else "target.py")
            revised_subtasks = [
                {
                    "subtask_id": "ST-REVISED-1",
                    "description": f"Refactored strategy: address failing diagnostics '{diag_body[:100]}' directly in {target_f}",
                    "target_file": target_f,
                    "relevant_symbols": ticket.get("relevant_graph_entities", []),
                    "completion_condition": "Diagnostics addressed and all tests pass."
                }
            ]
            return {
                "ordered_subtasks": revised_subtasks,
                "execution_dag": PlannerAgent.compute_execution_dag(revised_subtasks),
                "file_ownership": {target_f: "RepairAgent"},
                "protected_files": current_plan.get("protected_files", []),
                "risk_warnings": ["Previous approach repeated failing assertions. Must change algorithmic assumptions."]
            }

planner_agent = PlannerAgent()
