"""python -m digitaltwins.cli.import_dataset: login + role gate, then the in-process pipeline."""
import json
import shutil
from pathlib import Path

import pytest

from digitaltwins import tools
from digitaltwins.cli import import_dataset, keycloak_login
from digitaltwins.measurements import jobs, sessions
from digitaltwins.measurements.staging import dataset_dir
from digitaltwins.measurements.tree import build_tree
from test_datasets_workflows_api import tool_bucket  # noqa: F401  (fixture)

FIXTURE = Path(__file__).parent / "data" / "example_sds_dataset"
FIXTURE_ZIP = Path(__file__).parent / "data" / "example_sds_dataset.zip"


# ── Unit: role gate + device flow ──────────────────────────────────────


@pytest.mark.parametrize("roles", [["admin"], ["offline_access", "researcher"]])
def test_role_gate_accepts_upload_roles(roles):
    claims = {"preferred_username": "alice", "realm_access": {"roles": roles}}
    assert keycloak_login.require_upload_role(claims) == "alice"


def test_the_cli_verifies_tokens_with_the_shared_verifier(monkeypatch):
    import time
    import jwt
    from digitaltwins.core.keycloak_verifier import InvalidToken
    from test_keycloak_verifier import ISSUER, REALM, FakeRealm, _rsa_key

    realm = FakeRealm()
    realm.keys["k1"] = _rsa_key()
    monkeypatch.setenv("KEYCLOAK_BASE_URL", realm.base_url)
    monkeypatch.setenv("KEYCLOAK_REALM", REALM)
    monkeypatch.setattr(keycloak_login, "_verifier", None)

    def token(azp):
        now = int(time.time())
        claims = {"iss": ISSUER, "azp": azp, "typ": "Bearer", "iat": now, "exp": now + 300}
        return jwt.encode(claims, realm.keys["k1"], algorithm="RS256", headers={"kid": "k1"})

    try:
        assert keycloak_login.verify_token(token("api"))["azp"] == "api"
        with pytest.raises(InvalidToken):
            keycloak_login.verify_token(token("grafana"))
    finally:
        realm.stop()


def test_role_gate_rejects_other_users():
    claims = {"preferred_username": "bob", "realm_access": {"roles": ["viewer"]}}
    with pytest.raises(PermissionError, match="bob"):
        keycloak_login.require_upload_role(claims)


def test_device_login_polls_until_the_user_signs_in(monkeypatch, capsys):
    responses = iter([
        (200, {"device_code": "dc", "verification_uri_complete": "https://kc/device?code=X", "interval": 0}),
        (400, {"error": "authorization_pending"}),
        (200, {"access_token": "tok", "refresh_token": "rt"}),
    ])
    monkeypatch.setattr(keycloak_login, "_post_form", lambda url, data: next(responses))

    assert keycloak_login.device_login() == ("tok", "rt")
    assert "https://kc/device?code=X" in capsys.readouterr().out


@pytest.mark.parametrize("roles, admin", [(["offline_access", "admin"], True), (["researcher"], False), ([], False)])
def test_is_admin_reads_the_tokens_realm_roles(monkeypatch, roles, admin):
    monkeypatch.setattr(keycloak_login, "verify_token", lambda token: {"realm_access": {"roles": roles}})
    assert keycloak_login.is_admin("tok") is admin


def test_login_falls_back_to_password_when_device_flow_is_unavailable(monkeypatch):
    monkeypatch.setattr(keycloak_login, "device_login", lambda: (_ for _ in ()).throw(RuntimeError("off")))
    monkeypatch.setattr(keycloak_login, "password_login", lambda username=None: ("tok", "rt"))
    monkeypatch.setattr(keycloak_login, "verify_token", lambda token: {
        "preferred_username": "alice", "realm_access": {"roles": ["admin"]}})

    assert keycloak_login.login() == ("alice", "tok", "rt")


def test_refresh_exchanges_the_refresh_token_for_a_fresh_access_token(monkeypatch):
    sent = {}

    def post(url, data):
        sent.update(data)
        return 200, {"access_token": "fresh"}

    monkeypatch.setattr(keycloak_login, "_post_form", post)

    assert keycloak_login.refresh("rt") == "fresh"
    assert (sent["grant_type"], sent["refresh_token"]) == ("refresh_token", "rt")


def test_refresh_raises_when_the_sign_in_has_expired(monkeypatch):
    monkeypatch.setattr(keycloak_login, "_post_form", lambda url, data: (400, {"error": "invalid_grant"}))

    with pytest.raises(PermissionError, match="invalid_grant"):
        keycloak_login.refresh("rt")


def test_category_is_required_and_checked_before_sign_in(monkeypatch, capsys):
    monkeypatch.setattr(import_dataset, "login", lambda **kw: pytest.fail("signed in without a category"))

    assert import_dataset.main([str(FIXTURE)]) == 2
    assert "--category" in capsys.readouterr().err


# ── Integration: import ────────────────────────────────────────────────


@pytest.fixture
def cli_env(platform_db, minio_bucket, hapi, tmp_path, monkeypatch):
    monkeypatch.setenv("DATASET_STAGING_DIR", str(tmp_path / "staging"))
    monkeypatch.setattr(import_dataset, "MEASUREMENTS", minio_bucket)
    monkeypatch.setattr(import_dataset, "login", lambda **kw: ("alice", "t", "r"))
    monkeypatch.setattr(import_dataset, "refresh", lambda refresh_token: "t2")
    monkeypatch.setattr(import_dataset, "is_admin", lambda token: False)
    return {"db": platform_db, "bucket": minio_bucket, "tmp": tmp_path}


def _dataset(env, dataset_uuid):
    with env["db"]().cursor() as cur:
        cur.execute("SELECT dataset_name, fhir_status FROM dataset WHERE dataset_uuid = %s", (dataset_uuid,))
        return cur.fetchone()


def _only_session(env):
    with env["db"]().cursor() as cur:
        cur.execute("SELECT upload_id FROM upload_session")
        [(upload_id,)] = cur.fetchall()
    return sessions.get_session(env["db"](), upload_id)


@pytest.mark.integration
def test_imports_a_folder_with_auto_fhir(cli_env, capsys):
    code = import_dataset.main([str(FIXTURE), "--name", "CLI import", "--fhir", "auto",
                                "--category", cli_env["bucket"]])

    assert code == 0
    session = _only_session(cli_env)
    assert _dataset(cli_env, session["dataset_uuid"]) == ("CLI import", "completed")
    assert session["dataset_uuid"] in capsys.readouterr().out
    assert FIXTURE.is_dir()  # copied, not moved, by default


@pytest.mark.integration
def test_imports_a_zip(cli_env):
    assert import_dataset.main([str(FIXTURE_ZIP), "--category", cli_env["bucket"]]) == 0
    assert _dataset(cli_env, _only_session(cli_env)["dataset_uuid"]) == ("example_sds_dataset", "none")


@pytest.mark.integration
def test_move_consumes_the_staged_copy(cli_env):
    staged = cli_env["tmp"] / "import-staging" / "example"
    shutil.copytree(FIXTURE, staged)

    assert import_dataset.main([str(staged), "--move", "--category", cli_env["bucket"]]) == 0
    assert not staged.exists()


@pytest.mark.integration
def test_invalid_dataset_exits_2_without_a_session(cli_env, capsys):
    broken = cli_env["tmp"] / "broken"
    broken.mkdir()
    (broken / "dataset_description.xlsx").write_bytes(b"")

    assert import_dataset.main([str(broken), "--category", cli_env["bucket"]]) == 2
    assert "primary/" in capsys.readouterr().err
    with cli_env["db"]().cursor() as cur:
        cur.execute("SELECT count(*) FROM upload_session")
        assert cur.fetchone() == (0,)


@pytest.mark.integration
def test_user_without_an_upload_role_exits_3(cli_env, monkeypatch, capsys):
    def denied(**kw):
        raise PermissionError("User 'bob' lacks an upload role")

    monkeypatch.setattr(import_dataset, "login", denied)

    assert import_dataset.main([str(FIXTURE), "--category", cli_env["bucket"]]) == 3
    assert "bob" in capsys.readouterr().err


@pytest.mark.integration
def test_unknown_category_exits_2_without_a_session(cli_env, capsys):
    assert import_dataset.main([str(FIXTURE), "--category", "measurement"]) == 2
    assert "measurement" in capsys.readouterr().err
    with cli_env["db"]().cursor() as cur:
        cur.execute("SELECT count(*) FROM upload_session")
        assert cur.fetchone() == (0,)


@pytest.mark.integration
def test_zip_over_the_upload_limit_exits_2(cli_env, monkeypatch, capsys):
    monkeypatch.setattr(import_dataset, "max_upload_bytes", lambda: 1)

    assert import_dataset.main([str(FIXTURE_ZIP), "--category", cli_env["bucket"]]) == 2
    assert "Cannot extract" in capsys.readouterr().err


@pytest.mark.integration
def test_warns_about_subjects_without_samples(cli_env, capsys):
    dataset = cli_env["tmp"] / "with_empty_subject"
    shutil.copytree(FIXTURE, dataset)
    (dataset / "primary" / "sub-3").mkdir()

    assert import_dataset.main([str(dataset), "--category", cli_env["bucket"]]) == 0
    assert "primary/sub-3 has no sample folders" in capsys.readouterr().out


@pytest.mark.integration
def test_failed_commit_exits_1_with_a_retry_hint(cli_env, monkeypatch, capsys):
    def broken(session, root, api_token):
        raise RuntimeError("minio down")

    monkeypatch.setattr(jobs, "_commit", broken)

    assert import_dataset.main([str(FIXTURE), "--category", cli_env["bucket"]]) == 1
    err = capsys.readouterr().err
    upload_id = _only_session(cli_env)["upload_id"]
    assert "minio down" in err and f"POST /datasets/uploads/{upload_id}/approve" in err


@pytest.mark.integration
def test_expired_sign_in_fails_the_session_and_exits_3(cli_env, monkeypatch, capsys):
    def expired(refresh_token):
        raise PermissionError("Sign-in expired")

    monkeypatch.setattr(import_dataset, "refresh", expired)

    assert import_dataset.main([str(FIXTURE), "--category", cli_env["bucket"]]) == 3
    session = _only_session(cli_env)
    assert (session["status"], session["failure_stage"]) == ("failed", "auth")
    assert f"POST /datasets/uploads/{session['upload_id']}/approve" in capsys.readouterr().err


@pytest.mark.integration
def test_login_errors_exit_3_without_a_traceback(cli_env, monkeypatch, capsys):
    def unreachable(**kw):
        raise OSError("Connection refused")

    monkeypatch.setattr(import_dataset, "login", unreachable)

    assert import_dataset.main([str(FIXTURE), "--category", cli_env["bucket"]]) == 3
    assert "Login failed: Connection refused" in capsys.readouterr().err


@pytest.mark.integration
def test_missing_path_exits_2_before_sign_in(cli_env, monkeypatch):
    monkeypatch.setattr(import_dataset, "login", lambda **kw: pytest.fail("signed in for a missing path"))

    assert import_dataset.main([str(cli_env["tmp"] / "nope"), "--category", cli_env["bucket"]]) == 2


def _with_fhir_json(env, descriptions):
    dataset = env["tmp"] / "annotated"
    shutil.copytree(FIXTURE, dataset)
    (dataset / "fhir.json").write_text(json.dumps(descriptions))
    return dataset


@pytest.mark.integration
def test_a_root_fhir_json_is_used_as_the_annotation(cli_env, monkeypatch, capsys):
    descriptions = build_tree(FIXTURE, "annotated")["descriptions"]
    descriptions["dataset"]["description"] = "hand annotated"
    dataset = _with_fhir_json(cli_env, descriptions)
    staged_at_commit = []
    commit = jobs.run_commit_and_push

    def spy(upload_id, *args, **kwargs):
        staged_at_commit.append((dataset_dir(upload_id) / "fhir.json").exists())
        return commit(upload_id, *args, **kwargs)

    monkeypatch.setattr(jobs, "run_commit_and_push", spy)

    assert import_dataset.main([str(dataset), "--category", cli_env["bucket"]]) == 0
    session = _only_session(cli_env)
    assert session["fhir_mode"] == "descriptions"
    assert session["fhir_descriptions"]["dataset"]["description"] == "hand annotated"
    assert _dataset(cli_env, session["dataset_uuid"]) == ("annotated", "completed")
    assert staged_at_commit == [False]  # not published as data
    assert (dataset / "fhir.json").exists()  # the source is left alone
    assert "fhir.json" in capsys.readouterr().out


@pytest.mark.integration
def test_a_root_fhir_json_that_does_not_match_exits_2_without_a_session(cli_env, capsys):
    dataset = _with_fhir_json(cli_env, {"dataset": {"name": "x"}, "patients": [
        {"name": "sub-9", "observations": [], "imagingStudy": [], "documentReference": []}]})

    assert import_dataset.main([str(dataset), "--category", cli_env["bucket"]]) == 2
    assert "sub-9" in capsys.readouterr().err
    with cli_env["db"]().cursor() as cur:
        cur.execute("SELECT count(*) FROM upload_session")
        assert cur.fetchone() == (0,)


@pytest.mark.integration
def test_move_removes_a_staged_zip(cli_env):
    staged = cli_env["tmp"] / "import-staging" / "example.zip"
    staged.parent.mkdir()
    shutil.copy(FIXTURE_ZIP, staged)

    assert import_dataset.main([str(staged), "--move", "--category", cli_env["bucket"]]) == 0
    assert not staged.exists()


TOOL_CWL = "cwlVersion: v1.2\nclass: CommandLineTool\nlabel: Tool - convert\ninputs: []\noutputs: []\n"


@pytest.fixture
def tool_dir(cli_env, seek, monkeypatch):
    monkeypatch.setattr(tools, "CATEGORY", cli_env["bucket"])
    root = cli_env["tmp"] / "sds_tool_convert"
    (root / "primary").mkdir(parents=True)
    (root / "primary" / "tool_convert.cwl").write_text(TOOL_CWL)
    (root / "dataset_description.xlsx").write_bytes((FIXTURE / "dataset_description.xlsx").read_bytes())
    cli_env["seek"] = seek
    return root


@pytest.mark.integration
def test_imports_a_tool_and_registers_it_in_seek_as_the_signed_in_user(cli_env, tool_dir):
    code = import_dataset.main([str(tool_dir), "--category", cli_env["bucket"], "--tool-type", "notebook",
                                "--seek-project-id", "11", "--fhir", "auto"])

    assert code == 0
    session = _only_session(cli_env)
    assert _dataset(cli_env, session["dataset_uuid"]) == ("sds_tool_convert", "completed")
    [workflow] = cli_env["seek"].workflows.values()
    # The token refreshed just before the commit, not the one from sign-in.
    assert (workflow["tool_type"], workflow["project_id"], workflow["token"]) == ("notebook", 11, "t2")


@pytest.mark.integration
def test_tool_import_needs_the_tool_options(cli_env, tool_dir, capsys):
    assert import_dataset.main([str(tool_dir), "--category", cli_env["bucket"]]) == 2
    assert "--tool-type" in capsys.readouterr().err


@pytest.mark.integration
def test_tool_import_without_a_cwl_exits_2(cli_env, tool_dir, capsys):
    (tool_dir / "primary" / "tool_convert.cwl").unlink()
    (tool_dir / "primary" / "notes.txt").write_text("no tool")

    assert import_dataset.main([str(tool_dir), "--category", cli_env["bucket"], "--tool-type", "script",
                                "--seek-project-id", "11"]) == 2
    assert "tool_*.cwl" in capsys.readouterr().err


@pytest.fixture
def workflow_dir(cli_env, seek, tool_bucket, monkeypatch):
    from digitaltwins import workflows
    from test_datasets_workflows_api import script_files

    monkeypatch.setattr(workflows, "CATEGORY", cli_env["bucket"])
    monkeypatch.setattr(tools, "CATEGORY", tool_bucket)
    root = cli_env["tmp"] / "wf_convert"
    for rel, data in script_files().items():
        (root / rel).parent.mkdir(parents=True, exist_ok=True)
        (root / rel).write_bytes(data)
    cli_env["seek"] = seek
    return root


@pytest.mark.integration
def test_imports_a_workflow_with_its_tools(cli_env, workflow_dir):
    code = import_dataset.main([str(workflow_dir), "--category", cli_env["bucket"], "--workflow-type", "script",
                                "--seek-project-id", "11"])

    assert code == 0
    session = _only_session(cli_env)
    assert session["workflow_type"] == "script"
    assert sorted(w.get("workflow_type", "tool") for w in cli_env["seek"].workflows.values()) == [
        "script", "tool", "tool"]


@pytest.fixture
def airflow(cli_env, workflow_dir, monkeypatch):
    """A dags dir and a faked Airflow that has loaded the DAG by its second poll; the workflow ships a valid DAG."""
    from digitaltwins.workflows import deploy
    from test_workflow_deploy_api import GOOD_DAG, FakeAirflow, _now

    (workflow_dir / "code" / "workflow_convert.py").write_bytes(GOOD_DAG)
    dags = cli_env["tmp"] / "dags"
    dags.mkdir()
    monkeypatch.setenv("AIRFLOW_DAGS_DIR", str(dags))
    monkeypatch.setenv("AIRFLOW_ENDPOINT", "http://airflow.test/airflow")
    monkeypatch.setattr(deploy, "POLL_INTERVAL", 0)
    fake = FakeAirflow(parsed=[None, _now(3600)])
    monkeypatch.setattr(deploy, "_airflow_session", lambda: fake)
    return dags


def _dag_status(env, dataset_uuid):
    with env["db"]().cursor() as cur:
        cur.execute("SELECT seek_id, dag_status FROM dataset WHERE dataset_uuid = %s", (dataset_uuid,))
        return cur.fetchone()


@pytest.mark.integration
def test_an_admin_importing_a_script_workflow_deploys_its_dag(cli_env, workflow_dir, airflow, monkeypatch, capsys):
    monkeypatch.setattr(import_dataset, "is_admin", lambda token: True)

    code = import_dataset.main([str(workflow_dir), "--category", cli_env["bucket"], "--workflow-type", "script",
                                "--seek-project-id", "11"])

    assert code == 0
    seek_id, status = _dag_status(cli_env, _only_session(cli_env)["dataset_uuid"])
    assert status == "deployed"
    assert (airflow / f"workflow_{seek_id}" / "workflow_convert.py").exists()
    assert f"DAG deployed as workflow_{seek_id}" in capsys.readouterr().out


@pytest.mark.integration
def test_a_researcher_importing_a_script_workflow_leaves_it_for_an_admin(cli_env, workflow_dir, airflow, capsys):
    code = import_dataset.main([str(workflow_dir), "--category", cli_env["bucket"], "--workflow-type", "script",
                                "--seek-project-id", "11"])

    assert code == 0
    dataset_uuid = _only_session(cli_env)["dataset_uuid"]
    assert _dag_status(cli_env, dataset_uuid)[1] == "pending"
    assert list(airflow.iterdir()) == []
    assert f"POST /workflows/{dataset_uuid}/deploy" in capsys.readouterr().out


@pytest.mark.integration
def test_a_failed_deploy_is_reported_but_the_import_stands(cli_env, workflow_dir, airflow, monkeypatch, capsys):
    monkeypatch.setattr(import_dataset, "is_admin", lambda token: True)
    (workflow_dir / "code" / "workflow_convert.py").write_text(
        "from airflow.decorators import dag\n@dag(dag_id='workflow_89')\ndef wf():\n    pass\n")

    code = import_dataset.main([str(workflow_dir), "--category", cli_env["bucket"], "--workflow-type", "script",
                                "--seek-project-id", "11"])

    assert code == 0
    assert _dag_status(cli_env, _only_session(cli_env)["dataset_uuid"])[1] == "failed"
    assert "DAG deploy failed" in capsys.readouterr().err


@pytest.mark.integration
def test_workflow_import_needs_the_workflow_options(cli_env, workflow_dir, capsys):
    assert import_dataset.main([str(workflow_dir), "--category", cli_env["bucket"]]) == 2
    assert "--workflow-type" in capsys.readouterr().err


@pytest.mark.integration
def test_invalid_workflow_import_exits_2(cli_env, workflow_dir, capsys):
    assert import_dataset.main([str(workflow_dir), "--category", cli_env["bucket"], "--workflow-type", "gui",
                                "--seek-project-id", "11"]) == 2
    assert "exactly one step" in capsys.readouterr().err


# ── Models ─────────────────────────────────────────────────────────────


@pytest.fixture
def model_dir(cli_env, monkeypatch):
    from digitaltwins import models
    from test_model_pipeline import make_model

    monkeypatch.setattr(models, "CATEGORY", cli_env["bucket"])
    return make_model(cli_env["tmp"] / "model_skin_test")


@pytest.mark.integration
def test_imports_a_model_with_auto_fhir(cli_env, model_dir):
    # A single weights file directly under primary/: valid for a model, not for measurements.
    shutil.rmtree(model_dir / "primary")
    (model_dir / "primary").mkdir()
    (model_dir / "primary" / "model.onnx").write_bytes(b"weights")

    code = import_dataset.main([str(model_dir), "--category", cli_env["bucket"], "--fhir", "auto"])

    assert code == 0
    assert _dataset(cli_env, _only_session(cli_env)["dataset_uuid"]) == ("model_skin_test", "completed")


@pytest.mark.integration
def test_model_import_without_primary_files_exits_2(cli_env, model_dir, capsys):
    shutil.rmtree(model_dir / "primary")

    assert import_dataset.main([str(model_dir), "--category", cli_env["bucket"]]) == 2
    assert "primary/" in capsys.readouterr().err
