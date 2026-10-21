import re
from typing import Dict, Any, Optional
from app.core.config import settings
from app.core.logging import logger
from app.providers.ollama_provider import ollama_provider
from app.providers.groq_provider import groq_provider
from app.providers.mock_provider import mock_provider
from app.providers.budget import ProviderErrorCategory, EvaluationBudgetController


def redact_sensitive_strings(text: Optional[str]) -> Optional[str]:
    """Redacts API keys or credentials from error details."""
    if not text:
        return text
    clean = str(text)
    if settings.GROQ_API_KEY and settings.GROQ_API_KEY in clean:
        clean = clean.replace(settings.GROQ_API_KEY, "[REDACTED_API_KEY]")
    clean = re.sub(r"gsk_[a-zA-Z0-9]{20,}", "[REDACTED_GROQ_KEY]", clean)
    clean = re.sub(r"(Bearer\s+)[a-zA-Z0-9_\-\.]{20,}", r"\1[REDACTED_TOKEN]", clean)
    return clean


def classify_provider_error(err_msg: str, exc: Optional[Exception] = None) -> str:
    """Classifies an error string or exception into a structured ProviderErrorCategory."""
    msg_lower = (err_msg or "").lower()
    if exc:
        msg_lower += " " + str(exc).lower()
        exc_type = type(exc).__name__.lower()
        if "auth" in exc_type or "permission" in exc_type:
            return ProviderErrorCategory.AUTH_ERROR.value
        if "ratelimit" in exc_type or "rate_limit" in exc_type:
            return ProviderErrorCategory.RATE_LIMITED.value
        if "timeout" in exc_type:
            return ProviderErrorCategory.TIMEOUT.value

    if any(k in msg_lower for k in ["401", "unauthorized", "api_key", "invalid api key", "authentication", "not configured"]):
        return ProviderErrorCategory.AUTH_ERROR.value
    if any(k in msg_lower for k in ["429", "rate limit", "quota", "too many requests"]):
        return ProviderErrorCategory.RATE_LIMITED.value
    if any(k in msg_lower for k in ["timeout", "timed out", "deadline"]):
        return ProviderErrorCategory.TIMEOUT.value
    if any(k in msg_lower for k in ["malformed", "jsondecode", "invalid response"]):
        return ProviderErrorCategory.MALFORMED_RESPONSE.value
    return ProviderErrorCategory.UNAVAILABLE.value


class ModelRouter:
    """
    Intelligent routing and fail-closed execution controller.
    Supports three operating modes:
    - 'mock': Strictly deterministic offline mock provider. Zero network or credentials required.
    - 'live': Strictly remote live provider (Groq). Fails closed with structured error on any failure.
              NEVER falls back to MockProvider on provider errors or rate limits.
    - 'auto': Legacy interactive development routing with local Ollama priority and safe fallback.
    """

    def __init__(self):
        self._mode: str = "auto"
        self._budget_controller: Optional[EvaluationBudgetController] = None

    def set_mode(self, mode: str):
        if mode not in ("auto", "mock", "live"):
            raise ValueError(f"Invalid provider mode: {mode}. Must be 'auto', 'mock', or 'live'.")
        self._mode = mode
        logger.info(f"ModelRouter operating mode set to: {self._mode.upper()}")

    def get_mode(self) -> str:
        return self._mode

    def set_budget_controller(self, controller: Optional[EvaluationBudgetController]):
        self._budget_controller = controller

    def get_budget_controller(self) -> Optional[EvaluationBudgetController]:
        return self._budget_controller

    @property
    def allow_remote_fallback(self) -> bool:
        return settings.ALLOW_REMOTE_FALLBACK

    @property
    def strict_local_only(self) -> bool:
        return settings.STRICT_LOCAL_ONLY

    @property
    def require_confirmation(self) -> bool:
        return settings.REQUIRE_FALLBACK_CONFIRMATION

    async def route_task(
        self,
        agent_role: str,
        prompt: str,
        system_instruction: Optional[str] = None,
        force_mock: bool = False
    ) -> Dict[str, Any]:
        """
        Routes the agent prompt to the designated provider based on policy.
        Enforces strict fail-closed guarantees when operating in live mode.
        """
        # Strict conflict check
        if self._mode == "live" and force_mock:
            raise ValueError("Conflicting configuration: force_mock=True requested while router is in strict LIVE mode.")

        # 1. Explicit Mock Mode
        if self._mode == "mock" or force_mock:
            logger.info(f"Routing {agent_role} to deterministic MockProvider (mode={self._mode}, force_mock={force_mock}).")
            return await mock_provider.generate(prompt, system_instruction)

        # 2. Strict Live Mode (Fail-closed on any provider failure)
        if self._mode == "live":
            return await self._route_live_fail_closed(agent_role, prompt, system_instruction)

        # 3. Auto Mode (Legacy interactive development)
        return await self._route_auto(agent_role, prompt, system_instruction)

    async def _route_live_fail_closed(
        self,
        agent_role: str,
        prompt: str,
        system_instruction: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Executes strictly against the live remote provider with pacing, budget checks,
        and fail-closed error classification. NEVER falls back to MockProvider.
        """
        target_model = settings.GROQ_REASONING_MODEL if agent_role in ("Architect", "Planner") else settings.GROQ_FAST_MODEL

        # Pacing and Budget enforcement
        if self._budget_controller:
            await self._budget_controller.wait_pacing()
            est_in = max(100, len(prompt) // 4)
            ok, budget_err = self._budget_controller.check_and_reserve(
                estimated_prompt_tokens=est_in,
                max_output_tokens=2048,
                model_name=target_model,
                role=agent_role
            )
            if not ok:
                err_category = ProviderErrorCategory.BUDGET_EXHAUSTED.value
                if "Token ceiling" in (budget_err or ""):
                    err_category = ProviderErrorCategory.TOKEN_CEILING_EXCEEDED.value
                elif "Cost ceiling" in (budget_err or ""):
                    err_category = ProviderErrorCategory.COST_CEILING_EXCEEDED.value

                logger.error(f"[Fail-Closed] Live request denied by budget controller: {budget_err}")
                return {
                    "content": "",
                    "provider": "groq",
                    "model": target_model,
                    "input_tokens": 0,
                    "output_tokens": 0,
                    "latency_ms": 0,
                    "is_error": True,
                    "error_type": err_category,
                    "error_message": budget_err,
                    "is_fallback": False,
                    "diff_text": ""
                }

        # Check API key presence
        if not settings.GROQ_API_KEY:
            logger.error("[Fail-Closed] GROQ_API_KEY not configured in environment for live mode.")
            return {
                "content": "",
                "provider": "groq",
                "model": target_model,
                "input_tokens": 0,
                "output_tokens": 0,
                "latency_ms": 0,
                "is_error": True,
                "error_type": ProviderErrorCategory.AUTH_ERROR.value,
                "error_message": "GROQ_API_KEY is not configured in environment.",
                "is_fallback": False,
                "diff_text": ""
            }

        logger.info(f"Routing {agent_role} to GroqProvider ({target_model}) [STRICT LIVE MODE].")
        try:
            res = await groq_provider.generate(
                prompt=prompt,
                system_instruction=system_instruction,
                model_name=target_model
            )
        except Exception as exc:
            err_cat = classify_provider_error(str(exc), exc)
            logger.error(f"[Fail-Closed] Live provider exception for {agent_role}: {exc}")
            return {
                "content": "",
                "provider": "groq",
                "model": target_model,
                "input_tokens": 0,
                "output_tokens": 0,
                "latency_ms": 0,
                "is_error": True,
                "error_type": err_cat,
                "error_message": redact_sensitive_strings(str(exc)),
                "is_fallback": False,
                "diff_text": ""
            }

        if res.get("is_error"):
            err_cat = classify_provider_error(res.get("error_message", ""))
            logger.error(f"[Fail-Closed] Live provider error for {agent_role}: {res.get('error_message')} ({err_cat}).")
            res["error_type"] = err_cat
            res["error_message"] = redact_sensitive_strings(res.get("error_message"))
            res["diff_text"] = ""
            return res

        # Success - reconcile usage
        if self._budget_controller:
            est_in = max(100, len(prompt) // 4)
            self._budget_controller.reconcile_usage(
                actual_tokens_in=res.get("input_tokens"),
                actual_tokens_out=res.get("output_tokens"),
                estimated_prompt_tokens=est_in,
                max_output_tokens=2048,
                model_name=target_model
            )

        return res

    async def _route_auto(
        self,
        agent_role: str,
        prompt: str,
        system_instruction: Optional[str] = None
    ) -> Dict[str, Any]:
        """Legacy auto-mode routing with safe fallbacks for interactive development."""
        # Architect and Planner prefer Groq for strong reasoning
        if agent_role in ("Architect", "Planner"):
            if not self.strict_local_only and self.allow_remote_fallback and settings.GROQ_API_KEY:
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
                        "error_type": "CONFIRMATION_REQUIRED",
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

        return await mock_provider.generate(prompt, system_instruction)


model_router = ModelRouter()
