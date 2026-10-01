"""Tool FHIR descriptions (fhir-cda ``workflow_tool`` shape) and ActivityDefinition cleanup."""
import asyncio

import pytest

from digitaltwins.tools import fhir as tool_fhir

CWL = """cwlVersion: v1.2
class: CommandLineTool
label: Tool - convert
doc: Converts DICOM to NIfTI.
inputs:
  src:
    type: Directory
    doc: measurements
outputs:
  - id: nifti
    type: File
"""


@pytest.fixture
def root(tmp_path):
    (tmp_path / "primary").mkdir()
    (tmp_path / "primary" / "tool_convert.cwl").write_text(CWL)
    (tmp_path / "dataset_description.xlsx").write_bytes(b"")  # a lone primary/ would be unwrapped as a wrapper
    return tmp_path


def test_server_fills_identity_from_the_dataset_and_cwl(root):
    d = tool_fhir.build_descriptions(root, "uuid-1", "sds_tool_convert")["workflow_tool"]

    assert (d["uuid"], d["name"], d["title"], d["description"]) == (
        "uuid-1", "sds_tool_convert", "Tool - convert", "Converts DICOM to NIfTI.")
    assert (d["version"], d["model"], d["software"], d["input"], d["output"]) == ("", [], [], [], [])


def test_client_fields_are_kept_and_server_fields_overwritten(root):
    client = {"workflow_tool": {
        "uuid": "forged", "name": "forged", "title": "forged", "version": "1.2.0", "description": "Mine",
        "model": ["m-uuid"], "software": ["s-uuid"],
        "input": [{"id": "src", "resourceType": "ImagingStudy"}],
        "output": [{"id": "nifti", "resourceType": "Observation", "code": "123", "system": "http://loinc.org"}],
    }}

    d = tool_fhir.build_descriptions(root, "uuid-1", "sds_tool_convert", client)["workflow_tool"]

    assert (d["uuid"], d["name"], d["title"]) == ("uuid-1", "sds_tool_convert", "Tool - convert")
    assert (d["version"], d["description"], d["model"], d["software"]) == ("1.2.0", "Mine", ["m-uuid"], ["s-uuid"])
    assert d["input"] == client["workflow_tool"]["input"] and d["output"] == client["workflow_tool"]["output"]


@pytest.mark.parametrize("client, message", [
    ({"patients": []}, "workflow_tool"),
    ({"workflow_tool": {"colour": "red"}}, "colour"),
    ({"workflow_tool": {"input": [{"id": "missing"}]}}, "missing"),
    ({"workflow_tool": {"output": [{"resourceType": "Observation"}]}}, "id"),
    ({"workflow_tool": {"model": "not-a-list"}}, "model"),
])
def test_invalid_client_descriptions_are_rejected(root, client, message):
    with pytest.raises(ValueError, match=message):
        tool_fhir.build_descriptions(root, "uuid-1", "x", client)


def test_ports_lists_the_cwl_inputs_and_outputs(root):
    assert tool_fhir.ports(root) == {
        "inputs": [{"id": "src", "type": "Directory", "doc": "measurements"}],
        "outputs": [{"id": "nifti", "type": "File", "doc": None}],
    }


class _Fhir:
    def __init__(self):
        self.store = {"ActivityDefinition/1": {"identifier": [{"value": "uuid-1"}]},
                      "ActivityDefinition/2": {"identifier": [{"value": "other"}]}}
        self.deleted = []

    def search(self, resource_type, identifier):
        return [{"resourceType": resource_type, "id": ref.split("/")[1], **r}
                for ref, r in self.store.items()
                if ref.startswith(resource_type) and r["identifier"][0]["value"] == identifier]

    def delete(self, ref):
        self.deleted.append(ref)


def test_delete_removes_only_the_tools_activity_definition():
    fhir = _Fhir()

    assert tool_fhir.delete("uuid-1", fhir) == 1
    assert fhir.deleted == ["ActivityDefinition/1"]


def test_push_hands_the_descriptions_to_the_workflow_tool_adapter(root):
    calls = []

    class Adapter:
        def digital_twin(self):
            return self

        def workflow_tool(self):
            return self

        def add_workflow_tool_description(self, d):
            calls.append(d)
            return self

        async def generate_resources(self):
            calls.append("generated")

    descriptions = tool_fhir.build_descriptions(root, "uuid-1", "x")
    asyncio.run(tool_fhir.push(descriptions, Adapter()))

    assert calls == [descriptions, "generated"]
