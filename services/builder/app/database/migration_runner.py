"""Numbered SQL migration runner, shared by the platform API and the builder.

Applies ``NNNN_<name>.sql`` files from a directory, in version order, to one
Postgres schema. Each file runs in its own transaction and is recorded in that
schema's ``schema_migrations`` table. Runs are serialised with a Postgres
advisory lock, so processes starting together apply each migration exactly once.

This file is copied verbatim to services/builder/app/database/migration_runner.py
(the two services share no code); a builder test fails if the copies differ, so
edit both together. It needs nothing beyond the standard library and a DB-API
connection. docs/decisions/2026-10-21-builder-numbered-sql-migrations.md
"""
import logging
import re
from pathlib import Path

logger = logging.getLogger(__name__)

_FILENAME = re.compile(r"^(\d{4})_[\w-]+\.sql$")


def discover(migrations_dir):
    """Return ``[(version, path), ...]`` sorted by version."""
    found = {}
    for path in Path(migrations_dir).iterdir():
        match = _FILENAME.match(path.name)
        if not match:
            continue
        version = match.group(1)
        if version in found:
            raise ValueError(f"Duplicate migration version {version}: {found[version].name}, {path.name}")
        found[version] = path
    return sorted(found.items())


def apply_migrations(conn, migrations_dir, schema, lock_key):
    """Apply pending migrations on ``conn``; return the versions applied.

    ``schema`` holds the ``schema_migrations`` table; ``lock_key`` identifies the
    caller's advisory lock. A failing migration is rolled back and re-raised;
    later migrations are not attempted.
    """
    migrations = discover(migrations_dir)
    table = f"{schema}.schema_migrations"
    applied_now = []
    with conn.cursor() as cur:
        cur.execute("SELECT pg_advisory_lock(%s)", (lock_key,))
        conn.commit()
        try:
            cur.execute(
                f"CREATE TABLE IF NOT EXISTS {table} ("
                " version varchar(4) PRIMARY KEY,"
                " name text NOT NULL,"
                " applied_at timestamptz NOT NULL DEFAULT now())"
            )
            cur.execute(f"SELECT version FROM {table}")
            done = {row[0] for row in cur.fetchall()}
            conn.commit()

            for version, path in migrations:
                if version in done:
                    continue
                try:
                    cur.execute(path.read_text())
                    cur.execute(
                        f"INSERT INTO {table} (version, name) VALUES (%s, %s)",
                        (version, path.name),
                    )
                    conn.commit()
                except Exception:
                    conn.rollback()
                    logger.error("Migration %s failed; rolled back", path.name)
                    raise
                logger.info("Applied migration %s", path.name)
                applied_now.append(version)
        finally:
            cur.execute("SELECT pg_advisory_unlock(%s)", (lock_key,))
            conn.commit()
    return applied_now
