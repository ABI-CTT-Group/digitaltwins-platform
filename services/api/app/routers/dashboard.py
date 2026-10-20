"""
Dashboard Router.

The portal's study dashboard: SEEK's programme tree, the assay config dialog and assay launch,
reshaped for the frontend (moved here from portal-backend). SEEK reads go through the caller's
Querier; assay operations call the assays routes in-process, through the module so tests can
replace them.
"""
import os
from typing import Optional
from urllib.parse import quote

import requests
from fastapi import APIRouter, Cookie, Depends, Header, HTTPException, Query, Request, status
from fastapi.security import HTTPAuthorizationCredentials
from pydantic import ValidationError

from digitaltwins import Querier, Uploader
from digitaltwins.jupyterhub.hub import JupyterHub
from digitaltwins.minio.downloader import Downloader as MinioDownloader
from . import assays
from .auth import auth_bearer, validate_credentials
from .dataset_uploads import get_conn
from .dependencies import get_jupyterhub, get_minio_downloader, get_querier, get_uploader
from ..schemas.assay import AssayDataModel, AssayDetails

router = APIRouter(prefix="/dashboard", tags=["dashboard"])

NO_GUI_TOOL_MESSAGE = ("This assay's workflow has no launchable GUI tool. Build and approve it in the portal, "
                       "or link the assay to a workflow that has one.")


def assay_type(tags) -> Optional[str]:
    """The assay's one SEEK type tag (script, gui or notebook), wherever it is among its tags.

    None when it has no type tag or more than one, as it can't be launched then.
    """
    types = {t.strip().lower() for t in tags or [] if isinstance(t, str)} & {'script', 'gui', 'notebook'}
    return types.pop() if len(types) == 1 else None


def get_workflow_type(tags) -> str:
    tags_lower = {t.lower() if isinstance(t, str) else t for t in tags}
    types = tags_lower & {'script', 'gui', 'notebook'}
    if len(types) > 1:
        return 'error'
    return types.pop() if types else 'other'


def _relationship_ids(resource: dict, relationship: str) -> list:
    """IDs of a SEEK JSON:API resource's ``relationship`` (e.g. its projects)."""
    data = ((resource.get("relationships") or {}).get(relationship) or {}).get("data") or []
    return [str(ref.get("id")) for ref in data]


def _fetch_gui_tool(workflow_seek_id, token: str) -> Optional[dict]:
    """The gui tool bundle portal-backend serves for a SEEK workflow, asked as the user; None when it has none."""
    if workflow_seek_id in (None, ""):
        return None
    base = os.getenv("PORTAL_BACKEND_URL", "http://portal-backend:8000").rstrip("/")
    try:
        res = requests.get(f"{base}/api/portal/workflow/gui-tool", params={"workflow_seek_id": workflow_seek_id},
                           headers={"Authorization": f"Bearer {token}"}, timeout=15)
    except requests.RequestException as e:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=f"Portal backend unreachable: {e}")
    if res.status_code == 404:
        return None
    if res.status_code != 200:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY,
                            detail=f"Portal backend answered {res.status_code} for the GUI tool")
    return res.json()


# ── The programme tree ────────────────────────────────────────────────


@router.get("/programmes")
def get_programmes(querier: Querier = Depends(get_querier)):
    programmes = []
    for data in querier.get_programs(get_details=False):
        category = data.get("type", None)
        programmes.append({
            "seek_id": data.get("id", None),
            "name": data.get("attributes").get("title", None),
            "category": category.capitalize() if category is not None else None,
            "description": data.get("attributes").get("description", None),
        })
    return programmes


@router.get("/category-children")
def get_category_children(seek_id: Optional[int] = Query(None), category: Optional[str] = Query(None),
                          querier: Querier = Depends(get_querier)):
    if seek_id is None or category is None:
        return None

    category = category.lower()
    if category == "programmes":
        dependencies = querier.get_program(seek_id).get("relationships").get("projects").get("data")
    elif category == "projects":
        dependencies = querier.get_project(seek_id).get("relationships").get("investigations").get("data")
    elif category == "investigations":
        dependencies = querier.get_investigation(seek_id).get("relationships").get("studies").get("data")
    elif category == "studies":
        dependencies = querier.get_study(seek_id).get("relationships").get("assays").get("data")
    else:  # assays have no children
        return None

    fetch = {"projects": querier.get_project, "investigations": querier.get_investigation,
             "studies": querier.get_study, "assays": querier.get_assay}
    children = []
    for data in dependencies:
        if data.get("type") not in fetch:
            continue
        child = fetch[data.get("type")](data.get("id"))
        send_category = child.get("type", None)

        if send_category == "assays":
            # tags/workflows are often present but EMPTY (e.g. an assay with no linked SEEK Workflow:
            # relationships.workflows is `[]`, not null), so never index them blindly.
            tags_list = child.get("attributes", {}).get("tags") or []
            workflows_rel = child.get("relationships", {}).get("workflows") or []
            # One list per linked SOP; a plain protocol SOP links no workflow.
            workflow_seek_id = next(
                (w[0].get('id') for w in workflows_rel if isinstance(w, list) and w), None)
            children.append({
                "seek_id": child.get("id", None),
                "name": child.get("attributes").get("title", None),
                "tag": assay_type(tags_list) or (tags_list[0] if tags_list else None),
                "workflow_seek_id": workflow_seek_id,
                # The config dialog offers only workflows from these projects.
                "project_ids": _relationship_ids(child, "projects"),
                "category": send_category.capitalize() if send_category else None,
                "description": child.get("attributes").get("description", None),
            })
        else:
            children.append({
                "seek_id": child.get("id", None),
                "name": child.get("attributes").get("title", None),
                "category": send_category.capitalize() if send_category else None,
                "description": child.get("attributes").get("description", None),
            })
    return children


@router.get("/assays/{assay_seek_id}")
def get_assay(assay_seek_id: int, querier: Querier = Depends(get_querier)):
    assay = querier.get_assay(assay_seek_id)
    if assay is None:
        raise HTTPException(status_code=404, detail="Assay not found")

    relationships = assay.get("relationships", {})
    study_data = relationships.get("study", {}).get("data")
    investigation_data = relationships.get("investigation", {}).get("data")
    return {
        "seek_id": assay.get("id", None),
        "name": assay.get("attributes", {}).get("title", None),
        "relationships": {
            "study_seek_id": study_data.get("id") if study_data else None,
            "investigation_seek_id": investigation_data.get("id") if investigation_data else None,
        }
    }


# ── Workflows and datasets for the config dialog ──────────────────────


@router.get("/workflows")
def get_workflows(querier: Querier = Depends(get_querier)):
    workflows = []
    for w in querier.get_workflows() or []:
        w_seek_id = w.get("id", None)
        if not w_seek_id:
            continue
        workflow_detail = querier.get_workflow(w_seek_id) or {}
        workflows.append({
            "seek_id": w_seek_id,
            "uuid": "",
            "name": w.get('attributes', {}).get('title', None),
            "type": get_workflow_type(workflow_detail.get('attributes', {}).get('tags', [])),
            "project_ids": _relationship_ids(workflow_detail, "projects"),
        })
    return workflows


def _port_name(port: dict):
    return port.get('name', '') if port.get('name') is not None else port.get('id', '')


@router.get("/workflow-detail")
def get_workflow_detail(seek_id: Optional[int] = Query(None), querier: Querier = Depends(get_querier)):
    if seek_id is None:
        return None
    workflow_detail = querier.get_workflow(seek_id)
    if not workflow_detail:
        raise HTTPException(status_code=404, detail="Workflow not found")

    attributes = workflow_detail.get('attributes', {})
    internals = attributes.get('internals', {})
    return {
        "seek_id": str(seek_id),
        "uuid": "",
        "name": attributes.get('title', ''),
        "inputs": [{"input": {"name": _port_name(i), "category": i.get('description', '')},
                    "dataset_selected_uuid": "", "sample_selected_type": ""}
                   for i in internals.get('inputs', [])],
        "outputs": [{"output": {"name": _port_name(o), "category": o.get('description', '')},
                     "dataset_name": "New dataset", "sample_name": _port_name(o)}
                    for o in internals.get('outputs', [])],
    }


@router.get("/datasets")
def get_datasets(category: Optional[str] = Query(None), querier: Querier = Depends(get_querier)):
    if category is None:
        return None
    datasets = querier.get_datasets(descriptions=False, categories=[category], keywords=None)
    return [{"uuid": d.get("dataset_uuid", None), "name": d.get("dataset_name", None)} for d in datasets]


@router.get("/dataset-detail")
def get_dataset_detail(uuid: Optional[str] = Query(None), querier: Querier = Depends(get_querier)):
    if uuid is None:
        return None
    return querier.get_dataset_sample_types(dataset_uuid=uuid)


# ── Assay config ──────────────────────────────────────────────────────


@router.post("/assay-details")
async def set_assay_details(details: AssayDetails, uploader: Uploader = Depends(get_uploader),
                            credentials: dict = Depends(validate_credentials)):
    if not details.workflow.seek_id:
        raise HTTPException(status_code=400, detail="Select a workflow")
    try:
        assay_data = AssayDataModel.model_validate({
            "assay_uuid": details.uuid,
            "assay_seek_id": details.seek_id,
            "workflow_seek_id": details.workflow.seek_id,
            # Link the workflow to the assay in SEEK (through an SOP) as part of the save.
            "link_workflow": True,
            "cohort": [str(n) for n in details.number_of_participants],
            "ready": details.is_assay_ready_to_launch,
            "inputs": [
                {"name": i.get("input").get("name"),
                 "category": i.get("input").get("category"),
                 "dataset_uuid": i.get("dataset_selected_uuid"),
                 "sample_type": i.get("sample_selected_type")} for i in details.workflow.inputs
            ],
            "outputs": [
                {"name": o.get("output").get("name"),
                 "category": o.get("output").get("category"),
                 "dataset_name": o.get("dataset_name"),
                 "sample_name": o.get("sample_name")} for o in details.workflow.outputs
            ],
        })
    except ValidationError as e:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=e.errors(include_url=False))
    await assays.configure_assay(assay_data, uploader, credentials)
    return True


@router.get("/assay-details")
def get_assay_details(seek_id: int = Query(...), querier: Querier = Depends(get_querier)):
    configs = querier.get_assay(seek_id, get_configs=True).get("configs", None)
    if configs is None:
        return None
    return {
        "seek_id": str(configs.get("assay_seek_id", None)),
        "uuid": str(configs.get("assay_uuid", "")),
        "workflow": {
            "seek_id": str(configs.get("workflow_seek_id", None)),
            "uuid": str(configs.get("workflow_uuid", "")),
            "inputs": [{
                "input": {"name": i.get("name", None), "category": i.get("category", None)},
                "dataset_selected_uuid": i.get("dataset_uuid", None),
                "sample_selected_type": i.get("sample_type", None),
            } for i in configs.get("inputs", [])],
            "outputs": [{
                "output": {"name": o.get("name", None), "category": o.get("category", None)},
                "dataset_name": o.get("dataset_name", None),
                "sample_name": o.get("sample_name", None),
            } for o in configs.get("outputs", [])],
        },
        "number_of_participants": [int(n) for n in (configs.get("cohort") or []) if str(n).isdigit()],
        "is_assay_ready_to_launch": configs.get("ready", None)
    }


# ── Launch ────────────────────────────────────────────────────────────


@router.get("/assay-launch")
def launch_assay(seek_id: int = Query(...), credentials: dict = Depends(validate_credentials),
                 querier: Querier = Depends(get_querier), conn=Depends(get_conn),
                 downloader: MinioDownloader = Depends(get_minio_downloader),
                 hub: JupyterHub = Depends(get_jupyterhub)):
    """What the dashboard's launch button does: run a script or notebook assay, or open a gui one in /tool-view."""
    assay = querier.get_assay(seek_id, get_configs=True)
    configs = assay.get("configs", None)
    if configs is None:
        return None
    workflow_type = assay_type(assay.get("attributes", {}).get("tags"))
    if workflow_type is None:
        return {"message": "Tag this assay in SEEK with exactly one of script, notebook or gui."}
    if workflow_type == "gui":
        # The tool runs in the browser: /tool-view loads the assay's inputs through /assay-gui-context.
        if _fetch_gui_tool(configs.get("workflow_seek_id"), credentials["token"]) is None:
            return {"message": NO_GUI_TOOL_MESSAGE}
        return {"type": "gui", "data": f"/tool-view?assay={seek_id}"}

    res = assays.run_assay(seek_id, credentials, querier, conn, downloader, hub)
    if workflow_type == "script":
        return {"type": "airflow", "data": res.get("monitor_url", "")}
    return {"type": "notebook", "data": res.get("url", "")}


@router.get("/assay-gui-context")
def get_assay_gui_context(request: Request, seek_id: int = Query(...),
                          credentials: dict = Depends(validate_credentials), querier: Querier = Depends(get_querier),
                          downloader: MinioDownloader = Depends(get_minio_downloader)):
    """What /tool-view needs to open a gui assay: the tool bundle, and the assay's input files as URLs."""
    configs = querier.get_assay(seek_id, get_configs=True).get("configs") or {}
    tool = _fetch_gui_tool(configs.get("workflow_seek_id"), credentials["token"])
    if tool is None:
        raise HTTPException(status_code=404, detail=NO_GUI_TOOL_MESSAGE)
    gui_inputs = assays.get_assay_gui_inputs(seek_id, querier, downloader)

    # Under the public prefix (uvicorn --root-path), so the browser reaches the file proxy below.
    files_url = f"{request.scope.get('root_path', '')}/dashboard/assays/{seek_id}/input-files"
    inputs = [{
        "name": inp.get("name"),
        "dataset_uuid": inp.get("dataset_uuid"),
        "sample_type": inp.get("sample_type"),
        "files": [{
            "name": f.get("name"),
            "subject_id": f.get("subject_id"),
            "sample_id": f.get("sample_id"),
            "url": f"{files_url}/{quote(f['bucket'], safe='')}/{quote(f['key'])}",
        } for f in inp.get("files", [])],
    } for inp in gui_inputs.get("inputs", [])]
    return {"assay_id": str(seek_id), "tool": tool, "inputs": inputs}


# ── File proxy ────────────────────────────────────────────────────────


def get_input_file_token(authorization: Optional[str] = Header(None),
                         dt_assay_file_token: Optional[str] = Cookie(None)) -> str:
    """The bearer for an input-file download: the Authorization header, else the cookie /tool-view sets.

    VolView downloads `urls=` with the browser's plain fetch, which sends no Authorization header but does
    send same-origin cookies, so /tool-view scopes the user's token to the assay's input-files path."""
    if authorization:
        scheme, _, token = authorization.partition(" ")
        if scheme.lower() != "bearer" or not token:
            raise HTTPException(status_code=401, detail="Invalid Authorization header")
        return token
    if dt_assay_file_token:
        return dt_assay_file_token
    raise HTTPException(status_code=401, detail="Missing Authorization header")


def get_input_file_querier(token: str = Depends(get_input_file_token)) -> Querier:
    """A Querier as the token's user, once the token is verified like any bearer token."""
    auth_bearer(HTTPAuthorizationCredentials(scheme="Bearer", credentials=token))
    return Querier(api_token=token)


@router.get("/assays/{seek_id}/input-files/{bucket}/{key:path}")
def get_assay_input_file(seek_id: int, bucket: str, key: str, querier: Querier = Depends(get_input_file_querier),
                         downloader: MinioDownloader = Depends(get_minio_downloader)):
    """Stream one of the assay's input files (only keys of the assay's input datasets)."""
    return assays.get_assay_input_file(seek_id, bucket, key, querier, downloader)


# ── Results ───────────────────────────────────────────────────────────


@router.post("/assay-results-submit")
async def submit_assay_results(seek_id: int = Query(...), uploader: Uploader = Depends(get_uploader),
                               querier: Querier = Depends(get_querier),
                               credentials: dict = Depends(validate_credentials)):
    return await assays.upload_workspace_datasets(seek_id, None, uploader, querier, credentials)


@router.get("/assay-download")
def download_assay_results(seek_id: Optional[int] = Query(None), querier: Querier = Depends(get_querier),
                           credentials: dict = Depends(validate_credentials)):
    if not seek_id:
        raise HTTPException(status_code=400, detail="seek_id is required")
    return assays.download_workspace_dataset(seek_id, None, querier, credentials)
