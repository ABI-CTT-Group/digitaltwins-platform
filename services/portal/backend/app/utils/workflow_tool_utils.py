from sqlalchemy.orm import Session
from app.client.minio import get_minio_client
from fastapi import HTTPException
from typing import Tuple, Optional, Union, Type
from app.models.db_model import (
    Plugin, Workflow, PluginCreate, PluginBuild, PluginResponse,
    PluginBuildResponse, BuildStatus, SessionLocal,
    DeployStatus, PluginDeployment, PluginDeployResponse,
    WorkflowBuild
)
from app.builder.deploy_tool import PluginDeployer
from app.builder.logger import get_logger, configure_logging

configure_logging()
logger = get_logger(__name__)


def get_build_record_or_404(build_id: str, db: Session, Build: Type[Union[PluginBuild, WorkflowBuild]]):
    build_record = db.query(Build).filter(Build.build_id == build_id).first()  # type: ignore
    if build_record is None:
        raise HTTPException(status_code=404, detail="Build not found")

    if not build_record.s3_path:
        raise HTTPException(status_code=404, detail="No artifacts available for this build")

    if build_record.status != BuildStatus.COMPLETED.value:
        raise HTTPException(status_code=400, detail="Build is not completed")

    return build_record


def get_object_key_from_s3_path(s3_path: str) -> str:
    if not s3_path.startswith("s3://"):
        raise HTTPException(status_code=500, detail="Invalid S3 path format")
    return s3_path.replace("s3://", "").split("/", 1)[1]


def get_public_url_for_build(build_record: Union[PluginBuild, WorkflowBuild], client_name: str) -> tuple[str, str]:
    s3_path = build_record.s3_path
    object_key = get_object_key_from_s3_path(s3_path)
    minio_client = get_minio_client(client_name)
    url = minio_client.get_public_url(object_key)
    return url, s3_path


# def get_latest_build_record(id: str, category: str, db: Session) -> Tuple[Union[Plugin, Workflow], Optional[PluginBuild]]:
#     if category == "workflow":
#         model = db.query(Workflow).filter(Workflow.id == id).first()  # type: ignore
#     else:
#         model = db.query(Plugin).filter(Plugin.id == id).first()  # type: ignore
#
#     if model is None:
#         raise HTTPException(status_code=404, detail=f"Plugin / Workflow with id {id} not found")
#
#     if category == "workflow":
#         latest_build = (
#             db.query(WorkflowBuild)
#             .filter(WorkflowBuild.workflow_id == model.id)
#             .order_by(WorkflowBuild.created_at.desc())
#             .first()
#         )
#     else:
#         latest_build = (
#             db.query(PluginBuild)
#             .filter(PluginBuild.plugin_id == model.id)
#             .order_by(PluginBuild.created_at.desc())
#             .first()
#         )
#
#     return model, latest_build

def get_latest_build_record(
        id: str,
        category: str,
        db: Session
) -> Tuple[Union["Plugin", "Workflow"], Optional[Union["PluginBuild", "WorkflowBuild"]]]:
    """Return the model (Plugin/Workflow) and its latest build record."""

    model_map = {
        "workflow": (Workflow, WorkflowBuild, WorkflowBuild.workflow_id),
        "plugin": (Plugin, PluginBuild, PluginBuild.plugin_id),
    }

    if category not in model_map:
        raise HTTPException(status_code=400, detail=f"Invalid category: {category}")

    model_cls, build_cls, build_fk = model_map[category]

    model = db.query(model_cls).filter(model_cls.id == id).first()
    if model is None:
        raise HTTPException(status_code=404, detail=f"{category.capitalize()} with id {id} not found")

    latest_build = (
        db.query(build_cls)
        .filter(build_fk == model.id)
        .order_by(build_cls.created_at.desc())
        .first()
    )

    return model, latest_build


def shuttle_down_deployed_backend(plugin_id: str, deployer: PluginDeployer):
    try:
        with SessionLocal() as session:
            deploys = session.query(PluginDeployment).filter(PluginDeployment.plugin_id == plugin_id).all()
            for deployment in deploys:
                logger.info("Start to shuttle down the deployment {}".format(deployment.id))
                deploy_dict = {
                    "backend_dir": deployment.source_path
                }
                logger.info("the deployment is {}".format(deploy_dict))
                deployer.delete(deploy_dict)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
