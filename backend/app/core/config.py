import os
from pathlib import Path
from typing import List, Optional
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field

# Base Directory of Project Ouroboros
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent
BACKEND_DIR = Path(__file__).resolve().parent.parent.parent

class Settings(BaseSettings):
    # Core Application
    APP_ENV: str = "development"
    APP_NAME: str = "Project Ouroboros"
    HOST: str = "127.0.0.1"
    PORT: int = 8000
    LOG_LEVEL: str = "INFO"
    CORS_ORIGINS: str = "http://localhost:5173,http://127.0.0.1:5173"
    DATABASE_URL: str = f"sqlite:///{BACKEND_DIR / 'ouroboros.db'}"

    # Target Repository Paths
    DEFAULT_REPO_PATH: str = r"E:\MM Office\Agent Chess"
    NAVIGATOR_PATH: str = r"E:\MM Office\Meta-Graph-Codebase-Navigator"
    NAVIGATOR_API_URL: str = "http://localhost:8001"

    # Local Inference Runtime (Ollama / Quantized CPU)
    OLLAMA_BASE_URL: str = "http://localhost:11434"
    LOCAL_MODEL_NAME: str = "qwen2.5-coder:1.5b"
    LOCAL_MODEL_CONTEXT_TOKENS: int = 2048
    LOCAL_MODEL_KEEP_ALIVE: str = "5m"
    MAX_LOCAL_CONCURRENCY: int = 1
    AUTO_DOWNLOAD_LOCAL_MODELS: bool = False

    # Remote Provider (Groq API) - Backend Only
    GROQ_API_KEY: Optional[str] = None
    GROQ_REASONING_MODEL: str = "qwen/qwen3.8-27b"
    GROQ_FAST_MODEL: str = "qwen/qwen3.8-27b"

    # Routing & Fallback Policies
    ALLOW_REMOTE_FALLBACK: bool = True
    REQUIRE_FALLBACK_CONFIRMATION: bool = False
    STRICT_LOCAL_ONLY: bool = False

    # Swarm Guardrails & Resource Limits (8 GB RAM System Constraints)
    MAX_REPAIR_ATTEMPTS: int = 3
    MAX_TICKETS_PER_BATCH: int = 1
    MAX_CONCURRENT_TESTS: int = 1
    MEMORY_WARNING_THRESHOLD_MB: int = 1500
    SUBPROCESS_TIMEOUT_SECONDS: int = 60
    MAX_OUTPUT_CAPTURE_BYTES: int = 65536

    # Execution Security & Sandbox Policy ('auto', 'docker', 'restricted_local', 'fail_closed')
    SANDBOX_MODE: str = "auto"
    REQUIRE_CONTAINER_SANDBOX: bool = False
    ISOLATED_WORKTREE_DIR: str = str(BACKEND_DIR / "worktrees")
    AUTONOMY_MODE: str = "SUPERVISED"

    # Arize Phoenix AI Observability & Tracing Privacy Controls
    PHOENIX_ENABLED: bool = True
    PHOENIX_PORT: int = 6006
    PHOENIX_PROJECT_NAME: str = "ouroboros-swarm"
    PHOENIX_COLLECTOR_ENDPOINT: Optional[str] = None
    PHOENIX_CAPTURE_PROMPTS: bool = False
    PHOENIX_MASK_CODE_SNIPPETS: bool = True

    model_config = SettingsConfigDict(
        env_file=str(PROJECT_ROOT / ".env"),
        env_file_encoding="utf-8",
        extra="ignore"
    )

    @property
    def cors_origins_list(self) -> List[str]:
        return [origin.strip() for origin in self.CORS_ORIGINS.split(",") if origin.strip()]

    def get_masked_groq_key(self) -> str:
        """Returns a securely masked version of the Groq API key for UI diagnostics."""
        if not self.GROQ_API_KEY:
            return "NOT_CONFIGURED"
        clean = self.GROQ_API_KEY.strip()
        if len(clean) <= 8:
            return "********"
        return f"{clean[:4]}...{clean[-4:]}"

settings = Settings()
