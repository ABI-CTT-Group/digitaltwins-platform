from fastapi import APIRouter, Query
from data import assays_data, launch_workflow
from models import model
import json
from pathlib import Path
from digitaltwins import Querier, Uploader
import pprint

current_file = Path(__file__).resolve()
root_dir = current_file.parent.parent
config_path = root_dir / "configs.ini"
querier = Querier(config_path)
uploader = Uploader(config_path)

router = APIRouter()

"""
Categories:
    - Programmes
    - Projects
    - Investigations
    - Studies
    - Assaysx`
"""


@router.get("/api/dashboard/programmes")
async def get_dashboard_programmes():
    programs = querier.get_programs()
    programmes = []
    for data in programs:
        program = querier.get_program(data.get("id"))
        category = program.get("type", None)
        temp = {
            "seekId": program.get("id", None),
            "name": program.get("attributes").get("title", None),
            "category": category.capitalize() if category is not None else None,
            "description": program.get("attributes").get("description", None),
        }
        programmes.append(temp)
    return programmes


@router.get("/api/dashboard/category-children")
async def get_dashboard_category_children_by_uuid(seek_id: str = Query(None), category: str = Query(None)):
    if seek_id is None or category is None:
        return None
    category = category.lower()
    if category == "assays":
        return None
    if category == "programmes":
        program = querier.get_program(program_id=seek_id)
        dependencies = querier.get_dependencies(program, "projects")
    elif category == "projects":
        project = querier.get_project(project_id=seek_id)
        dependencies = querier.get_dependencies(project, "investigations")
    elif category == "investigations":
        investigation = querier.get_investigation(investigation_id=seek_id)
        dependencies = querier.get_dependencies(investigation, "studies")
    elif category == "studies":
        study = querier.get_study(study_id=seek_id)
        dependencies = querier.get_dependencies(study, "assays")
    else:
        return None
    children = []
    for data in dependencies:
        if data.get("type") == "projects":
            child = querier.get_project(project_id=data.get("id"))
        elif data.get("type") == "investigations":
            child = querier.get_investigation(investigation_id=data.get("id"))
        elif data.get("type") == "studies":
            child = querier.get_study(study_id=data.get("id"))
        elif data.get("type") == "assays":
            child = querier.get_assay(assay_id=data.get("id"))
        else:
            return None
        send_category = child.get("type", None)
        temp = {
            "seekId": child.get("id", None),
            "name": child.get("attributes").get("title", None),
            "category": send_category.capitalize() if send_category is not None else None,
            "description": child.get("attributes").get("description", None),
        }
        children.append(temp)
    return children


@router.get("/api/dashboard/workflows")
async def get_dashboard_workflows():
    sops = querier.get_sops()
    workflows = []
    for data in sops:
        title = data['attributes']['title']
        if title is None:
            name = None
            workflow_type = None
        else:
            name = title.split(" - ")[0].rstrip()
            workflow_type = title.split(" - ")[1].lstrip()
        temp = {
            "seekId": data.get("id", None),
            "uuid": "",
            "name": name,
            "type": workflow_type,
        }
        workflows.append(temp)
    return workflows


@router.get("/api/dashboard/workflow-detail")
async def get_dashboard_workflow_detail_by_uuid(seek_id: str = Query(None)):
    if seek_id is None:
        return None
    try:
        data = querier.get_sop(sop_id=seek_id)
        title = data['attributes']['title']
        if not title:
            name = None
            workflow_type = None
        else:
            name = title.split(" - ")[0].rstrip()
            workflow_type = title.split(" - ")[1].lstrip()
        return {
            "seekId": seek_id,
            "uuid": "",
            "name": name,
            "type": workflow_type,
            "inputs": data.get("inputs", None),
            "outputs": data.get("outputs", None),
        }
    except KeyError as e:
        return None


@router.get("/api/dashboard/datasets")
async def get_dashboard_datasets(category: str = Query(None)):
    if category is None:
        return None
    dtp_datasets = querier.get_datasets(categories=[category])
    datasets = []
    for data in dtp_datasets:
        temp = {
            "uuid": data.get("dataset_uuid", None),
            "name": data.get("dataset_name", None),
        }
        datasets.append(temp)
    return datasets


@router.get("/api/dashboard/dataset-detail")
async def get_dashboard_dataset_detail_by_uuid(uuid: str = Query(None)):
    if uuid is None:
        return None
    sample_types = querier.get_dataset_sample_types(dataset_uuid=uuid)
    return sample_types


@router.post("/api/dashboard/assay-details")
async def set_dashboard_assay_details(details: model.AssayDetails):
    pprint.pprint(details)
    assay_data = {
        "assay_uuid": details.uuid,
        "assay_seek_id": int(details.seekId),
        "workflow_seek_id": int(details.workflow.seekId),
        "cohort": details.numberOfParticipants,
        "ready": details.isAssayReadyToLaunch,
        "inputs": [
            {"name": i.get("input").get("name"),
             "category": i.get("input").get("category"),
             "dataset_uuid": i.get("datasetSelectedUUID"),
             "sample_type": i.get("sampleSelectedType")} for i in details.workflow.inputs
        ],
        "outputs": [
            {"name": o.get("output").get("name"),
             "category": o.get("output").get("category"),
             "dataset_name": o.get("datasetName"),
             "sample_name": o.get("sampleName")} for o in details.workflow.outputs
        ]
    }
    uploader.upload_assay(assay_data)
    return True


@router.get("/api/dashboard/assay-details")
async def get_dashboard_assay_detail_by_uuid(seek_id: str = Query(None)):
    try:
        assay_detail = querier.get_assay(seek_id, get_params=True)
        params = assay_detail.get("params", None)
        pprint.pprint(params)
        if params is None:
            return None
        details = {
            "seekId": str(params.get("assay_seek_id", None)),
            "uuid": str(params.get("assay_uuid", "")),
            "workflow": {
                "seekId": str(params.get("workflow_seek_id", None)),
                "uuid": str(params.get("workflow_uuid", "")),
                "inputs": [{
                    "input": {
                        "name": i.get("name", None),
                        "category": i.get("category", None),
                    },
                    "datasetSelectedUUID": i.get("dataset_uuid", None),
                    "sampleSelectedType": i.get("sample_type", None),
                } for i in params.get("inputs", [])],
                "outputs": [{
                    "output": {
                        "name": o.get("name", None),
                        "category": o.get("category", None),
                    },
                    "datasetName": o.get("dataset_name", None),
                    "sampleName": o.get("sample_name", None),
                } for o in params.get("outputs", [])],
            },
            "numberOfParticipants": params.get("cohort", None),
            "isAssayReadyToLaunch": params.get("ready", None)
        }
        return details
    except (TypeError, IndexError):
        print("TypeError|IndexError")
        return None


@router.get("/api/dashboard/assay-launch")
async def launch_dashboard_assay_detail_by_uuid(seek_id: str = Query(None)):
    """
        When user click launch in assay, what should we do?
    """
    details = assays_data.get(seek_id, None)
    if details is None:
        return None
    details = json.loads(details)
    return launch_workflow.get(details["workflow"]["uuid"], None)
