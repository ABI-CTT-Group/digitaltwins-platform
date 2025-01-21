from fastapi import APIRouter, Query
from utils import tools
from fastapi.responses import FileResponse
from pathlib import Path
from models import model
import json

router = APIRouter()

except_cases = ["Breast_014", "C-V0001"]


@router.get("/api/tumour_position")
async def get_tumour_position_app_detail():
    tools.get_metadata()
    case_names = tools.get_all_case_names(except_case=except_cases)
    case_names.sort()
    res = {}
    res["details"] = []
    for name in case_names:
        registration_nrrd_paths = tools.get_category_files(name, "nrrd", "registration")
        segmentation_breast_points_paths = tools.get_category_files(name, "json", "segmentation")
        tumour_report_path = tools.get_file_path(name, "json", "tumour_position_study.json")
        report = {}

        if tumour_report_path.exists() and tumour_report_path.stat().st_size != 0:
            # get study status
            with open(tumour_report_path, 'r') as file:
                report = json.load(file)
        else:
            # init tumour position study report json file
            tools.init_tumour_position_json(tumour_report_path)

        # Get tumour position {x,y,z}
        if len([item for item in segmentation_breast_points_paths if "tumour_window.json" in item]) == 0:
            tumour_window = None
        else:
            tumour_windows_path = [item for item in segmentation_breast_points_paths if "tumour_window.json" in item][0]
            with open(tumour_windows_path, 'r') as file:
                tumour_window = json.load(file)
        res["details"].append(
            {"name": name, "file_path": registration_nrrd_paths[1],
             "tumour_window": tumour_window,
             "report": report})
    return res


@router.get("/api/tumour_position/report_clear")
async def get_tumour_position_report_clear():
    tools.get_metadata()
    case_names = tools.get_all_case_names(except_case=except_cases)
    case_names.sort()
    for name in case_names:
        tumour_position_path = tools.get_file_path(name, "json", "tumour_position_study.json")
        if tumour_position_path.exists():
            tumour_position_path.unlink()

    return "Clear successfully"


@router.get("/api/tumour_position/tumour_center_clear")
async def get_tumour_position_tumour_center_clear():
    tools.get_metadata()
    case_names = tools.get_all_case_names(except_case=except_cases)
    case_names.sort()
    for name in case_names:
        tumour_position_path = tools.get_file_path(name, "json", "tumour_window.json")
        if tumour_position_path.exists():
            with open(tumour_position_path, 'r') as file:
                tumour_position = json.load(file)
                tumour_position["validate"] = False
            with open(tumour_position_path, 'w') as file:
                json.dump(tumour_position, file)
    return "Clear successfully"


@router.get("/api/tumour_position/display")
async def get_tumour_position_display_nrrd(filepath: str = Query(None)):
    filepath = Path(filepath)
    if filepath.exists():
        return FileResponse(filepath, media_type="application/octet-stream", filename="contrast1.nrrd")
    else:
        return False


@router.post("/api/tumour_position/report")
async def save_tumour_position_report(study_report: model.TumourStudyReport):
    tumour_report_path = tools.get_file_path(study_report.case_name, "json", "tumour_position_study.json")
    with open(tumour_report_path, 'w') as file:
        json.dump(study_report.model_dump(), file, indent=4)
    return True


@router.post("/api/tumour_position/assisted")
async def save_tumour_position_assisted(study_report: model.TumourAssisted):
    save_position = study_report.tumour_position
    assisted_report = study_report.tumour_study_report
    tumour_assisted_path = tools.get_file_path(assisted_report.case_name, "json",
                                               "tumour_position_study_assisted.json")
    tumour_report_path = tools.get_file_path(assisted_report.case_name, "json", "tumour_position_study.json")
    tumour_position_path = tools.get_file_path(save_position.case_name, "json", "tumour_window.json")

    with open(tumour_assisted_path, 'w') as file:
        json.dump(assisted_report.model_dump(), file, indent=4)

    if tumour_report_path.exists():
        with open(tumour_report_path, 'r') as file:
            report = json.load(file)
        report["assisted"] = assisted_report.assisted
        with open(tumour_report_path, 'w') as file:
            json.dump(report, file, indent=4)

    if tumour_position_path.exists():
        with open(tumour_position_path, "r") as tumour_position_file:
            data = tumour_position_file.read()
            position_json = json.loads(data)

    position_json["center"] = save_position.model_dump().get("position")
    # position_json["validate"] = save_position.model_dump().get("validate", False)
    with open(tumour_position_path, "w") as tumour_position_file:
        json.dump(position_json, tumour_position_file, indent=4)

    return True
