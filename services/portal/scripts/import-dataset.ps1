# One-click measurement dataset import (Windows PowerShell).
#
# The dataset can live anywhere on this PC — give its path:
#   .\scripts\import-dataset.ps1 C:\data\mydataset
#   .\scripts\import-dataset.ps1 C:\data\mydataset.zip --name X
# It copies the dataset into the portal-backend container, then runs the
# importer. Sign in (admin) via your browser when prompted.
param(
  [Parameter(Position = 0)] [string] $Source,
  [Parameter(ValueFromRemainingArguments = $true)] [string[]] $Rest
)
$ErrorActionPreference = "Stop"
Set-Location (Join-Path $PSScriptRoot "..")   # -> clinical-dashboard\

if (-not $Source) { $Source = Read-Host "Dataset folder or .zip (full path)" }
$Source = $Source.TrimEnd('\', '/')
if (-not (Test-Path $Source)) { Write-Host "  X No such path: $Source"; Read-Host "Press Enter to close"; exit 1 }

docker compose version *> $null
if ($LASTEXITCODE -eq 0) { $dc = @("docker", "compose") } else { $dc = @("docker-compose") }
function dc { & $dc[0] $dc[1..($dc.Length - 1)] @args }

$base = Split-Path $Source -Leaf
$stageDir = "/portal_workspace/import-staging"
$stage = "$stageDir/$base"

dc exec -T portal-backend sh -c "rm -rf '$stage'; mkdir -p '$stageDir'"

# Windows has no pv; show the size so the copy isn't a blind wait, then docker cp.
try {
  $sizeMB = [math]::Round(((Get-ChildItem -Recurse -File -ErrorAction SilentlyContinue $Source | Measure-Object Length -Sum).Sum) / 1MB, 1)
  Write-Host "  Copying '$base' ($sizeMB MB) into the container…"
} catch { Write-Host "  Copying '$base' into the container…" }
dc cp $Source "portal-backend:$stage"

dc exec -it portal-backend python -m app.cli.import_measurement $stage @Rest
$code = $LASTEXITCODE

Write-Host ""
Read-Host "Done (exit $code). Press Enter to close"
exit $code
