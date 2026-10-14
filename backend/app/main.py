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

    yield
    logger.info("Project Ouroboros Backend shutting down...")

app = FastAPI(
    title=settings.APP_NAME,
    description="Hierarchical Software Evolution and Deterministic Repair Engine",
    version="0.1.0",
    lifespan=lifespan
)

# Narrow CORS configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
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

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app", host=settings.HOST, port=settings.PORT, reload=True)
