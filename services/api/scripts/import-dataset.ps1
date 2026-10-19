# One-click dataset import (Windows PowerShell): measurements, models, tools or
# workflows. Without --category, it asks for the category first.
#
# The dataset can live anywhere on this PC — give its path:
#   .\scripts\import-dataset.ps1 C:\data\mydataset --category measurements
#   .\scripts\import-dataset.ps1 C:\data\mydataset.zip --category measurements --name X --fhir auto
#   .\scripts\import-dataset.ps1 C:\data\mymodel --category models --fhir auto
#   .\scripts\import-dataset.ps1 C:\data\mytool --category tools --tool-type script --seek-project-id 1
# It copies the dataset into the running digitaltwins-api container, then runs
# the importer. Sign in (admin or researcher) via your browser when prompted.
param(
  [Parameter(Position = 0)] [string] $Source,
  [Parameter(ValueFromRemainingArguments = $true)] [string[]] $Rest
)
$ErrorActionPreference = "Stop"

if (-not $Source) { $Source = Read-Host "Dataset folder or .zip (full path)" }
$Source = $Source.TrimEnd('\', '/')
if (-not (Test-Path $Source)) { Write-Host "  X No such path: $Source"; Read-Host "Press Enter to close"; exit 1 }

$cid = (docker ps -q --filter "label=com.docker.compose.service=digitaltwins-api" | Select-Object -First 1)
if (-not $cid) { Write-Host "  X The digitaltwins-api container is not running."; Read-Host "Press Enter to close"; exit 1 }

# --category is required; ask for it (and a tool's or workflow's options) before the copy.
if (-not $Rest) { $Rest = @() }
if (-not ($Rest -match '^--category(=|$)')) {
  $category = Read-Host "Category (measurements, models, tools, workflows)"
  $Rest += @("--category", $category)
  if ($category -in @("tools", "workflows")) {
    $kind = Read-Host "Type (script, notebook, gui)"
    $project = Read-Host "SEEK project ID"
    $Rest += @("--$($category.TrimEnd('s'))-type", $kind, "--seek-project-id", $project)
  }
}

$base = Split-Path $Source -Leaf
$stageDir = "/dataset_staging/import-staging"
$stage = "$stageDir/$base"

docker exec $cid sh -c "rm -rf '$stage'; mkdir -p '$stageDir'"

# Windows has no pv; show the size so the copy isn't a blind wait, then docker cp.
try {
  $sizeMB = [math]::Round(((Get-ChildItem -Recurse -File -ErrorAction SilentlyContinue $Source | Measure-Object Length -Sum).Sum) / 1MB, 1)
  Write-Host "  Copying '$base' ($sizeMB MB) into the container…"
} catch { Write-Host "  Copying '$base' into the container…" }
docker cp $Source "${cid}:$stage"

docker exec -it $cid python -m digitaltwins.cli.import_dataset $stage --move @Rest
$code = $LASTEXITCODE

Write-Host ""
Read-Host "Done (exit $code). Press Enter to close"
exit $code
