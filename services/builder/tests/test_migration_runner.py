"""The builder runs the platform API's migration runner, as a verbatim copy (the services share no code).

`make test-builder` mounts the API's file read-only at its repo path for the comparison.
See docs/decisions/2026-10-21-builder-numbered-sql-migrations.md.

Run from `services/builder/`:
    python -m pytest tests/test_migration_runner.py
"""
from pathlib import Path

from app.database import migration_runner
from app.database.database import MIGRATIONS_DIR

SERVICE_ROOT = Path(__file__).resolve().parents[1]
API_RUNNER = SERVICE_ROOT.parents[1] / "services" / "api" / "src" / "digitaltwins" / "postgres" / "migration_runner.py"


def test_the_runner_is_an_exact_copy_of_the_apis():
    ours = SERVICE_ROOT / "app" / "database" / "migration_runner.py"
    assert ours.read_bytes() == API_RUNNER.read_bytes(), (
        "app/database/migration_runner.py differs from services/api/src/digitaltwins/postgres/migration_runner.py; "
        "change both together"
    )


def test_the_shipped_migrations_start_at_0001():
    assert [v for v, _ in migration_runner.discover(MIGRATIONS_DIR)][0] == "0001"
