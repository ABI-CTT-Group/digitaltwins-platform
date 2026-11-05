import threading
import uuid
import yaml
from datetime import datetime
from pathlib import Path
from sqlalchemy.orm import Session
from fastapi import HTTPException
from typing import Tuple, Optional, Union, Type
from app.models.db_model import (
    Plugin, Workflow, PluginBuild, BuildStatus, SessionLocal,
    DeployStatus, PluginDeployment, WorkflowBuild
)
from app.engine.deploy_tool import PluginDeployer
from app.engine.logger import get_logger, configure_logging
from app.engine.log_stream import log_registry, bind_thread_job, unbind_thread_job

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


def parse_docker_compose_routing(backend_dir: Path, expose_name: str = "") -> dict:
    """Extract container_name and internal port from docker-compose.yml for nginx routing."""
    for fname in ("docker-compose.yml", "docker-compose.yaml"):
        compose_path = backend_dir / fname
        if compose_path.exists():
            break
    else:
        return {}

    try:
        with open(compose_path, "r", encoding="utf-8") as f:
            compose = yaml.safe_load(f)
        services = compose.get("services", {})
        if not services:
            return {}
        # Use the first service
        service_name, service_conf = next(iter(services.items()))
        # Try explicit container_name, otherwise use project-based name
        container_name = service_conf.get("container_name")
        if not container_name:
            # With -p flag: <expose_name>-<service>-1, fallback to directory name
            project = expose_name if expose_name else backend_dir.name
            container_name = f"{project}-{service_name}-1"
        # Extract internal port from ports mapping (e.g. "8002:8082" → "8082")
        internal_port = "8082"  # default
        ports = service_conf.get("ports", [])
        if ports:
            port_str = str(ports[0])
            if ":" in port_str:
                internal_port = port_str.split(":")[-1]
            else:
                internal_port = port_str
        # Check if websocket is likely (default True for plugins with backend)
        has_websocket = True
        return {
            "internal_host": container_name,
            "internal_port": internal_port,
            "has_websocket": has_websocket,
        }
    except Exception as e:
        logger.error(f"Failed to parse docker-compose for routing: {e}")
        return {}


def run_deployment(deployer: PluginDeployer, deploy_id: str, deploy_dict: dict) -> None:
    """Run a deployment row's backend (docker compose) and route /plugin/<expose> to it: a tool's or a gui workflow's.

    ``deploy_dict`` holds ``expose_name``, ``dataset_path`` and ``backend_folder`` (PluginDeployer.deploy).
    """
    job_key = f"deploy:{deploy_id}"
    try:
        with SessionLocal() as session:
            deploy_record = session.query(PluginDeployment).filter(
                PluginDeployment.deploy_id == deploy_id).first()  # type: ignore
            if deploy_record:
                deploy_record.status = DeployStatus.DEPLOYING.value
                session.commit()
        log_registry.open(job_key)
        # Bind this thread so every deploy log record (compose up output AND
        # the surrounding orchestration steps) streams into the console.
        bind_thread_job(job_key)
        logger.info("Starting plugin deployment...")
        try:
            result = deployer.deploy(deploy_dict)
        finally:
            unbind_thread_job()
        with SessionLocal() as session:
            deploy_record = session.query(PluginDeployment).filter(PluginDeployment.deploy_id == deploy_id).first()
            if deploy_record:
                if result["success"]:
                    log_registry.finish(job_key, "completed")
                    deploy_record.status = DeployStatus.COMPLETED.value
                    deploy_record.source_path = result["backend_dir"]
                    deploy_record.up = True

                    # Generate nginx config for this plugin
                    expose_name = deploy_dict["expose_name"]
                    backend_dir = Path(result["backend_dir"])
                    routing = parse_docker_compose_routing(backend_dir, expose_name)
                    if routing and expose_name:
                        route_prefix = f"/plugin/{expose_name}"
                        deploy_record.route_prefix = route_prefix
                        deploy_record.internal_host = routing["internal_host"]
                        deploy_record.internal_port = routing["internal_port"]
                        deploy_record.has_websocket = routing.get("has_websocket", True)
                        deployer.generate_nginx_conf(
                            expose_name=expose_name,
                            internal_host=routing["internal_host"],
                            internal_port=routing["internal_port"],
                            has_websocket=routing.get("has_websocket", True),
                        )
                        deployer.reload_nginx()
                        logger.info(f"Nginx config generated for plugin {expose_name}")
                else:
                    log_registry.finish(job_key, "failed")
                    deploy_record.status = BuildStatus.FAILED.value
                    deploy_record.error = result["error_message"]

                deploy_record.updated_at = datetime.now()
                session.commit()
    except Exception as e:
        log_registry.finish(job_key, "failed")
        logger.error(f"Deploy failed: {e}")
        with SessionLocal() as session:
            deploy_record = session.query(PluginDeployment).filter(PluginDeployment.deploy_id == deploy_id).first()
            if deploy_record:
                deploy_record.status = DeployStatus.FAILED.value
                deploy_record.error = str(e)
                deploy_record.updated_at = datetime.now()
                session.commit()


def _shut_down(deploys, deployer: PluginDeployer) -> None:
    for deployment in deploys:
        logger.info("Start to shuttle down the deployment {}".format(deployment.id))
        expose_name = deployment.route_prefix.replace("/plugin/", "") if deployment.route_prefix else ""
        deploy_dict = {
            "backend_dir": deployment.source_path,
            "expose_name": expose_name,
        }
        logger.info("the deployment is {}".format(deploy_dict))
        deployer.delete(deploy_dict)


def shuttle_down_deployed_backend(plugin_id: str, deployer: PluginDeployer):
    try:
        with SessionLocal() as session:
            _shut_down(session.query(PluginDeployment).filter(PluginDeployment.plugin_id == plugin_id).all(), deployer)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


def shut_down_workflow_backends(workflow_id: str, deployer: PluginDeployer):
    """Stop every backend deployed from a gui workflow's builds (before a rebuild or a delete)."""
    try:
        with SessionLocal() as session:
            deploys = (session.query(PluginDeployment)
                       .join(WorkflowBuild, PluginDeployment.workflow_build_id == WorkflowBuild.build_id)
                       .filter(WorkflowBuild.workflow_id == workflow_id).all())
            _shut_down(deploys, deployer)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


def served_workflow_build(db: Session, workflow: Workflow) -> Optional[WorkflowBuild]:
    """The build whose gui tool the Tool Hub launches and deploys: the approved one, else the latest with a bundle."""
    builds = (db.query(WorkflowBuild)
              .filter(WorkflowBuild.workflow_id == workflow.id,
                      WorkflowBuild.status == BuildStatus.COMPLETED.value,
                      WorkflowBuild.tool_name.isnot(None))
              .order_by(WorkflowBuild.created_at.desc())
              .all())
    approved = next((b for b in builds if workflow.uuid and b.dataset_uuid == workflow.uuid), None)
    return approved or (builds[0] if builds else None)


def workflow_bundle_path(build: WorkflowBuild) -> Optional[str]:
    """Where the launcher loads a gui workflow's bundle: its platform tool dataset once approved, else tool-builds."""
    ts = int(build.created_at.timestamp()) if build.created_at else 0
    if build.tool_dataset_uuid:
        return f"/tools/{build.tool_dataset_uuid}/primary/my-app.umd.js?v={ts}"
    if build.bundle_path:
        return f"/{build.bundle_path}/my-app.umd.js?v={ts}"
    return None


def latest_deployment(db: Session, build: WorkflowBuild) -> Optional[PluginDeployment]:
    return (db.query(PluginDeployment)
            .filter(PluginDeployment.workflow_build_id == build.build_id)
            .order_by(PluginDeployment.created_at.desc())
            .first())


# ── Starting a GUI tool's backend on launch (docs/decisions/2026-11-05-start-gui-backends-on-launch.md) ──

# Starts and deploys under way in this process, by expose name: "starting" | "deploying".
# The builder runs as one uvicorn process, so a lock and a dict are enough.
backend_jobs: dict = {}
_backend_lock = threading.Lock()


def spawn(fn, *args) -> None:
    threading.Thread(target=fn, args=args, daemon=True).start()


def _backend_target(db: Session, expose_name: str):
    """The build behind /plugin/<expose_name>: (owner, build, deployment filter, deployment fields).

    404 when no completed build has that expose name; owner None when its tool has no backend.
    """
    build = (db.query(PluginBuild)
             .filter(PluginBuild.expose_name == expose_name, PluginBuild.status == BuildStatus.COMPLETED.value)
             .first())
    if build is not None:
        plugin = build.plugin
        owner = plugin if plugin.label == "GUI" and plugin.has_backend else None
        return owner, build, PluginDeployment.build_id == build.build_id, {"plugin_id": plugin.id, "build_id": build.build_id}
    build = (db.query(WorkflowBuild)
             .filter(WorkflowBuild.expose_name == expose_name, WorkflowBuild.status == BuildStatus.COMPLETED.value)
             .first())
    if build is None:
        raise HTTPException(status_code=404, detail="No built tool has this expose name")
    workflow = db.query(Workflow).filter(Workflow.id == build.workflow_id).first()
    owner = workflow if workflow is not None and workflow.has_backend else None
    return owner, build, PluginDeployment.workflow_build_id == build.build_id, {"workflow_build_id": build.build_id}


def start_deployment(deployer: PluginDeployer, record: PluginDeployment) -> dict:
    """Run a completed deployment's containers again and route /plugin/<expose> to them; the caller commits."""
    expose_name = record.route_prefix.replace("/plugin/", "") if record.route_prefix else ""
    result = deployer.compose_up({"backend_dir": record.source_path, "expose_name": expose_name})
    if result["success"]:
        record.up = True
        if record.route_prefix and record.internal_host:
            deployer.generate_nginx_conf(
                expose_name=expose_name,
                internal_host=record.internal_host,
                internal_port=record.internal_port or "8082",
                has_websocket=record.has_websocket or False,
            )
            deployer.reload_nginx()
    return result


def _start_job(deployer: PluginDeployer, expose_name: str, deploy_id: str) -> None:
    try:
        with SessionLocal() as session:
            record = session.query(PluginDeployment).filter(PluginDeployment.deploy_id == deploy_id).one()
            result = start_deployment(deployer, record)
            if not result["success"]:
                # The next launch redeploys it.
                record.status = DeployStatus.FAILED.value
                record.error = result.get("message")
            record.updated_at = datetime.now()
            session.commit()
    finally:
        backend_jobs.pop(expose_name, None)


def _deploy_job(deployer: PluginDeployer, expose_name: str, deploy_id: str, deploy_dict: dict) -> None:
    try:
        run_deployment(deployer, deploy_id, deploy_dict)
    finally:
        backend_jobs.pop(expose_name, None)


def backend_state(expose_name: str) -> dict:
    """What /tool-view waits on: none | stopped | starting | deploying | running | failed."""
    with SessionLocal() as db:
        owner, _, row_filter, _ = _backend_target(db, expose_name)
        if owner is None:
            return {"state": "none", "error": None, "deploy_id": None}
        row = db.query(PluginDeployment).filter(row_filter).first()
        deploy_id = row.deploy_id if row else None
        if expose_name in backend_jobs:
            return {"state": backend_jobs[expose_name], "error": None, "deploy_id": deploy_id}
        if row is None:
            return {"state": "stopped", "error": None, "deploy_id": None}
        if row.status == DeployStatus.FAILED.value:
            return {"state": "failed", "error": row.error, "deploy_id": deploy_id}
        state = "running" if row.status == DeployStatus.COMPLETED.value and row.up else "stopped"
        return {"state": state, "error": None, "deploy_id": deploy_id}


def start_backend(deployer: PluginDeployer, expose_name: str) -> dict:
    """Make sure the backend behind /plugin/<expose_name> runs: start its deployment, else deploy the build."""
    with _backend_lock:
        if expose_name not in backend_jobs:
            with SessionLocal() as db:
                owner, build, row_filter, fields = _backend_target(db, expose_name)
                if owner is None:
                    return {"state": "none", "error": None, "deploy_id": None}
                row = db.query(PluginDeployment).filter(row_filter).first()
                if row is not None and row.status == DeployStatus.COMPLETED.value:
                    if not (row.up and deployer.is_project_running(expose_name) == "running"):
                        backend_jobs[expose_name] = "starting"
                        spawn(_start_job, deployer, expose_name, row.deploy_id)
                else:
                    # Never deployed, failed, or cut short by a restart: deploy it, reusing its row.
                    if row is None:
                        row = PluginDeployment(deploy_id=str(uuid.uuid4()), **fields)
                        db.add(row)
                    row.status, row.error, row.up = DeployStatus.PENDING.value, None, False
                    row.updated_at = datetime.now()
                    db.commit()
                    deploy_dict = {"expose_name": build.expose_name, "dataset_path": build.dataset_path,
                                   "backend_folder": owner.backend_folder}
                    logger.info("Deploying the backend of %s on launch", expose_name)
                    backend_jobs[expose_name] = "deploying"
                    spawn(_deploy_job, deployer, expose_name, row.deploy_id, deploy_dict)
    return backend_state(expose_name)

