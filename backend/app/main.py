from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pathlib import Path

from app.core.config import settings
from app.core.logging import logger
from app.database.session import init_db, SessionLocal
from app.database.repositories import get_or_create_repository

# API Routers
from app.api.health import router as health_router
from app.api.repositories import router as repositories_router
from app.api.models import router as models_router
from app.api.tickets import router as tickets_router
from app.api.runs import router as runs_router
from app.api.failures import router as failures_router
from app.api.settings import router as settings_router
from app.api.evaluation import router as evaluation_router

from app.observability.phoenix_service import phoenix_service

@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Initializing Project Ouroboros Backend...")
    init_db()
    phoenix_service.initialize()

    # Seed default repository registration if present on disk
    default_repo_path = Path(settings.DEFAULT_REPO_PATH)
    if default_repo_path.exists():
        db = SessionLocal()
        try:
            get_or_create_repository(
                db=db,
                repo_id="agent_chess",
                name="Agent Chess (ChessMind Arena)",
                path=str(default_repo_path),
                file_count=48
            )
            logger.info(f"Registered default target repository: {default_repo_path}")
        except Exception as e:
            logger.warning(f"Could not seed default repository: {e}")
        finally:
            db.close()

    # Reconcile interrupted runs on server restart
    rec_db = SessionLocal()
    try:
        from app.database.models import RunModel
        interrupted = rec_db.query(RunModel).filter(
            RunModel.state.in_([
                "IDLE", "BASELINE_VALIDATION", "PLANNING", "CODING",
                "PATCH_VALIDATION", "ACCEPTANCE_TESTS", "REGRESSION_TESTS",
                "REPAIR_REQUIRED", "REVIEW"
            ])
        ).all()
        for r in interrupted:
            r.state = "FAILED"
            r.error_message = "Process interrupted by server restart. Run halted safely."
        if interrupted:
            rec_db.commit()
            logger.info(f"Reconciled {len(interrupted)} interrupted run(s) on startup.")
    except Exception as rec_err:
        logger.debug(f"Startup run reconciliation notice: {rec_err}")
    finally:
        rec_db.close()

    # Clean up stale candidate worktrees
    try:
        from app.integrations.git.worktree import git_worktree_manager
        await git_worktree_manager.garbage_collect_stale_worktrees(
            repo_path=default_repo_path if default_repo_path.exists() else None,
            max_age_hours=24
        )
    except Exception as gc_err:
        logger.debug(f"Startup worktree GC notice: {gc_err}")

    yield
    logger.info("Project Ouroboros Backend shutting down...")

app = FastAPI(
    title=settings.APP_NAME,
    description="Hierarchical Software Evolution and Deterministic Repair Engine",
    version="0.1.0",
    lifespan=lifespan
)

# CORS configuration with multi-domain cloud support
_origins = settings.cors_origins_list
_has_wildcard = "*" in _origins

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"] if _has_wildcard else _origins,
    allow_credentials=False if _has_wildcard else True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount Routers under /api
app.include_router(health_router, prefix="/api")
app.include_router(repositories_router, prefix="/api")
app.include_router(models_router, prefix="/api")
app.include_router(tickets_router, prefix="/api")
app.include_router(runs_router, prefix="/api")
app.include_router(failures_router, prefix="/api")
app.include_router(settings_router, prefix="/api")
app.include_router(evaluation_router)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app", host=settings.HOST, port=settings.PORT, reload=True)
