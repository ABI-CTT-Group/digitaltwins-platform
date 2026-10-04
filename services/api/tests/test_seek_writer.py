"""Tests for ``digitaltwins.seek.writer``: the tool RO-Crate and the SEEK calls (requests faked)."""
import io
import json
import zipfile

import pytest
import requests

from digitaltwins.seek import writer
from digitaltwins.seek.writer import Writer, build_tool_crate, build_workflow_crate

CWL = """cwlVersion: v1.2
class: CommandLineTool
label: "Tool - convert"
doc: Converts things.
baseCommand: [python, convert.py]
inputs:
  src:
    type: Directory
    doc: measurements
outputs: []
"""


class FakeResponse:
    def __init__(self, status_code=200, payload=None):
        self.status_code = status_code
        self._payload = payload if payload is not None else {}
        self.text = json.dumps(self._payload)

    def json(self):
        return self._payload

    def raise_for_status(self):
        if self.status_code >= 400:
            raise requests.HTTPError(f"{self.status_code} error", response=self)


@pytest.fixture
def cwl_path(tmp_path):
    path = tmp_path / "tool_convert.cwl"
    path.write_text(CWL)
    return path


@pytest.fixture
def seek_env(monkeypatch):
    monkeypatch.setenv("SEEK_BASE_URL", "http://seek.test/seek")


def _crate(data: bytes):
    with zipfile.ZipFile(io.BytesIO(data)) as zf:
        meta = json.loads(zf.read("ro-crate-metadata.json"))
        return {e["@id"]: e for e in meta["@graph"]}, zf.namelist(), zf


def test_crate_root_carries_title_description_and_tags(cwl_path):
    graph, names, _ = _crate(build_tool_crate(cwl_path, "script"))
    root = graph["./"]
    assert root["name"] == "Tool - convert"
    assert root["description"] == "Converts things."
    assert root["keywords"] == ["tool", "script"]
    assert root["mainEntity"] == {"@id": "tool_convert.cwl"}
    assert graph["tool_convert.cwl"]["programmingLanguage"] == {"@id": "#cwl"}
    assert "ComputationalWorkflow" in graph["tool_convert.cwl"]["@type"]
    assert sorted(names) == ["ro-crate-metadata.json", "tool_convert.cwl"]


def test_crate_holds_the_cwl_verbatim(cwl_path):
    with zipfile.ZipFile(io.BytesIO(build_tool_crate(cwl_path, "script"))) as zf:
        assert zf.read("tool_convert.cwl").decode() == CWL


def test_crate_falls_back_to_the_file_stem_without_label_or_doc(tmp_path):
    path = tmp_path / "tool_bare.cwl"
    path.write_text("cwlVersion: v1.2\nclass: CommandLineTool\ninputs: []\noutputs: []\n")
    graph, _, _ = _crate(build_tool_crate(path, "script"))
    assert graph["./"]["name"] == "tool_bare"
    assert "description" not in graph["./"]


def test_writer_requires_seek_base_url(monkeypatch):
    monkeypatch.delenv("SEEK_BASE_URL", raising=False)
    with pytest.raises(ValueError, match="SEEK_BASE_URL"):
        Writer(api_token="tok")


def test_register_tool_posts_one_crate(seek_env, cwl_path, monkeypatch):
    calls = []

    def fake_post(url, **kwargs):
        calls.append((url, kwargs))
        return FakeResponse(200, {"data": {"id": "42", "type": "workflows"}})

    monkeypatch.setattr(writer.requests, "post", fake_post)
    assert Writer(api_token="tok").register_tool(cwl_path, "script", project_id=11) == 42

    [(url, kwargs)] = calls
    assert url == "http://seek.test/seek/workflows"
    # No Accept header: SEEK would then demand a JSON:API body and reject the multipart crate (422).
    assert kwargs["headers"] == {"Authorization": "Bearer tok"}
    assert kwargs["data"] == {"workflow[project_ids][]": 11}
    filename, content, content_type = kwargs["files"]["ro_crate"]
    assert content_type == "application/zip"
    graph, _, _ = _crate(content)
    assert graph["./"]["keywords"] == ["tool", "script"]


def test_register_tool_raises_on_seek_error(seek_env, cwl_path, monkeypatch):
    payload = {"errors": [{"detail": "Projects: you are not a member"}]}
    monkeypatch.setattr(writer.requests, "post", lambda url, **kw: FakeResponse(422, payload))
    with pytest.raises(RuntimeError, match="not a member"):
        Writer(api_token="tok").register_tool(cwl_path, "script", project_id=11)


def test_register_tool_raises_when_seek_is_unreachable(seek_env, cwl_path, monkeypatch):
    def fake_post(url, **kwargs):
        raise requests.ConnectionError("refused")

    monkeypatch.setattr(writer.requests, "post", fake_post)
    with pytest.raises(RuntimeError, match="refused"):
        Writer(api_token="tok").register_tool(cwl_path, "script", project_id=11)


def test_delete_workflow(seek_env, monkeypatch):
    calls = []

    def fake_delete(url, **kwargs):
        calls.append((url, kwargs["headers"]))
        return FakeResponse(200)

    monkeypatch.setattr(writer.requests, "delete", fake_delete)
    Writer(api_token="tok").delete_workflow(42)
    assert calls == [("http://seek.test/seek/workflows/42",
                      {"Authorization": "Bearer tok", "Accept": "application/json"})]


def test_delete_workflow_raises_on_seek_error(seek_env, monkeypatch):
    monkeypatch.setattr(writer.requests, "delete", lambda url, **kw: FakeResponse(403, {"errors": [{"title": "Forbidden"}]}))
    with pytest.raises(RuntimeError, match="Forbidden"):
        Writer(api_token="tok").delete_workflow(42)


def test_crate_tags_the_notebook_type(cwl_path):
    graph, _, _ = _crate(build_tool_crate(cwl_path, "notebook"))
    assert graph["./"]["keywords"] == ["tool", "notebook"]


def test_crate_tags_the_gui_type(cwl_path):
    graph, _, _ = _crate(build_tool_crate(cwl_path, "gui"))
    assert graph["./"]["keywords"] == ["tool", "gui"]


WORKFLOW_CWL = """cwlVersion: v1.2
class: Workflow
label: "Workflow - convert"
doc: Converts twice.
inputs: {src: Directory}
outputs: {}
steps:
  convert: {run: tool_convert.cwl, in: {src: src}, out: []}
  other: {run: tool_other.cwl, in: {src: src}, out: []}
"""


@pytest.fixture
def workflow_paths(tmp_path, cwl_path):
    workflow = tmp_path / "workflow_convert.cwl"
    workflow.write_text(WORKFLOW_CWL)
    other = tmp_path / "tool_other.cwl"
    other.write_text("cwlVersion: v1.2\nclass: CommandLineTool\ninputs: []\noutputs: []\n")
    return workflow, [cwl_path, other]


def test_workflow_crate_tags_workflow_and_packs_its_tool_cwls(workflow_paths):
    workflow, tool_cwls = workflow_paths
    graph, names, zf = _crate(build_workflow_crate(workflow, tool_cwls, "script"))
    root = graph["./"]
    assert root["name"] == "Workflow - convert"
    assert root["description"] == "Converts twice."
    assert root["keywords"] == ["workflow", "script"]
    assert root["mainEntity"] == {"@id": "workflow_convert.cwl"}
    assert root["hasPart"] == [{"@id": "workflow_convert.cwl"}, {"@id": "tool_convert.cwl"}, {"@id": "tool_other.cwl"}]
    assert "ComputationalWorkflow" in graph["workflow_convert.cwl"]["@type"]
    assert "ComputationalWorkflow" not in graph["tool_convert.cwl"]["@type"]
    assert sorted(names) == ["ro-crate-metadata.json", "tool_convert.cwl", "tool_other.cwl", "workflow_convert.cwl"]
    with zipfile.ZipFile(io.BytesIO(build_workflow_crate(workflow, tool_cwls, "script"))) as z:
        assert z.read("workflow_convert.cwl").decode() == WORKFLOW_CWL
        assert z.read("tool_convert.cwl").decode() == CWL


def test_register_workflow_posts_one_crate(seek_env, workflow_paths, monkeypatch):
    workflow, tool_cwls = workflow_paths
    calls = []

    def fake_post(url, **kwargs):
        calls.append((url, kwargs))
        return FakeResponse(200, {"data": {"id": "43", "type": "workflows"}})

    monkeypatch.setattr(writer.requests, "post", fake_post)
    assert Writer(api_token="tok").register_workflow(workflow, tool_cwls, "gui", project_id=11) == 43

    [(url, kwargs)] = calls
    assert url == "http://seek.test/seek/workflows"
    assert kwargs["headers"] == {"Authorization": "Bearer tok"}
    assert kwargs["data"] == {"workflow[project_ids][]": 11}
    filename, content, content_type = kwargs["files"]["ro_crate"]
    assert filename == "workflow_convert.crate.zip"
    graph, _, _ = _crate(content)
    assert graph["./"]["keywords"] == ["workflow", "gui"]


def test_register_workflow_raises_on_seek_error(seek_env, workflow_paths, monkeypatch):
    workflow, tool_cwls = workflow_paths
    monkeypatch.setattr(writer.requests, "post", lambda url, **kw: FakeResponse(422, {"errors": [{"detail": "bad"}]}))
    with pytest.raises(RuntimeError, match="workflow registration failed.*bad"):
        Writer(api_token="tok").register_workflow(workflow, tool_cwls, "script", project_id=11)
