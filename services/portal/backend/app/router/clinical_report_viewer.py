from fastapi import APIRouter, Query
from app.utils import digitaltwins_configs
from pprint import pprint
router = APIRouter()

@router.get("/api/report_viewer/report_detail")
async def get_report_detail_via_assay_id(seek_id: str = Query(None)):
    assay = digitaltwins_configs.querier.get_assay(assay_id=seek_id, get_params=True)
    inputs = assay["params"]["inputs"]
    dataset_uuid = ""
    sample_type = ""
    for i in inputs:
        if i["category"] == "measurement":
            dataset_uuid = i["dataset_uuid"]
            sample_type = i["sample_type"]
            break
    if dataset_uuid == "" or sample_type == "":
        return None
    else:
        samples = digitaltwins_configs.querier.get_dataset_samples(dataset_uuid=dataset_uuid, sample_type=sample_type)
        res = []
        for sample in samples:
            res.append({
                "uuid": sample["subject_id"],
                "date": "18/03/2025"
            })
        return res
