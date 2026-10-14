from typing import List, Optional, Dict, Any
from pydantic import BaseModel

class SystemSettings(BaseModel):
    # General
    app_name: str = "Project Ouroboros"
    theme: str = "dark"
    log_level: str = "INFO"
    
    # Repositories
    default_repo_path: str = r"E:\MM Office\Agent Chess"
    navigator_path: str = r"E:\MM Office\Meta-Graph-Codebase-Navigator"
    
    # Resource Limits
    max_local_concurrency: int = 1
    max_test_concurrency: int = 1
    memory_warning_threshold_mb: int = 1500
    max_repair_attempts: int = 3
    max_tickets_per_batch: int = 1
    
    # Agent Behavior & Gates
    require_ticket_approval: bool = True
    require_remote_fallback_confirmation: bool = False
    require_merge_approval: bool = True
    
    # Sandbox
    sandbox_mode: str = "auto"
    subprocess_timeout_seconds: int = 60

class MetricsOverviewResponse(BaseModel):
    total_runs: int
    successful_runs: int
    failed_runs: int
    acceptance_rate: float
    total_trajectories: int
    avg_run_duration_sec: float
    free_ram_mb: int
    total_ram_mb: int
    cpu_percent: float
    docker_available: bool
    ollama_available: bool
    groq_available: bool
