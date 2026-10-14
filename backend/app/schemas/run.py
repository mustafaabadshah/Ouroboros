from typing import List, Optional, Dict, Any
from pydantic import BaseModel
from datetime import datetime

class RunCreateRequest(BaseModel):
    ticket_id: str
    autonomy_mode: str = "SUPERVISED"  # OBSERVE, SUPERVISED, BOUNDED_AUTONOMOUS
    use_mock_agents: bool = False

class RunResponse(BaseModel):
    id: str
    ticket_id: str
    repo_id: str
    state: str
    active_agent: Optional[str] = None
    active_provider: Optional[str] = None
    active_model: Optional[str] = None
    base_commit: Optional[str] = None
    candidate_branch: Optional[str] = None
    retry_count: int = 0
    max_retries: int = 3
    verdict: Optional[str] = None
    error_message: Optional[str] = None
    started_at: datetime
    completed_at: Optional[datetime] = None

    class Config:
        from_attributes = True

class RunApprovalRequest(BaseModel):
    action: str  # approve, reject
    notes: Optional[str] = None
