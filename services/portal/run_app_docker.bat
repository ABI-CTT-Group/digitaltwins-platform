@echo off
cls
type logo.txt
echo Starting Tumour Position & Extent Reporting App Docker...
echo.

@echo off
echo Starting VeraCrypt...


if exist I:\ (
    echo I: drive is already mounted.
) else (
    echo Mounting VeraCrypt volume...
    REM start VeraCrypt and mounted volume to I: 
    "C:\Program Files\VeraCrypt\VeraCrypt.exe" /q /v "C:\Users\lgao142\Desktop\volume veracrypt\duke_dataset.hc"" /l I /p Brea$t0_$egmentation

    REM check if VeraCrypt is mounted or not
    if exist I:\ (
        echo VeraCrypt volume mounted successfully.
    ) else (
        echo Failed to mount VeraCrypt volume.
        exit /b 1
    )
)

docker-compose -f docker-compose.yml up

pause