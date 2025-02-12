from fastapi import APIRouter, Query
from data import dashboard_data, workflows_data, datasets_data

router = APIRouter()

"""
Categories:
    - Programmes
    - Projects
    - Investigations
    - Studies
    - Assays
"""


@router.get("/api/dashboard/programmes")
async def get_dashboard_programmes():
    programmes = []
    for data in dashboard_data:
        temp = {
            "uuid": data.get("uuid", None),
            "name": data.get("name", None),
            "category": data.get("category", None),
            "description": data.get("description", None),
        }
        programmes.append(temp)
    return programmes


@router.get("/api/dashboard/category-children")
async def get_dashboard_category_children_by_uuid(uuid: str = Query(None), category: str = Query(None)):
    if uuid is None or category is None:
        return None
    if category == "Assays":
        return None
    filtered_data = test_get_filter_data(dashboard_data, uuid)
    print(filtered_data)
    if filtered_data is None:
        return None
    children = []
    for data in filtered_data.get("children", []):
        temp = {
            "uuid": data.get("uuid", None),
            "name": data.get("name", None),
            "category": data.get("category", None),
            "description": data.get("description", None),
        }
        children.append(temp)
    return children


def test_get_filter_data(data, uuid):
    for d in data:
        if d["uuid"] == uuid:
            return d
        result = test_get_filter_data(d["children"], uuid)
        if result:
            return result
    return None


@router.get("/api/dashboard/workflows")
async def get_dashboard_workflows():
    workflows = []
    for data in workflows_data:
        temp = {
            "uuid": data.get("uuid", None),
            "name": data.get("name", None),
            "type": data.get("type", None),
        }
        workflows.append(temp)
    return workflows


@router.get("/api/dashboard/workflow-detail")
async def get_dashboard_workflows_detail_by_uuid(uuid: str = Query(None)):
    if uuid is None:
        return None
    for data in workflows_data:
        if data["uuid"] == uuid:
            return {
                "inputs": data.get("inputs", None),
                "outputs": data.get("outputs", None),
            }
    return None


@router.get("/api/dashboard/datasets")
async def get_dashboard_datasets():
    datasets = []
    for data in datasets_data:
        temp = {
            "uuid": data.get("uuid", None),
            "name": data.get("name", None),
        }
        datasets.append(temp)
    return datasets


@router.get("/api/dashboard/dataset-detail")
async def get_dashboard_dataset_detail_by_uuid(uuid: str = Query(None)):
    if uuid is None:
        return None
    for data in datasets_data:
        if data["uuid"] == uuid:
            return {
                "samples": data.get("samples", None),
            }
    return None
