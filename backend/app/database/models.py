import uuid
from datetime import datetime, timezone
from sqlalchemy import Column, String, Integer, Float, Boolean, Text, JSON, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from app.database.session import Base

def get_utc_now():
    return datetime.now(timezone.utc)

class RepositoryModel(Base):
    __tablename__ = "repositories"

    id = Column(String(50), primary_key=True)
    name = Column(String(100), nullable=False)
    path = Column(String(500), nullable=False)
    is_valid = Column(Boolean, default=True)
    commit_hash = Column(String(40), nullable=True)
    indexed_at = Column(DateTime(timezone=True), nullable=True)
    file_count = Column(Integer, default=0)
    warnings_json = Column(JSON, default=list)
    created_at = Column(DateTime(timezone=True), default=get_utc_now)

    tickets = relationship("TicketModel", back_populates="repository", cascade="all, delete-orphan")
    runs = relationship("RunModel", back_populates="repository", cascade="all, delete-orphan")

class TicketModel(Base):
    __tablename__ = "tickets"

    id = Column(String(36), primary_key=True, default=lambda: f"ouro-{uuid.uuid4().hex[:6]}")
    repo_id = Column(String(50), ForeignKey("repositories.id", ondelete="CASCADE"), nullable=False, index=True)
    title = Column(String(200), nullable=False)
    problem_statement = Column(Text, nullable=False)
    motivation = Column(Text, nullable=False)
    current_behavior = Column(Text, nullable=False)
    desired_behavior = Column(Text, nullable=False)
    acceptance_criteria_json = Column(JSON, default=list)
    proposed_tests_json = Column(JSON, default=list)
    relevant_graph_entities_json = Column(JSON, default=list)
    candidate_files_json = Column(JSON, default=list)
    risk_level = Column(String(20), default="low")  # low, medium, high
    expected_complexity = Column(String(20), default="small")
    estimated_resources = Column(String(100), default="1 LLM call, 1 pytest run")
    evidence_json = Column(JSON, default=list)
    out_of_scope = Column(Text, nullable=True)
    acceptance_test_template = Column(Text, nullable=True)
    status = Column(String(30), default="PROPOSED")  # PROPOSED, REVIEWED, APPROVED, IMPLEMENTING, EVALUATING, ACCEPTED, REJECTED
    created_at = Column(DateTime(timezone=True), default=get_utc_now)
    updated_at = Column(DateTime(timezone=True), default=get_utc_now, onupdate=get_utc_now)

    repository = relationship("RepositoryModel", back_populates="tickets")
    runs = relationship("RunModel", back_populates="ticket", cascade="all, delete-orphan")
    failure_trajectories = relationship("FailureTrajectoryModel", back_populates="ticket", cascade="all, delete-orphan")

class RunModel(Base):
    __tablename__ = "runs"

    id = Column(String(36), primary_key=True, default=lambda: f"run-{uuid.uuid4().hex[:8]}")
    ticket_id = Column(String(36), ForeignKey("tickets.id", ondelete="CASCADE"), nullable=False, index=True)
    repo_id = Column(String(50), ForeignKey("repositories.id", ondelete="CASCADE"), nullable=False, index=True)
    state = Column(String(40), default="IDLE", index=True)
    active_agent = Column(String(50), nullable=True)
    active_provider = Column(String(50), nullable=True)
    active_model = Column(String(100), nullable=True)
    base_commit = Column(String(40), nullable=True)
    candidate_branch = Column(String(100), nullable=True)
    worktree_path = Column(String(500), nullable=True)
    retry_count = Column(Integer, default=0)
    max_retries = Column(Integer, default=3)
    error_message = Column(Text, nullable=True)
    verdict = Column(String(30), nullable=True)  # PASS, FAIL, BLOCKED, NEEDS_HUMAN_REVIEW
    started_at = Column(DateTime(timezone=True), default=get_utc_now)
    completed_at = Column(DateTime(timezone=True), nullable=True)

    ticket = relationship("TicketModel", back_populates="runs")
    repository = relationship("RepositoryModel", back_populates="runs")
    candidates = relationship("CandidateModel", back_populates="run", cascade="all, delete-orphan")
    test_results = relationship("TestResultModel", back_populates="run", cascade="all, delete-orphan")
    failure_trajectories = relationship("FailureTrajectoryModel", back_populates="run", cascade="all, delete-orphan")
    model_usages = relationship("ModelUsageModel", back_populates="run", cascade="all, delete-orphan")

class CandidateModel(Base):
    __tablename__ = "candidates"

    id = Column(String(36), primary_key=True, default=lambda: f"cand-{uuid.uuid4().hex[:8]}")
    run_id = Column(String(36), ForeignKey("runs.id", ondelete="CASCADE"), nullable=False, index=True)
    ticket_id = Column(String(36), ForeignKey("tickets.id", ondelete="CASCADE"), nullable=False)
    attempt = Column(Integer, default=1)
    diff_content = Column(Text, nullable=False)
    diff_hash = Column(String(64), nullable=False)
    patch_explanation = Column(Text, nullable=True)
    changed_files_json = Column(JSON, default=list)
    ast_changes_json = Column(JSON, default=dict)
    status = Column(String(30), default="PENDING")  # PENDING, APPLIED, EVALUATED, REJECTED, APPROVED
    created_at = Column(DateTime(timezone=True), default=get_utc_now)

    run = relationship("RunModel", back_populates="candidates")

class TestResultModel(Base):
    __tablename__ = "test_results"

    id = Column(String(36), primary_key=True, default=lambda: f"tst-{uuid.uuid4().hex[:8]}")
    run_id = Column(String(36), ForeignKey("runs.id", ondelete="CASCADE"), nullable=False, index=True)
    candidate_id = Column(String(36), nullable=True)
    test_type = Column(String(30), nullable=False)  # baseline, acceptance, regression
    test_command = Column(String(500), nullable=False)
    exit_code = Column(Integer, nullable=False)
    duration_ms = Column(Integer, default=0)
    passed_count = Column(Integer, default=0)
    failed_count = Column(Integer, default=0)
    error_count = Column(Integer, default=0)
    failures_json = Column(JSON, default=list)
    stdout_excerpt = Column(Text, nullable=True)
    stderr_excerpt = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), default=get_utc_now)

    run = relationship("RunModel", back_populates="test_results")

class FailureTrajectoryModel(Base):
    __tablename__ = "failure_trajectories"

    id = Column(String(36), primary_key=True, default=lambda: f"fail-{uuid.uuid4().hex[:8]}")
    run_id = Column(String(36), ForeignKey("runs.id", ondelete="CASCADE"), nullable=False, index=True)
    ticket_id = Column(String(36), ForeignKey("tickets.id", ondelete="CASCADE"), nullable=False, index=True)
    attempt = Column(Integer, default=1)
    provider = Column(String(50), nullable=True)
    model = Column(String(100), nullable=True)
    failed_tests_json = Column(JSON, default=list)
    traceback_excerpt = Column(Text, nullable=True)
    ast_diff_json = Column(JSON, default=dict)
    patch_hash = Column(String(64), nullable=True)
    root_cause_hypothesis = Column(Text, nullable=True)
    repair_hint = Column(Text, nullable=True)
    status = Column(String(30), default="UNRESOLVED")  # UNRESOLVED, REPAIRED, REPEATED
    created_at = Column(DateTime(timezone=True), default=get_utc_now)

    run = relationship("RunModel", back_populates="failure_trajectories")
    ticket = relationship("TicketModel", back_populates="failure_trajectories")

class ModelUsageModel(Base):
    __tablename__ = "model_usage"

    id = Column(String(36), primary_key=True, default=lambda: f"usg-{uuid.uuid4().hex[:8]}")
    run_id = Column(String(36), ForeignKey("runs.id", ondelete="CASCADE"), nullable=True, index=True)
    task_id = Column(String(50), nullable=True)
    agent_name = Column(String(50), nullable=False)
    provider = Column(String(50), nullable=False)
    model = Column(String(100), nullable=False)
    input_tokens = Column(Integer, nullable=True)
    output_tokens = Column(Integer, nullable=True)
    latency_ms = Column(Integer, default=0)
    estimated_cost_usd = Column(Float, nullable=True)
    is_fallback = Column(Boolean, default=False)
    status = Column(String(30), default="SUCCESS")
    created_at = Column(DateTime(timezone=True), default=get_utc_now)

    run = relationship("RunModel", back_populates="model_usages")

class AuditEventModel(Base):
    __tablename__ = "audit_events"

    id = Column(String(36), primary_key=True, default=lambda: f"aud-{uuid.uuid4().hex[:8]}")
    event_type = Column(String(50), nullable=False, index=True)  # TICKET_APPROVAL, MERGE_APPROVAL, REJECT, CONFIG_CHANGE
    actor = Column(String(100), default="human_operator")
    details_json = Column(JSON, default=dict)
    created_at = Column(DateTime(timezone=True), default=get_utc_now)

class AppSettingModel(Base):
    __tablename__ = "app_settings"

    key = Column(String(100), primary_key=True)
    value_json = Column(JSON, nullable=False)
    updated_at = Column(DateTime(timezone=True), default=get_utc_now, onupdate=get_utc_now)
