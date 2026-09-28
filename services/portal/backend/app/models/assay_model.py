from pydantic import BaseModel
from typing import Union

class AssayWorkflowDetails(BaseModel):
    uuid: str
    seekId: str
    inputs: list
    outputs: list


class AssayDetails(BaseModel):
    uuid: str
    seekId: str
    workflow: AssayWorkflowDetails
    numberOfParticipants: int
    isAssayReadyToLaunch: bool
