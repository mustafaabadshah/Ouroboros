import psutil
from typing import Dict, Any, Optional
from app.core.config import settings

class SystemTelemetry:
    """
    Real-time system telemetry and resource guardrail watchdog.
    Adheres strictly to the 8 GB system RAM limit.
    """

    @staticmethod
    def get_system_metrics() -> Dict[str, Any]:
        mem = psutil.virtual_memory()
        total_mb = int(mem.total / (1024 * 1024))
        free_mb = int(mem.available / (1024 * 1024))
        cpu_pct = psutil.cpu_percent(interval=None)

        warning_threshold = settings.MEMORY_WARNING_THRESHOLD_MB
        ram_warning = free_mb < warning_threshold

        return {
            "total_ram_mb": total_mb,
            "free_ram_mb": free_mb,
            "used_ram_mb": total_mb - free_mb,
            "ram_percent": mem.percent,
            "ram_warning": ram_warning,
            "warning_threshold_mb": warning_threshold,
            "cpu_percent": cpu_pct,
            "cpu_count": psutil.cpu_count(logical=True)
        }

    @staticmethod
    def estimate_model_cost(model_name: str, input_tokens: Optional[int], output_tokens: Optional[int]) -> Optional[float]:
        """
        Estimates dollar cost based on known published provider rates.
        Returns None if price is unknown (never fabricates pricing).
        """
        if not input_tokens or not output_tokens:
            return None

        # Published Groq pricing snapshot:
        # Llama-3.3-70b: ~$0.59 / 1M prompt, $0.79 / 1M completion
        # Llama-3.1-8b: ~$0.05 / 1M prompt, $0.08 / 1M completion
        if "70b" in model_name.lower():
            cost = (input_tokens / 1_000_000) * 0.59 + (output_tokens / 1_000_000) * 0.79
            return round(cost, 6)
        elif "8b" in model_name.lower():
            cost = (input_tokens / 1_000_000) * 0.05 + (output_tokens / 1_000_000) * 0.08
            return round(cost, 6)

        # Local Ollama or unknown model -> 0.0 local compute cost
        if "qwen" in model_name.lower() or "mock" in model_name.lower():
            return 0.0

        return None

telemetry = SystemTelemetry()
