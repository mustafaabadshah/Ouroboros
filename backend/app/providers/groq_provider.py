import time
import asyncio
from typing import Dict, Any, Optional
from groq import AsyncGroq, APIError, RateLimitError

from app.core.config import settings
from app.core.logging import logger
from app.core.security import mask_secret
from app.providers.base import BaseLLMProvider

class GroqProvider(BaseLLMProvider):
    """
    Groq Remote Inference Provider.
    Provides fast, cloud-assisted reasoning for Architect and Planner agents.
    Strictly prevents secret leaks: API key is never logged or returned by APIs.
    """

    def __init__(self, api_key: Optional[str] = None, default_model: Optional[str] = None):
        self.api_key = api_key or settings.GROQ_API_KEY
        self.default_model = default_model or settings.GROQ_REASONING_MODEL
        self._client: Optional[AsyncGroq] = None
        self._health_cache: Optional[Dict[str, Any]] = None
        self._health_cache_time: float = 0.0
        self._health_cache_ttl: float = 60.0  # 60s cache avoids transatlantic round-trips on status polls

    def reset_health_cache(self) -> None:
        """Invalidates the cached health response."""
        self._health_cache = None
        self._health_cache_time = 0.0

    def _get_client(self) -> AsyncGroq:
        if self._client is None:
            key = self.api_key or settings.GROQ_API_KEY
            if not key:
                raise ValueError("GROQ_API_KEY is not configured.")
            self._client = AsyncGroq(api_key=key)
        return self._client

    async def check_health(self, force_refresh: bool = False) -> Dict[str, Any]:
        """Tests connectivity without returning or logging the raw key. Caches for 60s."""
        now = time.monotonic()
        if not force_refresh and self._health_cache is not None and (now - self._health_cache_time) < self._health_cache_ttl:
            return dict(self._health_cache)

        key = self.api_key or settings.GROQ_API_KEY
        if not key:
            res = {
                "available": False,
                "configured": False,
                "masked_key": "NOT_CONFIGURED",
                "message": "Groq API key not set in environment."
            }
            self._health_cache = res
            self._health_cache_time = now
            return dict(res)

        start_time = time.perf_counter()
        try:
            client = self._get_client()
            models_res = await client.models.list()
            latency = int((time.perf_counter() - start_time) * 1000)
            model_ids = [m.id for m in models_res.data]
            res = {
                "available": True,
                "configured": True,
                "latency_ms": latency,
                "masked_key": mask_secret(key),
                "available_models": [m for m in model_ids if "llama" in m or "qwen" in m][:10],
                "message": "Groq API connected successfully."
            }
        except Exception as e:
            latency = int((time.perf_counter() - start_time) * 1000)
            logger.warning(f"Groq API connection test failed: {e}")
            res = {
                "available": False,
                "configured": True,
                "latency_ms": latency,
                "masked_key": mask_secret(key),
                "message": f"Groq connection error: {str(e)}"
            }

        self._health_cache = res
        self._health_cache_time = now
        return dict(res)

    async def generate(
        self,
        prompt: str,
        system_instruction: Optional[str] = None,
        model_name: Optional[str] = None,
        max_tokens: int = 4096,
        temperature: float = 0.2
    ) -> Dict[str, Any]:
        """
        Executes generation on Groq with exponential backoff on 429.
        """
        model = model_name or self.default_model
        messages = []
        if system_instruction:
            messages.append({"role": "system", "content": system_instruction})
        messages.append({"role": "user", "content": prompt})

        max_attempts = 3
        backoff = 1.0
        start_time = time.perf_counter()

        for attempt in range(1, max_attempts + 1):
            try:
                client = self._get_client()
                completion = await client.chat.completions.create(
                    model=model,
                    messages=messages,
                    max_tokens=max_tokens,
                    temperature=temperature
                )
                latency = int((time.perf_counter() - start_time) * 1000)

                input_tokens = completion.usage.prompt_tokens if completion.usage else None
                output_tokens = completion.usage.completion_tokens if completion.usage else None
                content = completion.choices[0].message.content or ""

                return {
                    "content": content,
                    "provider": "groq",
                    "model": model,
                    "input_tokens": input_tokens,
                    "output_tokens": output_tokens,
                    "latency_ms": latency,
                    "is_error": False,
                    "error_message": None
                }

            except RateLimitError as rle:
                if attempt == max_attempts:
                    latency = int((time.perf_counter() - start_time) * 1000)
                    return {
                        "content": "",
                        "provider": "groq",
                        "model": model,
                        "latency_ms": latency,
                        "is_error": True,
                        "error_message": f"Groq rate limit exceeded after {max_attempts} retries."
                    }
                logger.warning(f"Groq 429 rate limit hit. Backing off for {backoff}s...")
                await asyncio.sleep(backoff)
                backoff *= 2.0

            except Exception as e:
                latency = int((time.perf_counter() - start_time) * 1000)
                logger.error(f"Groq API error on attempt {attempt}: {e}")
                if attempt == max_attempts:
                    return {
                        "content": "",
                        "provider": "groq",
                        "model": model,
                        "latency_ms": latency,
                        "is_error": True,
                        "error_message": f"Groq API error: {str(e)}"
                    }
                await asyncio.sleep(backoff)
                backoff *= 1.5

        return {
            "content": "",
            "provider": "groq",
            "model": model,
            "latency_ms": int((time.perf_counter() - start_time) * 1000),
            "is_error": True,
            "error_message": "Generation aborted."
        }

groq_provider = GroqProvider()
