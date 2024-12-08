@echo off
cls
type logo.txt
echo Starting Tumour Position & Extent Reporting App...
echo.

@echo off
echo Starting VeraCrypt...


if exist I:\ (
    echo I: drive is already mounted.
) else (
    echo Mounting VeraCrypt volume...
    REM start VeraCrypt and mounted volume to I: 
    "C:\Program Files\VeraCrypt\VeraCrypt.exe" /q /v "C:\Users\lgao142\OneDrive - The University of Auckland\Desktop\volume veracrypt\tomour_segmentation.hc" /l I /p Brea$t0_$egmentation

    REM check if VeraCrypt is mounted or not
    if exist I:\ (
        echo VeraCrypt volume mounted successfully.
    ) else (
        echo Failed to mount VeraCrypt volume.
        exit /b 1
    )
)

echo Starting FastAPI...
REM switch to FastAPI backend folder
cd "./backend"

REM run FastAPI backend

call venv\Scripts\activate
start "FastAPI Backend" cmd /c "pip install -r requirements.txt && uvicorn main:app --host 0.0.0.0 --port 8000"
echo FastAPI backend started successfully.

REM delay，make sure FastAPI start
ping 127.0.0.1 -n 5 > nul

echo Starting Vue.js frontend...
REM switch Vite frontend
cd "../frontend"

REM run tumour position report app
start "Tumour Position & Extent Reporting Frontend" cmd /c "yarn && yarn dev"

start "" "chrome.exe" "--start-fullscreen" "http://localhost:3000/"

pause

@REM docker-compose -f docker-compose.yml up