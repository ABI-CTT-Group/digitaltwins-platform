"""The builder's numbered SQL migrations (the runner itself is a copy of the API's; see test_shared_with_api.py).

Run from `services/builder/`:
    python -m pytest tests/test_migration_runner.py
"""
from app.database import migration_runner
from app.database.database import MIGRATIONS_DIR


def test_the_shipped_migrations_start_at_0001():
    assert [v for v, _ in migration_runner.discover(MIGRATIONS_DIR)][0] == "0001"
