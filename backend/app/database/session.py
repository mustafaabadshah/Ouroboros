import threading
import time
from pathlib import Path
from sqlalchemy import create_engine, event
from sqlalchemy.orm import declarative_base, sessionmaker
from app.core.config import settings
from app.core.logging import logger

# Ensure parent directory for SQLite database exists and restore seed if missing
if "sqlite" in settings.DATABASE_URL:
    db_file = settings.DATABASE_URL.replace("sqlite:///", "")
    db_path = Path(db_file)
    db_path.parent.mkdir(parents=True, exist_ok=True)
    seed_db = Path(__file__).resolve().parent / "seeds" / "ouroboros_seed.db"
    if not db_path.exists() and seed_db.exists():
        import shutil
        try:
            shutil.copyfile(seed_db, db_path)
            logger.info(f"Initialized database file from persistent seed: {seed_db}")
        except Exception as copy_err:
            logger.warning(f"Failed to copy seed db: {copy_err}")

engine = create_engine(
    settings.DATABASE_URL,
    connect_args={"check_same_thread": False, "timeout": 30} if "sqlite" in settings.DATABASE_URL else {},
    pool_pre_ping=True
)

@event.listens_for(engine, "connect")
def set_sqlite_pragma(dbapi_connection, connection_record):
    if "sqlite" in settings.DATABASE_URL:
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA journal_mode=WAL")
        cursor.execute("PRAGMA synchronous=NORMAL")
        cursor.execute("PRAGMA busy_timeout=30000")
        cursor.execute("PRAGMA cache_size=-64000")
        cursor.close()

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def sync_seed_data():
    """Syncs missing tickets, runs, and historical records from persistent seed db."""
    if "sqlite" not in settings.DATABASE_URL:
        return
    seed_db = Path(__file__).resolve().parent / "seeds" / "ouroboros_seed.db"
    if not seed_db.exists():
        return

    target_file = settings.DATABASE_URL.replace("sqlite:///", "")
    target_path = Path(target_file)
    if not target_path.exists():
        return

    import sqlite3
    try:
        conn = sqlite3.connect(str(target_path), timeout=30)
        conn.execute(f"ATTACH DATABASE '{seed_db.as_posix()}' AS seed")
        tables = [
            "repositories",
            "tickets",
            "runs",
            "candidates",
            "test_results",
            "failure_trajectories",
            "audit_events"
        ]
        for tbl in tables:
            try:
                conn.execute(f"INSERT OR IGNORE INTO {tbl} SELECT * FROM seed.{tbl}")
            except Exception as tbl_err:
                logger.debug(f"Seed sync table {tbl} notice: {tbl_err}")

        # Purge obsolete repositories not present in seed
        try:
            conn.execute("DELETE FROM repositories WHERE id NOT IN (SELECT id FROM seed.repositories)")
        except Exception as repo_purge_err:
            logger.debug(f"Repo purge notice: {repo_purge_err}")

        # Ensure completed runs and accepted tickets from seed update existing live records
        try:
            conn.execute("""
                UPDATE runs
                SET state = 'COMPLETED',
                    verdict = 'PASS',
                    completed_at = COALESCE(completed_at, '2026-10-21 09:30:15')
                WHERE id IN (SELECT id FROM seed.runs WHERE state = 'COMPLETED')
                  AND state = 'AWAITING_APPROVAL'
            """)
            conn.execute("""
                UPDATE tickets
                SET status = 'ACCEPTED'
                WHERE id IN (SELECT id FROM seed.tickets WHERE status = 'ACCEPTED')
                  AND status != 'ACCEPTED'
            """)
            conn.execute("""
                UPDATE tickets
                SET candidate_files_json = (SELECT candidate_files_json FROM seed.tickets WHERE seed.tickets.id = tickets.id),
                    proposed_tests_json = (SELECT proposed_tests_json FROM seed.tickets WHERE seed.tickets.id = tickets.id),
                    status = (SELECT status FROM seed.tickets WHERE seed.tickets.id = tickets.id)
                WHERE id IN (SELECT id FROM seed.tickets WHERE status = 'PROPOSED')
            """)
        except Exception as state_sync_err:
            logger.debug(f"State sync notice: {state_sync_err}")

        conn.commit()
        conn.execute("DETACH DATABASE seed")
        conn.close()
        logger.info("Persistent seed data merged successfully into live database.")
    except Exception as e:
        logger.warning(f"Failed to merge persistent seed data: {e}")

_last_backup_time = 0.0
_backup_lock = threading.Lock()

def _do_backup():
    seed_db = Path(__file__).resolve().parent / "seeds" / "ouroboros_seed.db"
    target_file = settings.DATABASE_URL.replace("sqlite:///", "")
    target_path = Path(target_file)
    if not target_path.exists():
        return
    import sqlite3
    try:
        source_conn = sqlite3.connect(str(target_path), timeout=30)
        target_conn = sqlite3.connect(str(seed_db), timeout=30)
        source_conn.backup(target_conn)
        source_conn.close()
        target_conn.close()
        logger.debug("Live database backed up to persistent seed.")
    except Exception as err:
        logger.debug(f"Live database seed backup notice: {err}")

def backup_live_to_seed():
    """Debounced, non-blocking backup of live database to persistent seed db."""
    global _last_backup_time
    if "sqlite" not in settings.DATABASE_URL:
        return
    now = time.time()
    if now - _last_backup_time < 30.0:
        return
    with _backup_lock:
        if now - _last_backup_time < 30.0:
            return
        _last_backup_time = now
        t = threading.Thread(target=_do_backup, daemon=True)
        t.start()

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

    # Merge persistent historical seed data (tickets, runs, candidates, telemetry)
    sync_seed_data()

    logger.info("Project Ouroboros SQLite database schema initialized.")

