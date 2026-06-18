# terminial-> venv/Scripts/activate.bat
import uvicorn
from fastapi import FastAPI, HTTPException, Request, Response, Depends
from fastapi.middleware.cors import CORSMiddleware
from uvicorn.middleware.proxy_headers import ProxyHeadersMiddleware
from pathlib import Path
import io
from app.router import dashboard, clinical_report_viewer, workflow_tool_plugin, workflow_router, measurement_router
from contextlib import asynccontextmanager
from app.database.database import init_db
from dotenv import load_dotenv
import os
from app.builder.logger import configure_logging, get_logger
from datetime import datetime
from app.models.dashboard import LoginRequest, DashBoardSignInResponse
from app.client.digitaltwins_api import DigitalTWINSAPIClient
from typing import Optional
from httpx import HTTPStatusError
from app.utils.auth import get_current_user

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
    from app.builder.deploy_tool import PluginDeployer

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

    # Measurement chunked uploads: tmp/upload_<measurement_id>/ is the live chunk
    # store for a pending_upload row (no local_archive_path until finalize, so the
    # Plugin/Workflow pass above can't see it). Protect fresh ones from the generic
    # sweep; reap abandoned ones (dir + row) so a closed-tab upload can't pin disk.
    from datetime import datetime, timedelta
    from app.models.db_model import Measurement, MeasurementStatus

    row_cutoff = datetime.utcnow() - timedelta(hours=max_age_hours)
    try:
        with SessionLocal() as session:
            pending = session.query(Measurement).filter(
                Measurement.status == MeasurementStatus.PENDING_UPLOAD.value
            ).all()
            for row in pending:
                updir = tmp_dir / f"upload_{row.id}"
                last_active = (
                    datetime.utcfromtimestamp(updir.stat().st_mtime)
                    if updir.exists() else None
                )
                abandoned = (
                    (last_active is not None and last_active < row_cutoff)
                    or (last_active is None and bool(row.created_at) and row.created_at < row_cutoff)
                )
                if abandoned:
                    if updir.exists():
                        force_rmtree(updir)
                    session.delete(row)
                else:
                    referenced.add(updir.name)
            session.commit()
    except Exception as e:
        logger.warning(f"Orphan-staging cleanup: measurement pass failed: {e}")

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
    """Force-stop all up=True plugin backends in one batch before portal-backend exits.
    Uses batch `docker rm -f` so multiple containers are killed in parallel by Docker."""
    from app.models.db_model import SessionLocal, PluginDeployment
    from app.builder.deploy_tool import PluginDeployer

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
    # Shutdown: cascade-stop all plugin backends so they don't outlive portal-backend
    print("ending lifespan: shutting down plugin backends")
    _shutdown_all_plugin_backends()

app = FastAPI(title="DigitalTWINS Portal API", verison="1.0.0", lifespan=lifespan)
app.add_middleware(ProxyHeadersMiddleware, trusted_hosts="*")
app.include_router(dashboard.router)
app.include_router(clinical_report_viewer.router)
app.include_router(workflow_tool_plugin.router)

app.include_router(workflow_router.router)
app.include_router(measurement_router.router)

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

    _use_ssl = os.environ.get('USE_SSL', 'false') == 'true'
    _domain = os.environ.get('PORTAL_BACKEND_HOST', 'localhost')
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


@app.get("/api/test")
async def test():
    blob_content = b"This is the content of the blob."
    blob_stream = io.BytesIO(blob_content)

    # Create the response
    response = Response(content=blob_stream.getvalue())

    # Set the headers to indicate the file type and disposition
    response.headers["Content-Type"] = "application/octet-stream"
    response.headers["Content-Disposition"] = "attachment; filename=blob_file.txt"

    # Add the string data to the response headers
    response.headers["x-file-name"] = "This is a custom string."

    return response


@app.get("/health")
async def health_check():
    return {"status": "healthy", "timestamp": datetime.utcnow()}


@app.post("/api/login", response_model=DashBoardSignInResponse)
async def sign_in(data: LoginRequest, response: Response):
    username = data.username
    password = data.password
    dtp_client = DigitalTWINSAPIClient(username=username, password=password)
    try:
        res = await dtp_client.post("/login")
        tokens = res.json()
        response.set_cookie(
            key="refresh_token",
            value=tokens.get("refresh_token"),
            httponly=True,
            secure=True,
            samesite="strict",
            max_age=tokens.get("refresh_expires_in", 1800),
        )

        return {"access_token": tokens.get("access_token")}
    except Exception as e:
        logger.error(e)
        raise HTTPException(status_code=401, detail=str(e))


@app.post("/api/refresh")
async def refresh(request: Request, response: Response):
    refresh_token: Optional[str] = request.cookies.get("refresh_token")
    if not refresh_token:
        raise HTTPException(status_code=401, detail="Refresh token missing")
    dtp_client = DigitalTWINSAPIClient(token=refresh_token)
    try:
        res = await dtp_client.post("/token")
        tokens = res.json()
        response.set_cookie(
            key="refresh_token",
            value=tokens.get("refresh_token"),
            httponly=True,
            secure=True,
            samesite="strict",
            max_age=tokens.get("refresh_expires_in", 1800),
        )

        return {"access_token": tokens.get("access_token")}
    except HTTPStatusError as e:
        if e.response.status_code == 401:
            raise HTTPException(status_code=401, detail="Refresh token invalid")
        else:
            logger.error(e)
            raise HTTPException(status_code=502, detail="Upstream service error")
    except Exception as e:
        logger.error(e)
        raise HTTPException(status_code=500, detail="Internal server error")


@app.post("/api/auth/test")
async def auth_test(request: Request, user_info=Depends(get_current_user)):
    authorization = request.headers.get("authorization", "")
    _, _, token = authorization.partition(" ")
    return {
        "authenticated": True,
        "access_token": token,
        "user": user_info,
    }


@app.get("/api/auth/keycloak-status")
async def keycloak_status():
    """Check Keycloak server connectivity and configuration"""
    from app.client.keycloak import get_keycloak_client
    import requests
    
    try:
        keycloak_client = get_keycloak_client()
        server_url = keycloak_client.server_url.rstrip('/')
        realm = keycloak_client.realm_name
        
        # Try to fetch the public key to test connectivity
        try:
            public_key = keycloak_client.get_public_key()
            return {
                "status": "connected",
                "server_url": server_url,
                "realm": realm,
                "client_id": keycloak_client.client_id,
                "message": "Keycloak server is reachable and configured correctly"
            }
        except Exception as e:
            # Try a simple HTTP request to test basic connectivity
            try:
                certs_url = f"{server_url}/realms/{realm}/.well-known/openid-configuration"
                resp = requests.get(certs_url, verify=False, timeout=5)
                return {
                    "status": "connection_error",
                    "server_url": server_url,
                    "realm": realm,
                    "client_id": keycloak_client.client_id,
                    "error": str(e),
                    "http_status": resp.status_code if resp else "no_response",
                    "message": "Server responds but key fetch failed"
                }
            except Exception as e2:
                return {
                    "status": "unreachable",
                    "server_url": server_url,
                    "realm": realm,
                    "client_id": keycloak_client.client_id,
                    "error": str(e2),
                    "message": "Cannot reach Keycloak server - check URL and network"
                }
    except Exception as e:
        return {
            "status": "error",
            "error": str(e),
            "message": "Failed to initialize Keycloak client"
        }


@app.post("/api/auth/login-keycloak")
async def login_test(data: LoginRequest, response: Response):
    """Login endpoint that authenticates with Keycloak and returns real JWT token"""
    from app.client.keycloak import get_keycloak_client
    
    username = data.username
    password = data.password
    
    try:
        keycloak_client = get_keycloak_client()
        # Authenticate with Keycloak using username and password
        token_response = keycloak_client.authenticate_with_credentials(username, password)
        
        # Set refresh token in HTTP-only cookie
        refresh_token = token_response.get("refresh_token")
        if refresh_token:
            response.set_cookie(
                key="refresh_token",
                value=refresh_token,
                httponly=True,
                secure=True,
                samesite="strict",
                max_age=token_response.get("refresh_expires_in", 1800),
            )
        
        logger.info(f"Keycloak login successful for user: {username}")
        return {"access_token": token_response.get("access_token")}
    
    except Exception as e:
        logger.error(f"Keycloak login failed for user {username}: {e}")
        raise HTTPException(status_code=401, detail=f"Authentication failed: {str(e)}")


if __name__ == '__main__':
    # uvicorn.run(app)
    uvicorn.run(app, port=8000)
