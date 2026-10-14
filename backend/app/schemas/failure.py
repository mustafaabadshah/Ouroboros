from typing import List, Optional, Dict, Any
from pydantic import BaseModel
from datetime import datetime

class FailureTrajectoryResponse(BaseModel):
    id: str
    run_id: str
    ticket_id: str
    attempt: int
    provider: Optional[str] = None
    model: Optional[str] = None
    failed_tests: List[str] = []
    traceback_excerpt: Optional[str] = None
    ast_diff: Dict[str, Any] = {}
    patch_hash: Optional[str] = None
    root_cause_hypothesis: Optional[str] = None
    repair_hint: Optional[str] = None
    status: str
    created_at: datetime

    class Config:
        from_attributes = True

class FailureExportResponse(BaseModel):
    total_records: int
    exported_at: datetime
    trajectories: List[FailureTrajectoryResponse]
