"""Tests for ``digitaltwins.workflows.validation.load_workflow``."""
import pytest
import yaml

from digitaltwins.workflows.validation import load_workflow

TOOL = {"cwlVersion": "v1.2", "class": "CommandLineTool", "inputs": {}, "outputs": {}}


def _workflow(root, steps, tools=None, code=(), name="workflow_convert.cwl"):
    """A workflow dataset: ``steps`` maps step id -> run file; ``tools`` defaults to every run file."""
    primary = root / "primary"
    primary.mkdir(parents=True)
    (root / "code").mkdir()
    cwl = {"cwlVersion": "v1.2", "class": "Workflow", "inputs": {}, "outputs": {},
           "steps": {step: {"run": run, "in": {}, "out": []} for step, run in steps.items()}}
    (primary / name).write_text(yaml.safe_dump(cwl))
    for tool in tools if tools is not None else set(steps.values()):
        (primary / tool).write_text(yaml.safe_dump(TOOL))
    for rel in code:
        path = root / "code" / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("x")
    return root


def _rel(root, paths):
    return sorted(str(p.relative_to(root)) for p in paths)


def test_script_workflow_steps_and_tools_by_name(tmp_path):
    _workflow(tmp_path, {"to_nifti": "tool_to_nifti.cwl", "to_nrrd": "tool_to_nrrd.cwl"},
              code=["tool_to_nifti.py", "tool_to_nrrd.py", "workflow_convert.py"])
    layout = load_workflow(tmp_path, "script")
    assert layout.root == tmp_path
    assert layout.workflow_cwl == tmp_path / "primary" / "workflow_convert.cwl"
    assert [(s.step_id, s.tool_cwl.name) for s in layout.steps] == [
        ("to_nifti", "tool_to_nifti.cwl"), ("to_nrrd", "tool_to_nrrd.cwl")]
    code = {cwl.name: _rel(tmp_path, paths) for cwl, paths in layout.tool_code.items()}
    assert code == {"tool_to_nifti.cwl": ["code/tool_to_nifti.py"], "tool_to_nrrd.cwl": ["code/tool_to_nrrd.py"]}


def test_list_form_steps_are_accepted(tmp_path):
    _workflow(tmp_path, {}, tools=["tool_a.cwl"], code=["tool_a.py"])
    cwl = tmp_path / "primary" / "workflow_convert.cwl"
    data = yaml.safe_load(cwl.read_text())
    data["steps"] = [{"id": "#a", "run": "tool_a.cwl", "in": [], "out": []}]
    cwl.write_text(yaml.safe_dump(data))
    assert [s.step_id for s in load_workflow(tmp_path, "script").steps] == ["a"]


def test_per_tool_subfolder_wins_over_files_by_name(tmp_path):
    _workflow(tmp_path, {"a": "tool_a.cwl"}, code=["tool_a/main.py", "tool_a.py"])
    layout = load_workflow(tmp_path, "script")
    assert _rel(tmp_path, layout.tool_code[layout.steps[0].tool_cwl]) == ["code/tool_a"]


def test_gui_tool_gets_the_whole_code_folder(tmp_path):
    _workflow(tmp_path, {"viewer": "tool_viewer.cwl"}, code=["package.json", "src/app.ts"])
    layout = load_workflow(tmp_path, "gui")
    assert _rel(tmp_path, layout.tool_code[layout.steps[0].tool_cwl]) == ["code"]


def test_notebook_tool_uses_its_subfolder_when_present(tmp_path):
    _workflow(tmp_path, {"select": "tool_select.cwl"}, code=["tool_select/select.ipynb", "other.txt"])
    layout = load_workflow(tmp_path, "notebook")
    assert _rel(tmp_path, layout.tool_code[layout.steps[0].tool_cwl]) == ["code/tool_select"]


def test_two_steps_running_one_tool_share_it(tmp_path):
    _workflow(tmp_path, {"first": "tool_a.cwl", "second": "tool_a.cwl"}, code=["tool_a.py"])
    layout = load_workflow(tmp_path, "script")
    assert [s.tool_cwl.name for s in layout.steps] == ["tool_a.cwl", "tool_a.cwl"]
    assert list(layout.tool_code) == [tmp_path / "primary" / "tool_a.cwl"]


def test_wrapper_folder_is_unwrapped(tmp_path):
    _workflow(tmp_path / "wf", {"a": "tool_a.cwl"}, code=["tool_a.py"])
    assert load_workflow(tmp_path, "script").root == tmp_path / "wf"


@pytest.mark.parametrize("workflow_type", ["notebook", "gui"])
def test_single_step_types_reject_two_steps(tmp_path, workflow_type):
    _workflow(tmp_path, {"a": "tool_a.cwl", "b": "tool_b.cwl"})
    with pytest.raises(ValueError, match="exactly one step"):
        load_workflow(tmp_path, workflow_type)


def test_unknown_type_is_rejected(tmp_path):
    _workflow(tmp_path, {"a": "tool_a.cwl"}, code=["tool_a.py"])
    with pytest.raises(ValueError, match="workflow type"):
        load_workflow(tmp_path, "pipeline")


def test_missing_primary_is_rejected(tmp_path):
    with pytest.raises(ValueError, match="primary/"):
        load_workflow(tmp_path, "script")


def test_no_workflow_cwl_is_rejected(tmp_path):
    (tmp_path / "primary").mkdir()
    (tmp_path / "code").mkdir()
    (tmp_path / "primary" / "tool_a.cwl").write_text(yaml.safe_dump(TOOL))
    with pytest.raises(ValueError, match="exactly one workflow_"):
        load_workflow(tmp_path, "script")


def test_two_workflow_cwls_are_rejected(tmp_path):
    _workflow(tmp_path, {"a": "tool_a.cwl"}, code=["tool_a.py"])
    (tmp_path / "primary" / "workflow_other.cwl").write_text("class: Workflow\n")
    with pytest.raises(ValueError, match="exactly one workflow_"):
        load_workflow(tmp_path, "script")


def test_workflow_cwl_must_be_class_workflow(tmp_path):
    _workflow(tmp_path, {"a": "tool_a.cwl"}, code=["tool_a.py"])
    (tmp_path / "primary" / "workflow_convert.cwl").write_text(yaml.safe_dump(TOOL))
    with pytest.raises(ValueError, match="class: Workflow"):
        load_workflow(tmp_path, "script")


def test_workflow_without_steps_is_rejected(tmp_path):
    _workflow(tmp_path, {})
    with pytest.raises(ValueError, match="no steps"):
        load_workflow(tmp_path, "script")


def test_step_running_a_missing_tool_cwl_is_rejected(tmp_path):
    _workflow(tmp_path, {"a": "tool_a.cwl"}, tools=[])
    with pytest.raises(ValueError, match="tool_a.cwl"):
        load_workflow(tmp_path, "script")


def test_step_must_run_a_tool_prefixed_file(tmp_path):
    _workflow(tmp_path, {"a": "convert.cwl"})
    with pytest.raises(ValueError, match="tool_"):
        load_workflow(tmp_path, "script")


def test_inline_run_is_rejected(tmp_path):
    _workflow(tmp_path, {"a": "tool_a.cwl"}, code=["tool_a.py"])
    cwl = tmp_path / "primary" / "workflow_convert.cwl"
    data = yaml.safe_load(cwl.read_text())
    data["steps"]["a"]["run"] = TOOL
    cwl.write_text(yaml.safe_dump(data))
    with pytest.raises(ValueError, match="run"):
        load_workflow(tmp_path, "script")


def test_tool_cwl_must_be_a_command_line_tool(tmp_path):
    _workflow(tmp_path, {"a": "tool_a.cwl"}, code=["tool_a.py"])
    (tmp_path / "primary" / "tool_a.cwl").write_text("class: Workflow\n")
    with pytest.raises(ValueError, match="CommandLineTool"):
        load_workflow(tmp_path, "script")


def test_unused_tool_cwl_is_rejected(tmp_path):
    _workflow(tmp_path, {"a": "tool_a.cwl"}, tools=["tool_a.cwl", "tool_b.cwl"], code=["tool_a.py"])
    with pytest.raises(ValueError, match="tool_b.cwl"):
        load_workflow(tmp_path, "script")


def test_script_tool_without_code_is_rejected(tmp_path):
    _workflow(tmp_path, {"a": "tool_a.cwl"}, code=["workflow_convert.py"])
    with pytest.raises(ValueError, match="code/tool_a"):
        load_workflow(tmp_path, "script")


def test_unparsable_cwl_is_rejected(tmp_path):
    _workflow(tmp_path, {"a": "tool_a.cwl"}, code=["tool_a.py"])
    (tmp_path / "primary" / "workflow_convert.cwl").write_text("steps: [unclosed\n")
    with pytest.raises(ValueError, match="workflow_convert.cwl"):
        load_workflow(tmp_path, "script")
