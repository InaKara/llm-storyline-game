# scripts/run_backend.ps1
# Starts the FastAPI development server with auto-reload.

$ErrorActionPreference = "Stop"

# Activate venv if not already active
if (-not $env:VIRTUAL_ENV) {
    $venvActivate = Join-Path $PSScriptRoot ".." ".venv" "Scripts" "Activate.ps1"
    if (Test-Path $venvActivate) {
        & $venvActivate
    }
}

# Change to project root (parent of scripts/)
Push-Location (Join-Path $PSScriptRoot "..")
try {
    uvicorn backend.app.main:app --reload --host 0.0.0.0 --port 8000
}
finally {
    Pop-Location
}
