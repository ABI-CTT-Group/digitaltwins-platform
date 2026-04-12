from pydantic import BaseModel
from typing import Union, List

class AssayWorkflowDetails(BaseModel):
    uuid: str
    seekId: str
    inputs: list
    outputs: list


class AssayDetails(BaseModel):
    uuid: str
    seekId: str
    workflow: AssayWorkflowDetails
    numberOfParticipants: List[int]
    isAssayReadyToLaunch: bool
