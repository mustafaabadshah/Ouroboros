import os
from pathlib import Path
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database.session import get_db
from app.database.repositories import (
    list_repositories,
    get_repository,
    get_or_create_repository
)
from app.schemas.repository import (
    RepositoryRegisterRequest,
    RepositoryResponse,
    GraphStatusResponse
)
from app.integrations.graph.adapter import meta_graph_adapter
from app.integrations.git.worktree import git_worktree_manager

router = APIRouter(prefix="/repositories", tags=["Repositories"])

@router.get("", response_model=list[RepositoryResponse])
async def get_all_repositories(db: Session = Depends(get_db)):
    return list_repositories(db)

@router.post("", response_model=RepositoryResponse)
async def register_repository(req: RepositoryRegisterRequest, db: Session = Depends(get_db)):
    repo_path = Path(req.path)
    if not repo_path.exists():
        raise HTTPException(status_code=400, detail=f"Directory does not exist: {req.path}")

    commit_hash = None
    try:
        commit_hash = await git_worktree_manager.get_base_commit(repo_path)
    except Exception:
        pass

    repo = get_or_create_repository(
        db=db,
        repo_id=req.id,
        name=req.name,
        path=str(repo_path),
        commit_hash=commit_hash
    )
    return repo

@router.get("/{repo_id}", response_model=RepositoryResponse)
async def get_repository_by_id(repo_id: str, db: Session = Depends(get_db)):
    repo = get_repository(db, repo_id)
    if not repo:
        raise HTTPException(status_code=404, detail=f"Repository '{repo_id}' not found.")
    return repo

@router.get("/{repo_id}/graph-status", response_model=GraphStatusResponse)
async def get_repo_graph_status(repo_id: str, db: Session = Depends(get_db)):
    repo = get_repository(db, repo_id)
    if not repo:
        raise HTTPException(status_code=404, detail=f"Repository '{repo_id}' not found.")

    status = await meta_graph_adapter.check_connection(repo_id)
    return GraphStatusResponse(
        repo_id=repo_id,
        backend_mode=status.get("mode", "UNKNOWN"),
        connected=status.get("connected", False),
        node_count=status.get("node_count", 0),
        edge_count=status.get("edge_count", 0),
        source_index_file=status.get("index_path"),
        message=str(status.get("details") or status.get("message", "OK"))
    )

@router.post("/{repo_id}/analyze")
async def analyze_repository(repo_id: str, db: Session = Depends(get_db)):
    repo = get_repository(db, repo_id)
    if not repo:
        raise HTTPException(status_code=404, detail=f"Repository '{repo_id}' not found.")

    summary = meta_graph_adapter.get_architectural_summary(repo_id)
    return {
        "repo_id": repo_id,
        "summary": summary
    }
