from pathlib import Path
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from typing import List, Optional

from app.core.config import settings
from app.core.logging import logger
from app.database.session import get_db
from app.database.repositories import (
    list_tickets,
    get_ticket,
    create_ticket,
    update_ticket_status,
    record_audit_event,
    get_repository,
    list_repositories,
    get_or_create_repository
)
from app.schemas.ticket import (
    TicketResponse,
    TicketCreate,
    TicketUpdate,
    TicketGenerationRequest
)
from app.agents.architect import architect_agent
from app.integrations.graph.adapter import meta_graph_adapter

router = APIRouter(prefix="/tickets", tags=["Tickets"])

import json

def _ensure_list(val) -> list:
    if val is None:
        return []
    if isinstance(val, list):
        return val
    if isinstance(val, str):
        try:
            parsed = json.loads(val)
            if isinstance(parsed, list):
                return parsed
        except Exception:
            return [val] if val.strip() else []
    return []

@router.get("", response_model=List[TicketResponse])
async def get_all_tickets(
    repo_id: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    db: Session = Depends(get_db)
):
    tickets = list_tickets(db, repo_id=repo_id, status=status)
    return [
        TicketResponse(
            id=t.id,
            repo_id=t.repo_id,
            title=t.title,
            problem_statement=t.problem_statement,
            motivation=t.motivation,
            current_behavior=t.current_behavior,
            desired_behavior=t.desired_behavior,
            acceptance_criteria=_ensure_list(t.acceptance_criteria_json),
            proposed_tests=_ensure_list(t.proposed_tests_json),
            relevant_graph_entities=_ensure_list(t.relevant_graph_entities_json),
            candidate_files=_ensure_list(t.candidate_files_json),
            risk_level=t.risk_level or "low",
            expected_complexity=t.expected_complexity or "small",
            estimated_resources=t.estimated_resources or "1 LLM call, 1 pytest run",
            evidence=_ensure_list(t.evidence_json),
            out_of_scope=t.out_of_scope,
            acceptance_test_template=getattr(t, "acceptance_test_template", None),
            status=t.status,
            created_at=t.created_at,
            updated_at=t.updated_at
        ) for t in tickets
    ]

@router.post("/generate", response_model=TicketResponse)
async def generate_ticket(
    req: TicketGenerationRequest,
    use_mock: bool = Query(False),
    db: Session = Depends(get_db)
):
    try:
        repo = get_repository(db, req.repo_id)
        if not repo:
            all_repos = list_repositories(db)
            if all_repos:
                repo = all_repos[0]
                logger.info(f"Repository '{req.repo_id}' not found, falling back to registered repository: {repo.id}")
            else:
                # Check candidate paths on disk
                candidate_paths = [
                    Path(settings.DEFAULT_REPO_PATH),
                    Path("/opt/render/project/multi_agent_ai_chess_arena"),
                    Path.cwd().parent / "multi_agent_ai_chess_arena",
                    Path.cwd() / "repos" / "multi_agent_ai_chess_arena",
                    Path("/opt/render/project/agent_chess")
                ]
                resolved_repo_path = next((p for p in candidate_paths if p.exists() and p.is_dir()), None)
                if resolved_repo_path:
                    repo = get_or_create_repository(
                        db=db,
                        repo_id=req.repo_id or "agent_chess",
                        name="Agent Chess (ChessMind Arena)",
                        path=str(resolved_repo_path),
                        file_count=48
                    )
                else:
                    raise HTTPException(status_code=404, detail=f"Repository '{req.repo_id}' not found. Please clone or register a repository first.")

        actual_repo_id = repo.id
        summary = meta_graph_adapter.get_architectural_summary(actual_repo_id)
        existing_titles = [t.title for t in list_tickets(db, repo_id=actual_repo_id)]
        generated = await architect_agent.generate_ticket(
            repo_id=actual_repo_id,
            repo_summary=summary,
            target_focus=req.target_area or req.custom_prompt,
            existing_tickets=existing_titles,
            force_mock=use_mock
        )

        ticket_record = create_ticket(db, {
            "repo_id": actual_repo_id,
            "title": generated.title,
            "problem_statement": generated.problem_statement,
            "motivation": generated.motivation,
            "current_behavior": generated.current_behavior,
            "desired_behavior": generated.desired_behavior,
            "acceptance_criteria_json": generated.acceptance_criteria,
            "proposed_tests_json": generated.proposed_tests,
            "relevant_graph_entities_json": generated.relevant_graph_entities,
            "candidate_files_json": generated.candidate_files,
            "risk_level": generated.risk_level,
            "expected_complexity": generated.expected_complexity,
            "estimated_resources": generated.estimated_resources,
            "evidence_json": generated.evidence,
            "out_of_scope": generated.out_of_scope,
            "acceptance_test_template": generated.acceptance_test_template,
            "status": "PROPOSED"
        })

        try:
            record_audit_event(db, "TICKET_GENERATED", details={"ticket_id": ticket_record.id, "title": ticket_record.title})
        except Exception as audit_err:
            logger.warning(f"Audit event recording notice: {audit_err}")

        return TicketResponse(
            id=ticket_record.id,
            repo_id=ticket_record.repo_id,
            title=ticket_record.title,
            problem_statement=ticket_record.problem_statement,
            motivation=ticket_record.motivation,
            current_behavior=ticket_record.current_behavior,
            desired_behavior=ticket_record.desired_behavior,
            acceptance_criteria=_ensure_list(ticket_record.acceptance_criteria_json),
            proposed_tests=_ensure_list(ticket_record.proposed_tests_json),
            relevant_graph_entities=_ensure_list(ticket_record.relevant_graph_entities_json),
            candidate_files=_ensure_list(ticket_record.candidate_files_json),
            risk_level=ticket_record.risk_level or "low",
            expected_complexity=ticket_record.expected_complexity or "small",
            estimated_resources=ticket_record.estimated_resources or "1 LLM call, 1 pytest run",
            evidence=_ensure_list(ticket_record.evidence_json),
            out_of_scope=ticket_record.out_of_scope,
            acceptance_test_template=ticket_record.acceptance_test_template,
            status=ticket_record.status,
            created_at=ticket_record.created_at,
            updated_at=ticket_record.updated_at
        )
    except HTTPException:
        raise
    except Exception as e:
        import traceback
        err_trace = traceback.format_exc()
        logger.error(f"Error in generate_ticket: {e}\n{err_trace}")
        raise HTTPException(status_code=500, detail=f"Ticket generation error: {str(e)}")

@router.get("/{ticket_id}", response_model=TicketResponse)
async def get_ticket_by_id(ticket_id: str, db: Session = Depends(get_db)):
    t = get_ticket(db, ticket_id)
    if not t:
        raise HTTPException(status_code=404, detail=f"Ticket '{ticket_id}' not found.")
    return TicketResponse(
        id=t.id,
        repo_id=t.repo_id,
        title=t.title,
        problem_statement=t.problem_statement,
        motivation=t.motivation,
        current_behavior=t.current_behavior,
        desired_behavior=t.desired_behavior,
        acceptance_criteria=_ensure_list(t.acceptance_criteria_json),
        proposed_tests=_ensure_list(t.proposed_tests_json),
        relevant_graph_entities=_ensure_list(t.relevant_graph_entities_json),
        candidate_files=_ensure_list(t.candidate_files_json),
        risk_level=t.risk_level or "low",
        expected_complexity=t.expected_complexity or "small",
        estimated_resources=t.estimated_resources or "1 LLM call, 1 pytest run",
        evidence=_ensure_list(t.evidence_json),
        out_of_scope=t.out_of_scope,
        acceptance_test_template=getattr(t, "acceptance_test_template", None),
        status=t.status,
        created_at=t.created_at,
        updated_at=t.updated_at
    )

@router.patch("/{ticket_id}", response_model=TicketResponse)
async def update_ticket(ticket_id: str, req: TicketUpdate, db: Session = Depends(get_db)):
    t = get_ticket(db, ticket_id)
    if not t:
        raise HTTPException(status_code=404, detail=f"Ticket '{ticket_id}' not found.")

    if req.title is not None:
        t.title = req.title
    if req.problem_statement is not None:
        t.problem_statement = req.problem_statement
    if req.motivation is not None:
        t.motivation = req.motivation
    if req.current_behavior is not None:
        t.current_behavior = req.current_behavior
    if req.desired_behavior is not None:
        t.desired_behavior = req.desired_behavior
    if req.acceptance_criteria is not None:
        t.acceptance_criteria_json = req.acceptance_criteria
    if req.proposed_tests is not None:
        t.proposed_tests_json = req.proposed_tests
    if req.candidate_files is not None:
        t.candidate_files_json = req.candidate_files
    if req.risk_level is not None:
        t.risk_level = req.risk_level
    if req.status is not None:
        t.status = req.status

    db.commit()
    db.refresh(t)
    return await get_ticket_by_id(ticket_id, db)

@router.post("/{ticket_id}/approve", response_model=TicketResponse)
async def approve_ticket(ticket_id: str, db: Session = Depends(get_db)):
    t = update_ticket_status(db, ticket_id, "APPROVED")
    if not t:
        raise HTTPException(status_code=404, detail=f"Ticket '{ticket_id}' not found.")
    record_audit_event(db, "TICKET_APPROVED", details={"ticket_id": ticket_id, "title": t.title})
    return await get_ticket_by_id(ticket_id, db)

@router.post("/{ticket_id}/reject", response_model=TicketResponse)
async def reject_ticket(ticket_id: str, db: Session = Depends(get_db)):
    t = update_ticket_status(db, ticket_id, "REJECTED")
    if not t:
        raise HTTPException(status_code=404, detail=f"Ticket '{ticket_id}' not found.")
    record_audit_event(db, "TICKET_REJECTED", details={"ticket_id": ticket_id})
    return await get_ticket_by_id(ticket_id, db)
