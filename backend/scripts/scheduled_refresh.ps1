# Run from repo root or set BACKEND to backend folder.
$ErrorActionPreference = "Stop"
$backend = if ($env:BACKEND) { $env:BACKEND } else { Join-Path $PSScriptRoot ".." }
Set-Location $backend
if (-not $env:VIRTUAL_ENV -and (Test-Path "..\.venv\Scripts\Activate.ps1")) {
  & "..\.venv\Scripts\Activate.ps1"
}
$env:REFRESH_UNIVERSE_MODE = if ($env:REFRESH_UNIVERSE_MODE) { $env:REFRESH_UNIVERSE_MODE } else { "sp500" }
python scheduled_refresh.py
