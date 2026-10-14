import re
import json
from abc import ABC, abstractmethod
from typing import Dict, Any, Optional

from app.core.logging import logger
from app.providers.router import model_router

class AgentRuntime(ABC):
    """
    Decoupled Agent Runtime Boundary.
    Allows swappable orchestration (AutoGen, LangGraph, or Direct Router)
    without rewriting the deterministic workflow state machine.
    """

    @abstractmethod
    async def execute_task(
        self,
        role: str,
        prompt: str,
        system_instruction: Optional[str] = None,
        force_mock: bool = False
    ) -> Dict[str, Any]:
        pass

class AutoGenRuntime(AgentRuntime):
    """
    Microsoft AutoGen 0.7+ compatible runtime adapter.
    Executes role-specific prompt tasks bounded to single deterministic turns.
    """

    async def execute_task(
        self,
        role: str,
        prompt: str,
        system_instruction: Optional[str] = None,
        force_mock: bool = False
    ) -> Dict[str, Any]:
        logger.info(f"AutoGenRuntime executing task for role: {role}")
        # Delegate to model router
        return await model_router.route_task(
            agent_role=role,
            prompt=prompt,
            system_instruction=system_instruction,
            force_mock=force_mock
        )

# Global default runtime
agent_runtime: AgentRuntime = AutoGenRuntime()

def extract_json_from_response(text: str) -> Dict[str, Any]:
    """Extracts JSON object from text containing markdown fences or raw JSON."""
    clean = text.strip()
    if "```json" in clean:
        clean = clean.split("```json", 1)[1].split("```", 1)[0].strip()
    elif "```" in clean:
        clean = clean.split("```", 1)[1].split("```", 1)[0].strip()

    try:
        return json.loads(clean)
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", clean, re.DOTALL)
        if match:
            return json.loads(match.group(0))
        raise ValueError(f"Could not parse valid JSON from agent response: {clean[:200]}")
