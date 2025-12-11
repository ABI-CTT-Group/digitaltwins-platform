# terminial-> venv/Scripts/activate.bat
import uvicorn
from fastapi import FastAPI, HTTPException, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from pathlib import Path
import io
from app.router import dashboard, clinical_report_viewer, workflow_tool_plugin, workflow_router
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

configure_logging()
logger = get_logger(__name__)


# When fastapi start will execute this function first
# yield will pause the code, when fastapi stop will execute the remain codes
@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    load_dotenv()
    init_db()
    print("starting lifespan")
    yield
    # Shutdown
    print("ending lifespan")
    pass

app = FastAPI(title="DigitalTWINS Portal API", verison="1.0.0", lifespan=lifespan)
app.include_router(dashboard.router)
app.include_router(clinical_report_viewer.router)
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

    _use_ssl = os.environ.get('USE_SSL', 'false') == 'true'
    _domain = os.environ.get('PORTAL_BACKEND_HOST_IP', 'localhost')
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
    current_path = Path.cwd()
    # Get the directory of the current script
    script_path = Path(__file__).resolve().parent
    print(script_path)
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


if __name__ == '__main__':
    # uvicorn.run(app)
    uvicorn.run(app, port=8000)
