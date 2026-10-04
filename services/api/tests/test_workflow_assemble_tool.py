"""Tests for ``digitaltwins.workflows.pipeline._assemble_tool``: ``primary/<tool stem>/`` joins the tool's primary/."""
import yaml

from digitaltwins.tools.validation import find_tool_cwl
from digitaltwins.workflows.pipeline import _assemble_tool
from digitaltwins.workflows.validation import load_workflow

TOOL = {"cwlVersion": "v1.2", "class": "CommandLineTool", "inputs": {}, "outputs": {}}
WORKFLOW = {"cwlVersion": "v1.2", "class": "Workflow", "inputs": {}, "outputs": {},
            "steps": {"viewer": {"run": "tool_viewer.cwl", "in": {}, "out": []}}}


def _gui_workflow(root):
    (root / "primary").mkdir(parents=True)
    (root / "code").mkdir()
    (root / "dataset_description.xlsx").write_bytes(b"xlsx")
    (root / "primary" / "workflow_viewer.cwl").write_text(yaml.safe_dump(WORKFLOW))
    (root / "primary" / "tool_viewer.cwl").write_text(yaml.safe_dump(TOOL))
    (root / "code" / "package.json").write_text("{}")
    return root


def _files(root):
    return sorted(p.relative_to(root).as_posix() for p in root.rglob("*") if p.is_file())


def _assemble(root, parent):
    layout = load_workflow(root, "gui")
    return _assemble_tool(layout, layout.steps[0].tool_cwl, parent)


def test_a_tool_primary_folder_is_copied_into_the_tool_primary(tmp_path):
    root = _gui_workflow(tmp_path / "wf")
    (root / "primary" / "tool_viewer" / "assets").mkdir(parents=True)
    (root / "primary" / "tool_viewer" / "my-app.umd.js").write_text("//")
    (root / "primary" / "tool_viewer" / "assets" / "a.wasm").write_bytes(b"\0")

    tool = _assemble(root, tmp_path / "out")

    assert _files(tool / "primary") == ["assets/a.wasm", "my-app.umd.js", "tool_viewer.cwl"]
    assert find_tool_cwl(tool).name == "tool_viewer.cwl"


def test_without_the_folder_the_tool_is_assembled_as_before(tmp_path):
    tool = _assemble(_gui_workflow(tmp_path / "wf"), tmp_path / "out")

    assert _files(tool) == ["code/package.json", "dataset_description.xlsx", "primary/tool_viewer.cwl"]
