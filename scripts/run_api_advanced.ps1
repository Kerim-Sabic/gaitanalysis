# Start the Horalix API with the advanced single-runtime (SAM2 + Depth available).
#
#   pwsh scripts/run_api_advanced.ps1            # default port 8010
#   pwsh scripts/run_api_advanced.ps1 -Port 8020
#
# With the pre-analysis setup flow, SAM2/Depth are activated PER REQUEST
# (Advanced Clinical mode), so env flags are no longer required. They are still
# set here so the server defaults match the advanced demo and the existing
# baseline checks (which post no options) see helpers active.
param([int]$Port = 8010)

$ErrorActionPreference = "Stop"
$repo = Split-Path -Parent $PSScriptRoot
Set-Location (Join-Path $repo "apps/api")

$venvPy = Join-Path (Get-Location) ".venv/Scripts/python.exe"
if (-not (Test-Path $venvPy)) {
  Write-Host "No .venv found in apps/api. Create it and install:" -ForegroundColor Yellow
  Write-Host "  python -m venv .venv; .venv\Scripts\activate"
  Write-Host "  pip install -r requirements-real.txt -r requirements-depth.txt -r requirements-sam2.txt"
  exit 1
}

$env:HORALIX_POSE_BACKEND   = "auto_best"
$env:HORALIX_AUTO_BEST_MODE = "fast"
$env:HORALIX_ENABLE_SAM2    = "true"
$env:HORALIX_SEGMENTATION_BACKEND = "sam2"
$env:HORALIX_ENABLE_DEPTH   = "true"
$env:HORALIX_DEPTH_BACKEND  = "depth_anything_v2"

Write-Host "Starting Horalix API (advanced runtime) on http://0.0.0.0:$Port" -ForegroundColor Green
Write-Host "Model cards:  GET /models/capabilities"
Write-Host "Preflight:    POST /analysis/preflight"
& $venvPy -m uvicorn app.main:app --host 0.0.0.0 --port $Port
