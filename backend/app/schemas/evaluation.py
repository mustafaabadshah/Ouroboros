from typing import List, Optional, Dict, Any
from pydantic import BaseModel
from datetime import datetime

class TestResultResponse(BaseModel):
    id: str
    run_id: str
    candidate_id: Optional[str] = None
    test_type: str
    test_command: str
    exit_code: int
    duration_ms: int
    passed_count: int
    failed_count: int
    error_count: int
    failures: List[Dict[str, Any]] = []
    stdout_excerpt: Optional[str] = None
    stderr_excerpt: Optional[str] = None
    created_at: datetime

    class Config:
        from_attributes = True

class DiffInspectionResponse(BaseModel):
    run_id: str
    candidate_id: Optional[str] = None
    attempt: int
    diff_content: str
    diff_hash: str
    patch_explanation: Optional[str] = None
    changed_files: List[str] = []
    lines_added: int = 0
    lines_removed: int = 0
    ast_changes: Dict[str, Any] = {}
    protected_files_affected: List[str] = []
    verdict: Optional[str] = None
