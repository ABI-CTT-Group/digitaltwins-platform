from app.models.db_model import SessionLocal, Base, engine, PORTAL_DB_SCHEMA
import os
import logging

logger = logging.getLogger(__name__)


def create_tables(bind=engine):
    Base.metadata.create_all(bind=bind)


def migrate_add_missing_columns(bind=engine):
    """Add columns that exist in the SQLAlchemy model but not yet in the database."""
    from sqlalchemy import inspect, text

    inspector = inspect(bind)
    for table_name, table in Base.metadata.tables.items():
        if not inspector.has_table(table_name):
            continue
        existing_cols = {col["name"] for col in inspector.get_columns(table_name)}
        for col in table.columns:
            if col.name not in existing_cols:
                col_type = col.type.compile(dialect=bind.dialect)
                default = ""
                if col.default is not None and col.default.is_scalar:
                    default = f" DEFAULT {col.default.arg!r}"
                stmt = f"ALTER TABLE {table_name} ADD COLUMN {col.name} {col_type}{default}"
                logger.info(f"Migrating: {stmt}")
                with bind.begin() as conn:
                    conn.execute(text(stmt))


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
    from sqlalchemy import inspect, text

    if bind.dialect.name == "sqlite":
        ensure_data_directory()
    # Check first: even CREATE SCHEMA IF NOT EXISTS needs CREATE on the database,
    # which the platform's portal role (owner of the schema only) does not have.
    elif not inspect(bind).has_schema(PORTAL_DB_SCHEMA):
        with bind.begin() as conn:
            conn.execute(text(f"CREATE SCHEMA IF NOT EXISTS {PORTAL_DB_SCHEMA}"))
    create_tables(bind)
    migrate_add_missing_columns(bind)
