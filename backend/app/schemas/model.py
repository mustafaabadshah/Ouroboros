from typing import List, Optional, Dict, Any
from pydantic import BaseModel

class ModelStatusResponse(BaseModel):
    local_runtime: str = "Ollama"
    local_available: bool = False
    installed_models: List[str] = []
    default_local_model: str = "qwen2.5-coder:1.5b"
    active_local_model: Optional[str] = None
    groq_available: bool = False
    groq_masked_key: str = "NOT_CONFIGURED"
    groq_reasoning_model: str = "llama-3.3-70b-versatile"
    groq_fast_model: str = "llama-3.1-8b-instant"
    allow_remote_fallback: bool = True
    require_fallback_confirmation: bool = False
    current_free_ram_mb: int = 0
    ram_warning: bool = False

class ModelConfigUpdate(BaseModel):
    local_model_name: Optional[str] = None
    local_context_tokens: Optional[int] = None
    groq_api_key: Optional[str] = None
    groq_reasoning_model: Optional[str] = None
    groq_fast_model: Optional[str] = None
    allow_remote_fallback: Optional[bool] = None
    require_fallback_confirmation: Optional[bool] = None

class ConnectionTestRequest(BaseModel):
    provider: str  # ollama or groq
    api_key: Optional[str] = None

class ConnectionTestResponse(BaseModel):
    provider: str
    success: bool
    latency_ms: int = 0
    message: str
