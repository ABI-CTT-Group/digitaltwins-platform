"""
Workflow Router.
"""
from fastapi import APIRouter, Depends, HTTPException, status

from digitaltwins import Querier
from digitaltwins.workflows import deploy
from .auth import require_admin_role
from .dataset_uploads import get_conn
from .dependencies import get_querier


router = APIRouter()


@router.get("/workflows", tags=["workflows"])
def get_workflows(querier: Querier = Depends(get_querier)):
    """
    Retrieve a list of workflows.

    Args:
        querier (Querier): Per-request querier authenticated as the calling user.

    Returns:
        dict: A dictionary containing the list of workflows under the 'workflows' key.
    """
    workflows = querier.get_workflows()
    return {"workflows": workflows}


@router.get("/workflows/{workflow_id}", tags=["workflows"])
def get_workflow(workflow_id: int, querier: Querier = Depends(get_querier)):
    """
    Retrieve a specific workflow by its ID.

    Args:
        workflow_id (int): The ID of the workflow to retrieve.
        querier (Querier): Per-request querier authenticated as the calling user.

    Returns:
        dict: A dictionary containing the workflow details under the 'workflow' key.
    """
    workflow = querier.get_workflow(workflow_id)
    return {"workflow": workflow}


@router.post("/workflows/{dataset_uuid}/deploy", tags=["workflows"])
def deploy_workflow_dag(dataset_uuid: str, conn=Depends(get_conn), _admin: dict = Depends(require_admin_role)):
    """Deploy a registered script workflow's Airflow DAG (admin only).

    The DAG in the workflow's ``code/`` must name itself after its folder
    (``dag_id=Path(__file__).parent.name``); it is deployed as
    ``workflow_<seek_id>``, the DAG an assay run triggers, then unpaused once
    Airflow has loaded it. Blocks until Airflow loads the DAG, reports an import
    error, or ``AIRFLOW_DAG_DEPLOY_TIMEOUT`` passes. Deploying again replaces it.

    Returns:
        ``{dataset_uuid, dag_id, dag_status, dag_error}``; ``dag_status`` is
        ``deployed``, or ``failed`` with the reason (e.g. Airflow's stack trace).

    Raises:
        HTTPException 404: No workflow dataset with this UUID.
        HTTPException 409: Not a script workflow.
        HTTPException 422: The DAG fails the static check (stored as ``failed``).
        HTTPException 503: Deploying is not configured, or MinIO / Airflow is unreachable.
    """
    try:
        return deploy.deploy_workflow(conn, dataset_uuid)
    except LookupError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except deploy.NotScriptWorkflow as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    except deploy.DeployUnavailable as exc:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc
