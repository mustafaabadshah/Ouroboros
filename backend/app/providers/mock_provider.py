import re
import json
from pathlib import Path
from typing import Dict, Any, Optional, Tuple, List
from app.providers.base import BaseLLMProvider

def _find_benchmark_task(prompt: str) -> Optional[Dict[str, Any]]:
    try:
        from app.evaluation.benchmark import BENCHMARK_TASKS_V1
        prompt_lower = prompt.lower()
        for t in BENCHMARK_TASKS_V1:
            if t["task_id"].lower() in prompt_lower or t["target_file"].lower() in prompt_lower or t["name"].lower() in prompt_lower:
                return t
    except Exception:
        pass
    return None

def _extract_target_file(prompt: str) -> str:
    """
    Extracts the target file from the prompt.
    Checks Target File: header first, then Candidate Files list, then subtask JSON.
    """
    # 1. Target File: header from CoderLead or RepairAgent
    m_tf = re.search(r"Target File:\s*([^\r\n]+)", prompt, re.IGNORECASE)
    if m_tf:
        cand = m_tf.group(1).strip()
        if cand and not cand.startswith("{") and not cand.startswith("$"):
            return cand.replace("\\", "/")

    # 2. Candidate Files: [...]
    m_cf = re.search(r"Candidate Files:\s*(\[[^\]]+\])", prompt, re.IGNORECASE)
    if m_cf:
        try:
            files = json.loads(m_cf.group(1).replace("'", '"'))
            if files and isinstance(files, list):
                return str(files[0]).replace("\\", "/")
        except Exception:
            pass

    # 3. Regex for Candidate Files list
    m_cf_raw = re.search(r"Candidate Files:\s*\[?['\"]([^'\",\]]+)", prompt, re.IGNORECASE)
    if m_cf_raw:
        cand = m_cf_raw.group(1).strip()
        if cand:
            return cand.replace("\\", "/")

    # 4. JSON field "target_file": "..."
    m_json = re.search(r'"target_file":\s*"([^"]+)"', prompt)
    if m_json:
        return m_json.group(1).strip().replace("\\", "/")

    return "backend/app/agents/groq_agent.py"

def _extract_file_context(prompt: str, target_file: str) -> Tuple[str, str]:
    """
    Extracts two consecutive non-empty code lines for hunk context from prompt or disk.
    """
    code_match = re.search(r"```python\s*\n(.*?)\n```", prompt, re.DOTALL)
    if code_match:
        code_text = code_match.group(1)
        lines = [
            l for l in code_text.splitlines()
            if l.strip() and not l.strip().startswith("#") and not l.strip().startswith('"""') and not l.strip().startswith("'''")
        ]
        if len(lines) >= 2:
            return lines[0], lines[1]
        elif len(lines) == 1:
            return lines[0], ""

    # Fallback: attempt reading the target file directly from disk
    search_roots = [
        Path(r"E:\MM Office\Agent Chess"),
        Path(r"E:\MM Office\Ouroboros"),
        Path.cwd()
    ]
    for root in search_roots:
        candidate_path = root / target_file
        if candidate_path.exists():
            try:
                with open(candidate_path, "r", encoding="utf-8", errors="replace") as f:
                    disk_lines = [
                        l.rstrip("\r\n") for l in f.readlines()
                        if l.strip() and not l.strip().startswith("#") and not l.strip().startswith('"""')
                    ]
                    if len(disk_lines) >= 2:
                        return disk_lines[0], disk_lines[1]
                    elif len(disk_lines) == 1:
                        return disk_lines[0], ""
            except Exception:
                pass

    return "", ""

MOCK_TICKETS_POOL: List[Dict[str, Any]] = [
    {
        "title": "Add defensive input validation and 422 error handling for tournament creation parameters",
        "problem_statement": "The tournament creation endpoint in Tournament API does not validate player counts or time control bounds, allowing malformed payload initialization.",
        "motivation": "Prevent worker process starvation and ensure consistent API error taxonomy for tournament management.",
        "current_behavior": "Malformed player lists or negative time controls cause internal 500 crashes instead of 422 Unprocessable Entity.",
        "desired_behavior": "Validate tournament creation parameters and raise HTTPException(status_code=422) on invalid configurations.",
        "acceptance_criteria": [
            "Tournament creation validates player_count >= 2 and time_control > 0",
            "A deterministic unit test verifies 422 error response on invalid input parameters",
            "Existing baseline tests continue to pass with 0 regressions"
        ],
        "proposed_tests": [
            "backend/tests/test_tournament.py::test_create_tournament_invalid_params_returns_422"
        ],
        "relevant_graph_entities": [
            "create_tournament",
            "TournamentModel"
        ],
        "candidate_files": [
            "backend/app/api/tournament.py",
            "backend/app/schemas/tournament.py",
            "backend/tests/test_tournament.py"
        ],
        "risk_level": "low",
        "expected_complexity": "small",
        "estimated_resources": "1 LLM call, 1 pytest run",
        "evidence": [
            "backend/app/api/tournament.py:45"
        ],
        "out_of_scope": "Do not modify matchmaking brackets or pairing algorithms."
    },
    {
        "title": "Add latency telemetry and timeout guard for Stockfish position evaluations",
        "problem_statement": "StockfishEvaluator blocks synchronously without recording evaluation duration or tracking subprocess evaluation timeouts.",
        "motivation": "Prevent worker thread starvation when Stockfish processes deep tactical search positions.",
        "current_behavior": "Stockfish evaluations do not record duration_ms in evaluation result payloads.",
        "desired_behavior": "StockfishEvaluator records duration_ms and logs warnings if evaluation exceeds threshold.",
        "acceptance_criteria": [
            "StockfishEvaluator adds duration_ms to evaluation output dict",
            "A deterministic unit test mocks a delayed evaluator and confirms duration metric is captured",
            "All existing baseline tests continue to pass with 0 regressions"
        ],
        "proposed_tests": [
            "backend/tests/test_api.py::test_stockfish_evaluation_latency_metric"
        ],
        "relevant_graph_entities": [
            "get_game_analysis",
            "StockfishEvaluator"
        ],
        "candidate_files": [
            "backend/app/api/analysis.py",
            "backend/tests/test_api.py"
        ],
        "risk_level": "low",
        "expected_complexity": "small",
        "estimated_resources": "1 LLM call, 1 pytest run",
        "evidence": [
            "backend/app/api/analysis.py:48"
        ],
        "out_of_scope": "Do not change core chess legality rules in validator.py."
    },
    {
        "title": "Add FEN parsing boundary checks and invariant validation in BoardManager",
        "problem_statement": "BoardManager parses raw FEN strings without checking rank boundaries or board width invariants.",
        "motivation": "Prevent unexpected IndexErrors during game state hydration and move replay.",
        "current_behavior": "Malformed FEN with incorrect square counts causes uncontrolled exceptions.",
        "desired_behavior": "BoardManager validates square count and raises ValueError on malformed FEN layouts.",
        "acceptance_criteria": [
            "BoardManager validates 64-square layout consistency before loading position",
            "Deterministic test verifies ValueError on corrupted FEN",
            "Existing baseline tests pass with 0 regressions"
        ],
        "proposed_tests": [
            "backend/tests/test_chess.py::test_board_manager_invalid_fen_boundary"
        ],
        "relevant_graph_entities": [
            "BoardManager.set_fen",
            "BoardManager.get_board_state"
        ],
        "candidate_files": [
            "backend/app/chess/board_manager.py",
            "backend/tests/test_chess.py"
        ],
        "risk_level": "low",
        "expected_complexity": "small",
        "estimated_resources": "1 LLM call, 1 pytest run",
        "evidence": [
            "backend/app/chess/board_manager.py:62"
        ],
        "out_of_scope": "Do not modify move generator legal transitions."
    },
    {
        "title": "Add telemetry and deterministic test for agent emergency fallback",
        "problem_statement": "When GroqChessAgent hits API limits or errors, it falls back to emergency moves without recording error taxonomy counters in match summary telemetry.",
        "motivation": "Enhance tournament observability and ensure fallback frequency is tracked accurately.",
        "current_behavior": "Emergency fallback moves are tagged as 'fallback' but tournament summary statistics do not aggregate fallback rates.",
        "desired_behavior": "Expose fallback_count and last_error_type in tournament game summary telemetry.",
        "acceptance_criteria": [
            "MoveModel records move_source='fallback' on emergency triggers",
            "A new deterministic unit test validates fallback move creation without network calls",
            "Existing baseline tests continue to pass with 0 regressions"
        ],
        "proposed_tests": [
            "backend/tests/test_agents.py::test_groq_agent_emergency_fallback_telemetry"
        ],
        "relevant_graph_entities": [
            "GroqChessAgent._select_emergency_move",
            "MoveModel.move_source"
        ],
        "candidate_files": [
            "backend/app/agents/groq_agent.py"
        ],
        "risk_level": "low",
        "expected_complexity": "small",
        "estimated_resources": "1 LLM call, 1 pytest run",
        "evidence": [
            "backend/app/agents/groq_agent.py:225"
        ],
        "out_of_scope": "Do not modify backend/app/chess/validator.py or legality rules."
    }
]


class MockProvider(BaseLLMProvider):
    """
    Deterministic offline mock LLM provider.
    Used for unit tests, CI pipelines, and offline demonstrations.
    Does not require Groq credentials, Ollama, or network access.
    Dynamically extracts target files and context lines from prompts to satisfy
    zero-trust AST and boundary policies.
    """

    async def check_health(self, force_refresh: bool = False) -> Dict[str, Any]:
        return {
            "available": True,
            "provider": "mock",
            "message": "Deterministic mock provider is active."
        }

    async def generate(
        self,
        prompt: str,
        system_instruction: Optional[str] = None,
        max_tokens: int = 1000,
        temperature: float = 0.0
    ) -> Dict[str, Any]:
        """
        Synthesizes deterministic structured outputs based on prompt intent.
        """
        prompt_lower = prompt.lower()
        matched_task = _find_benchmark_task(prompt)

        # 0. Benchmark Task Dispatcher (Deterministic mock for reproducible evaluation)
        if matched_task:
            if "plan" in prompt_lower:
                plan_data = {
                    "ordered_subtasks": [
                        {
                            "subtask_id": "ST-1",
                            "description": matched_task["problem_statement"],
                            "target_file": matched_task["target_file"],
                            "relevant_symbols": [],
                            "completion_condition": "Acceptance criteria satisfied."
                        }
                    ],
                    "file_ownership": {matched_task["target_file"]: "LocalCoder"},
                    "protected_files": [".env", ".git"],
                    "risk_warnings": []
                }
                content = f"```json\n{json.dumps(plan_data, indent=2)}\n```"
            elif (
                "structured failure diagnostics" in prompt_lower
                or "prior attempt trajectories" in prompt_lower
                or (system_instruction and "repair specialist" in system_instruction.lower())
            ):
                patch_diff = matched_task.get("repair_patch") or matched_task.get("flawed_patch", "")
                content = f"```diff\n{patch_diff}\n```\nExplanation: Applied failure-informed repair patch addressing diagnostics."
            else:
                patch_diff = matched_task.get("flawed_patch", "")
                content = f"```diff\n{patch_diff}\n```\nExplanation: Applied initial naive patch."

            return {
                "content": content,
                "provider": "mock",
                "model": "mock-deterministic-v1",
                "input_tokens": 120,
                "output_tokens": 240,
                "latency_ms": 15,
                "is_error": False,
                "error_message": None
            }

        # 1. Ticket Generation: dynamically rotate across diverse pool to prevent duplicates
        if "generate ticket" in prompt_lower or "architect" in prompt_lower or "jira" in prompt_lower:
            selected_ticket = None
            for candidate_t in MOCK_TICKETS_POOL:
                if candidate_t["title"].lower() not in prompt_lower:
                    selected_ticket = candidate_t
                    break
            if not selected_ticket:
                # If all standard titles already exist, generate a unique numbered variant
                base = MOCK_TICKETS_POOL[0]
                selected_ticket = dict(base)
                selected_ticket["title"] = f"{base['title']} (Extended Audit #{len(prompt) % 100})"
            content = f"```json\n{json.dumps(selected_ticket, indent=2)}\n```"

        # 2. Planning: dynamically target the actual candidate file requested in the prompt
        elif "plan" in prompt_lower:
            target_f = _extract_target_file(prompt)
            plan_data = {
                "ordered_subtasks": [
                    {
                        "subtask_id": "ST-1",
                        "description": f"Implement bounded telemetry and defensive validation in {target_f}",
                        "target_file": target_f,
                        "relevant_symbols": [],
                        "completion_condition": "Acceptance criteria satisfied and tests pass."
                    }
                ],
                "file_ownership": {target_f: "LocalCoder"},
                "protected_files": ["backend/app/chess/validator.py", "backend/app/chess/stockfish.py", ".env"],
                "risk_warnings": ["Avoid changing chess legality checks."]
            }
            content = f"```json\n{json.dumps(plan_data, indent=2)}\n```"

        # 3. Repair Agent: dynamically patch target file with diagnostic-aware fix
        elif "repair" in prompt_lower or "traceback" in prompt_lower or (system_instruction and "repair specialist" in system_instruction.lower()):
            target_f = _extract_target_file(prompt)
            line1, line2 = _extract_file_context(prompt, target_f)
            if line1 and line2:
                hunk_body = f" {line1}\n+# [Project Ouroboros Autonomic Repair] Corrected static constraint and telemetry\n {line2}"
            elif line1:
                hunk_body = f" {line1}\n+# [Project Ouroboros Autonomic Repair] Corrected static constraint and telemetry"
            else:
                hunk_body = "+# [Project Ouroboros Autonomic Repair] Corrected static constraint and telemetry"

            repair_diff = f"""--- a/{target_f}
+++ b/{target_f}
@@ -1,3 +1,4 @@
{hunk_body}
"""
            content = f"```diff\n{repair_diff}\n```\nExplanation: Applied failure-informed repair patch targeting {target_f}."

        # 4. Default Patch Generation (LocalCoder): dynamically patch target file within allowed scope
        else:
            target_f = _extract_target_file(prompt)
            line1, line2 = _extract_file_context(prompt, target_f)
            if line1 and line2:
                hunk_body = f" {line1}\n+# [Project Ouroboros Autonomic Patch] Verified bounds and telemetry metrics\n {line2}"
            elif line1:
                hunk_body = f" {line1}\n+# [Project Ouroboros Autonomic Patch] Verified bounds and telemetry metrics"
            else:
                hunk_body = "+# [Project Ouroboros Autonomic Patch] Verified bounds and telemetry metrics"

            sample_diff = f"""--- a/{target_f}
+++ b/{target_f}
@@ -1,3 +1,4 @@
{hunk_body}
"""
            content = f"```diff\n{sample_diff}\n```\nExplanation: Added telemetry docstring and defensive boundary checks to {target_f}."

        return {
            "content": content,
            "provider": "mock",
            "model": "mock-deterministic-v1",
            "input_tokens": 120,
            "output_tokens": 240,
            "latency_ms": 15,
            "is_error": False,
            "error_message": None
        }

mock_provider = MockProvider()
