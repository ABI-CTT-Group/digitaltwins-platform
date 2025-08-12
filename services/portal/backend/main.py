# terminial-> venv/Scripts/activate.bat
import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response
from pathlib import Path
import io
from router import tumour_position, dashboard, clinical_report_viewer, tumour_segmentation
from utils import Config

app = FastAPI()

app.include_router(tumour_position.router)
app.include_router(tumour_segmentation.router)
app.include_router(dashboard.router)
app.include_router(clinical_report_viewer.router)

expose_headers = ["x-volume", "x-file-name", "Content-Disposition"]

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=expose_headers
)


# @app.on_event("startup")
# async def startup_event():


@app.get('/')
async def root():
    print(Config.BASE_PATH)
    current_path = Path.cwd()
    print(current_path)

    # Get the directory of the current script
    script_path = Path(__file__).resolve().parent
    print(script_path)
    return "Welcome to segmentation backend"


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
