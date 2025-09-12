# terminial-> venv/Scripts/activate.bat
import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response
from pathlib import Path
import io
from router import dashboard, clinical_report_viewer
from utils import Config
from contextlib import asynccontextmanager


# When fastapi start will execute this function first
# yield will pause the code, when fastapi stop will execute the remain codes
@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    print("starting lifespan")
    yield
    # Shutdown
    print("ending lifespan")
    pass


app = FastAPI(title="DigitalTWINS Portal API", verison="1.0.0", lifespan=lifespan)
app.include_router(dashboard.router)
app.include_router(clinical_report_viewer.router)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get('/')
async def root():
    print(Config.BASE_PATH)
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


if __name__ == '__main__':
    # uvicorn.run(app)
    uvicorn.run(app, port=8000)
