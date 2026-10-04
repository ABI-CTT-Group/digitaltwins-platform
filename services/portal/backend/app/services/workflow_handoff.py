"""Hand an approved SDS workflow build to digitaltwins-api, as the approving user.

Same session protocol and token relay as :mod:`app.services.tool_handoff`. The
API ingests the package as a workflow dataset plus a tool dataset per tool
(docs/decisions/2026-10-02-workflow-dataset-ingest.md); a re-approval or a
delete removes the previous dataset with its tools
(docs/decisions/2026-10-02-portal-sds-workflow-approval.md).
"""
import json
import logging
from typing import Any, Dict, Optional

from app.models.db_model import Workflow, WorkflowBuild
from app.services import tool_handoff

logger = logging.getLogger(__name__)

WORKFLOW_CATEGORY = "workflows"
PLACEHOLDER_PREFIX = "sparc-workflow-"  # the legacy approval stub's uuid; never in the platform


def in_platform(workflow: Workflow) -> bool:
    return bool(workflow.uuid) and not workflow.uuid.startswith(PLACEHOLDER_PREFIX)


def fhir_descriptions(workflow: Workflow) -> Dict[str, Any]:
    """``{"workflow": {...}, "workflow_tools": {...}}`` from the Annotation step's ``{"steps": [...]}`` draft.

    Steps that run the same tool share its ActivityDefinition: the first one's ports annotate it.
    """
    note = workflow.annotation.fhir_note if workflow.annotation else None
    draft = json.loads(note) if note else {}
    actions, tools, seen = [], {}, set()
    for step in draft.get("steps") or []:
        actions.append({
            "step": step["step"],
            "input": [{"id": p["name"], "resource_type": p["resource"]}
                      for p in step.get("inputs") or [] if p.get("resource")],
            "output": [{"id": p["name"], "resource_type": p["resource"],
                        **{k: p[k] for k in ("code", "system", "unit") if p.get(k)}}
                       for p in step.get("outputs") or [] if p.get("resource")],
        })
        if step.get("tool") not in seen:
            seen.add(step.get("tool"))
            tools[step["step"]] = tool_handoff.tool_section(workflow.version, step)
    section: Dict[str, Any] = {"version": workflow.version}
    if workflow.author:
        section["author"] = workflow.author
    if workflow.description:
        section["description"] = workflow.description
    section["action"] = actions
    return {"workflow": section, "workflow_tools": tools}


def start(db, workflow: Workflow, build: WorkflowBuild, user: Dict[str, Any], seek_project_id: int,
          fhir: bool) -> None:
    """Open the API upload session for ``build`` as ``user`` (the caller then runs :func:`run` in the background)."""
    token = user["token"]
    body = {"name": workflow.name, "description": workflow.description, "category": WORKFLOW_CATEGORY,
            "workflow_type": workflow.workflow_type, "seek_project_id": seek_project_id}
    if fhir:
        body["fhir_descriptions"] = fhir_descriptions(workflow)
    tool_handoff.open_session(tool_handoff.Api(tool_handoff.make_http(), lambda: token),
                              build, user["username"], body)
    workflow.seek_project_id = seek_project_id
    db.commit()
    tool_handoff.relay.put(build.build_id, token)


def _tool_dataset_uuid(api: tool_handoff.Api, workflow: Workflow, dataset_uuid: str) -> Optional[str]:
    """The platform tool dataset of a gui workflow's one step, so the Tool Hub can launch it (None if unknown)."""
    if workflow.workflow_type != "gui":
        return None
    try:
        tools = api.request("GET", f"/datasets/{dataset_uuid}/workflow-tools")["tools"]
    except Exception as exc:
        logger.warning("Tool dataset of gui workflow %s not found: %s", workflow.id, exc)
        return None
    return tools[0]["dataset_uuid"] if len(tools) == 1 else None


def _complete(db, api: tool_handoff.Api, build: WorkflowBuild, dataset_uuid: str) -> None:
    """Record the committed dataset; with re-approval, the previous one (and its tools) is deleted only now."""
    workflow = build.workflow
    seek_id = api.request("GET", f"/datasets/{dataset_uuid}")["dataset"].get("seek_id")
    previous = workflow.uuid if in_platform(workflow) else None
    build.dataset_uuid, build.seek_id, build.handoff_status = dataset_uuid, seek_id, "completed"
    build.tool_dataset_uuid = _tool_dataset_uuid(api, workflow, dataset_uuid)
    workflow.uuid = dataset_uuid
    db.commit()
    if previous and previous != dataset_uuid:
        try:
            api.request("DELETE", f"/datasets/{previous}", expect=(200, 404), params={"delete_tools": "true"})
            db.query(WorkflowBuild).filter(WorkflowBuild.dataset_uuid == previous).update({"dataset_uuid": None})
        except Exception as exc:
            logger.warning("Previous dataset %s of workflow %s not deleted: %s", previous, workflow.id, exc)
            build.handoff_error = f"Approved, but the previous version {previous} could not be deleted: {exc}"
        db.commit()


def run(build_id: str) -> None:
    tool_handoff.run(build_id, WorkflowBuild, _complete)
