"""
Model Router.

Model datasets live in Postgres + MinIO only (no SEEK); they are uploaded via
/datasets/uploads or POST /datasets with ``category=models``.
"""
from fastapi import APIRouter, Depends

from digitaltwins import Querier, models
from .dependencies import get_querier

router = APIRouter()


@router.get("/models", tags=["models"])
def get_models(querier: Querier = Depends(get_querier)):
    """
    Retrieve the registered model datasets.

    Args:
        querier (Querier): Per-request querier authenticated as the calling user.

    Returns:
        dict: The model datasets (as in ``GET /datasets``) under the 'models' key.
    """
    return {"models": querier.get_datasets(categories=[models.CATEGORY])}
