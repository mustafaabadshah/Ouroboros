import asyncio
import hashlib
from pathlib import Path
from fastapi import APIRouter, Depends, HTTPException, Query, BackgroundTasks
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
from typing import List, Optional

from app.database.session import get_db
from app.database.repositories import (
    list_runs,
    get_run,
    create_run,
    get_ticket,
    get_repository,
    get_latest_candidate,
    get_run_test_results,
    record_audit_event,
    update_run_state
)
from app.schemas.run import RunResponse, RunCreateRequest, RunApprovalRequest
from app.schemas.evaluation import TestResultResponse, DiffInspectionResponse
from app.orchestration.workflow import workflow_controller
from app.integrations.git.worktree import git_worktree_manager
from app.integrations.git.diff_parser import UnifiedDiffParser
from app.core.events import event_bus
from app.core.logging import logger

router = APIRouter(prefix="/runs", tags=["Agent Runs"])

@router.get("", response_model=List[RunResponse])
async def get_all_runs(repo_id: Optional[str] = Query(None), db: Session = Depends(get_db)):
    return list_runs(db, repo_id=repo_id)

@router.post("", response_model=RunResponse)
async def start_run(
    req: RunCreateRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db)
):
    ticket = get_ticket(db, req.ticket_id)
    if not ticket:
        raise HTTPException(status_code=404, detail=f"Ticket '{req.ticket_id}' not found.")

    if ticket.status != "APPROVED":
        raise HTTPException(
            status_code=400,
            detail=f"Cannot start run: Ticket '{ticket.id}' is '{ticket.status}', must be 'APPROVED' first."
        )

    # Prevent concurrent duplicate runs on the same ticket
    active_runs = [
        r for r in list_runs(db, repo_id=ticket.repo_id)
        if r.ticket_id == ticket.id and r.state not in ["COMPLETED", "FAILED", "CANCELLED", "BLOCKED"]
    ]
    if active_runs:
        raise HTTPException(
            status_code=409,
            detail=f"Conflict: An active run '{active_runs[0].id}' is already in progress for ticket '{ticket.id}'."
        )

    repo = get_repository(db, ticket.repo_id)
    if not repo:
        raise HTTPException(status_code=404, detail=f"Repository '{ticket.repo_id}' not found.")

    # Create run in DB
    run_record = create_run(db, {
        "ticket_id": ticket.id,
        "repo_id": repo.id,
        "state": "IDLE",
        "active_agent": "WorkflowController",
        "max_retries": 3
    })

    record_audit_event(db, "RUN_STARTED", details={"run_id": run_record.id, "ticket_id": ticket.id})

    # Launch workflow asynchronously in background
    background_tasks.add_task(
        workflow_controller.execute_run_lifecycle,
        run_record.id,
        req.use_mock_agents
    )

    return run_record

@router.get("/{run_id}", response_model=RunResponse)
async def get_run_by_id(run_id: str, db: Session = Depends(get_db)):
    run = get_run(db, run_id)
    if not run:
        raise HTTPException(status_code=404, detail=f"Run '{run_id}' not found.")
    return run

@router.post("/{run_id}/cancel")
async def cancel_run(run_id: str, db: Session = Depends(get_db)):
    run = get_run(db, run_id)
    if not run:
        raise HTTPException(status_code=404, detail=f"Run '{run_id}' not found.")

    workflow_controller.cancel_run(run_id)
    update_run_state(db, run_id, "CANCELLED", error_message="Cancelled by user.")
    record_audit_event(db, "RUN_CANCELLED", details={"run_id": run_id})
    return {"message": f"Run {run_id} cancelled."}

@router.get("/{run_id}/events")
async def stream_run_events(run_id: str):
    """Server-Sent Events (SSE) endpoint for streaming live run transitions."""
    queue = event_bus.subscribe(run_id)

    async def event_generator():
        try:
            while True:
                # Wait for next event or send periodic keepalive
                try:
                    payload = await asyncio.wait_for(queue.get(), timeout=15.0)
                    yield f"data: {payload}\n\n"
                except asyncio.TimeoutError:
                    yield ": keepalive\n\n"
        except asyncio.CancelledError:
            pass
        finally:
            event_bus.unsubscribe(run_id, queue)

    return StreamingResponse(event_generator(), media_type="text/event-stream")

@router.get("/{run_id}/results", response_model=List[TestResultResponse])
async def get_run_results(run_id: str, db: Session = Depends(get_db)):
    results = get_run_test_results(db, run_id)
    return [
        TestResultResponse(
            id=r.id,
            run_id=r.run_id,
            candidate_id=r.candidate_id,
            test_type=r.test_type,
            test_command=r.test_command,
            exit_code=r.exit_code,
            duration_ms=r.duration_ms,
            passed_count=r.passed_count,
            failed_count=r.failed_count,
            error_count=r.error_count,
            failures=r.failures_json or [],
            stdout_excerpt=r.stdout_excerpt,
            stderr_excerpt=r.stderr_excerpt,
            created_at=r.created_at
        ) for r in results
    ]

@router.get("/{run_id}/diff", response_model=DiffInspectionResponse)
async def get_run_diff(run_id: str, db: Session = Depends(get_db)):
    run = get_run(db, run_id)
    if not run:
        raise HTTPException(status_code=404, detail=f"Run '{run_id}' not found.")

    cand = get_latest_candidate(db, run_id)
    diff_content = cand.diff_content if cand else ""

    # Count additions & deletions
    added = sum(1 for line in diff_content.splitlines() if line.startswith("+") and not line.startswith("+++"))
    removed = sum(1 for line in diff_content.splitlines() if line.startswith("-") and not line.startswith("---"))

    return DiffInspectionResponse(
        run_id=run_id,
        candidate_id=cand.id if cand else None,
        attempt=cand.attempt if cand else 0,
        diff_content=diff_content,
        diff_hash=cand.diff_hash if cand else "",
        patch_explanation=cand.patch_explanation if cand else None,
        changed_files=cand.changed_files_json if cand else [],
        lines_added=added,
        lines_removed=removed,
        ast_changes=cand.ast_changes_json if cand else {},
        protected_files_affected=[],
        verdict=run.verdict
    )

_merge_lock = asyncio.Lock()

@router.post("/{run_id}/approve-merge")
async def approve_merge(req: RunApprovalRequest, run_id: str, db: Session = Depends(get_db)):
    """
    Explicit Human Approval Gate:
    Merges candidate branch into target branch and cleans up the isolated worktree.
    Serialized via _merge_lock to prevent concurrent double-merging.
    """
    async with _merge_lock:
        run = get_run(db, run_id)
        if not run:
            raise HTTPException(status_code=404, detail=f"Run '{run_id}' not found.")

        if run.state != "AWAITING_APPROVAL":
            raise HTTPException(status_code=400, detail=f"Run is in state '{run.state}', not 'AWAITING_APPROVAL'.")

    # Policy revalidation: only PASS or PASS_WITH_WARNINGS verdicts can be approved and merged
    if run.verdict not in ["PASS", "PASS_WITH_WARNINGS"]:
        raise HTTPException(
            status_code=403,
            detail=f"Approval rejected: Run verdict is '{run.verdict}', must be PASS or PASS_WITH_WARNINGS."
        )

    # Cryptographic revision binding: re-verify candidate hash
    cand = get_latest_candidate(db, run_id)
    if not cand:
        raise HTTPException(status_code=400, detail="No candidate record found for this run.")

    if req.candidate_id and req.candidate_id != cand.id:
        raise HTTPException(
            status_code=409,
            detail=f"Approval invalidated: Approved candidate '{req.candidate_id}' does not match current candidate '{cand.id}'."
        )

    # Re-verify candidate hash against stored diff content
    computed_hash = hashlib.sha256(cand.diff_content.encode("utf-8")).hexdigest()
    if cand.diff_hash and computed_hash != cand.diff_hash:
        raise HTTPException(
            status_code=409,
            detail="Approval invalidated: Candidate diff hash does not match computed hash (diff altered)."
        )

    if req.candidate_hash and req.candidate_hash != cand.diff_hash:
        raise HTTPException(
            status_code=409,
            detail=f"Approval invalidated: Provided hash '{req.candidate_hash[:8]}' does not match candidate hash '{cand.diff_hash[:8]}'."
        )

    # Revalidate patch boundary and protected files before merge
    is_safe, err_msg = UnifiedDiffParser.validate_patch_boundaries(
        diff_text=cand.diff_content,
        allowed_files=cand.changed_files_json or []
    )
    if not is_safe:
        raise HTTPException(status_code=403, detail=f"Merge rejected by policy: {err_msg}")

    repo = get_repository(db, run.repo_id)
    repo_path = Path(repo.path)

    # Verify base commit has not drifted unexpectedly
    current_head = await git_worktree_manager.get_base_commit(repo_path)
    if run.base_commit and current_head != run.base_commit:
        logger.warning(f"Target repository HEAD drifted from {run.base_commit[:8]} to {current_head[:8]}")

    success, msg = await git_worktree_manager.merge_candidate(
        repo_path=repo_path,
        candidate_branch=run.candidate_branch,
        target_branch="main"
    )

    if not success:
        raise HTTPException(status_code=500, detail=f"Merge failed: {msg}")

    # Clean up worktree
    await git_worktree_manager.remove_worktree(repo_path, run.ticket_id, run.candidate_branch)

    # Complete run
    update_run_state(db, run_id, "COMPLETED")
    record_audit_event(db, "MERGE_APPROVED", details={"run_id": run_id, "notes": req.notes})

    return {"success": True, "message": "Candidate patch successfully merged into main branch."}

@router.post("/{run_id}/reject-merge")
async def reject_merge(req: RunApprovalRequest, run_id: str, db: Session = Depends(get_db)):
    """Human Rejection Gate: Closes candidate without merging and removes worktree."""
    run = get_run(db, run_id)
    if not run:
        raise HTTPException(status_code=404, detail=f"Run '{run_id}' not found.")

    repo = get_repository(db, run.repo_id)
    repo_path = Path(repo.path)

    # Clean up worktree and delete candidate branch
    await git_worktree_manager.remove_worktree(repo_path, run.ticket_id, run.candidate_branch)

    update_run_state(db, run_id, "FAILED", error_message="Rejected by operator.")
    record_audit_event(db, "MERGE_REJECTED", details={"run_id": run_id, "notes": req.notes})

    return {"success": True, "message": "Candidate patch rejected. Worktree cleaned."}
