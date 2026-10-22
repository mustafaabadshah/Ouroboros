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

    # Ensure test harness dependencies (pytest, pytest-asyncio) are available
    try:
        import pytest
    except ImportError:
        logger.info("pytest not found in runtime environment. Auto-installing pytest...")
        try:
            import subprocess, sys
            subprocess.run([sys.executable, "-m", "pip", "install", "pytest>=8.0.0", "pytest-asyncio>=0.23.0"], check=False)
            logger.info("pytest installation check finished.")
        except Exception as pi_err:
            logger.error(f"Failed to auto-install pytest: {pi_err}")

    # Seed default repository registration if present on disk
    candidate_paths = [
        Path(settings.DEFAULT_REPO_PATH),
        Path("/opt/render/project/multi_agent_ai_chess_arena"),
        Path.cwd().parent / "multi_agent_ai_chess_arena",
        Path.cwd() / "repos" / "multi_agent_ai_chess_arena",
        Path("/opt/render/project/agent_chess")
    ]
    resolved_repo_path = next((p for p in candidate_paths if p.exists() and p.is_dir()), None)
    
    if not resolved_repo_path:
        default_cloud_path = Path("/opt/render/project/multi_agent_ai_chess_arena")
        try:
            if default_cloud_path.parent.exists() and not default_cloud_path.exists():
                logger.info("Auto-cloning default repo for cloud startup...")
                import subprocess
                subprocess.run(
                    ["git", "clone", "--depth", "1", "https://github.com/mustafaabadshah/Multi-Agent-AI-Chess-Arena.git", str(default_cloud_path)],
                    capture_output=True, timeout=60
                )
                if default_cloud_path.exists() and default_cloud_path.is_dir():
                    resolved_repo_path = default_cloud_path
        except Exception as clone_err:
            logger.warning(f"Startup cloud auto-clone notice: {clone_err}")

    if resolved_repo_path:
        db = SessionLocal()
        try:
            get_or_create_repository(
                db=db,
                repo_id="agent_chess",
                name="Agent Chess (ChessMind Arena)",
                path=str(resolved_repo_path),
                file_count=48
            )
            get_or_create_repository(
                db=db,
                repo_id="multi_agent_ai_chess_arena",
                name="Multi-Agent-AI-Chess-Arena",
                path=str(resolved_repo_path),
                file_count=48
            )
            logger.info(f"Registered default target repositories at: {resolved_repo_path}")
        except Exception as e:
            logger.warning(f"Could not seed default repositories: {e}")
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
            repo_path=resolved_repo_path if resolved_repo_path and resolved_repo_path.exists() else None,
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

from fastapi.responses import JSONResponse

@app.exception_handler(Exception)
async def global_exception_handler(request, exc):
    import traceback
    tb = traceback.format_exc()
    logger.error(f"Global unhandled error on {request.url.path}: {exc}\n{tb}")
    return JSONResponse(
        status_code=500,
        content={"detail": str(exc), "traceback": tb.splitlines()}
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

@app.get("/")
async def root_index():
    return {"message": "Project Ouroboros API is running", "docs": "/docs", "health": "/health"}

@app.get("/health")
async def root_health():
    return {"status": "ok", "app": settings.APP_NAME, "version": "0.1.0"}

from fastapi.responses import HTMLResponse
from app.observability.dashboard_html import get_phoenix_dashboard_html

@app.get("/phoenix", response_class=HTMLResponse)
@app.get("/observability", response_class=HTMLResponse)
async def phoenix_dashboard_view():
    """Renders the standalone Arize Phoenix AI Observability & Log Dashboard."""
    return HTMLResponse(content=get_phoenix_dashboard_html(), status_code=200)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app", host=settings.HOST, port=settings.PORT, reload=True)
