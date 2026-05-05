from pydantic import BaseModel
from typing import Union, List


class AssayWorkflowDetails(BaseModel):
    uuid: str
    seek_id: str
    inputs: list
    outputs: list


class AssayDetails(BaseModel):
    uuid: str
    seek_id: str
    workflow: AssayWorkflowDetails
    number_of_participants: List[int]
    is_assay_ready_to_launch: bool
