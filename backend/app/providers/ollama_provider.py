import time
import asyncio
from typing import Dict, Any, Optional
import httpx

from app.core.config import settings
from app.core.logging import logger
from app.providers.base import BaseLLMProvider

class OllamaProvider(BaseLLMProvider):
    """
    Ollama Local Inference Provider.
    Adheres strictly to 8 GB RAM hardware guardrails:
    - Default model: qwen2.5-coder:1.5b (~986 MB download)
    - 1 active model, 1 concurrent request lock
    - Context window bounded to 2048 tokens
    - Automatic downloads disabled by default
    """

    def __init__(self, base_url: Optional[str] = None, model_name: Optional[str] = None):
        self.base_url = (base_url or settings.OLLAMA_BASE_URL).rstrip("/")
        self.model_name = model_name or settings.LOCAL_MODEL_NAME
        self.context_tokens = settings.LOCAL_MODEL_CONTEXT_TOKENS
        self._lock = asyncio.Lock()  # Hardware guardrail: global local inference lock
        self._health_cache: Optional[Dict[str, Any]] = None
        self._health_cache_time: float = 0.0
        self._health_cache_ttl: float = 30.0  # 30s cache prevents 2s offline connection timeouts on status polls

    def reset_health_cache(self) -> None:
        """Invalidates the cached health response."""
        self._health_cache = None
        self._health_cache_time = 0.0

    async def check_health(self, force_refresh: bool = False) -> Dict[str, Any]:
        now = time.monotonic()
        if not force_refresh and self._health_cache is not None and (now - self._health_cache_time) < self._health_cache_ttl:
            return dict(self._health_cache)

        res: Dict[str, Any]
        try:
            async with httpx.AsyncClient(timeout=1.5) as client:
                resp = await client.get(f"{self.base_url}/api/tags")
                if resp.status_code == 200:
                    data = resp.json()
                    models = [m.get("name") for m in data.get("models", [])]
                    res = {
                        "available": True,
                        "url": self.base_url,
                        "installed_models": models,
                        "selected_model": self.model_name,
                        "model_installed": any(self.model_name in m for m in models)
                    }
                    self._health_cache = res
                    self._health_cache_time = now
                    return dict(res)
        except Exception as e:
            logger.debug(f"Ollama health check offline: {e}")

        res = {
            "available": False,
            "url": self.base_url,
            "installed_models": [],
            "selected_model": self.model_name,
            "model_installed": False,
            "message": "Ollama service is offline or not installed."
        }
        self._health_cache = res
        self._health_cache_time = now
        return dict(res)

    async def generate(
        self,
        prompt: str,
        system_instruction: Optional[str] = None,
        max_tokens: int = 1000,
        temperature: float = 0.2
    ) -> Dict[str, Any]:
        """
        Executes generation on local CPU Ollama instance under concurrency lock.
        """
        async with self._lock:
            start_time = time.perf_counter()
            payload = {
                "model": self.model_name,
                "prompt": prompt,
                "system": system_instruction or "",
                "stream": False,
                "options": {
                    "num_ctx": self.context_tokens,
                    "num_predict": max_tokens,
                    "temperature": temperature,
                    "num_thread": 2,  # Bound CPU cores to prevent system stutter
                },
                "keep_alive": settings.LOCAL_MODEL_KEEP_ALIVE
            }

            try:
                async with httpx.AsyncClient(timeout=60.0) as client:
                    res = await client.post(f"{self.base_url}/api/generate", json=payload)
                    latency = int((time.perf_counter() - start_time) * 1000)

                    if res.status_code == 200:
                        data = res.json()
                        return {
                            "content": data.get("response", ""),
                            "provider": "ollama",
                            "model": self.model_name,
                            "input_tokens": data.get("prompt_eval_count"),
                            "output_tokens": data.get("eval_count"),
                            "latency_ms": latency,
                            "is_error": False,
                            "error_message": None
                        }
                    else:
                        return {
                            "content": "",
                            "provider": "ollama",
                            "model": self.model_name,
                            "input_tokens": None,
                            "output_tokens": None,
                            "latency_ms": latency,
                            "is_error": True,
                            "error_message": f"Ollama HTTP error {res.status_code}: {res.text}"
                        }
            except Exception as e:
                latency = int((time.perf_counter() - start_time) * 1000)
                logger.warning(f"Ollama local inference failed: {e}")
                return {
                    "content": "",
                    "provider": "ollama",
                    "model": self.model_name,
                    "input_tokens": None,
                    "output_tokens": None,
                    "latency_ms": latency,
                    "is_error": True,
                    "error_message": f"Ollama connection error: {str(e)}"
                }

ollama_provider = OllamaProvider()
