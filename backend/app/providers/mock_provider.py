import time
import json
from typing import Dict, Any, Optional
from app.providers.base import BaseLLMProvider

class MockProvider(BaseLLMProvider):
    """
    Deterministic offline mock LLM provider.
    Used for unit tests, CI pipelines, and offline demonstrations.
    Does not require Groq credentials, Ollama, or network access.
    """

    async def check_health(self) -> Dict[str, Any]:
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

        # 1. Ticket Generation
        if "generate ticket" in prompt_lower or "architect" in prompt_lower or "jira" in prompt_lower:
            ticket_data = {
                "title": "Add telemetry and deterministic test for agent emergency fallback",
                "problem_statement": "When GroqChessAgent hits API limits or errors, it falls back to emergency moves without recording error taxonomy counters in match summary telemetry.",
                "motivation": "Enhance tournament observability and ensure fallback frequency is tracked accurately.",
                "current_behavior": "Emergency fallback moves are tagged as 'fallback' but tournament summary statistics do not aggregate fallback rates.",
                "desired_behavior": "Expose fallback_count and last_error_type in tournament game summary telemetry.",
                "acceptance_criteria": [
                    "MoveModel records move_source='fallback' on emergency triggers",
                    "A new deterministic unit test validates fallback move creation without network calls",
                    "Existing 19 baseline tests continue to pass with 0 regressions"
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
            content = f"```json\n{json.dumps(ticket_data, indent=2)}\n```"

        # 2. Planning
        elif "plan" in prompt_lower:
            plan_data = {
                "ordered_subtasks": [
                    {
                        "subtask_id": "ST-1",
                        "description": "Inspect emergency move return dictionary in groq_agent.py",
                        "target_file": "backend/app/agents/groq_agent.py",
                        "relevant_symbols": ["_select_emergency_move", "select_move"],
                        "completion_condition": "Confirm telemetry dictionary includes fallback metadata."
                    }
                ],
                "file_ownership": {"backend/app/agents/groq_agent.py": "LocalCoder"},
                "protected_files": ["backend/app/chess/validator.py", "backend/app/chess/stockfish.py"],
                "risk_warnings": ["Avoid changing chess legality checks."]
            }
            content = f"```json\n{json.dumps(plan_data, indent=2)}\n```"

        # 3. Repair Agent
        elif "repair" in prompt_lower or "traceback" in prompt_lower:
            repair_diff = """--- a/backend/app/agents/groq_agent.py
+++ b/backend/app/agents/groq_agent.py
@@ -238,6 +238,7 @@
                         "latency_ms": total_latency,
                         "input_tokens": total_input_tokens,
                         "output_tokens": total_output_tokens,
                         "move_source": "fallback",
+                        "fallback_reason": "emergency_trigger",
                         "attempts": attempt
                     }
"""
            content = f"```diff\n{repair_diff}\n```\nExplanation: Added fallback_reason to groq emergency telemetry."

        # 4. Default Patch Generation
        else:
            sample_diff = """--- a/backend/app/agents/groq_agent.py
+++ b/backend/app/agents/groq_agent.py
@@ -238,6 +238,7 @@
                         "latency_ms": total_latency,
                         "input_tokens": total_input_tokens,
                         "output_tokens": total_output_tokens,
                         "move_source": "fallback",
+                        "fallback_reason": "emergency_trigger",
                         "attempts": attempt
                     }
"""
            content = f"```diff\n{sample_diff}\n```\nExplanation: Added fallback_reason field to groq emergency fallback telemetry."

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
