from app.database import migration_runner
from app.models.db_model import SessionLocal, Base, engine, PORTAL_DB_SCHEMA
import os
import logging
from pathlib import Path

logger = logging.getLogger(__name__)

MIGRATIONS_DIR = Path(__file__).parent / "migrations"
# Arbitrary constant identifying the builder's migration advisory lock (the API's is "dtmi").
_LOCK_KEY = 0x6474_706D  # "dtpm"


def create_tables(bind=engine):
    Base.metadata.create_all(bind=bind)


def ensure_data_directory():
    database_path = os.getenv("DATABASE_PATH", "./data/plugin_registry.db")
    data_dir = os.path.dirname(database_path)
    if not os.path.exists(data_dir):
        os.makedirs(data_dir, exist_ok=True)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db(bind=engine):
    """Create or migrate the builder's tables.

    On Postgres, applies app/database/migrations/ to the portal schema with the runner the platform
    API also uses (docs/decisions/2026-10-21-builder-numbered-sql-migrations.md). SQLite databases
    are only test or standalone ones: their tables are created from the models.
    """
    from sqlalchemy import inspect, text

    if bind.dialect.name == "sqlite":
        ensure_data_directory()
        create_tables(bind)
        return
    # Check first: even CREATE SCHEMA IF NOT EXISTS needs CREATE on the database,
    # which the platform's portal role (owner of the schema only) does not have.
    if not inspect(bind).has_schema(PORTAL_DB_SCHEMA):
        with bind.begin() as conn:
            conn.execute(text(f"CREATE SCHEMA IF NOT EXISTS {PORTAL_DB_SCHEMA}"))
    conn = bind.raw_connection()
    try:
        applied = migration_runner.apply_migrations(conn.driver_connection, MIGRATIONS_DIR, PORTAL_DB_SCHEMA, _LOCK_KEY)
    finally:
        conn.close()
    logger.info("Applied %d migration(s): %s", len(applied), ", ".join(applied) or "none pending")
