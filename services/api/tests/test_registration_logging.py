"""Registration errors and steps reach the API's log. Unit tests: Postgres, MinIO and FHIR are stubbed."""
import logging
import logging.config
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest
import uvicorn.config
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app import logging_setup
from app.main import create_app
from app.request_logging import install_request_error_logging
from app.routers import auth, dataset_fhir, dataset_uploads, datasets
from digitaltwins.measurements import jobs

UPLOADER = {"username": "alice", "token": "t", "claims": {"realm_access": {"roles": ["researcher"]}}}


def _messages(caplog):
    return [r.getMessage() for r in caplog.records]


def _request_records(caplog):
    return [r for r in caplog.records if r.name == "app.request"]


# ── Logging setup ──────────────────────────────────────────────────────


@pytest.fixture
def root_logging():
    root = logging.getLogger()
    saved = (root.level, root.handlers[:])
    # app.main configured logging at import, bound to the real stdout: start without it.
    root.handlers[:] = [h for h in root.handlers if not isinstance(h, logging_setup._StdoutHandler)]
    yield
    root.setLevel(saved[0])
    root.handlers[:] = saved[1]


def test_app_info_lines_reach_stdout_once_and_uvicorn_lines_are_not_duplicated(root_logging, capsys):
    logging.config.dictConfig(uvicorn.config.LOGGING_CONFIG)
    logging_setup.configure_logging()
    logging_setup.configure_logging()  # idempotent

    logging.getLogger("digitaltwins.measurements.jobs").info("Registration models commit: upload_id=u1")
    logging.getLogger("uvicorn.access").info('%s - "%s %s HTTP/%s" %d', "10.0.0.1:5", "GET", "/health", "1.1", 200)

    out = capsys.readouterr()
    assert out.out.count("Registration models commit: upload_id=u1") == 1
    assert (out.out + out.err).count("GET /health") == 1


def test_chatty_libraries_stay_at_warning(root_logging):
    logging_setup.configure_logging()

    assert logging.getLogger("botocore").getEffectiveLevel() == logging.WARNING
    assert logging.getLogger("urllib3").getEffectiveLevel() == logging.WARNING


# ── Request errors ─────────────────────────────────────────────────────


@pytest.fixture
def error_client():
    app = FastAPI()
    install_request_error_logging(app)

    @app.get("/missing")
    def missing():
        raise HTTPException(status_code=404, detail="Upload session not found")

    @app.get("/broken")
    def broken():
        raise HTTPException(status_code=502, detail="SEEK registration failed")

    @app.get("/typed")
    def typed(n: int):
        return n

    return TestClient(app)


def test_a_client_error_is_a_warning_with_its_reason_and_no_query_string(error_client, caplog):
    with caplog.at_level(logging.INFO, logger="app.request"):
        r = error_client.get("/missing?token=abc")

    assert (r.status_code, r.json()) == (404, {"detail": "Upload session not found"})
    [record] = _request_records(caplog)
    assert record.levelno == logging.WARNING
    assert record.getMessage() == "GET /missing -> 404: Upload session not found"


def test_a_server_error_is_an_error(error_client, caplog):
    with caplog.at_level(logging.INFO, logger="app.request"):
        r = error_client.get("/broken")

    assert r.status_code == 502
    [record] = _request_records(caplog)
    assert (record.levelno, record.getMessage()) == (logging.ERROR, "GET /broken -> 502: SEEK registration failed")


def test_a_validation_error_is_logged_and_its_response_is_unchanged(error_client, caplog):
    plain = FastAPI()

    @plain.get("/typed")
    def typed(n: int):
        return n

    with caplog.at_level(logging.INFO, logger="app.request"):
        r = error_client.get("/typed?n=x")

    assert (r.status_code, r.json()) == (422, TestClient(plain).get("/typed?n=x").json())
    assert _request_records(caplog)[0].getMessage().startswith("GET /typed -> 422: ")


def test_the_platform_app_logs_request_errors(caplog):
    app = create_app()
    app.dependency_overrides[auth.validate_credentials] = lambda: UPLOADER
    app.dependency_overrides[dataset_uploads.get_conn] = lambda: None

    with caplog.at_level(logging.INFO, logger="app.request"):
        r = TestClient(app).post("/datasets/uploads", json={
            "name": "x", "category": "nope", "source_kind": "folder", "manifest": []})

    assert r.status_code == 400
    assert _request_records(caplog)[0].getMessage().startswith("POST /datasets/uploads -> 400: Upload sessions support")


# ── Upload session steps ───────────────────────────────────────────────


class FakeStore:
    def __init__(self, assembled):
        self.assembled = assembled

    def init(self, upload_id, source_kind, manifest):
        pass

    def is_complete(self, upload_id):
        return True

    def assemble(self, upload_id):
        return self.assembled

    def cleanup(self, upload_id):
        pass


@pytest.fixture
def client(monkeypatch, tmp_path):
    monkeypatch.setenv("DATASET_STAGING_DIR", str(tmp_path / "staging"))
    assembled = tmp_path / "assembled"
    (assembled / "primary").mkdir(parents=True)
    monkeypatch.setattr(dataset_uploads, "_chunk_store", lambda: FakeStore(assembled))
    session = {"upload_id": "u1", "category": "models", "status": "receiving", "source_kind": "folder",
               "commit_mode": "on_approve", "fhir_mode": "none", "fhir_descriptions": None, "name": "Heart",
               "description": ""}
    monkeypatch.setattr(dataset_uploads.sessions, "create_session", lambda conn, **kw: "u1")
    monkeypatch.setattr(dataset_uploads.sessions, "get_session", lambda conn, upload_id: dict(session))
    monkeypatch.setattr(dataset_uploads.sessions, "update_session", lambda conn, upload_id, **kw: session.update(kw))
    monkeypatch.setattr(dataset_uploads.sessions, "delete_session", lambda conn, upload_id: None)
    monkeypatch.setattr(dataset_uploads.jobs, "run_commit_and_push", lambda *a, **kw: None)
    monkeypatch.setattr(dataset_uploads, "validate_model_structure", lambda root: (True, ""))
    monkeypatch.setattr(dataset_uploads.model_fhir, "build_descriptions", lambda *a, **kw: {"model": {}})
    app = create_app()
    app.dependency_overrides[auth.validate_credentials] = lambda: UPLOADER
    app.dependency_overrides[dataset_uploads.get_conn] = lambda: None
    c = TestClient(app)
    c.session = session
    return c


def test_session_creation_is_logged_with_the_user(client, caplog):
    with caplog.at_level(logging.INFO):
        r = client.post("/datasets/uploads", json={
            "name": "Heart", "category": "models", "source_kind": "folder",
            "manifest": [{"rel_path": "heart/primary/a.txt", "size": 1, "parts": 1}]})

    assert r.status_code == 200, r.text
    assert "Registration models upload session: upload_id=u1 name=Heart user=alice" in _messages(caplog)


def test_finalize_is_logged_with_the_outcome(client, caplog):
    with caplog.at_level(logging.INFO):
        r = client.post("/datasets/uploads/u1/finalize")

    assert r.status_code == 200, r.text
    assert "Registration models finalize: upload_id=u1 status=staged user=alice" in _messages(caplog)


def test_annotation_approval_and_cancel_are_logged(client, caplog):
    client.session["status"] = "staged"
    with caplog.at_level(logging.INFO):
        assert client.put("/datasets/uploads/u1/fhir/annotation", json={"descriptions": {"model": {}}}).status_code == 200
        assert client.post("/datasets/uploads/u1/approve").status_code == 202
    client.session["status"] = "staged"
    with caplog.at_level(logging.INFO):
        assert client.delete("/datasets/uploads/u1").status_code == 200

    messages = _messages(caplog)
    assert "Registration models annotate: upload_id=u1 user=alice" in messages
    assert "Registration models approval requested: upload_id=u1 user=alice" in messages
    assert "Registration models cancel: upload_id=u1 user=alice" in messages


# ── Committed dataset steps ────────────────────────────────────────────


@pytest.fixture
def fhir_client(monkeypatch):
    dataset = {"category": "models", "dataset_name": "Heart", "workflow_type": None, "fhir_status": "none"}
    monkeypatch.setattr(dataset_fhir.pipeline, "get_dataset_row", lambda conn, uuid: dict(dataset))
    monkeypatch.setattr(dataset_fhir.pipeline, "save_annotation", lambda conn, uuid, d: None)
    monkeypatch.setattr(dataset_fhir.pipeline, "load_annotation", lambda conn, uuid: {"model": {}})
    monkeypatch.setattr(dataset_fhir.model_fhir, "build_descriptions", lambda *a, **kw: {"model": {}})
    monkeypatch.setattr(dataset_fhir.jobs, "set_fhir_status", lambda *a, **kw: None)
    monkeypatch.setattr(dataset_fhir.jobs, "run_fhir_push_job", lambda uuid: None)
    app = create_app()
    app.dependency_overrides[auth.validate_credentials] = lambda: UPLOADER
    app.dependency_overrides[dataset_uploads.get_conn] = lambda: None
    return TestClient(app)


def test_dataset_annotation_and_push_request_are_logged(fhir_client, caplog):
    with caplog.at_level(logging.INFO):
        assert fhir_client.put("/datasets/d1/fhir/annotation", json={"descriptions": {"model": {}}}).status_code == 200
        assert fhir_client.post("/datasets/d1/fhir/push").status_code == 202

    messages = _messages(caplog)
    assert "Registration models annotate: dataset_uuid=d1 user=alice" in messages
    assert "Registration models FHIR push requested: dataset_uuid=d1 user=alice" in messages


def test_a_one_shot_upload_is_logged_with_the_user(monkeypatch, tmp_path, caplog):
    monkeypatch.setenv("DATASET_STAGING_DIR", str(tmp_path))
    monkeypatch.setattr(datasets, "_receive_upload", lambda files, tmp: tmp)
    monkeypatch.setattr(datasets, "_ingest_model", lambda *a: {"dataset_uuid": "d1"})
    app = create_app()
    app.dependency_overrides[auth.validate_credentials] = lambda: UPLOADER
    app.dependency_overrides[datasets.get_uploader] = lambda: None

    with caplog.at_level(logging.INFO):
        r = TestClient(app).post("/datasets", params={"category": "models"},
                                 files=[("files", ("heart/primary/a.txt", b"x", "text/plain"))])

    assert r.status_code == 200, r.text
    assert "Registration models upload: dataset_uuid=d1 user=alice" in _messages(caplog)


# ── Background jobs ────────────────────────────────────────────────────


@pytest.fixture
def job_db(monkeypatch):
    class Conn:
        def close(self):
            pass

    session = {"category": "models"}
    monkeypatch.setattr(jobs, "_connect", Conn)
    monkeypatch.setattr(jobs.sessions, "get_session", lambda conn, upload_id: session)
    monkeypatch.setattr(jobs.sessions, "update_session", lambda *a, **kw: None)
    monkeypatch.setattr(jobs, "set_fhir_status", lambda *a, **kw: None)
    monkeypatch.setattr(jobs, "dataset_dir", lambda upload_id: Path("/nonexistent"))


def test_a_commit_is_logged(job_db, monkeypatch, caplog):
    monkeypatch.setattr(jobs, "_commit", lambda *a: SimpleNamespace(dataset_uuid="d1", descriptions=None))

    with caplog.at_level(logging.INFO):
        jobs.run_commit_job("u1")

    assert "Registration models commit: upload_id=u1 dataset_uuid=d1" in _messages(caplog)


def test_a_failed_commit_is_logged_with_its_traceback(job_db, monkeypatch, caplog):
    def fail(*a):
        raise RuntimeError("SEEK is down")

    monkeypatch.setattr(jobs, "_commit", fail)

    with caplog.at_level(logging.INFO):
        jobs.run_commit_job("u1")

    [record] = [r for r in caplog.records if r.levelno == logging.ERROR]
    assert record.getMessage() == "Registration models commit failed: upload_id=u1 reason=SEEK is down"
    assert record.exc_info is not None


def test_a_fhir_push_is_logged(job_db, monkeypatch, caplog):
    monkeypatch.setattr(jobs.pipeline, "load_annotation", lambda conn, uuid: {"model": {}})
    monkeypatch.setattr(jobs.pipeline, "get_dataset_row", lambda conn, uuid: {"category": "models", "workflow_type": None})
    monkeypatch.setattr(jobs.pipeline, "store_fhir_json", lambda *a: None)
    monkeypatch.setattr(jobs.model_fhir, "push", lambda d, rest: {})
    monkeypatch.setattr(jobs.fhir_service, "get_fhir_rest", lambda: None)

    with caplog.at_level(logging.INFO):
        jobs.run_fhir_push_job("d1")

    assert "Registration models FHIR push completed: dataset_uuid=d1" in _messages(caplog)


def test_a_failed_workflow_tool_push_is_logged(job_db, monkeypatch, caplog):
    rows = {"w1": {"category": "workflows", "workflow_type": "script"}, "t1": {"category": "tools"}}
    monkeypatch.setattr(jobs.pipeline, "load_annotation", lambda conn, uuid: {"x": {}})
    monkeypatch.setattr(jobs.pipeline, "get_dataset_row", lambda conn, uuid: rows[uuid])
    monkeypatch.setattr(jobs.fhir_service, "get_fhir_rest", lambda: None)
    monkeypatch.setattr(jobs.workflow_fhir, "delete", lambda *a: None)
    monkeypatch.setattr(jobs, "linked_tools", lambda conn, uuid: [{"dataset_uuid": "t1"}])

    def store(category, uuid, d):
        if uuid == "t1":
            raise RuntimeError("HAPI unreachable")

    monkeypatch.setattr(jobs.pipeline, "store_fhir_json", store)

    with caplog.at_level(logging.INFO):
        jobs.run_fhir_push_job("w1")

    messages = [r.getMessage() for r in caplog.records if r.levelno == logging.ERROR]
    assert "Registration tools FHIR push failed: dataset_uuid=t1 workflow_dataset_uuid=w1 reason=HAPI unreachable" in messages
    assert "Registration workflows FHIR push failed: dataset_uuid=w1 reason=HAPI unreachable" in messages
