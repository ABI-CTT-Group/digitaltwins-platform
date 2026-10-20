# terminial-> venv/Scripts/activate.bat
import uvicorn
from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from uvicorn.middleware.proxy_headers import ProxyHeadersMiddleware
from pathlib import Path
from app.router import workflow_tool_plugin, workflow_router
from contextlib import asynccontextmanager
from app.database.database import init_db
from dotenv import load_dotenv
import os
from app.engine.logger import configure_logging, get_logger
from datetime import datetime
from typing import Optional

configure_logging()
logger = get_logger(__name__)


def _reconcile_plugin_state():
    """Sync DB up=True deployments with actual docker container state at startup.
    Handles three cases:
      - running: container survived a previous unclean shutdown → reattach (regenerate nginx)
      - stopped: container exists but stopped → force-remove + mark down
      - gone:    container vanished → mark down
    Nginx is reloaded once at the end if any change happened.
    """
    from app.models.db_model import SessionLocal, PluginDeployment
    from app.engine.deploy_tool import PluginDeployer

    deployer = PluginDeployer()
    nginx_changed = False

    try:
        with SessionLocal() as session:
            deployments = session.query(PluginDeployment).filter(
                PluginDeployment.up == True  # noqa: E712
            ).all()

            if not deployments:
                logger.info("Reconcile: no up=True deployments to check")
                return

            logger.info(f"Reconcile: checking {len(deployments)} up=True deployments")

            for d in deployments:
                if not d.route_prefix:
                    continue
                expose_name = d.route_prefix.replace("/plugin/", "")
                status = deployer.is_project_running(expose_name)

                if status == "running":
                    if d.internal_host and d.internal_port:
                        deployer.generate_nginx_conf(
                            expose_name=expose_name,
                            internal_host=d.internal_host,
                            internal_port=d.internal_port,
                            has_websocket=d.has_websocket or False,
                        )
                        nginx_changed = True
                        logger.info(f"Reconcile: reattached running plugin '{expose_name}'")
                elif status == "stopped":
                    deployer.shutdown_all_plugins([expose_name])
                    deployer.remove_nginx_conf(expose_name)
                    nginx_changed = True
                    d.up = False
                    logger.info(f"Reconcile: cleaned up stopped plugin '{expose_name}'")
                else:
                    deployer.remove_nginx_conf(expose_name)
                    nginx_changed = True
                    d.up = False
                    logger.info(f"Reconcile: marked vanished plugin '{expose_name}' as down")

            session.commit()

        if nginx_changed:
            deployer.reload_nginx()
    except Exception as e:
        logger.error(f"Reconcile failed: {e}")


def _cleanup_orphan_staging(max_age_hours: float = 24):
    """Remove tmp/upload_* directories older than max_age_hours that aren't
    referenced by any Plugin/Workflow record. Called at startup to bound disk usage
    when users upload but never complete the wizard."""
    import time
    from pathlib import Path
    from app.models.db_model import SessionLocal, Plugin, Workflow
    from app.utils.utils import force_rmtree

    tmp_dir = Path("./tmp")
    if not tmp_dir.exists():
        return

    cutoff = time.time() - max_age_hours * 3600

    def _staging_basename(local_path: Optional[str]) -> Optional[str]:
        if not local_path:
            return None
        p = Path(local_path)
        # local_archive_path may be the staging dir itself or an inner project root
        for ancestor in (p, *p.parents):
            if ancestor.name.startswith("upload_"):
                return ancestor.name
        return None

    referenced: set[str] = set()
    try:
        with SessionLocal() as session:
            for row in session.query(Plugin).filter(Plugin.local_archive_path.isnot(None)).all():
                name = _staging_basename(row.local_archive_path)
                if name:
                    referenced.add(name)
            for row in session.query(Workflow).filter(Workflow.local_archive_path.isnot(None)).all():
                name = _staging_basename(row.local_archive_path)
                if name:
                    referenced.add(name)
    except Exception as e:
        logger.warning(f"Orphan-staging cleanup: failed to read DB references: {e}")
        return

    removed = 0
    for entry in tmp_dir.iterdir():
        if not entry.is_dir() or not entry.name.startswith("upload_"):
            continue
        if entry.name in referenced:
            continue
        try:
            if entry.stat().st_mtime < cutoff:
                force_rmtree(entry)
                removed += 1
        except Exception as e:
            logger.warning(f"Failed to clean orphan staging {entry}: {e}")

    if removed:
        logger.info(f"Orphan-staging cleanup: removed {removed} stale upload dir(s)")


def _shutdown_all_plugin_backends():
    """Force-stop all up=True plugin backends in one batch before the builder exits.
    Uses batch `docker rm -f` so multiple containers are killed in parallel by Docker."""
    from app.models.db_model import SessionLocal, PluginDeployment
    from app.engine.deploy_tool import PluginDeployer

    deployer = PluginDeployer()

    try:
        with SessionLocal() as session:
            deployments = session.query(PluginDeployment).filter(
                PluginDeployment.up == True  # noqa: E712
            ).all()

            if not deployments:
                logger.info("Shutdown hook: no up=True plugins to stop")
                return

            expose_names = [
                d.route_prefix.replace("/plugin/", "") for d in deployments
                if d.route_prefix
            ]

            result = deployer.shutdown_all_plugins(expose_names)

            for d in deployments:
                d.up = False
            session.commit()

            logger.info(f"Shutdown hook completed: removed {len(result.get('removed', []))} plugin containers")
    except Exception as e:
        logger.error(f"Shutdown hook failed: {e}")


# When fastapi start will execute this function first
# yield will pause the code, when fastapi stop will execute the remain codes
@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    load_dotenv()
    init_db()
    _reconcile_plugin_state()
    _cleanup_orphan_staging()
    print("starting lifespan")
    yield
    # Shutdown: cascade-stop all plugin backends so they don't outlive the builder
    print("ending lifespan: shutting down plugin backends")
    _shutdown_all_plugin_backends()

app = FastAPI(title="DigitalTWINS Portal API", verison="1.0.0", lifespan=lifespan)
app.add_middleware(ProxyHeadersMiddleware, trusted_hosts="*")
app.include_router(workflow_tool_plugin.router)

app.include_router(workflow_router.router)

# app.add_middleware(
#     CORSMiddleware,
#     allow_origins=["http://localhost", "*"],
#     allow_credentials=True,
#     allow_methods=["*"],
#     allow_headers=["*"],
# )
ALLOWED_ORIGINS = [
    "http://localhost",
]
@app.middleware("http")
async def dynamic_cors(request: Request, call_next):
    origin = request.headers.get("origin")

    _use_ssl = os.environ.get('SSL', 'false') == 'true'
    _domain = os.environ.get('PLATFORM_DOMAIN', 'localhost')
    ALLOWED_ORIGINS.append(f"http{'s' if _use_ssl else ''}://{_domain}")

    if request.method == "OPTIONS":
        response = Response(status_code=200)
    else:
        response = await call_next(request)

    if origin in ALLOWED_ORIGINS:
        response.headers["Access-Control-Allow-Origin"] = origin
        response.headers["Access-Control-Allow-Credentials"] = "true"
        response.headers["Access-Control-Allow-Methods"] = "GET,POST,PUT,DELETE,OPTIONS"
        response.headers["Access-Control-Allow-Headers"] = "Authorization,Content-Type"

    return response

@app.get('/')
async def root():
    return {"message": "DigitalTWINS Portal API", "version": "1.0.0"}


@app.get("/health")
async def health_check():
    return {"status": "healthy", "timestamp": datetime.utcnow()}


if __name__ == '__main__':
    # uvicorn.run(app)
    uvicorn.run(app, port=8000)
