from fastapi import APIRouter, Depends, HTTPException, Query, Response
from sqlalchemy.orm import Session
from typing import List, Optional

from app.database.session import get_db
from app.database.models import FailureTrajectoryModel
from app.database.repositories import list_failure_trajectories
from app.schemas.failure import FailureTrajectoryResponse
from app.memory.flywheel import failure_flywheel

router = APIRouter(prefix="/failures", tags=["Failure Flywheel"])

@router.get("", response_model=List[FailureTrajectoryResponse])
async def get_all_failures(
    ticket_id: Optional[str] = Query(None),
    repo_id: Optional[str] = Query(None),
    run_id: Optional[str] = Query(None),
    db: Session = Depends(get_db)
):
    records = list_failure_trajectories(db, repo_id=repo_id, ticket_id=ticket_id, run_id=run_id)
    return [
        FailureTrajectoryResponse(
            id=r.id,
            run_id=r.run_id,
            ticket_id=r.ticket_id,
            attempt=r.attempt,
            provider=r.provider,
            model=r.model,
            failed_tests=r.failed_tests_json or [],
            traceback_excerpt=r.traceback_excerpt,
            ast_diff=r.ast_diff_json or {},
            patch_hash=r.patch_hash,
            root_cause_hypothesis=r.root_cause_hypothesis,
            repair_hint=r.repair_hint,
            status=r.status,
            created_at=r.created_at
        ) for r in records
    ]

@router.get("/{failure_id}", response_model=FailureTrajectoryResponse)
async def get_failure_by_id(failure_id: str, db: Session = Depends(get_db)):
    r = db.query(FailureTrajectoryModel).filter(FailureTrajectoryModel.id == failure_id).first()
    if not r:
        raise HTTPException(status_code=404, detail=f"Failure trajectory '{failure_id}' not found.")
    return FailureTrajectoryResponse(
        id=r.id,
        run_id=r.run_id,
        ticket_id=r.ticket_id,
        attempt=r.attempt,
        provider=r.provider,
        model=r.model,
        failed_tests=r.failed_tests_json or [],
        traceback_excerpt=r.traceback_excerpt,
        ast_diff=r.ast_diff_json or {},
        patch_hash=r.patch_hash,
        root_cause_hypothesis=r.root_cause_hypothesis,
        repair_hint=r.repair_hint,
        status=r.status,
        created_at=r.created_at
    )

@router.post("/export")
async def export_failures(ticket_id: Optional[str] = Query(None), db: Session = Depends(get_db)):
    json_str = failure_flywheel.export_trajectories_json(db, ticket_id=ticket_id)
    return Response(
        content=json_str,
        media_type="application/json",
        headers={"Content-Disposition": "attachment; filename=ouroboros_failure_trajectories.json"}
    )

@router.delete("/{failure_id}")
async def delete_failure(failure_id: str, db: Session = Depends(get_db)):
    r = db.query(FailureTrajectoryModel).filter(FailureTrajectoryModel.id == failure_id).first()
    if not r:
        raise HTTPException(status_code=404, detail=f"Failure trajectory '{failure_id}' not found.")
    db.delete(r)
    db.commit()
    return {"message": f"Failure trajectory '{failure_id}' deleted."}
