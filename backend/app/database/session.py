from pathlib import Path
from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker
from app.core.config import settings
from app.core.logging import logger

# Ensure parent directory for SQLite database exists
if "sqlite" in settings.DATABASE_URL:
    db_file = settings.DATABASE_URL.replace("sqlite:///", "")
    db_path = Path(db_file)
    db_path.parent.mkdir(parents=True, exist_ok=True)

engine = create_engine(
    settings.DATABASE_URL,
    connect_args={"check_same_thread": False} if "sqlite" in settings.DATABASE_URL else {},
    pool_pre_ping=True
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def init_db():
    """Initializes tables in the SQLite database and applies non-destructive column additions."""
    from app.database import models  # noqa: F401
    Base.metadata.create_all(bind=engine)
    if "sqlite" in settings.DATABASE_URL:
        from sqlalchemy import text
        with engine.connect() as conn:
            try:
                conn.execute(text("ALTER TABLE tickets ADD COLUMN acceptance_test_template TEXT"))
                conn.commit()
            except Exception:
                pass
    logger.info("Project Ouroboros SQLite database schema initialized.")
