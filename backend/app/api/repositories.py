import os
import asyncio
from pathlib import Path
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database.session import get_db
from app.database.repositories import (
    list_repositories,
    get_repository,
    get_or_create_repository,
    update_repository,
    delete_repository
)
from app.schemas.repository import (
    RepositoryRegisterRequest,
    RepositoryCloneRequest,
    RepositoryUpdateRequest,
    RepositoryResponse,
    GraphStatusResponse
)
from app.integrations.graph.adapter import meta_graph_adapter
from app.integrations.git.worktree import git_worktree_manager
from app.core.logging import logger

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

    # Auto-index AST graph
    try:
        meta_graph_adapter.index_directory(req.id, repo_path)
    except Exception as e:
        logger.warning(f"AST auto-indexing warning on registration: {e}")

    repo = get_or_create_repository(
        db=db,
        repo_id=req.id,
        name=req.name,
        path=str(repo_path),
        commit_hash=commit_hash
    )
    return repo

@router.post("/clone", response_model=RepositoryResponse)
async def clone_repository(req: RepositoryCloneRequest, db: Session = Depends(get_db)):
    """Clones a remote Git repository, extracts AST call graph, and registers in Ouroboros."""
    parent_dir = Path("E:/MM Office") if Path("E:/MM Office").exists() else Path.cwd().parent
    target_dir = Path(req.target_path) if req.target_path else (parent_dir / req.id)

    if target_dir.exists() and any(target_dir.iterdir()):
        # Check if already a git repo
        if not (target_dir / ".git").exists():
            raise HTTPException(status_code=400, detail=f"Target directory exists and is not an empty or git repository: {target_dir}")
        logger.info(f"Directory already exists at {target_dir}, pulling / using existing.")
    else:
        target_dir.parent.mkdir(parents=True, exist_ok=True)
        logger.info(f"Cloning {req.git_url} into {target_dir}...")
        proc = await asyncio.create_subprocess_exec(
            "git", "clone", "--depth", "1", req.git_url, str(target_dir),
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        stdout, stderr = await proc.communicate()
        if proc.returncode != 0:
            err_msg = stderr.decode("utf-8", errors="replace")
            logger.error(f"Git clone failed: {err_msg}")
            raise HTTPException(status_code=500, detail=f"Git clone failed: {err_msg}")

    commit_hash = None
    try:
        commit_hash = await git_worktree_manager.get_base_commit(target_dir)
    except Exception:
        pass

    # Dynamic AST indexing
    try:
        meta_graph_adapter.index_directory(req.id, target_dir)
    except Exception as e:
        logger.warning(f"AST indexing error after clone: {e}")

    repo = get_or_create_repository(
        db=db,
        repo_id=req.id,
        name=req.name,
        path=str(target_dir),
        commit_hash=commit_hash
    )
    return repo

@router.patch("/{repo_id}", response_model=RepositoryResponse)
async def update_repository_endpoint(repo_id: str, req: RepositoryUpdateRequest, db: Session = Depends(get_db)):
    repo = get_repository(db, repo_id)
    if not repo:
        raise HTTPException(status_code=404, detail=f"Repository '{repo_id}' not found.")

    new_path = req.path
    if new_path:
        p = Path(new_path)
        if not p.exists():
            raise HTTPException(status_code=400, detail=f"Directory does not exist: {new_path}")
        try:
            meta_graph_adapter.index_directory(repo_id, p)
        except Exception as e:
            logger.warning(f"AST re-indexing warning: {e}")

    updated = update_repository(db, repo_id=repo_id, name=req.name, path=new_path)
    return updated

@router.post("/{repo_id}/reindex")
async def reindex_repository(repo_id: str, db: Session = Depends(get_db)):
    repo = get_repository(db, repo_id)
    if not repo:
        raise HTTPException(status_code=404, detail=f"Repository '{repo_id}' not found.")
    p = Path(repo.path)
    if not p.exists():
        raise HTTPException(status_code=400, detail=f"Repository path does not exist on disk: {repo.path}")

    graph = meta_graph_adapter.index_directory(repo_id, p)
    return {
        "status": "indexed",
        "repo_id": repo_id,
        "nodes": graph.number_of_nodes(),
        "edges": graph.number_of_edges(),
        "path": str(p)
    }

@router.delete("/{repo_id}")
async def delete_repository_endpoint(repo_id: str, db: Session = Depends(get_db)):
    repo = get_repository(db, repo_id)
    if not repo:
        raise HTTPException(status_code=404, detail=f"Repository '{repo_id}' not found.")
    deleted = delete_repository(db, repo_id)
    return {"deleted": deleted, "repo_id": repo_id}

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

@router.get("/{repo_id}/file-dependencies")
async def get_file_dependencies(repo_id: str, rel_path: str, db: Session = Depends(get_db)):
    repo = get_repository(db, repo_id)
    if not repo:
        raise HTTPException(status_code=404, detail=f"Repository '{repo_id}' not found.")

    return meta_graph_adapter.get_file_dependencies(repo_id, rel_path)

