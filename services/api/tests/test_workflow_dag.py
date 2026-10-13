"""Tests for ``digitaltwins.workflows.dag``: the static DAG check and the deployed folder layout."""
import os

import pytest

from digitaltwins.workflows.dag import dag_id_for, find_dag_file, remove_dag_folder, write_dag_folder

HEADER = "from pathlib import Path\nfrom airflow.decorators import dag, task\n"


def _code(root, files):
    code = root / "code"
    for rel, text in files.items():
        path = code / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text)
    return code


# ── find_dag_file: accepted ─────────────────────────────────────────────


@pytest.mark.parametrize("source", [
    HEADER + "DAG_ID = Path(__file__).parent.name\n@dag(dag_id=DAG_ID, schedule=None)\ndef wf():\n    pass\nwf()\n",
    HEADER + "DAG_ID: str = Path(__file__).parent.name\n@dag(dag_id=DAG_ID)\ndef wf():\n    pass\n",
    "from pathlib import Path\nfrom airflow import DAG\nwith DAG(dag_id=Path(__file__).parent.name) as d:\n    pass\n",
    "import pathlib\nfrom airflow import DAG\nDAG_ID = pathlib.Path(__file__).parent.name\nd = DAG(DAG_ID)\n",
    "from pathlib import Path\nimport airflow.models\nd = airflow.models.DAG(Path(__file__).parent.name)\n",
], ids=["decorator-name", "annotated-name", "with-inline", "positional-pathlib", "attribute-call"])
def test_accepts_a_folder_derived_dag_id(tmp_path, source):
    code = _code(tmp_path, {"workflow_convert.py": source, "tool_to_nifti.py": "def run():\n    pass\n"})
    assert find_dag_file(code) == code / "workflow_convert.py"


def test_tool_modules_that_mention_airflow_and_dag_id_are_not_dags(tmp_path):
    code = _code(tmp_path, {
        "workflow_convert.py": HEADER + "@dag(dag_id=Path(__file__).parent.name)\ndef wf():\n    pass\n",
        "tool_download.py": "BUCKET = 'airflow-workspace'\ndef run(dag_id):\n    return f'{dag_id}/inputs'\n",
    })
    assert find_dag_file(code) == code / "workflow_convert.py"


# ── find_dag_file: rejected ─────────────────────────────────────────────


@pytest.mark.parametrize("source, got", [
    (HEADER + "@dag(dag_id='workflow_89')\ndef wf():\n    pass\n", "'workflow_89'"),
    (HEADER + "N = 89\n@dag(dag_id=f'workflow_{N}')\ndef wf():\n    pass\n", "f'workflow_{N}'"),
    (HEADER + "DAG_ID = 'workflow_89'\n@dag(dag_id=DAG_ID)\ndef wf():\n    pass\n", "DAG_ID"),
    (HEADER + "@dag(schedule=None)\ndef wf():\n    pass\n", "no dag_id"),
    (HEADER + "@dag\ndef wf():\n    pass\n", "no dag_id"),
    (HEADER + "@dag(dag_id=Path(__file__).stem)\ndef wf():\n    pass\n", "Path(__file__).stem"),
], ids=["literal", "f-string", "literal-name", "missing", "bare-decorator", "file-stem"])
def test_rejects_any_other_dag_id(tmp_path, source, got):
    code = _code(tmp_path, {"workflow_convert.py": source})
    with pytest.raises(ValueError) as exc:
        find_dag_file(code)
    message = str(exc.value)
    assert "workflow_convert.py" in message
    assert got in message
    assert "Path(__file__).parent.name" in message


def test_rejects_a_dataset_without_a_dag(tmp_path):
    code = _code(tmp_path, {"tool_to_nifti.py": "def run():\n    pass\n"})
    with pytest.raises(ValueError, match="No Airflow DAG found"):
        find_dag_file(code)


def test_rejects_a_missing_code_folder(tmp_path):
    with pytest.raises(ValueError, match="No Airflow DAG found"):
        find_dag_file(tmp_path / "code")


def test_rejects_more_than_one_dag(tmp_path):
    good = HEADER + "@dag(dag_id=Path(__file__).parent.name)\ndef wf():\n    pass\n"
    code = _code(tmp_path, {"a.py": good, "b.py": good})
    with pytest.raises(ValueError, match="exactly one") as exc:
        find_dag_file(code)
    assert "a.py" in str(exc.value) and "b.py" in str(exc.value)


def test_rejects_two_dags_in_one_file(tmp_path):
    two = HEADER + ("@dag(dag_id=Path(__file__).parent.name)\ndef a():\n    pass\n"
                    "@dag(dag_id=Path(__file__).parent.name)\ndef b():\n    pass\n")
    code = _code(tmp_path, {"wf.py": two})
    with pytest.raises(ValueError, match="exactly one"):
        find_dag_file(code)


def test_rejects_a_dag_below_the_top_of_code(tmp_path):
    code = _code(tmp_path, {"dags/wf.py": HEADER + "@dag(dag_id=Path(__file__).parent.name)\ndef wf():\n    pass\n"})
    with pytest.raises(ValueError, match="directly in code/"):
        find_dag_file(code)


def test_rejects_a_dag_file_that_does_not_parse(tmp_path):
    code = _code(tmp_path, {"wf.py": HEADER + "@dag(dag_id=\ndef wf(:\n"})
    with pytest.raises(ValueError, match="wf.py.*cannot be parsed"):
        find_dag_file(code)


# ── dag_id_for ──────────────────────────────────────────────────────────


def test_dag_id_is_workflow_and_the_seek_id():
    assert dag_id_for(42) == "workflow_42"
    assert dag_id_for("42") == "workflow_42"


@pytest.mark.parametrize("seek_id", ["", "../x", "4/2", "4 2", None])
def test_dag_id_needs_a_numeric_seek_id(seek_id):
    with pytest.raises(ValueError):
        dag_id_for(seek_id)


# ── write_dag_folder / remove_dag_folder ────────────────────────────────


def _example(tmp_path):
    return _code(tmp_path / "src", {
        "wf.py": "x", "tool_a.py": "a", "sub/tool_b.py": "b", ".airflowignore": "nothing\n",
    })


def test_writes_the_code_folder_and_shows_only_the_dag_to_airflow(tmp_path):
    dags = tmp_path / "dags"
    dags.mkdir()
    target = write_dag_folder(_example(tmp_path), dags, "workflow_42", "wf.py")

    assert target == dags / "workflow_42"
    assert sorted(str(p.relative_to(target)) for p in target.rglob("*") if p.is_file()) == [
        ".airflowignore", "sub/tool_b.py", "tool_a.py", "wf.py"]
    assert (target / ".airflowignore").read_text() == "*.py\n!/wf.py\n"
    assert [p.name for p in dags.iterdir()] == ["workflow_42"]


def test_redeploy_replaces_the_previous_folder(tmp_path):
    dags = tmp_path / "dags"
    (dags / "workflow_42").mkdir(parents=True)
    (dags / "workflow_42" / "stale.py").write_text("old")

    write_dag_folder(_example(tmp_path), dags, "workflow_42", "wf.py")

    assert not (dags / "workflow_42" / "stale.py").exists()
    assert (dags / "workflow_42" / "wf.py").read_text() == "x"


def test_a_failed_write_leaves_no_staging_folder(tmp_path):
    dags = tmp_path / "dags"
    dags.mkdir()
    with pytest.raises(OSError):
        write_dag_folder(tmp_path / "does-not-exist", dags, "workflow_42", "wf.py")
    assert list(dags.iterdir()) == []


@pytest.mark.skipif(os.geteuid() != 0, reason="chown needs root")
def test_written_files_belong_to_the_owner_of_the_dags_folder(tmp_path):
    dags = tmp_path / "dags"
    dags.mkdir()
    os.chown(dags, 1234, 2345)

    target = write_dag_folder(_example(tmp_path), dags, "workflow_42", "wf.py")

    for path in [target, *target.rglob("*")]:
        assert (path.stat().st_uid, path.stat().st_gid) == (1234, 2345), path


def test_remove_is_idempotent(tmp_path):
    dags = tmp_path / "dags"
    (dags / "workflow_42").mkdir(parents=True)
    (dags / "workflow_42" / "wf.py").write_text("x")
    (dags / "workflow_7").mkdir()

    remove_dag_folder(dags, 42)
    remove_dag_folder(dags, 42)

    assert [p.name for p in dags.iterdir()] == ["workflow_7"]
