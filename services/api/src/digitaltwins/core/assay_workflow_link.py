"""Link a SEEK assay to a workflow through an SOP (Assay -> SOP -> Workflow), as the calling user.

The portal reads an assay's workflow by walking its SOPs, using the first workflow
found. Linking a new workflow detaches the assay from every SOP that links a
workflow (the SOPs themselves stay in SEEK) and creates a fresh SOP for the new one.
See docs/decisions/2026-10-05-link-assay-to-workflow-via-auto-created-sop.md.
"""
import logging
from typing import Callable

logger = logging.getLogger(__name__)


class WorkflowNotInAssayProject(ValueError):
    """The workflow shares no SEEK project with the assay, so it may not be linked to it."""


def _ids(resource: dict, relationship: str) -> list:
    data = ((resource.get("relationships") or {}).get(relationship) or {}).get("data") or []
    return [str(ref["id"]) for ref in data]


def _reattach(writer, detached) -> None:
    for sop_id, assay_ids in detached:
        try:
            writer.set_sop_assays(sop_id, assay_ids)
        except Exception:
            logger.warning("Could not re-attach SEEK SOP %s to its assays %s", sop_id, assay_ids)


def link_assay_workflow(querier, writer, assay_id, workflow_id) -> Callable[[], None]:
    """Make ``workflow_id`` the workflow SEEK links to ``assay_id``; return a best-effort undo.

    ``querier`` reads SEEK (``digitaltwins.seek.querier.Querier``) and ``writer``
    changes it (``digitaltwins.seek.writer.Writer``). Does nothing when the assay's
    first linked workflow already is ``workflow_id``. Raises ``WorkflowNotInAssayProject``,
    before changing SEEK, when the workflow is in none of the assay's projects.
    """
    assay = querier.get_assay(assay_id)
    workflow_sops = []  # (sop id, its workflow ids, its assay ids) for SOPs that link a workflow
    for sop_id in _ids(assay, "sops"):
        sop = querier.get_sop(sop_id)
        workflow_ids = _ids(sop, "workflows")
        if workflow_ids:
            workflow_sops.append((sop_id, workflow_ids, _ids(sop, "assays")))

    if workflow_sops and workflow_sops[0][1][0] == str(workflow_id):
        return lambda: None

    workflow = querier.get_workflow(workflow_id)
    assay_projects = _ids(assay, "projects")
    if not set(_ids(workflow, "projects")) & set(assay_projects):
        raise WorkflowNotInAssayProject(
            f"Workflow {workflow_id} is not in any of assay {assay_id}'s projects ({', '.join(assay_projects)}).")

    detached = []  # (sop id, its assay ids before the detach)
    try:
        for sop_id, _, assay_ids in workflow_sops:
            writer.set_sop_assays(sop_id, [a for a in assay_ids if a != str(assay_id)])
            detached.append((sop_id, assay_ids))

        title = (workflow.get("attributes") or {}).get("title") or f"Workflow {workflow_id}"
        content = (
            f"# Workflow link\n\n"
            f"Links SEEK assay {assay_id} to the workflow \"{title}\" ({workflow_id}).\n\n"
            f"Created by the DigitalTWINS Portal when the assay was configured.\n"
        )
        new_sop_id = writer.create_sop(
            f"Workflow link: {title}",
            "Created by the DigitalTWINS Portal to link this assay to its workflow.",
            assay_projects, assay_id, workflow_id, content,
        )
    except Exception:
        _reattach(writer, detached)
        raise

    def undo() -> None:
        try:
            writer.delete_sop(new_sop_id)
        except Exception:
            logger.warning("Could not delete SEEK SOP %s after a failed assay configure", new_sop_id)
        _reattach(writer, detached)

    return undo
