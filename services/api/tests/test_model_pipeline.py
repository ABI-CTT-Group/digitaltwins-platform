"""Model dataset commit: Postgres + MinIO, subjects from spreadsheets only, optional FHIR Device."""
import json
import shutil
from pathlib import Path

import pytest

from digitaltwins import models
from digitaltwins.measurements import jobs, sessions
from digitaltwins.measurements.staging import dataset_dir
from digitaltwins.models.pipeline import commit_model

EXAMPLE = Path(__file__).parent / "data" / "example_sds_dataset"
TRAINER = "primary/nnUNetTrainer__nnUNetPlans__3d_fullres"


def make_model(root: Path, with_subjects: bool = True) -> Path:
    """A small model dataset: SDS spreadsheets + nnUNet-like files under primary/."""
    root.mkdir(parents=True)
    names = ["dataset_description.xlsx"] + (["subjects.xlsx", "samples.xlsx"] if with_subjects else [])
    for name in names:
        shutil.copy(EXAMPLE / name, root / name)
    fold = root / TRAINER / "fold_0"
    fold.mkdir(parents=True)
    (fold / "checkpoint_final.pth").write_bytes(b"weights")
    (root / TRAINER / "dataset.json").write_text('{"labels": {"background": 0, "tumor": 1}}')
    return root


@pytest.fixture
def bucket(minio_bucket, monkeypatch):
    monkeypatch.setattr(models, "CATEGORY", minio_bucket)
    return minio_bucket


def _one(conn, sql, params):
    with conn.cursor() as cur:
        cur.execute(sql, params)
        return cur.fetchone()


def _all(conn, sql, params):
    with conn.cursor() as cur:
        cur.execute(sql, params)
        return cur.fetchall()


@pytest.mark.integration
def test_commit_model_stores_files_and_loads_subjects_from_spreadsheets_only(platform_db, bucket, s3, tmp_path):
    root = make_model(tmp_path / "model_skin_test")

    result = commit_model(root, dataset_name="Skin model")

    conn = platform_db()
    assert _one(conn, "SELECT dataset_name, category FROM dataset WHERE dataset_uuid = %s",
                (result.dataset_uuid,)) == ("Skin model", bucket)
    subjects = {row[0] for row in _all(conn, "SELECT DISTINCT subject_id FROM dataset_mapping WHERE dataset_uuid = %s",
                                       (result.dataset_uuid,))}
    assert subjects == {"sub-1", "sub-2"}  # nnUNetTrainer__… is not a subject
    key = f"{result.dataset_uuid}/{TRAINER}/fold_0/checkpoint_final.pth"
    assert s3.get_object(Bucket=bucket, Key=key)["Body"].read() == b"weights"
    assert result.descriptions is None


@pytest.mark.integration
def test_commit_model_without_subject_spreadsheets_registers_no_subjects(platform_db, bucket, tmp_path):
    result = commit_model(make_model(tmp_path / "m", with_subjects=False), dataset_name="m")

    assert _all(platform_db(), "SELECT subject_id FROM dataset_mapping WHERE dataset_uuid = %s",
                (result.dataset_uuid,)) == []


@pytest.mark.integration
def test_commit_model_with_descriptions_stores_the_stamped_annotation(platform_db, bucket, tmp_path):
    result = commit_model(make_model(tmp_path / "m"), dataset_name="Skin model",
                          descriptions={"model": {"version": "2.1"}})

    [stored] = _one(platform_db(), "SELECT descriptions FROM dataset_fhir_annotation WHERE dataset_uuid = %s",
                    (result.dataset_uuid,))
    assert stored == result.descriptions == {"model": {
        "uuid": result.dataset_uuid, "name": "Skin model", "description": "", "version": "2.1"}}


def _session(conn, tmp_path, monkeypatch, fhir_mode="none", fhir_descriptions=None):
    monkeypatch.setenv("DATASET_STAGING_DIR", str(tmp_path / "staging"))
    upload_id = sessions.create_session(
        conn, category=models.CATEGORY, name="Skin model", description="From upload", source_kind="folder",
        commit_mode="on_finalize", fhir_mode=fhir_mode, fhir_descriptions=fhir_descriptions,
    )
    make_model(dataset_dir(upload_id))
    sessions.update_session(conn, upload_id, status="processing")
    return upload_id


@pytest.mark.integration
def test_commit_job_commits_a_model_session_without_fhir(platform_db, bucket, tmp_path, monkeypatch):
    conn = platform_db()
    upload_id = _session(conn, tmp_path, monkeypatch)

    jobs.run_commit_and_push(upload_id)

    session = sessions.get_session(conn, upload_id)
    assert session["status"] == "completed", session["failure_message"]
    assert _one(conn, "SELECT category, fhir_status FROM dataset WHERE dataset_uuid = %s",
                (session["dataset_uuid"],)) == (bucket, "none")


@pytest.mark.integration
def test_commit_and_push_publishes_the_device_and_stores_fhir_json(platform_db, bucket, s3, hapi, tmp_path,
                                                                   monkeypatch):
    conn = platform_db()
    upload_id = _session(conn, tmp_path, monkeypatch, fhir_mode="descriptions",
                         fhir_descriptions={"model": {"version": "2.1"}})

    jobs.run_commit_and_push(upload_id)

    dataset_uuid = sessions.get_session(conn, upload_id)["dataset_uuid"]
    assert _one(conn, "SELECT fhir_status FROM dataset WHERE dataset_uuid = %s", (dataset_uuid,)) == ("completed",)
    [device] = hapi.search("Device", identifier=dataset_uuid)
    assert device["version"] == [{"value": "2.1"}] and device["note"] == [{"text": "From upload"}]
    stored = json.loads(s3.get_object(Bucket=bucket, Key=f"{dataset_uuid}/fhir.json")["Body"].read())
    assert stored["resourceType"] == "Device"


@pytest.mark.integration
def test_auto_fhir_pushes_a_default_device(platform_db, bucket, hapi, tmp_path, monkeypatch):
    conn = platform_db()
    upload_id = _session(conn, tmp_path, monkeypatch, fhir_mode="auto")

    jobs.run_commit_and_push(upload_id)

    dataset_uuid = sessions.get_session(conn, upload_id)["dataset_uuid"]
    [device] = hapi.search("Device", identifier=dataset_uuid)
    assert device["deviceName"][0]["name"] == "Skin model" and "version" not in device


@pytest.mark.integration
def test_failed_device_push_marks_fhir_failed_and_keeps_the_dataset(platform_db, bucket, hapi, tmp_path,
                                                                     monkeypatch):
    conn = platform_db()
    hapi.fail_push = True
    upload_id = _session(conn, tmp_path, monkeypatch, fhir_mode="auto")

    jobs.run_commit_and_push(upload_id)

    session = sessions.get_session(conn, upload_id)
    assert session["status"] == "completed"
    assert _one(conn, "SELECT fhir_status FROM dataset WHERE dataset_uuid = %s",
                (session["dataset_uuid"],)) == ("failed",)
