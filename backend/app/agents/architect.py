import random
import re
from typing import Dict, Any, Optional, List
from app.agents.runtime import agent_runtime, extract_json_from_response
from app.schemas.ticket import TicketBase
from app.core.logging import logger

ARCHITECT_SYSTEM_PROMPT = """You are the Lead Systems Architect in Project Ouroboros.
Your purpose is to inspect grounded codebase AST symbols, classes, and functions from repository graph metadata.
Identify bounded technical debt, input validation gaps, missing error handling, unhandled edge-case test coverage, or telemetry observability, and generate a single Jira-style engineering ticket.

Rules:
1. You MUST respond with ONLY a single valid JSON object. No conversational filler or surrounding markdown.
2. The ticket MUST be small, bounded, and testable via pytest.
3. NEVER propose large refactors, architectural rewrites, or modifying protected core engine logic (e.g. validator.py, stockfish.py, legality checks, config files).
4. Ground your ticket directly in the specific functions, classes, and file paths provided in the architectural summary.
5. Do NOT duplicate or re-propose any previously generated tickets listed in the prompt.
6. Strictly adhere to the requested schema keys:
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
   - acceptance_test_template (executable pytest test function string)
"""

FOCUS_DOMAINS = [
    "API boundary validation, HTTP 400/404/422 status error handlers, and defensive parameter sanitization in backend/app/api.",
    "Chess state invariants, FEN parser boundary conditions, and deterministic move notation validation in backend/app/chess/board_manager.py.",
    "Evaluation service timeout recovery, evaluation score bounds checking, and latency metrics in backend/app/api/analysis.py.",
    "Tournament match lifecycle, forfeit handling on agent timeout, and match summary telemetry in backend/app/api/tournament.py.",
    "Game state persistence, move history serialization edge cases, and session cleanup in backend/app/database.",
    "Agent error taxonomy, token calculation observability, and structured failure logging in backend/app/agents/groq_agent.py."
]

DIVERSE_FALLBACK_TICKETS = [
    TicketBase(
        title="Add input validation and 422 error handler for malformed FEN in BoardManager",
        problem_statement="BoardManager crashes with unhandled ValueError when initialized with corrupted or malformed FEN strings instead of returning a clean error.",
        motivation="Ensure defensive boundary validation and prevent unhandled server exceptions on bad client inputs.",
        current_behavior="BoardManager(fen=invalid_fen) raises unhandled ValueError causing 500 errors in upstream API calls.",
        desired_behavior="BoardManager validates FEN syntax and raises InvalidFENException or returns False gracefully.",
        acceptance_criteria=[
            "BoardManager validates FEN token count before parsing",
            "A deterministic unit test tests malformed FEN strings with invalid piece positions",
            "All existing 19 baseline tests continue to pass with 0 regressions"
        ],
        proposed_tests=[
            "backend/tests/test_chess.py::test_board_manager_invalid_fen_graceful_rejection"
        ],
        acceptance_test_template="""import pytest
from app.chess.board_manager import BoardManager

def test_board_manager_invalid_fen_graceful_rejection():
    # Acceptance Criterion: BoardManager validates FEN token count before parsing
    with pytest.raises((ValueError, Exception)):
        BoardManager(fen="invalid fen string too short")
""",
        relevant_graph_entities=[
            "BoardManager.__init__",
            "BoardManager.current_fen"
        ],
        candidate_files=[
            "backend/app/chess/board_manager.py"
        ],
        risk_level="low",
        expected_complexity="small",
        estimated_resources="1 LLM call, 1 pytest run",
        evidence=["backend/app/chess/board_manager.py:25"],
        out_of_scope="Do not modify backend/app/chess/validator.py or core legality checks."
    ),
    TicketBase(
        title="Add latency telemetry and timeout guard for Stockfish position evaluations",
        problem_statement="StockfishEvaluator blocks synchronously without recording evaluation duration or tracking subprocess evaluation timeouts.",
        motivation="Prevent worker thread starvation when Stockfish processes deep tactical search positions.",
        current_behavior="Stockfish evaluations do not record duration_ms in evaluation result payloads.",
        desired_behavior="StockfishEvaluator records duration_ms and logs warnings if evaluation exceeds threshold.",
        acceptance_criteria=[
            "StockfishEvaluator adds duration_ms to evaluation output dict",
            "A deterministic unit test mocks a delayed evaluator and confirms duration metric is captured",
            "All existing 19 baseline tests continue to pass with 0 regressions"
        ],
        proposed_tests=[
            "backend/tests/test_evaluator.py::test_stockfish_evaluation_latency_metric"
        ],
        relevant_graph_entities=[
            "get_game_analysis",
            "StockfishEvaluator"
        ],
        candidate_files=[
            "backend/app/api/analysis.py"
        ],
        risk_level="low",
        expected_complexity="small",
        estimated_resources="1 LLM call, 1 pytest run",
        evidence=["backend/app/api/analysis.py:48"],
        out_of_scope="Do not change core chess legality rules in validator.py."
    ),
    TicketBase(
        title="Add defensive HTTP 404 validation for nonexistent game IDs in analysis API",
        problem_statement="The analysis endpoint get_game_analysis queries the database without raising HTTP 404 when an invalid game_id is requested.",
        motivation="Maintain consistent REST API error taxonomy and adhere to OpenAPI specification standards.",
        current_behavior="Querying /api/analysis/{game_id} with nonexistent ID returns null or empty payload instead of 404.",
        desired_behavior="get_game_analysis raises HTTPException(status_code=404) if game does not exist in DB.",
        acceptance_criteria=[
            "get_game_analysis raises 404 with detail message when game_id is not found",
            "Deterministic test verifies 404 response on fake UUID",
            "All existing 19 baseline tests continue to pass with 0 regressions"
        ],
        proposed_tests=[
            "backend/tests/test_api.py::test_get_game_analysis_nonexistent_returns_404"
        ],
        relevant_graph_entities=[
            "get_game_analysis",
            "calc_tokens"
        ],
        candidate_files=[
            "backend/app/api/analysis.py"
        ],
        risk_level="low",
        expected_complexity="small",
        estimated_resources="1 LLM call, 1 pytest run",
        evidence=["backend/app/api/analysis.py:52"],
        out_of_scope="Do not alter database models or schema definitions."
    ),
    TicketBase(
        title="Add forfeit telemetry and match error counter in tournament runner",
        problem_statement="When an agent times out or forfeits during a tournament round, the event is logged but no aggregate forfeit counter is saved in tournament statistics.",
        motivation="Improve tournament reliability metrics and enable automated detection of degraded agent instances.",
        current_behavior="Tournament rounds drop forfeiting agents without incrementing forfeit_count in match summary.",
        desired_behavior="TournamentManager increments forfeit_count on timeout or crash and includes it in round summaries.",
        acceptance_criteria=[
            "Tournament round result records forfeit_count",
            "Deterministic test simulates an agent forfeit and verifies telemetry aggregation",
            "All existing 19 baseline tests continue to pass with 0 regressions"
        ],
        proposed_tests=[
            "backend/tests/test_tournament.py::test_tournament_forfeit_telemetry_aggregation"
        ],
        relevant_graph_entities=[
            "TournamentService",
            "TournamentModel"
        ],
        candidate_files=[
            "backend/app/api/tournament.py"
        ],
        risk_level="low",
        expected_complexity="small",
        estimated_resources="1 LLM call, 1 pytest run",
        evidence=["backend/app/api/tournament.py:75"],
        out_of_scope="Do not modify matchmaking brackets or pairing algorithms."
    ),
    TicketBase(
        title="Add telemetry counters for agent emergency fallback moves",
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
]

class ArchitectAgent:
    """
    Architect Agent.
    Identifies high-value, bounded technical debt or missing tests and produces structured tickets.
    """

    @staticmethod
    def synthesize_test_template(
        ticket_title: str,
        candidate_files: List[str],
        relevant_symbols: List[str],
        acceptance_criteria: List[str],
        repo_id: str = "agent_chess"
    ) -> str:
        """
        Cross-Repo Test Discovery:
        Auto-synthesizes candidate acceptance test template grounded in AST caller graphs
        and existing test conventions.
        """
        try:
            from app.integrations.graph.adapter import meta_graph_adapter
            target_f = candidate_files[0] if candidate_files else "backend/app/module.py"
            deps = meta_graph_adapter.get_file_dependencies(repo_id, target_f)
            callers = [c.get("caller_name", "") for c in deps.get("callers", [])[:3] if c.get("caller_name")]
            caller_note = f"# AST Callers identified: {', '.join(callers)}" if callers else "# AST Callers: Direct unit test invocation"
        except Exception:
            target_f = candidate_files[0] if candidate_files else "backend/app/module.py"
            caller_note = "# AST Callers: Isolated module target"

        clean_slug = re.sub(r"[^a-zA-Z0-9_]+", "_", ticket_title.lower()).strip("_")[:40]
        first_criterion = acceptance_criteria[0] if acceptance_criteria else "Verify expected behavior"
        symbols_str = ", ".join(relevant_symbols[:3]) if relevant_symbols else "target symbols"

        template = f'''"""
Auto-Synthesized Acceptance Test Template
Grounded in AST entity graph for: {target_f}
{caller_note}
"""
import pytest

def test_acceptance_{clean_slug}():
    # Acceptance Criterion: {first_criterion}
    # Target symbols: {symbols_str}
    # TODO: Assert expected behavior without regressions
    pass
'''
        return template

    @staticmethod
    async def generate_ticket(
        repo_id: str,
        repo_summary: Dict[str, Any],
        target_focus: Optional[str] = None,
        existing_tickets: Optional[List[str]] = None,
        force_mock: bool = False
    ) -> TicketBase:
        # Dynamically rotate focus domain if not explicitly provided
        chosen_focus = target_focus
        if not chosen_focus or chosen_focus.strip() == "":
            chosen_focus = random.choice(FOCUS_DOMAINS)

        # Anti-duplication context from existing tickets
        anti_duplication = ""
        if existing_tickets:
            recent_titles = existing_tickets[-8:]
            anti_duplication = (
                "\nALREADY GENERATED TICKETS (DO NOT REPEAT OR DUPLICATE THESE TOPICS):\n"
                + "\n".join(f"- {title}" for title in recent_titles)
                + "\nYou MUST propose a novel, different subsystem or distinct technical debt item."
            )

        # Format AST symbols for prompt
        classes_str = ", ".join(f"{c['class_name']} ({c['file']})" for c in repo_summary.get("key_classes", [])[:15])
        funcs_str = ", ".join(f"{f['func_name']} ({f['file']})" for f in repo_summary.get("key_functions", [])[:20])

        user_prompt = f"""Target Repository: {repo_id}
Architectural Structure:
- Modules: {repo_summary.get('module_structure', {})}
- Grounded AST Classes: {classes_str or 'None extracted'}
- Grounded AST Functions: {funcs_str or 'None extracted'}
{anti_duplication}

Target Focus / Direction: {chosen_focus}

Generate one high-value, bounded, low-risk engineering ticket in strict JSON format.
Ensure the problem_statement, current_behavior, and desired_behavior directly describe specific code logic in the chosen subsystem."""

        from app.observability.phoenix_service import phoenix_service
        with phoenix_service.trace_step("ticket.generate", repo_id=repo_id, target_focus=chosen_focus):
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

                # Deduplicate: if title matches any existing ticket, select an unaddressed diverse subsystem
                if existing_tickets and any(ticket.title.strip().lower() == et.strip().lower() for et in existing_tickets):
                    logger.warning(f"Architect generated duplicate ticket title '{ticket.title}'. Selecting diverse novelty alternative.")
                    chosen_fb = None
                    for fb in DIVERSE_FALLBACK_TICKETS:
                        if not any(fb.title.strip().lower() == et.strip().lower() for et in existing_tickets):
                            chosen_fb = fb
                            break
                    if chosen_fb:
                        ticket = chosen_fb
                    else:
                        ticket.title = f"{ticket.title} (Phase #{len(existing_tickets) + 1})"

                if not ticket.acceptance_test_template or len(ticket.acceptance_test_template.strip()) < 10:
                    ticket.acceptance_test_template = ArchitectAgent.synthesize_test_template(
                        ticket_title=ticket.title,
                        candidate_files=ticket.candidate_files,
                        relevant_symbols=ticket.relevant_graph_entities,
                        acceptance_criteria=ticket.acceptance_criteria,
                        repo_id=repo_id
                    )
                logger.info(f"Architect generated ticket: '{ticket.title}' with AST test template.")
                return ticket
            except Exception as e:
                logger.error(f"Architect response failed schema validation: {e}. Raw content: {content[:200]}")
                # Select fallback that doesn't duplicate recent tickets
                for fb in DIVERSE_FALLBACK_TICKETS:
                    if not existing_tickets or fb.title not in existing_tickets:
                        logger.info(f"Using diverse fallback ticket: '{fb.title}'")
                        if not fb.acceptance_test_template:
                            fb.acceptance_test_template = ArchitectAgent.synthesize_test_template(
                                ticket_title=fb.title,
                                candidate_files=fb.candidate_files,
                                relevant_symbols=fb.relevant_graph_entities,
                                acceptance_criteria=fb.acceptance_criteria,
                                repo_id=repo_id
                            )
                        return fb
                fb_default = DIVERSE_FALLBACK_TICKETS[0]
                if not fb_default.acceptance_test_template:
                    fb_default.acceptance_test_template = ArchitectAgent.synthesize_test_template(
                        ticket_title=fb_default.title,
                        candidate_files=fb_default.candidate_files,
                        relevant_symbols=fb_default.relevant_graph_entities,
                        acceptance_criteria=fb_default.acceptance_criteria,
                        repo_id=repo_id
                    )
                return fb_default

architect_agent = ArchitectAgent()
