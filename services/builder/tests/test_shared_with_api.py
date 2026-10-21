"""Files the builder carries as verbatim copies of the platform API's (the services share no code).

`make test-builder` mounts the API's files read-only at their repo paths for the comparison.
See docs/decisions/2026-10-21-builder-numbered-sql-migrations.md and
docs/decisions/2026-10-21-one-keycloak-token-verifier.md.

Run from `services/builder/`:
    python -m pytest tests/test_shared_with_api.py
"""
from pathlib import Path

import pytest

SERVICE_ROOT = Path(__file__).resolve().parents[1]
API_PACKAGE = SERVICE_ROOT.parents[1] / "services" / "api" / "src" / "digitaltwins"

COPIES = {
    "app/database/migration_runner.py": API_PACKAGE / "postgres" / "migration_runner.py",
    "app/client/keycloak_verifier.py": API_PACKAGE / "core" / "keycloak_verifier.py",
}


@pytest.mark.parametrize("ours", sorted(COPIES))
def test_the_copy_matches_the_apis(ours):
    theirs = COPIES[ours]
    assert (SERVICE_ROOT / ours).read_bytes() == theirs.read_bytes(), (
        f"{ours} differs from {theirs.relative_to(SERVICE_ROOT.parents[1])}; change both together"
    )
