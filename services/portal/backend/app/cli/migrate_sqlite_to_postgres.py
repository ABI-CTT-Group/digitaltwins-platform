"""CLI: one-off copy of the portal's SQLite database into the platform Postgres.

Runs inside the portal-backend container with the PORTAL_DB_* variables set
(the target is the app's own engine). The SQLite file is opened read-only.

What it does, in a single target transaction:
  1. Creates the ``portal`` schema and tables (same as app startup).
  2. Refuses to run if any portal table in the target already has rows, so a
     rerun can never duplicate data.
  3. Copies every table parent-first, keeping ids and timestamps verbatim.
     Only columns present in the source are copied; the rest get model defaults.
     NUL characters are removed from text (Postgres cannot store them; old build
     logs captured from vite output contain them) and reported per column.
     The target enforces foreign keys, so an orphaned row aborts the whole copy.
  4. Checks the target row count of every table matches the source.
With --dry-run, steps 2-4 run and are then rolled back (the empty schema and
tables from step 1 stay, exactly as app startup would leave them).

Usage:
  python -m app.cli.migrate_sqlite_to_postgres [--sqlite-path PATH] [--dry-run]

Exit codes: 0 success / 1 user error (no Postgres configured, missing file) / 2 migration refused or failed.
"""
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

from sqlalchemy import JSON, create_engine, func, inspect, null, select
from sqlalchemy.engine import Engine
from sqlalchemy.exc import SQLAlchemyError

from app.database.database import init_db
from app.models.db_model import Base


class MigrationError(Exception):
    pass


class _DryRun(Exception):
    pass


def migrate(source: Engine, target: Engine, dry_run: bool = False) -> tuple[dict[str, int], dict[str, int]]:
    """Copy all portal tables from ``source`` to ``target``.

    Returns (rows copied per table, values with NUL removed per ``table.column``).
    """
    init_db(bind=target)
    source_insp = inspect(source)
    counts: dict[str, int] = {}
    stripped: dict[str, int] = {}
    try:
        with source.connect() as src, target.begin() as dst:
            for table in Base.metadata.sorted_tables:
                if dst.execute(select(func.count()).select_from(table)).scalar_one():
                    raise MigrationError(f"target table {table.name!r} is not empty; refusing to migrate")

            for table in Base.metadata.sorted_tables:
                if not source_insp.has_table(table.name):
                    counts[table.name] = 0
                    continue
                source_cols = {c["name"] for c in source_insp.get_columns(table.name)}
                cols = [c for c in table.columns if c.name in source_cols]
                source_rows = src.execute(select(*cols)).mappings().all()
                for row in source_rows:
                    values = {}
                    for k, v in row.items():
                        if v is None and isinstance(table.c[k].type, JSON):
                            v = null()  # keeps SQL NULL (a bare None would be stored as JSON 'null')
                        elif isinstance(v, str) and "\x00" in v:
                            v = v.replace("\x00", "")
                            stripped[f"{table.name}.{k}"] = stripped.get(f"{table.name}.{k}", 0) + 1
                        values[k] = v
                    dst.execute(table.insert().values(**values))
                copied = dst.execute(select(func.count()).select_from(table)).scalar_one()
                if copied != len(source_rows):
                    raise MigrationError(f"{table.name}: copied {copied} rows, source has {len(source_rows)}")
                counts[table.name] = copied

            if dry_run:
                raise _DryRun
    except _DryRun:
        pass
    except SQLAlchemyError as e:
        raise MigrationError(f"copy failed and was rolled back: {e}") from e
    return counts, stripped


def _fail(message: str, code: int) -> None:
    print(f"\n  ✗ {message}", file=sys.stderr)
    sys.exit(code)


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Copy the portal SQLite database into Postgres.")
    parser.add_argument("--sqlite-path", default=os.getenv("DATABASE_PATH", "/data/plugin_registry.db"),
                        help="source SQLite file (default: $DATABASE_PATH)")
    parser.add_argument("--dry-run", action="store_true", help="run every check and the copy, then roll back")
    args = parser.parse_args(argv)

    from app.models.db_model import engine as target
    if target.dialect.name != "postgresql":
        _fail("target is not Postgres — set PORTAL_DB_HOST and the other PORTAL_DB_* variables", 1)
    sqlite_path = Path(args.sqlite_path).resolve()
    if not sqlite_path.is_file():
        _fail(f"SQLite file not found: {sqlite_path}", 1)
    source = create_engine(f"sqlite:///file:{sqlite_path}?mode=ro&uri=true")

    print(f"  Source: {sqlite_path}")
    print(f"  Target: {target.url.render_as_string(hide_password=True)} (schema portal)")
    try:
        counts, stripped = migrate(source, target, dry_run=args.dry_run)
    except MigrationError as e:
        _fail(str(e), 2)
    for name, n in counts.items():
        print(f"    {name:<30} {n}")
    for column, n in stripped.items():
        print(f"  ! removed NUL characters from {n} value(s) in {column}")
    print(f"\n  ✓ {'Dry run OK — nothing written' if args.dry_run else 'Migrated'}: {sum(counts.values())} rows.")


if __name__ == "__main__":
    main()
