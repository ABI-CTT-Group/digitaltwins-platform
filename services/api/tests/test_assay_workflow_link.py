"""Tests for ``digitaltwins.core.assay_workflow_link``: linking an assay to a workflow through a SEEK SOP."""
import pytest

from digitaltwins.core.assay_workflow_link import WorkflowNotInAssayProject, link_assay_workflow


def _refs(kind, ids):
    return {"data": [{"id": str(i), "type": kind} for i in ids]}


class FakeSeek:
    """In-memory SEEK: assays, SOPs and workflows, read by the querier and changed by the writer."""

    def __init__(self, assay_sops=(), sops=None, projects=("12",), workflow_projects=("12",)):
        self.assay_sops = list(assay_sops)
        self.projects = list(projects)
        self.workflow_projects = list(workflow_projects)
        self.sops = sops or {}  # sop id -> {"workflows": [...], "assays": [...]}
        self.created = []
        self.patched = []
        self.deleted = []
        self.fail_create = False
        self.fail_patch_for = None

    # querier
    def get_assay(self, assay_id):
        return {"id": str(assay_id), "relationships": {
            "sops": _refs("sops", self.assay_sops), "projects": _refs("projects", self.projects)}}

    def get_sop(self, sop_id):
        sop = self.sops[str(sop_id)]
        return {"id": str(sop_id), "relationships": {
            "workflows": _refs("workflows", sop["workflows"]), "assays": _refs("assays", sop["assays"])}}

    def get_workflow(self, workflow_id):
        return {"id": str(workflow_id), "attributes": {"title": f"Workflow {workflow_id}"},
                "relationships": {"projects": _refs("projects", self.workflow_projects)}}

    # writer
    def create_sop(self, title, description, project_ids, assay_id, workflow_id, content):
        if self.fail_create:
            raise RuntimeError("SEEK SOP create failed")
        self.created.append({"title": title, "projects": list(project_ids), "assay": assay_id,
                             "workflow": workflow_id, "content": content})
        return 100

    def set_sop_assays(self, sop_id, assay_ids):
        if str(sop_id) == self.fail_patch_for:
            raise RuntimeError(f"SEEK SOP {sop_id} update failed")
        self.patched.append((str(sop_id), list(assay_ids)))

    def delete_sop(self, sop_id):
        self.deleted.append(sop_id)


def test_already_linked_assay_is_left_alone():
    seek = FakeSeek(assay_sops=["5"], sops={"5": {"workflows": ["39"], "assays": ["42"]}})
    undo = link_assay_workflow(seek, seek, 42, 39)
    undo()
    assert seek.created == [] and seek.patched == [] and seek.deleted == []


def test_unlinked_assay_gets_one_new_sop_in_its_projects():
    seek = FakeSeek()
    link_assay_workflow(seek, seek, 42, 39)
    [sop] = seek.created
    assert sop["title"] == "Workflow link: Workflow 39"
    assert sop["projects"] == ["12"]
    assert (sop["assay"], sop["workflow"]) == (42, 39)
    assert "assay 42" in sop["content"] and "Workflow 39" in sop["content"] and "(39)" in sop["content"]
    assert seek.patched == []


def test_relink_detaches_only_sops_that_link_a_workflow():
    seek = FakeSeek(assay_sops=["4", "5"], sops={
        "4": {"workflows": [], "assays": ["42"]},            # a plain protocol SOP: kept
        "5": {"workflows": ["38"], "assays": ["42", "7"]},   # the old workflow link: detached
    })
    link_assay_workflow(seek, seek, 42, 39)
    assert seek.patched == [("5", ["7"])]
    assert len(seek.created) == 1


def test_undo_deletes_the_new_sop_and_reattaches_the_old_ones():
    seek = FakeSeek(assay_sops=["5"], sops={"5": {"workflows": ["38"], "assays": ["42", "7"]}})
    undo = link_assay_workflow(seek, seek, 42, 39)
    seek.patched.clear()
    undo()
    assert seek.deleted == [100]
    assert seek.patched == [("5", ["42", "7"])]


def test_failed_create_reattaches_the_detached_sops_and_raises():
    seek = FakeSeek(assay_sops=["5"], sops={"5": {"workflows": ["38"], "assays": ["42"]}})
    seek.fail_create = True
    with pytest.raises(RuntimeError, match="create failed"):
        link_assay_workflow(seek, seek, 42, 39)
    assert seek.patched == [("5", []), ("5", ["42"])]


def test_failed_detach_reattaches_earlier_ones_and_raises():
    seek = FakeSeek(assay_sops=["5", "6"], sops={
        "5": {"workflows": ["38"], "assays": ["42"]},
        "6": {"workflows": ["37"], "assays": ["42"]},
    })
    seek.fail_patch_for = "6"
    with pytest.raises(RuntimeError, match="SOP 6 update failed"):
        link_assay_workflow(seek, seek, 42, 39)
    assert seek.patched == [("5", []), ("5", ["42"])]
    assert seek.created == []


def test_undo_keeps_going_when_a_step_fails(caplog):
    seek = FakeSeek(assay_sops=["5"], sops={"5": {"workflows": ["38"], "assays": ["42"]}})
    undo = link_assay_workflow(seek, seek, 42, 39)

    def broken_delete(sop_id):
        raise RuntimeError("gone")

    seek.delete_sop = broken_delete
    seek.patched.clear()
    undo()
    assert seek.patched == [("5", ["42"])]
    assert "Could not delete SEEK SOP 100" in caplog.text


def test_workflow_from_another_project_is_rejected_before_seek_changes():
    seek = FakeSeek(assay_sops=["5"], sops={"5": {"workflows": ["38"], "assays": ["42"]}},
                    projects=["12"], workflow_projects=["11"])
    with pytest.raises(WorkflowNotInAssayProject, match="Workflow 39 is not in any of assay 42's projects"):
        link_assay_workflow(seek, seek, 42, 39)
    assert seek.patched == [] and seek.created == []


def test_workflow_sharing_one_of_the_assays_projects_is_accepted():
    seek = FakeSeek(projects=["12", "13"], workflow_projects=["11", "13"])
    link_assay_workflow(seek, seek, 42, 39)
    assert len(seek.created) == 1
