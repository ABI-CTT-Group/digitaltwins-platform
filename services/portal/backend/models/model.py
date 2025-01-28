from pydantic import BaseModel
from typing import Union


class Masks(BaseModel):
    caseId: str
    masks: object


class Mask(BaseModel):
    caseId: str
    sliceId: int
    label: str
    mask: list


class Sphere(BaseModel):
    caseId: str
    sliceId: int
    origin: list
    spacing: list
    sphereRadiusMM: int
    sphereOriginMM: list


class ReportPosition(BaseModel):
    x: Union[float, int, str]
    y: Union[float, int, str]
    z: Union[float, int, str]


class ReportPoint(BaseModel):
    position: ReportPosition
    distance: str
    start: str
    end: str
    duration: str


class ReportClockFace(BaseModel):
    face: str
    start: str
    end: str
    duration: str


class TumourStudyReport(BaseModel):
    case_name: str
    skin: ReportPoint
    ribcage: ReportPoint
    nipple: ReportPoint
    clock_face: ReportClockFace
    start: str
    end: str
    total_duration: str
    spacing: ReportPosition
    origin: ReportPosition
    complete: bool
    assisted: bool


class TumourPosition(BaseModel):
    case_name: str
    position: ReportPosition
    validate: bool


class TumourAssisted(BaseModel):
    tumour_position: TumourPosition
    tumour_study_report: TumourStudyReport
