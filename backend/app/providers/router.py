from typing import Dict, Any, Optional
from app.core.config import settings
from app.core.logging import logger
from app.providers.ollama_provider import ollama_provider
from app.providers.groq_provider import groq_provider
from app.providers.mock_provider import mock_provider

class ModelRouter:
    """
    Intelligent routing and fallback controller.
    - Routes Architect and Planner reasoning tasks to Groq when configured.
    - Routes Local Coder tasks to Ollama quantized CPU runtime.
    - Falls back to remote or mock providers if local runtime is offline or times out.
    - Enforces local-only privacy boundaries when configured.
    """

    def __init__(self):
        self.allow_remote_fallback = settings.ALLOW_REMOTE_FALLBACK
        self.strict_local_only = settings.STRICT_LOCAL_ONLY
        self.require_confirmation = settings.REQUIRE_FALLBACK_CONFIRMATION

    async def route_task(
        self,
        agent_role: str,
        prompt: str,
        system_instruction: Optional[str] = None,
        force_mock: bool = False
    ) -> Dict[str, Any]:
        """
        Routes the agent prompt to the designated provider based on policy.
        """
        if force_mock:
            logger.info(f"Routing {agent_role} to deterministic MockProvider (forced).")
            return await mock_provider.generate(prompt, system_instruction)

        # Architect and Planner prefer Groq for strong reasoning
        if agent_role in ("Architect", "Planner"):
            if not self.strict_local_only and settings.GROQ_API_KEY:
                logger.info(f"Routing {agent_role} to GroqProvider ({settings.GROQ_REASONING_MODEL}).")
                res = await groq_provider.generate(prompt, system_instruction)
                if not res["is_error"]:
                    return res
                logger.warning(f"Groq reasoning failed for {agent_role}: {res['error_message']}. Attempting fallback...")

            # Fallback to Ollama or Mock
            ollama_health = await ollama_provider.check_health()
            if ollama_health["available"]:
                logger.info(f"Fallback routing {agent_role} to Ollama local runtime.")
                return await ollama_provider.generate(prompt, system_instruction)

            logger.info(f"Fallback routing {agent_role} to MockProvider (offline environment).")
            return await mock_provider.generate(prompt, system_instruction)

        # Coder & Repair prefer local quantized CPU inference
        if agent_role in ("LocalCoder", "RepairAgent"):
            ollama_health = await ollama_provider.check_health()
            if ollama_health["available"] and ollama_health["model_installed"]:
                logger.info(f"Routing {agent_role} to Ollama CPU runtime ({settings.LOCAL_MODEL_NAME}).")
                res = await ollama_provider.generate(prompt, system_instruction)
                if not res["is_error"] and res["content"].strip():
                    return res
                logger.warning(f"Ollama local inference failed for {agent_role}: {res['error_message']}")

            # Remote Fallback check
            if self.allow_remote_fallback and not self.strict_local_only and settings.GROQ_API_KEY:
                if self.require_confirmation:
                    logger.warning(f"Remote fallback requires user confirmation for {agent_role}. Pausing...")
                    return {
                        "content": "",
                        "provider": "none",
                        "model": "none",
                        "is_error": True,
                        "error_message": "Remote fallback confirmation required by system policy."
                    }
                logger.info(f"Fallback routing {agent_role} to Groq ({settings.GROQ_FAST_MODEL}).")
                res = await groq_provider.generate(
                    prompt=prompt,
                    system_instruction=system_instruction,
                    model_name=settings.GROQ_FAST_MODEL
                )
                if not res["is_error"]:
                    res["is_fallback"] = True
                    return res

            logger.info(f"Fallback routing {agent_role} to MockProvider (all engines offline).")
            return await mock_provider.generate(prompt, system_instruction)

        # Default fallback
        return await mock_provider.generate(prompt, system_instruction)

model_router = ModelRouter()
