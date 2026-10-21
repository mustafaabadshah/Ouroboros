from abc import ABC, abstractmethod
from typing import Dict, Any, Optional

class BaseLLMProvider(ABC):
    """
    Abstract interface for model inference providers.
    Decouples agent logic from specific backend engines (Ollama, Groq, Mock).
    """

    @abstractmethod
    async def check_health(self, force_refresh: bool = False) -> Dict[str, Any]:
        """Checks connection health, availability, and installed models."""
        pass

    @abstractmethod
    async def generate(
        self,
        prompt: str,
        system_instruction: Optional[str] = None,
        max_tokens: int = 1000,
        temperature: float = 0.2
    ) -> Dict[str, Any]:
        """
        Executes a prompt generation.
        Returns:
        {
            "content": str,
            "provider": str,
            "model": str,
            "input_tokens": Optional[int],
            "output_tokens": Optional[int],
            "latency_ms": int,
            "is_error": bool,
            "error_message": Optional[str]
        }
        """
        pass
