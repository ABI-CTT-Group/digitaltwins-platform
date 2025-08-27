from fastapi import APIRouter, Query
from data import assays_data, launch_workflow
from models import model
import json
from pathlib import Path
# from sparc_me import Dataset, Sample, Subject
from utils import Config, digitaltwins_configs
import shutil
import pprint

current_file = Path(__file__).resolve()
root_dir = current_file.parent.parent

router = APIRouter()

"""
Categories:
    - Programmes
    - Projects
    - Investigations
    - Studies
    - Assaysx`
"""


def set_data_root_path():
    Config.BASE_PATH = root_dir / "data" / "duke"


@router.get("/api/dashboard/programmes")
async def get_dashboard_programmes():
    set_data_root_path()
    programs = digitaltwins_configs.querier.get_programs()
    programmes = []
    for data in programs:
        program = digitaltwins_configs.querier.get_program(data.get("id"))
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
        program = digitaltwins_configs.querier.get_program(program_id=seek_id)
        dependencies = digitaltwins_configs.querier.get_dependencies(program, "projects")
    elif category == "projects":
        project = digitaltwins_configs.querier.get_project(project_id=seek_id)
        dependencies = digitaltwins_configs.querier.get_dependencies(project, "investigations")
    elif category == "investigations":
        investigation = digitaltwins_configs.querier.get_investigation(investigation_id=seek_id)
        dependencies = digitaltwins_configs.querier.get_dependencies(investigation, "studies")
    elif category == "studies":
        study = digitaltwins_configs.querier.get_study(study_id=seek_id)
        dependencies = digitaltwins_configs.querier.get_dependencies(study, "assays")
    else:
        return None
    children = []
    for data in dependencies:
        if data.get("type") == "projects":
            child = digitaltwins_configs.querier.get_project(project_id=data.get("id"))
        elif data.get("type") == "investigations":
            child = digitaltwins_configs.querier.get_investigation(investigation_id=data.get("id"))
        elif data.get("type") == "studies":
            child = digitaltwins_configs.querier.get_study(study_id=data.get("id"))
        elif data.get("type") == "assays":
            child = digitaltwins_configs.querier.get_assay(assay_id=data.get("id"))
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
    sops = digitaltwins_configs.querier.get_sops()
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
        data = digitaltwins_configs.querier.get_sop(sop_id=seek_id)
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
            "origin": data
        }
    except KeyError as e:
        return None


@router.get("/api/dashboard/workflow-cwl")
async def get_dashboard_workflow_cwl():
    sop_cwl = digitaltwins_configs.querier.get_sop(1, get_cwl=True)
    print(sop_cwl)


@router.get("/api/dashboard/workflow")
async def get_dashboard_workflow(seek_id: str = Query(None)):
    sop = digitaltwins_configs.querier.get_sop(seek_id)
    return sop


@router.get("/api/dashboard/datasets")
async def get_dashboard_datasets(category: str = Query(None)):
    if category is None:
        return None
    dtp_datasets = digitaltwins_configs.querier.get_datasets(categories=[category])
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
    sample_types = digitaltwins_configs.querier.get_dataset_sample_types(dataset_uuid=uuid)
    return sample_types


@router.post("/api/dashboard/assay-details")
async def set_dashboard_assay_details(details: model.AssayDetails):
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
    digitaltwins_configs.uploader.upload_assay(assay_data)
    return True


@router.get("/api/dashboard/assay-details")
async def get_dashboard_assay_detail_by_uuid(seek_id: str = Query(None)):
    try:
        assay_detail = digitaltwins_configs.querier.get_assay(seek_id, get_params=True)
        params = assay_detail.get("params", None)
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


@router.get("/api/dashboard/assay-project")
async def get_project_by_assay_id(seek_id: str = Query(None)):
    print("aaa")
    assay_detail = digitaltwins_configs.querier.get_assay(seek_id, get_params=True)
    project_details = digitaltwins_configs.querier.get_project(
        project_id=assay_detail["relationships"]["projects"]["data"][0]["id"])
    return {
        "seekId": project_details["id"],
        "title": project_details["attributes"]["title"],
    }


@router.get("/api/dashboard/assay-launch")
async def launch_dashboard_assay_detail_by_uuid(seek_id: str = Query(None)):
    """
        When user click launch in assay, what should we do?
    """
    print(seek_id)
    # Step1: base on assay seek id to get the assay details.
    assay_detail = digitaltwins_configs.querier.get_assay(seek_id, get_params=True)
    # Step2: check the workflow type
    # Step2.1: cwl script based, return the airflow url
    # Step2.2: GUI based, execute Step 2
    workflow = digitaltwins_configs.querier.get_sop(sop_id=assay_detail.get("params").get("workflow_seek_id"))
    workflow_name = workflow.get("attributes").get("title")
    workflow_type = workflow_name.split("-")[1].lstrip()

    print("assay id", seek_id)

    if workflow_type != "GUI":
        response, workflow_monitor_url = digitaltwins_configs.workflow_dtp_executor.run(assay_id=int(seek_id))

        print("response.status_code:" + str(response.status_code))
        print("Monitoring workflow on: " + workflow_monitor_url)
        return {
            "type": "airflow",
            "data": workflow_monitor_url
        }
    else:
        # # Step3: base on the assay details to download all inputs datasets
        # # Step3.1: delete all previous inputs and outputs datasets
        # input_dataset_path = root_dir / "data" / "datasets" / "inputs"
        # output_dataset_path = root_dir / "data" / "datasets" / "outputs"
        # clear_folder(root_dir / "data" / "datasets")
        # # Step3.2: download all inputs datasets into dataset/inputs folder
        # download_inputs_datasets(input_dataset_path)
        # # Step3.3: using sparc-me to generate all outputs datasets into dataset/outputs folder
        # generate_outputs_datasets(output_dataset_path, assay_detail.get("params").get("outputs", []))
        #
        # # Step3.4: update overall METADATA
        # # Step4: return the workflow GUI frontend route name
        #
        # # details = assays_data.get(seek_id, None)
        # # if details is None:
        # #     return None
        # # details = json.loads(details)
        # # return launch_workflow.get(details["workflow"]["uuid"], None)
        if workflow_name == "Tumour position selection - GUI":
            return {
                "type": "gui",
                "data": "TumourCenterStudy"
            }
        if workflow_name == "Manual tumour position reporting - GUI":
            return {
                "type": "gui",
                "data": "TumourCalaulationStudy"
            }
        if workflow_name == "Automated tumour position reporting - GUI":
            return {
                "type": "gui",
                "data": "TumourAssistedStudy"
            }
        if workflow_name == "Clinical report visualisation - GUI":
            return {
                "type": "gui",
                "data": "ClinicalReportViewer"
            }
        # for EP3
        # if workflow_name == "Electrode selection - GUI":
        #     return {
        #         "type": "EP3 workflow launch",
        #         "data": "http://130.216.208.137:8888/lab/workspaces/auto-Q/tree/ep3/electrode_selection.ipynb?token=ctt_digitaltwins_0"
        #     }
        # if workflow_name == "Quantification of frequency of electrical activity from electrode measurements - GUI":
        #     return {
        #         "type": "EP3 workflow launch",
        #         "data": "http://130.216.208.137:8888/lab/workspaces/auto-Q/tree/ep3/quantification_of_frequency_of_electrical_activity_from_electrode_measurements.ipynb?token=ctt_digitaltwins_0"
        #     }
        # if workflow_name == "Statistical analysis of electrode measurements - GUI":
        #     return {
        #         "type": "EP3 workflow launch",
        #         "data": "http://130.216.208.137:8888/lab/workspaces/auto-Q/tree/ep3/statistical_analysis_of_electrode_measurements.ipynb?token=ctt_digitaltwins_0"
        #     }
        # for EP3 Public demo
        if workflow_name == "Electrode selection - GUI":
            return {
                "type": "EP3 workflow launch",
                "data": "http://130.216.216.26:8008/lab/tree/ep3/electrode_selection.ipynb"
            }
        if workflow_name == "Quantification of frequency of electrical activity from electrode measurements - GUI":
            return {
                "type": "EP3 workflow launch",
                "data": "http://130.216.216.26:8008/lab/tree/ep3/quantification_of_frequency_of_electrical_activity_from_electrode_measurements.ipynb"
            }
        if workflow_name == "Statistical analysis of electrode measurements - GUI":
            return {
                "type": "EP3 workflow launch",
                "data": "http://130.216.216.26:8008/lab/tree/ep3/statistical_analysis_of_electrode_measurements.ipynb"
            }
    return None


def generate_outputs_datasets(target_dataset_path, outputs):
    if not target_dataset_path.exists():
        target_dataset_path.mkdir(exist_ok=True, parents=True)
    for output in outputs:
        output_dataset_path = target_dataset_path / output.get("dataset_name")
        if output_dataset_path.exists():
            continue
        # dataset.create_empty_dataset(version="2.0.0")
        # # Save the template dataset.
        # dataset.save(save_dir=output_dataset_path)


def download_inputs_datasets(target_dataset_path):
    shutil.copytree(root_dir / "data" / "duke_test_data", target_dataset_path)


def clear_folder(folder_path):
    folder = Path(folder_path)

    if folder.exists() and folder.is_dir():
        for item in folder.iterdir():
            if item.is_file() or item.is_symlink():
                item.unlink()
            elif item.is_dir():
                clear_folder(item)
                item.rmdir()
    else:
        print(f"path not found: {folder}")
