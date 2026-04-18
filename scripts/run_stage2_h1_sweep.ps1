param(
    [string]$PythonExe = ".venv/Scripts/python.exe"
)

$ErrorActionPreference = "Stop"
$ProjectRoot = Split-Path -Parent $PSScriptRoot

Set-Location $ProjectRoot

Write-Host "Running Stage 2 H1 event-driven sweep..." -ForegroundColor Cyan
& $PythonExe "src/stage2_h1_runner.py"
