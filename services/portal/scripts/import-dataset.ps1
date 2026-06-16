# One-click measurement dataset import (Windows PowerShell).
#
#   1) Drop your dataset folder into  clinical-dashboard\measurement-import\
#   2) Right-click this file -> "Run with PowerShell"   (or run it from a terminal)
#   3) Sign in (admin) via your browser when prompted.
#
# Pass a folder name as an argument to skip the picker:
#   .\scripts\import-dataset.ps1 my-dataset
param([Parameter(ValueFromRemainingArguments = $true)] [string[]] $Args)

$ErrorActionPreference = "Stop"
Set-Location (Join-Path $PSScriptRoot "..")   # -> clinical-dashboard\

# Prefer `docker compose` (v2); fall back to docker-compose.
docker compose version *> $null
if ($LASTEXITCODE -eq 0) { $dc = @("docker", "compose") } else { $dc = @("docker-compose") }

& $dc[0] $dc[1..($dc.Length - 1)] exec -it portal-backend python -m app.cli.import_measurement @Args
$code = $LASTEXITCODE

Write-Host ""
Read-Host "Done (exit $code). Press Enter to close"
exit $code
