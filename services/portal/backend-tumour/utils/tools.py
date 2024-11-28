import json
import time
import pandas as pd
from .setup import Config
from pathlib import Path
from zipfile import ZipFile
from io import BytesIO


def get_metadata():
    """
    :return: df format metadata
    """
    metadata_path = Config.BASE_PATH / Config.METADATA_PATH
    if metadata_path.is_file() and metadata_path.suffix == ".xlsx":
        Config.METADATA = pd.read_excel(metadata_path, sheet_name="Sheet1")


def get_all_case_names():
    """
    :return: get each case name, the patient id for user to switch cases
    """
    if Config.METADATA is not None:
        case_names = list(set(Config.METADATA["patient_id"]))
        Config.CASE_NAMES = case_names
        return case_names
    return []


def check_file_exist(patient_id, filetype, filename):
    """
    :param patient_id: case name
    :param filename: mask.json mask.obj
    :return: if there is a mask.json file return true, else create a mask.json and return false
    """
    file_path = get_file_path(patient_id, filetype, filename)
    if file_path is not None:
        if filetype == "json":
            # Create the directory and all parent directories if they don't exist
            file_path.parent.mkdir(parents=True, exist_ok=True)
            if file_path.name != filename:
                new_file_path = file_path.parent / filename
                new_file_path.touch()
            else:
                if file_path.exists():
                    return True
                else:
                    file_path.touch()
        else:
            return file_path.exists()
    return False


def write_data_to_json(patient_id, masks):
    # todo 1: find mask.json path base on patient_id
    try:
        mask_json_path = get_file_path(patient_id, "json", "mask.json")
        if mask_json_path is not None:
            Config.MASK_FOLDER_PATH = mask_json_path.parent
            Config.MASK_FILE_PATH = mask_json_path
            Config.MASKS = masks
            saveMaskData()
    except :
        print("File not found!")


def get_file_path(patient_id, file_type, file_name):
    """
    :param patient_id: case name
    :param file_type: json, nrrd, nii
    :return: file full path via pathlib
    """
    if Config.METADATA is not None:
        file_df = Config.METADATA[
            (Config.METADATA["patient_id"] == patient_id) & (Config.METADATA["file type"] == file_type)]
        # index = mask_json_df.index.tolist()
        # path = mask_json_df.loc[index[0], 'filename']
        paths = list(file_df['filename'])
        new_paths = []
        for path in paths:
            new_paths.append(Config.BASE_PATH / path)
        file_path_arr = [path for path in new_paths if path.name==file_name]
        if len(file_path_arr) >0:
            file_path_full = file_path_arr[0]
            return file_path_full
    return None
def get_category_files(patient_id, file_type, categore, except_file_name=[]):
    """
        :param patient_id: case name
        :param file_type: json, nrrd, nii
        :return: file full path via pathlib
        """
    if Config.METADATA is not None:
        file_df = Config.METADATA[
            (Config.METADATA["patient_id"] == patient_id) & (Config.METADATA["file type"] == file_type)]
        paths = list(file_df['filename'])
        new_paths = []
        for path in paths:
            file_path = Config.BASE_PATH / path
            if file_path.name not in except_file_name:
                new_paths.append(file_path)

        file_path_arr = [str(path).replace("\\", "/") for path in new_paths if path.parent.name == categore and path.exists()]
        if len(file_path_arr) > 0:
            return file_path_arr
    return []


def save_sphere_points_to_json(patient_id, data):

    sphere_json_path = get_file_path(patient_id, "json", "sphere_points.json")
    if sphere_json_path is None:
        return False
    sphere_json_path = Path(sphere_json_path)
    if not sphere_json_path.parent.exists():
        sphere_json_path.mkdir(parents=True, exist_ok=True)

    with open(sphere_json_path, "w") as json_file:
        json.dump(data, json_file)
    return True
def replace_data_to_json(patient_id, slice):
    """
    :param patient_id: case name
    :param slice: a single slice mask pixels
    """
    mask_json_path = get_file_path(patient_id, "json", "mask.json")
    index = slice.sliceId
    label = slice.label
    if Config.MASKS == None:
        if mask_json_path is not None and mask_json_path.is_file():
            getMaskData(mask_json_path)
    Config.MASKS[label][index]["data"] = slice.mask
    Config.MASKS["hasData"] = True

def selectNrrdPaths(patient_id, file_type, limit):
    """
    :param patient_id: name
    :param file_type: nrrd / nii / json
    :param limit: file parent folder name
    :return:
    """
    all_nrrd_paths = []
    nrrds_df = Config.METADATA[(Config.METADATA["file type"] == file_type) & (Config.METADATA["patient_id"] == patient_id)]
    all_nrrd_paths.extend(list(nrrds_df["filename"]))
    selected_paths = []
    for file_path in all_nrrd_paths:
        if Path(file_path).parent.name == limit:
            selected_paths.append(file_path)
    return selected_paths

def getReturnedJsonFormat(path):
    """
    :param path:
    :return: returns BytesIO for response to frontend
    """
    with open(path, mode="rb") as file:
        file_contents = file.read()
    return BytesIO(file_contents)

def getJsonData(path):
    """
    get json core
    :param path:
    :return:
    """
    with open(path, 'rb') as file:
        # Load the JSON data from the file into a Python object
        return json.loads(file.read().decode('utf-8'))


def getMaskData(path):
    """
    :param path: A mask.json file full path
    :return:
    """
    Config.MASK_FILE_PATH = path
    if Config.MASKS is None:
        Config.MASKS = getJsonData(path)
    return Config.MASKS

def zipNrrdFiles(name, caseType):
    """
    :param name: patientId | caseId
    :param caseType: "origin" | "registration"
    :return:
    """
    # TODO 1: get all nrrd file paths
    file_paths = selectNrrdPaths(name, "nrrd", caseType)
    valide_path = Config.BASE_PATH / file_paths[0]
    if (valide_path.exists() is False) and (caseType == "registration"):
        file_paths = selectNrrdPaths(name, "nrrd", "origin")
    if caseType == "registration":
        # TODO 2: get mask.json file path
        json_df = Config.METADATA[(Config.METADATA["file type"] == "json") & (Config.METADATA["patient_id"] == name)]
        file_paths.extend(list(json_df["filename"]))
    # TODO 3: add base url to these paths
    file_paths = [Config.BASE_PATH / nrrd_path for nrrd_path in file_paths]
    # TODO 4: zip nrrd and json files
    with ZipFile('nrrd_files.zip', 'w') as zip_file:
        for file_path in file_paths:
            zip_file.write(file_path)
    Config.Current_Case_Name = name

def saveMaskData():
    """
    save mask.json to local drive
    """
    if Config.MASK_FILE_PATH != "":
        with open(Config.MASK_FILE_PATH, "wb") as file:
            # json.dump(MASKS, file)
            file.write(json.dumps(Config.MASKS).encode('utf-8'))
        Config.MASKS = None


def save():
    start_time = time.time()
    if Config.MASKS is not None:
        saveMaskData()
    end_time = time.time()
    run_time = end_time - start_time
    print("save json cost：{:.2f}s".format(run_time))
