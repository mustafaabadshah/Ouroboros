from typing import List, Optional, Dict, Any
from pydantic import BaseModel
from datetime import datetime

class RepositoryRegisterRequest(BaseModel):
    id: str
    name: str
    path: str

class RepositoryResponse(BaseModel):
    id: str
    name: str
    path: str
    is_valid: bool
    commit_hash: Optional[str] = None
    indexed_at: Optional[datetime] = None
    file_count: int = 0
    warnings: List[str] = []
    created_at: datetime

    class Config:
        from_attributes = True

class GraphStatusResponse(BaseModel):
    repo_id: str
    backend_mode: str
    connected: bool
    node_count: int
    edge_count: int
    source_index_file: Optional[str] = None
    message: str
