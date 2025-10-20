from sqlalchemy.orm import Session
from app.client.minio import get_minio_client
from fastapi import HTTPException
from typing import Tuple, Optional, Union, Type
from app.models.db_model import (
    Plugin, PluginCreate, PluginBuild, PluginResponse,
    PluginBuildResponse, BuildStatus, SessionLocal,
    DeployStatus, PluginDeployment, PluginDeployResponse,
    WorkflowBuild
)
from app.builder.deploy_tool import PluginDeployer
from app.builder.logger import get_logger, configure_logging

configure_logging()
logger = get_logger(__name__)


def get_build_record_or_404(build_id: str, db: Session, Build: Type):
    build_record = db.query(Build).filter(Build.build_id == build_id).first()  # type ignore
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


def get_latest_build_record(plugin_id: str, db: Session) -> Tuple[Plugin, Optional[PluginBuild]]:
    plugin = db.query(Plugin).filter(Plugin.id == plugin_id).first()  # type: ignore

    if plugin is None:
        raise HTTPException(status_code=404, detail=f"Plugin with id {plugin_id} not found")

    latest_build = (
        db.query(PluginBuild)
        .filter(PluginBuild.plugin_id == plugin.id)
        .order_by(PluginBuild.created_at.desc())
        .first()
    )

    return plugin, latest_build


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
