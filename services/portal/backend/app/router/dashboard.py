from fastapi import APIRouter, Query, HTTPException, Depends
from fastapi.responses import JSONResponse
from app.models import assay_model
import json
from pathlib import Path
# from sparc_me import Dataset, Sample, Subject
# from app.utils import digitaltwins_configs
import shutil
from pprint import pprint
import os
from app.utils.utils import force_rmtree, get_workflow_type
from app.client.digitaltwins_api import DigitalTWINSAPIClient
from fastapi import Header, HTTPException
from httpx import HTTPStatusError, RequestError

current_file = Path(__file__).resolve()
root_dir = current_file.parent.parent


# ADMIN_USER = os.getenv('DIGITALTWINS_ADMIN_USERNAME', "admin")
# ADMIN_PASS = os.getenv('DIGITALTWINS_ADMIN_PASSWORD', "admin")
async def get_token(authorization: str = Header(None)):
    if not authorization:
        raise HTTPException(status_code=401, detail="Missing Authorization header")

    # Authorization: Bearer xxx
    scheme, _, token = authorization.partition(" ")

    if scheme.lower() != "bearer" or not token:
        raise HTTPException(status_code=401, detail="Invalid Authorization header")

    return token


async def get_client(token: str = Depends(get_token)):
    client = DigitalTWINSAPIClient(token=token)
    try:
        yield client
    finally:
        await client.close()


router = APIRouter(prefix="/api/dashboard")

"""
Categories:
    - Programmes
    - Projects
    - Investigations
    - Studies
    - Assaysx`
"""


@router.get("/health")
async def proxy_request(client: DigitalTWINSAPIClient = Depends(get_client)):
    response = await client.get("/health")
    return JSONResponse(content=response.json(), status_code=response.status_code)


@router.get("/programmes")
async def get_programmes(client: DigitalTWINSAPIClient = Depends(get_client)):
    try:
        response = await client.get("/programs", {"get_details": False})
        print(response)
    except HTTPStatusError as e:
        raise HTTPException(status_code=e.response.status_code, detail=e.response.text)

    programmes = []
    for data in response.json().get('programs'):
        try:
            program_res = await client.get(f"/programs/{data['id']}")
        except HTTPStatusError as e:
            continue
        if program_res.status_code == 200:
            program = program_res.json().get('program')
            category = program.get("type", None)
            temp = {
                "seekId": program.get("id", None),
                "name": program.get("attributes").get("title", None),
                "category": category.capitalize() if category is not None else None,
                "description": program.get("attributes").get("description", None),
            }
            programmes.append(temp)
    return programmes


@router.get("/category-children")
async def get_dashboard_category_children_by_uuid(
        seek_id: str = Query(None),
        category: str = Query(None),
        client: DigitalTWINSAPIClient = Depends(get_client)
):
    if seek_id is None or category is None:
        return None

    category = category.lower()

    if category == "assays":
        return None

    try:
        if category == "programmes":
            res = await client.get(f"/programs/{seek_id}")
            print(res)
            root_obj = res.json().get('program')
            print(root_obj)
            dependencies = root_obj.get("relationships").get("projects").get("data")
        elif category == "projects":
            res = await client.get(f"/projects/{seek_id}")
            root_obj = res.json().get('project')
            dependencies = root_obj.get("relationships").get("investigations").get("data")
        elif category == "investigations":
            res = await client.get(f"/investigations/{seek_id}")
            root_obj = res.json().get('investigation')
            dependencies = root_obj.get("relationships").get("studies").get("data")
        elif category == "studies":
            res = await client.get(f"/studies/{seek_id}")
            root_obj = res.json().get('study')
            dependencies = root_obj.get("relationships").get("assays").get("data")
        else:
            return None
    except HTTPStatusError as e:
        raise HTTPException(status_code=e.response.status_code, detail=e.response.text)
    except RequestError as e:

        raise HTTPException(status_code=500, detail=str(e))

    children = []
    for data in dependencies:
        try:
            obj_type = data.get("type")
            obj_id = data.get("id")

            if obj_type == "projects":
                res = await client.get(f"/projects/{obj_id}")
                child = res.json().get('project')
            elif obj_type == "investigations":
                res = await client.get(f"/investigations/{obj_id}")
                child = res.json().get('investigation')
            elif obj_type == "studies":
                res = await client.get(f"/studies/{obj_id}")
                child = res.json().get('study')
            elif obj_type == "assays":
                res = await client.get(f"/assays/{obj_id}")
                child = res.json().get('assay')
            else:
                continue

            send_category = child.get("type", None)
            temp = {
                "seekId": child.get("id", None),
                "name": child.get("attributes").get("title", None),
                "category": send_category.capitalize() if send_category else None,
                "description": child.get("attributes").get("description", None),
            }
            children.append(temp)

        except HTTPStatusError as e:
            raise HTTPException(status_code=e.response.status_code, detail=e.response.text)
        except RequestError as e:
            raise HTTPException(status_code=500, detail=str(e))

    return children


@router.get("/assays/{assay_seek_id}")
async def get_seek_assay_by_id(
        assay_seek_id: str,
        client: DigitalTWINSAPIClient = Depends(get_client)
):
    try:
        res = await client.get(f"/assays/{assay_seek_id}")
        assay_res = res.json().get('assay')
        if assay_res is None:
            raise HTTPException(status_code=404, detail="Assay not found")

        relationships = assay_res.get("relationships", {})
        study_data = relationships.get("study", {}).get("data")
        investigation_data = relationships.get("investigation", {}).get("data")

        return {
            "seekId": assay_res.get("id", None),
            "name": assay_res.get("attributes", {}).get("title", None),
            "relationships": {
                "studySeekId": study_data.get("id") if study_data else None,
                "investigationSeekId": investigation_data.get("id") if investigation_data else None,
            }
        }

    except HTTPStatusError as e:
        raise HTTPException(status_code=e.response.status_code, detail=e.response.text)
    except RequestError as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/workflows")
async def get_dashboard_workflows(client: DigitalTWINSAPIClient = Depends(get_client)):
    try:
        workflows_res = await client.get("/workflows")
        workflows = workflows_res.json().get('workflows', [])
    except HTTPStatusError as e:
        raise HTTPException(status_code=e.response.status_code, detail=e.response.text)
    except RequestError as e:
        raise HTTPException(status_code=500, detail=str(e))

    workflows_response = []

    for w in workflows:
        try:
            title = w.get('attributes', {}).get('title', None)
            w_seek_id = w.get("id", None)
            if not w_seek_id:
                continue

            w_res = await client.get(f"/workflows/{w_seek_id}")
            workflow_detail = w_res.json().get('workflow', {})
            tags = workflow_detail.get('attributes', {}).get('tags', [])
            workflow_type = get_workflow_type(tags)

            temp = {
                "seekId": w_seek_id,
                "uuid": "",
                "name": title,
                "type": workflow_type,
            }
            workflows_response.append(temp)

        except HTTPStatusError as e:
            raise HTTPException(status_code=e.response.status_code, detail=e.response.text)
        except RequestError as e:
            raise HTTPException(status_code=500, detail=str(e))

    return workflows_response


@router.get("/workflow-detail")
async def get_dashboard_workflow_detail_by_uuid(
    seek_id: str = Query(None),
    client: DigitalTWINSAPIClient = Depends(get_client)
):
    if seek_id is None:
        return None

    try:
        w_res = await client.get(f"/workflows/{seek_id}")
        workflow_detail = w_res.json().get('workflow')
        if not workflow_detail:
            raise HTTPException(status_code=404, detail="Workflow not found")

        attributes = workflow_detail.get('attributes', {})
        title = attributes.get('title', '')
        tags = attributes.get('tags', [])
        workflow_type = get_workflow_type(tags)

        internals = attributes.get('internals', {})
        inputs = [
            {"name": i.get('name', ''), "category": i.get('description', '')}
            for i in internals.get('inputs', [])
        ]
        outputs = [
            {"name": i.get('name', ''), "category": i.get('description', '')}
            for i in internals.get('outputs', [])
        ]

        return {
            "seekId": seek_id,
            "uuid": "",
            "name": title,
            "type": workflow_type,
            "inputs": inputs,
            "outputs": outputs,
        }

    except HTTPStatusError as e:
        raise HTTPException(status_code=e.response.status_code, detail=e.response.text)
    except RequestError as e:
        raise HTTPException(status_code=500, detail=str(e))
    except KeyError:
        return None


@router.get("/workflow-cwl")
async def get_dashboard_workflow_cwl():
    # sop_cwl = digitaltwins_configs.querier.get_sop(1, get_cwl=True)
    # print(sop_cwl)
    return {"message": "Functionality currently disabled."}


@router.get("/workflow")
async def get_dashboard_workflow(seek_id: str = Query(None)):
    # sop = digitaltwins_configs.querier.get_sop(seek_id)
    # return sop
    return {"message": "Functionality currently disabled."}


@router.get("/datasets")
async def get_dashboard_datasets(category: str = Query(None)):
    # if category is None:
    #     return None
    # dtp_datasets = digitaltwins_configs.querier.get_datasets(categories=[category])
    # datasets = []
    # for data in dtp_datasets:
    #     temp = {
    #         "uuid": data.get("dataset_uuid", None),
    #         "name": data.get("dataset_name", None),
    #     }
    #     datasets.append(temp)
    # return datasets
    return {"message": "Functionality currently disabled."}


@router.get("/dataset-detail")
async def get_dashboard_dataset_detail_by_uuid(uuid: str = Query(None)):
    # if uuid is None:
    #     return None
    # sample_types = digitaltwins_configs.querier.get_dataset_sample_types(dataset_uuid=uuid)
    # return sample_types
    return {"message": "Functionality currently disabled."}


@router.post("/assay-details")
async def set_dashboard_assay_details(details: assay_model.AssayDetails):
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
    # digitaltwins_configs.uploader.upload_assay(assay_data)
    # return True
    return {"message": "Functionality currently disabled."}


@router.get("/assay-details")
async def get_dashboard_assay_detail_by_uuid(seek_id: str = Query(None),
                                             client: DigitalTWINSAPIClient = Depends(get_client)):
    try:
        # w_res = await client.get(f"/assay_detail/{seek_id}")
        # workflow_detail = w_res.json().get('workflow')
        # assay_detail = digitaltwins_configs.querier.get_assay(seek_id, get_params=True)
        assay_detail = {}
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


@router.get("/assay-project")
async def get_project_by_assay_id(seek_id: str = Query(None)):
    # assay_detail = digitaltwins_configs.querier.get_assay(seek_id, get_params=True)
    # project_details = digitaltwins_configs.querier.get_project(
    #     project_id=assay_detail["relationships"]["projects"]["data"][0]["id"])
    # return {
    #     "seekId": project_details["id"],
    #     "title": project_details["attributes"]["title"],
    # }
    return {"message": "Functionality currently disabled."}


@router.get("/assay-launch")
async def launch_dashboard_assay_detail_by_uuid(seek_id: str = Query(None)):
    """
        When user click launch in assay, what should we do?
    """
    # # Step1: base on assay seek id to get the assay details.
    # assay_detail = digitaltwins_configs.querier.get_assay(seek_id, get_params=True)
    # # Step2: check the workflow type
    # # Step2.1: cwl script based, return the airflow url
    # # Step2.2: GUI based, execute Step 2
    # workflow = digitaltwins_configs.querier.get_sop(sop_id=assay_detail.get("params").get("workflow_seek_id"))
    # workflow_name = workflow.get("attributes").get("title")
    # workflow_type = workflow_name.split("-")[1].lstrip()

    # print("assay id", seek_id)

    # if workflow_type != "GUI":
    #     response, workflow_monitor_url = digitaltwins_configs.workflow_dtp_executor.run(assay_id=int(seek_id))

    #     print("response.status_code:" + str(response.status_code))
    #     print("Monitoring workflow on: " + workflow_monitor_url)
    #     return {
    #         "type": "airflow",
    #         "data": workflow_monitor_url
    #     }
    # else:
    #     # # Step3: base on the assay details to download all inputs datasets
    #     # # Step3.1: delete all previous inputs and outputs datasets
    #     # input_dataset_path = root_dir / "data" / "datasets" / "inputs"
    #     # output_dataset_path = root_dir / "data" / "datasets" / "outputs"
    #     # clear_folder(root_dir / "data" / "datasets")
    #     # # Step3.2: download all inputs datasets into dataset/inputs folder
    #     # download_inputs_datasets(input_dataset_path)
    #     # # Step3.3: using sparc-me to generate all outputs datasets into dataset/outputs folder
    #     # generate_outputs_datasets(output_dataset_path, assay_detail.get("params").get("outputs", []))
    #     #
    #     # # Step3.4: update overall METADATA
    #     # # Step4: return the workflow GUI frontend route name
    #     #
    #     # # details = assays_data.get(seek_id, None)
    #     # # if details is None:
    #     # #     return None
    #     # # details = json.loads(details)
    #     # # return launch_workflow.get(details["workflow"]["uuid"], None)
    #     if workflow_name == "Tumour position selection - GUI":
    #         return {
    #             "type": "gui",
    #             "data": "TumourCenterStudy"
    #         }
    #     if workflow_name == "Manual tumour position reporting - GUI":
    #         return {
    #             "type": "gui",
    #             "data": "TumourCalaulationStudy"
    #         }
    #     if workflow_name == "Automated tumour position reporting - GUI":
    #         return {
    #             "type": "gui",
    #             "data": "TumourAssistedStudy"
    #         }
    #     if workflow_name == "Clinical report visualisation - GUI":
    #         return {
    #             "type": "gui",
    #             "data": "ClinicalReportViewer"
    #         }
    #     # for EP3
    #     # if workflow_name == "Electrode selection - GUI":
    #     #     return {
    #     #         "type": "EP3 workflow launch",
    #     #         "data": "http://130.216.208.137:8888/lab/workspaces/auto-Q/tree/ep3/electrode_selection.ipynb?token=ctt_digitaltwins_0"
    #     #     }
    #     # if workflow_name == "Quantification of frequency of electrical activity from electrode measurements - GUI":
    #     #     return {
    #     #         "type": "EP3 workflow launch",
    #     #         "data": "http://130.216.208.137:8888/lab/workspaces/auto-Q/tree/ep3/quantification_of_frequency_of_electrical_activity_from_electrode_measurements.ipynb?token=ctt_digitaltwins_0"
    #     #     }
    #     # if workflow_name == "Statistical analysis of electrode measurements - GUI":
    #     #     return {
    #     #         "type": "EP3 workflow launch",
    #     #         "data": "http://130.216.208.137:8888/lab/workspaces/auto-Q/tree/ep3/statistical_analysis_of_electrode_measurements.ipynb?token=ctt_digitaltwins_0"
    #     #     }
    #     # for EP3 Public demo
    #     if workflow_name == "Electrode selection - GUI":
    #         return {
    #             "type": "EP3 workflow launch",
    #             "data": "http://130.216.216.26:8008/lab/tree/ep3/electrode_selection.ipynb"
    #         }
    #     if workflow_name == "Quantification of frequency of electrical activity from electrode measurements - GUI":
    #         return {
    #             "type": "EP3 workflow launch",
    #             "data": "http://130.216.216.26:8008/lab/tree/ep3/quantification_of_frequency_of_electrical_activity_from_electrode_measurements.ipynb"
    #         }
    #     if workflow_name == "Statistical analysis of electrode measurements - GUI":
    #         return {
    #             "type": "EP3 workflow launch",
    #             "data": "http://130.216.216.26:8008/lab/tree/ep3/statistical_analysis_of_electrode_measurements.ipynb"
    #         }
    # return None
    return {"message": "Functionality currently disabled."}


@router.get("/copy_dataset/{name}")
def copy_dataset(name: str):
    measurements_path = os.environ.get("DATASET_DIR_MEASUREMENT", "./datasets_measurement")
    src = Path(measurements_path) / name
    dst = Path("./data")
    dst.mkdir(parents=True, exist_ok=True)
    if not src.exists():
        raise HTTPException(status_code=404, detail=f"dataset directory {src} does not exist")

    for item in src.iterdir():
        target = dst / item.name

        if target.exists():
            if target.is_file():
                target.unlink()
            else:
                shutil.rmtree(target)

        if item.is_dir():
            shutil.copytree(item, target)
        else:
            shutil.copy2(item, target)

    return {
        "status": "200",
        "message": "dataset moved successfully"
    }


@router.get("/clear_data")
def clear_data():
    dst = Path("./data")
    force_rmtree(dst, True)

    return {
        "status": "200",
        "message": "dataset moved successfully"
    }


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
