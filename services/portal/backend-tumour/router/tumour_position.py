from fastapi import APIRouter, Query
from utils import tools
from fastapi.responses import FileResponse
from pathlib import Path
import json

router = APIRouter()


@router.get("/api/tumour_position")
async def get_tumour_position_app_detail():
    tools.get_metadata()
    case_names = tools.get_all_case_names(except_case=["test", "C-V0001"])
    case_names.sort()
    res = {}
    res["details"] = []
    for name in case_names:
        registration_nrrd_paths = tools.get_category_files(name, "nrrd", "registration")
        segmentation_breast_points_paths = tools.get_category_files(name, "json", "segmentation")
        tumour_position_path = tools.get_file_path(name, "json", "tumour_position_study.json")
        report = {}

        if tumour_position_path.exists():
            # get study status
            with open(tumour_position_path, 'r') as file:
                report = json.load(file)
        else:
            # init tumour position study report json file
            tools.init_tumour_position_json(tumour_position_path)

        # Get tumour position {x,y,z}
        if len([item for item in segmentation_breast_points_paths if "tumour_window.json" in item]) == 0:
            tumour_position = None
        else:
            tumour_windows_path = [item for item in segmentation_breast_points_paths if "tumour_window.json" in item][0]
            with open(tumour_windows_path, 'r') as file:
                tumour_position = json.load(file)
        res["details"].append(
            {"name": name, "file_path": registration_nrrd_paths[1],
             "tumour_position": tumour_position,
             "report": report})
    return res


@router.get("/api/tumour_position/clear")
async def get_tumour_position_clear():
    tools.get_metadata()
    case_names = tools.get_all_case_names(except_case=["test", "C-V0001"])
    case_names.sort()
    for name in case_names:
        tumour_position_path = tools.get_file_path(name, "json", "tumour_position_study.json")
        if tumour_position_path.exists():
            tumour_position_path.unlink()

    return "Clear successfully"


@router.get("/api/tumour_position/display")
async def get_tumour_position_display_nrrd(filepath: str = Query(None)):
    filepath = Path(filepath)
    print(filepath)
    if filepath.exists():
        return FileResponse(filepath, media_type="application/octet-stream", filename="contrast1.nrrd")
    else:
        return False
