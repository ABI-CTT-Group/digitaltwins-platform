"""Tests for ``digitaltwins.workflows.fhir.build_descriptions``: the PlanDefinition descriptions and its tools'."""
import pytest
import yaml

from digitaltwins.workflows import fhir as workflow_fhir
from digitaltwins.workflows.validation import load_workflow


def _tool(name):
    return {"cwlVersion": "v1.2", "class": "CommandLineTool", "label": f"Tool - {name}", "doc": f"Does {name}.",
            "inputs": {"src": {"type": "Directory"}}, "outputs": {"out": {"type": "File"}}}


@pytest.fixture
def layout(tmp_path):
    (tmp_path / "primary").mkdir()
    (tmp_path / "code").mkdir()
    workflow = {"cwlVersion": "v1.2", "class": "Workflow", "label": "Workflow - convert", "doc": "Converts.",
                "inputs": {}, "outputs": {},
                "steps": {"a": {"run": "tool_a.cwl", "in": {}, "out": ["out"]},
                          "b": {"run": "tool_b.cwl", "in": {}, "out": ["out"]},
                          "a_again": {"run": "tool_a.cwl", "in": {}, "out": ["out"]}}}
    (tmp_path / "primary" / "workflow_convert.cwl").write_text(yaml.safe_dump(workflow, sort_keys=False))
    for name in ("a", "b"):
        (tmp_path / "primary" / f"tool_{name}.cwl").write_text(yaml.safe_dump(_tool(name)))
        (tmp_path / "code" / f"tool_{name}.py").write_text("x")
    return load_workflow(tmp_path, "script")


def _uuids(layout):
    return {cwl: f"uuid-{cwl.stem}" for cwl in layout.tool_code}


def test_defaults_come_from_the_cwls_and_link_each_step_to_its_tool(layout):
    workflow, tool_descriptions = workflow_fhir.build_descriptions(layout, "wf-uuid", "wf_convert", _uuids(layout))

    assert workflow == {"workflow": {
        "uuid": "wf-uuid", "name": "wf_convert", "title": "Workflow - convert", "version": "",
        "description": "Converts.", "purpose": "", "usage": "", "author": "", "goal": [],
        "action": [
            {"title": "a", "description": "Tool - a", "related_tool_uuid": "uuid-tool_a", "input": [], "output": []},
            {"title": "b", "description": "Tool - b", "related_tool_uuid": "uuid-tool_b", "input": [], "output": []},
            {"title": "a_again", "description": "Tool - a", "related_tool_uuid": "uuid-tool_a",
             "input": [], "output": []},
        ]}}
    tool_a = tool_descriptions[layout.steps[0].tool_cwl]["workflow_tool"]
    assert (tool_a["uuid"], tool_a["name"], tool_a["title"], tool_a["description"]) == (
        "uuid-tool_a", "tool_a", "Tool - a", "Does a.")
    assert len(tool_descriptions) == 2


def test_client_fields_actions_and_tool_sections(layout):
    client = {
        "workflow": {"version": "1.0", "purpose": "Convert", "author": "alice",
                     "action": [{"step": "a",
                                 "input": [{"id": "src", "resource_type": "ImagingStudy"}],
                                 "output": [{"id": "out", "resource_type": "Observation", "code": "123",
                                             "system": "http://loinc.org", "unit": "mm"}]}]},
        "workflow_tools": {"b": {"version": "2.0", "software": ["sw-uuid"]}},
    }
    workflow, tool_descriptions = workflow_fhir.build_descriptions(layout, "wf-uuid", "n", _uuids(layout), client)

    w = workflow["workflow"]
    assert (w["version"], w["purpose"], w["author"]) == ("1.0", "Convert", "alice")
    assert w["action"][0]["input"] == [{"display": "src", "resource_type": "ImagingStudy"}]
    assert w["action"][0]["output"] == [{"display": "out", "resource_type": "Observation", "code": "123",
                                         "system": "http://loinc.org", "unit": "mm"}]
    tool_b = tool_descriptions[layout.steps[1].tool_cwl]["workflow_tool"]
    assert (tool_b["version"], tool_b["software"]) == ("2.0", ["sw-uuid"])


def test_stored_descriptions_round_trip(layout):
    client = {"workflow": {"action": [{"step": "a", "input": [{"id": "src", "resource_type": "ImagingStudy"}]}]}}
    first, tools_first = workflow_fhir.build_descriptions(layout, "wf-uuid", "n", _uuids(layout), client)
    again = {"workflow": first["workflow"],
             "workflow_tools": {s.step_id: tools_first[s.tool_cwl]["workflow_tool"] for s in layout.steps}}

    assert workflow_fhir.build_descriptions(layout, "wf-uuid", "n", _uuids(layout), again) == (first, tools_first)


@pytest.mark.parametrize("client, match", [
    ({"patients": []}, "workflow_tools"),
    ({"workflow": {"colour": "red"}}, "colour"),
    ({"workflow": {"action": [{"step": "zzz"}]}}, "zzz"),
    ({"workflow": {"action": [{"step": "a"}, {"step": "a"}]}}, "more than once"),
    ({"workflow": {"action": [{"step": "a", "input": [{"id": "nope", "resource_type": "ImagingStudy"}]}]}}, "nope"),
    ({"workflow": {"action": [{"step": "a", "output": [{"id": "out", "resource_type": "Patient"}]}]}}, "Patient"),
    ({"workflow": {"action": [{"step": "a", "input": [{"id": "src"}]}]}}, "resource_type"),
    ({"workflow_tools": {"zzz": {}}}, "zzz"),
    ({"workflow_tools": {"a": {"colour": "red"}}}, "colour"),
    ({"workflow_tools": {"a": {"version": "1"}, "a_again": {"version": "2"}}}, "same tool"),
])
def test_invalid_descriptions_are_rejected(layout, client, match):
    with pytest.raises(ValueError, match=match):
        workflow_fhir.build_descriptions(layout, "", "", {}, client)


class FakeRest:
    def __init__(self, found):
        self.found, self.deleted = found, []

    def search(self, resource_type, **params):
        assert (resource_type, params) == ("PlanDefinition", {"identifier": "wf-uuid"})
        return self.found

    def delete(self, reference):
        self.deleted.append(reference)


def test_delete_removes_the_plan_definition():
    rest = FakeRest([{"id": "7"}])
    assert workflow_fhir.delete("wf-uuid", rest) == 1
    assert rest.deleted == ["PlanDefinition/7"]
