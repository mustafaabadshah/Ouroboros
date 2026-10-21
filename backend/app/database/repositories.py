from typing import List, Optional, Dict, Any
from sqlalchemy.orm import Session
from sqlalchemy import desc
from datetime import datetime, timezone
from app.database.models import (
    RepositoryModel,
    TicketModel,
    RunModel,
    CandidateModel,
    TestResultModel,
    FailureTrajectoryModel,
    ModelUsageModel,
    AuditEventModel,
    AppSettingModel
)

def get_or_create_repository(
    db: Session,
    repo_id: str,
    name: str,
    path: str,
    commit_hash: Optional[str] = None,
    file_count: int = 0
) -> RepositoryModel:
    repo = db.query(RepositoryModel).filter(RepositoryModel.id == repo_id).first()
    if not repo:
        repo = RepositoryModel(
            id=repo_id,
            name=name,
            path=path,
            commit_hash=commit_hash,
            file_count=file_count,
            is_valid=True
        )
        db.add(repo)
        db.commit()
        db.refresh(repo)
    else:
        if commit_hash:
            repo.commit_hash = commit_hash
        if file_count:
            repo.file_count = file_count
        db.commit()
        db.refresh(repo)
    return repo

def list_repositories(db: Session) -> List[RepositoryModel]:
    return db.query(RepositoryModel).order_by(RepositoryModel.name).all()

def get_repository(db: Session, repo_id: str) -> Optional[RepositoryModel]:
    return db.query(RepositoryModel).filter(RepositoryModel.id == repo_id).first()

def update_repository(
    db: Session,
    repo_id: str,
    name: Optional[str] = None,
    path: Optional[str] = None,
    commit_hash: Optional[str] = None,
    file_count: Optional[int] = None
) -> Optional[RepositoryModel]:
    repo = get_repository(db, repo_id)
    if not repo:
        return None
    if name is not None:
        repo.name = name
    if path is not None:
        repo.path = path
    if commit_hash is not None:
        repo.commit_hash = commit_hash
    if file_count is not None:
        repo.file_count = file_count
    db.commit()
    db.refresh(repo)
    return repo

def delete_repository(db: Session, repo_id: str) -> bool:
    repo = get_repository(db, repo_id)
    if not repo:
        return False
    db.delete(repo)
    db.commit()
    return True

# Tickets
def create_ticket(db: Session, ticket_data: Dict[str, Any]) -> TicketModel:
    ticket = TicketModel(**ticket_data)
    db.add(ticket)
    db.commit()
    db.refresh(ticket)
    return ticket

def get_ticket(db: Session, ticket_id: str) -> Optional[TicketModel]:
    return db.query(TicketModel).filter(TicketModel.id == ticket_id).first()

def list_tickets(db: Session, repo_id: Optional[str] = None, status: Optional[str] = None) -> List[TicketModel]:
    query = db.query(TicketModel)
    if repo_id:
        query = query.filter(TicketModel.repo_id == repo_id)
    if status:
        query = query.filter(TicketModel.status == status)
    return query.order_by(desc(TicketModel.created_at)).all()

def update_ticket_status(db: Session, ticket_id: str, status: str) -> Optional[TicketModel]:
    ticket = get_ticket(db, ticket_id)
    if ticket:
        ticket.status = status
        db.commit()
        db.refresh(ticket)
    return ticket

# Runs
def create_run(db: Session, run_data: Dict[str, Any]) -> RunModel:
    run = RunModel(**run_data)
    db.add(run)
    db.commit()
    db.refresh(run)
    return run

def get_run(db: Session, run_id: str) -> Optional[RunModel]:
    return db.query(RunModel).filter(RunModel.id == run_id).first()

def list_runs(db: Session, repo_id: Optional[str] = None) -> List[RunModel]:
    query = db.query(RunModel)
    if repo_id:
        query = query.filter(RunModel.repo_id == repo_id)
    return query.order_by(desc(RunModel.started_at)).all()

def update_run_state(
    db: Session,
    run_id: str,
    state: str,
    active_agent: Optional[str] = None,
    active_provider: Optional[str] = None,
    active_model: Optional[str] = None,
    error_message: Optional[str] = None,
    verdict: Optional[str] = None
) -> Optional[RunModel]:
    run = get_run(db, run_id)
    if run:
        run.state = state
        if active_agent is not None:
            run.active_agent = active_agent
        if active_provider is not None:
            run.active_provider = active_provider
        if active_model is not None:
            run.active_model = active_model
        if error_message is not None:
            run.error_message = error_message
        if verdict is not None:
            run.verdict = verdict
        if state in ["COMPLETED", "FAILED", "CANCELLED", "BLOCKED"]:
            run.completed_at = datetime.now(timezone.utc)
        db.commit()
        db.refresh(run)
    return run

# Candidates
def create_candidate(db: Session, cand_data: Dict[str, Any]) -> CandidateModel:
    cand = CandidateModel(**cand_data)
    db.add(cand)
    db.commit()
    db.refresh(cand)
    return cand

def get_latest_candidate(db: Session, run_id: str) -> Optional[CandidateModel]:
    return db.query(CandidateModel).filter(CandidateModel.run_id == run_id).order_by(desc(CandidateModel.attempt)).first()

# Test Results
def record_test_result(db: Session, result_data: Dict[str, Any]) -> TestResultModel:
    res = TestResultModel(**result_data)
    db.add(res)
    db.commit()
    db.refresh(res)
    return res

def get_run_test_results(db: Session, run_id: str) -> List[TestResultModel]:
    return db.query(TestResultModel).filter(TestResultModel.run_id == run_id).order_by(TestResultModel.created_at).all()

# Failure Trajectories
def create_failure_trajectory(db: Session, traj_data: Dict[str, Any]) -> FailureTrajectoryModel:
    traj = FailureTrajectoryModel(**traj_data)
    db.add(traj)
    db.commit()
    db.refresh(traj)
    return traj

def list_failure_trajectories(
    db: Session,
    repo_id: Optional[str] = None,
    ticket_id: Optional[str] = None,
    run_id: Optional[str] = None
) -> List[FailureTrajectoryModel]:
    query = db.query(FailureTrajectoryModel)
    if ticket_id:
        query = query.filter(FailureTrajectoryModel.ticket_id == ticket_id)
    if run_id:
        query = query.filter(FailureTrajectoryModel.run_id == run_id)
    return query.order_by(desc(FailureTrajectoryModel.created_at)).all()

# Audit Events
def record_audit_event(db: Session, event_type: str, actor: str = "human_operator", details: Optional[Dict[str, Any]] = None) -> AuditEventModel:
    event = AuditEventModel(
        event_type=event_type,
        actor=actor,
        details_json=details or {}
    )
    db.add(event)
    db.commit()
    db.refresh(event)
    return event

def list_audit_events(db: Session, limit: int = 50) -> List[AuditEventModel]:
    return db.query(AuditEventModel).order_by(desc(AuditEventModel.created_at)).limit(limit).all()

# App Settings
def get_setting(db: Session, key: str, default: Any = None) -> Any:
    item = db.query(AppSettingModel).filter(AppSettingModel.key == key).first()
    return item.value_json if item else default

def set_setting(db: Session, key: str, value: Any) -> AppSettingModel:
    item = db.query(AppSettingModel).filter(AppSettingModel.key == key).first()
    if not item:
        item = AppSettingModel(key=key, value_json=value)
        db.add(item)
    else:
        item.value_json = value
    db.commit()
    db.refresh(item)
    return item
