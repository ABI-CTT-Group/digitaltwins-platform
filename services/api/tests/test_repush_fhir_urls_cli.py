"""Re-pushing measurement datasets whose stored FHIR file URLs name an old API address.

After the API moved from /digitaltwins-api to /api, HAPI, the stored annotation and fhir.json still
link /digitaltwins-api/datasets/<uuid>/files/primary/...; a re-push recomputes them from API_PUBLIC_URL.
"""
import pytest

from digitaltwins.cli import repush_fhir_urls as cli
from digitaltwins.measurements import jobs

UUID = "0b9f6c1e-0000-11f1-8000-0242ac120002"
NEW = "https://platform.example/api"
OLD = "https://platform.example/digitaltwins-api"


def _descriptions(*bases):
    files = f"/datasets/{UUID}/files/primary"
    return {"patients": [{"name": "sub-1", "imagingStudy": [{"endpointUrl": f"{b}{files}/sub-1"} for b in bases]}]}


# ── Which annotations are stale ───────────────────────────────────────


@pytest.mark.parametrize("descriptions, stale", [
    (_descriptions(OLD), True),
    (_descriptions(NEW, OLD), True),   # half-migrated
    (_descriptions(NEW), False),
    ({"patients": [{"name": "sub-1"}]}, False),  # no file URLs at all
])
def test_is_stale(descriptions, stale):
    assert cli.is_stale(descriptions, UUID, NEW) is stale


def test_the_current_base_ignores_a_trailing_slash():
    assert cli.is_stale(_descriptions(NEW), UUID, NEW + "/") is False


# ── The run ───────────────────────────────────────────────────────────


def _row(uuid, status="completed", base=OLD, name=None):
    files = f"/datasets/{uuid}/files/primary"
    return {"dataset_uuid": uuid, "dataset_name": name or uuid, "fhir_status": status,
            "descriptions": {"patients": [{"imagingStudy": [{"endpointUrl": f"{base}{files}/s"}]}]}}


@pytest.fixture
def run(monkeypatch):
    """The CLI against canned candidate rows; pushes record what they did and how they ended."""
    monkeypatch.setenv("API_PUBLIC_URL", NEW)
    state = {"rows": [], "pushed": [], "outcome": {}, "closed": False}

    class Conn:
        def close(self):
            state["closed"] = True

    def push(dataset_uuid):
        state["pushed"].append(dataset_uuid)
        outcome = state["outcome"].get(dataset_uuid, ("completed", None))
        if isinstance(outcome, Exception):
            raise outcome
        state["status"] = outcome

    monkeypatch.setattr(cli, "_connect", Conn)
    monkeypatch.setattr(cli, "candidates", lambda conn: state["rows"])
    monkeypatch.setattr(jobs, "run_fhir_push_job", push)
    monkeypatch.setattr(cli, "_fhir_status", lambda conn, dataset_uuid: state["status"])
    return state


def test_dry_run_lists_the_stale_datasets_and_pushes_nothing(run, capsys):
    run["rows"] = [_row("a"), _row("b", base=NEW)]
    assert cli.main(["--dry-run"]) == 0
    assert run["pushed"] == []
    out = capsys.readouterr().out
    assert "a" in out and "Would re-push 1 dataset" in out


def test_stale_completed_datasets_are_re_pushed(run, capsys):
    run["rows"] = [_row("a"), _row("b", base=NEW), _row("c")]
    assert cli.main([]) == 0
    assert run["pushed"] == ["a", "c"]
    assert "2 re-pushed, 0 failed, 0 skipped" in capsys.readouterr().out
    assert run["closed"]


def test_a_push_in_progress_is_skipped_and_reported(run, capsys):
    run["rows"] = [_row("a", status="pushing"), _row("b", status="pending")]
    assert cli.main([]) == 0
    assert run["pushed"] == []
    out = capsys.readouterr().out
    assert "0 re-pushed, 0 failed, 2 skipped" in out and "in progress" in out


def test_a_failed_push_does_not_stop_the_others(run, capsys):
    run["rows"] = [_row("a"), _row("b"), _row("c")]
    run["outcome"] = {"a": ("failed", "HAPI 500"), "b": RuntimeError("MinIO down")}
    assert cli.main([]) == 1
    assert run["pushed"] == ["a", "b", "c"]
    captured = capsys.readouterr()
    assert "1 re-pushed, 2 failed, 0 skipped" in captured.out
    assert "HAPI 500" in captured.err and "MinIO down" in captured.err


def test_nothing_stale_is_nothing_to_do(run, capsys):
    run["rows"] = [_row("a", base=NEW)]
    assert cli.main([]) == 0
    assert run["pushed"] == []
    assert "Nothing to re-push" in capsys.readouterr().out


# ── The candidate query, against the real schema ──────────────────────


@pytest.mark.integration
def test_candidates_are_annotated_measurement_datasets_with_a_push_on_record(platform_db):
    from psycopg2.extras import Json

    conn = platform_db()
    rows = {
        "measurement": ("measurements", None, "completed"),
        "in-flight": ("measurements", None, "pushing"),
        "never-pushed": ("measurements", None, "none"),
        "failed": ("measurements", None, "failed"),
        "tool": ("tools", None, "completed"),
        "model": ("models", None, "completed"),
        "workflow": ("workflows", "script", "completed"),
    }
    uuids = {}
    with conn.cursor() as cur:
        for name, (category, workflow_type, status) in rows.items():
            cur.execute("INSERT INTO dataset (dataset_name, category, workflow_type, fhir_status) "
                        "VALUES (%s, %s, %s, %s) RETURNING dataset_uuid", (name, category, workflow_type, status))
            uuids[name] = str(cur.fetchone()[0])
            cur.execute("INSERT INTO dataset_fhir_annotation (dataset_uuid, descriptions) VALUES (%s, %s)",
                        (uuids[name], Json({"name": name})))
        cur.execute("INSERT INTO dataset (dataset_name, category, fhir_status) VALUES ('unannotated', "
                    "'measurements', 'completed')")
    conn.commit()

    found = {r["dataset_name"]: r for r in cli.candidates(conn)}
    conn.close()
    assert sorted(found) == ["in-flight", "measurement"]
    assert found["measurement"]["dataset_uuid"] == uuids["measurement"]
    assert found["measurement"]["descriptions"] == {"name": "measurement"}
