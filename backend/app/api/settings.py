from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database.session import get_db
from app.database.models import RunModel, FailureTrajectoryModel
from app.database.repositories import (
    list_audit_events,
    get_setting,
    set_setting,
    record_audit_event
)
from app.schemas.settings import SystemSettings, MetricsOverviewResponse
from app.core.config import settings
from app.observability.telemetry import telemetry
from app.sandbox.detector import sandbox_detector
from app.providers.ollama_provider import ollama_provider
from app.providers.groq_provider import groq_provider

router = APIRouter(tags=["Settings & Telemetry"])

@router.get("/settings", response_model=SystemSettings)
async def get_system_settings(db: Session = Depends(get_db)):
    return SystemSettings(
        app_name=get_setting(db, "APP_NAME", settings.APP_NAME),
        theme=get_setting(db, "THEME", "dark"),
        log_level=get_setting(db, "LOG_LEVEL", settings.LOG_LEVEL),
        default_repo_path=get_setting(db, "DEFAULT_REPO_PATH", settings.DEFAULT_REPO_PATH),
        navigator_path=get_setting(db, "NAVIGATOR_PATH", settings.NAVIGATOR_PATH),
        max_local_concurrency=settings.MAX_LOCAL_CONCURRENCY,
        max_test_concurrency=settings.MAX_CONCURRENT_TESTS,
        memory_warning_threshold_mb=settings.MEMORY_WARNING_THRESHOLD_MB,
        max_repair_attempts=settings.MAX_REPAIR_ATTEMPTS,
        max_tickets_per_batch=settings.MAX_TICKETS_PER_BATCH,
        require_ticket_approval=True,
        require_remote_fallback_confirmation=settings.REQUIRE_FALLBACK_CONFIRMATION,
        require_merge_approval=True,
        sandbox_mode=settings.SANDBOX_MODE,
        subprocess_timeout_seconds=settings.SUBPROCESS_TIMEOUT_SECONDS
    )

@router.patch("/settings")
async def update_system_settings(req: dict, db: Session = Depends(get_db)):
    for k, v in req.items():
        set_setting(db, k.upper(), v)
    record_audit_event(db, "SETTINGS_UPDATED", details=req)
    return {"message": "Settings updated successfully."}

@router.get("/metrics/overview", response_model=MetricsOverviewResponse)
async def get_metrics_overview(db: Session = Depends(get_db)):
    runs = db.query(RunModel).all()
    total_runs = len(runs)
    successful_runs = sum(1 for r in runs if r.state == "COMPLETED")
    failed_runs = sum(1 for r in runs if r.state == "FAILED")
    acceptance_rate = round((successful_runs / total_runs) * 100, 1) if total_runs > 0 else 0.0

    trajectories_count = db.query(FailureTrajectoryModel).count()

    durations = [
        (r.completed_at - r.started_at).total_seconds()
        for r in runs if r.completed_at and r.started_at
    ]
    avg_duration = round(sum(durations) / len(durations), 1) if durations else 0.0

    sys_metrics = telemetry.get_system_metrics()
    sandbox = await sandbox_detector.detect_capabilities()
    ollama = await ollama_provider.check_health()
    groq = await groq_provider.check_health()

    return MetricsOverviewResponse(
        total_runs=total_runs,
        successful_runs=successful_runs,
        failed_runs=failed_runs,
        acceptance_rate=acceptance_rate,
        total_trajectories=trajectories_count,
        avg_run_duration_sec=avg_duration,
        free_ram_mb=sys_metrics["free_ram_mb"],
        total_ram_mb=sys_metrics["total_ram_mb"],
        cpu_percent=sys_metrics["cpu_percent"],
        docker_available=sandbox.get("docker_running", False),
        ollama_available=ollama.get("available", False),
        groq_available=groq.get("available", False)
    )

@router.get("/audit-events")
async def get_audit_log(db: Session = Depends(get_db)):
    events = list_audit_events(db, limit=40)
    return [
        {
            "id": e.id,
            "event_type": e.event_type,
            "actor": e.actor,
            "details": e.details_json,
            "created_at": e.created_at
        } for e in events
    ]
