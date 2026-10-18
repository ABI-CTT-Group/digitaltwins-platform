@echo off
REM Double-click launcher for the dataset importer (Windows). It asks for the
REM dataset path and its category (measurements, models, tools or workflows).
REM
REM Double-clicking a .ps1 only opens it in an editor, so use THIS .bat instead.
REM It runs the PowerShell wrapper with ExecutionPolicy Bypass (no system policy
REM change needed) and prompts for the dataset path and category.
REM
REM You can also drag a dataset folder/zip onto this .bat to pass its path.
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0import-dataset.ps1" %*
