from app.models.db_model import SessionLocal, Base, engine, PORTAL_DB_SCHEMA, DEPLOYMENT_ONE_BUILD
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


def migrate_workflow_is_sds(bind=engine):
    """Add workflows.is_sds, backfilled from workflow_type, only when the column is created.

    Until 2026-10-02 a set workflow_type marked an SDS package. Since then every
    workflow has a type, so running the backfill again would mark root-.cwl workflows as SDS.
    """
    from sqlalchemy import inspect, text

    inspector = inspect(bind)
    if not inspector.has_table("workflows"):
        return
    if "is_sds" in {col["name"] for col in inspector.get_columns("workflows")}:
        return
    logger.info("Migrating: ALTER TABLE workflows ADD COLUMN is_sds BOOLEAN, backfilled from workflow_type")
    with bind.begin() as conn:
        conn.execute(text("ALTER TABLE workflows ADD COLUMN is_sds BOOLEAN"))
        conn.execute(text("UPDATE workflows SET is_sds = (workflow_type IS NOT NULL)"))


def migrate_plugin_deployments_for_workflows(bind=engine):
    """Let a deployment belong to a gui workflow's build (create_all does this for new tables).

    Postgres tables created before 2026-10-02 get nullable plugin_id/build_id, the workflow_build_id
    foreign key and the one-build check. SQLite databases are only test or legacy ones and are left alone.
    """
    from sqlalchemy import inspect, text

    if bind.dialect.name != "postgresql":
        return
    inspector = inspect(bind)
    if not inspector.has_table("plugin_deployments"):
        return
    foreign_keys = {fk["name"] for fk in inspector.get_foreign_keys("plugin_deployments")}
    checks = {ck["name"] for ck in inspector.get_check_constraints("plugin_deployments")}
    with bind.begin() as conn:
        conn.execute(text("ALTER TABLE plugin_deployments ALTER COLUMN plugin_id DROP NOT NULL"))
        conn.execute(text("ALTER TABLE plugin_deployments ALTER COLUMN build_id DROP NOT NULL"))
        if "plugin_deployments_workflow_build_id_fkey" not in foreign_keys:
            logger.info("Migrating: plugin_deployments.workflow_build_id references workflow_builds.build_id")
            conn.execute(text("ALTER TABLE plugin_deployments ADD CONSTRAINT plugin_deployments_workflow_build_id_fkey "
                              "FOREIGN KEY (workflow_build_id) REFERENCES workflow_builds (build_id)"))
        if DEPLOYMENT_ONE_BUILD not in checks:
            logger.info("Migrating: a plugin deployment belongs to exactly one build")
            conn.execute(text(f"ALTER TABLE plugin_deployments ADD CONSTRAINT {DEPLOYMENT_ONE_BUILD} "
                              "CHECK ((build_id IS NULL) <> (workflow_build_id IS NULL))"))


def migrate_enum_values(bind=engine):
    """Add enum values that exist in the models but not yet in Postgres' native enum types."""
    from sqlalchemy import Enum, text

    if bind.dialect.name != "postgresql":
        return
    enums = {col.type.name: col.type.enums for table in Base.metadata.tables.values()
             for col in table.columns if isinstance(col.type, Enum) and col.type.name}
    # ADD VALUE is not allowed in a transaction block on older Postgres.
    with bind.connect().execution_options(isolation_level="AUTOCOMMIT") as conn:
        for name, values in enums.items():
            for value in values:
                conn.execute(text(f"ALTER TYPE {name} ADD VALUE IF NOT EXISTS '{value}'"))


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
    migrate_workflow_is_sds(bind)
    migrate_add_missing_columns(bind)
    migrate_plugin_deployments_for_workflows(bind)
    migrate_enum_values(bind)
