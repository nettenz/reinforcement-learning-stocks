# Quick launcher for sanitize_apply.py v0.1.0
# Usage:
#   .\scripts\run_sanitize.ps1 -Action preview     (default, shows what will happen)
#   .\scripts\run_sanitize.ps1 -Action execute     (apply mutations)
#   .\scripts\run_sanitize.ps1 -Action force       (expert mode, skip checks)
#   .\scripts\run_sanitize.ps1 -Action help        (show help)

param(
    [ValidateSet('preview', 'execute', 'force', 'help')]
    [string]$Action = 'preview',
    
    [string]$RootDir = '.',
    [string]$DataDir = 'data',
    [string]$ReportJson = 'reports/sanity_scan_report.json',
    [string]$QuarantineJson = 'reports/sanity_quarantine.json'
)

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$RepoRoot = Split-Path -Parent $ScriptDir

if ($RootDir -eq '.') {
    $RootDir = $RepoRoot
} elseif (-not [System.IO.Path]::IsPathRooted($RootDir)) {
    $RootDir = Join-Path $RepoRoot $RootDir
}

$ScriptPath = Join-Path $RepoRoot 'scripts\sanitize_apply.py'

Set-Location $RootDir

# Verify script exists
if (-not (Test-Path $ScriptPath)) {
    Write-Host "[ERROR] Script not found: $ScriptPath" -ForegroundColor Red
    exit 1
}

# Verify Python
try {
    $pythonVersion = python --version 2>&1
    Write-Host "[INFO] Using: $pythonVersion" -ForegroundColor Green
} catch {
    Write-Host "[ERROR] Python not found or not in PATH" -ForegroundColor Red
    exit 1
}

# Build command
$baseCmd = @(
    $ScriptPath,
    '--root-dir', $RootDir,
    '--data-dir', $DataDir,
    '--report-json', $ReportJson,
    '--quarantine-json', $QuarantineJson
)

switch ($Action) {
    'preview' {
        Write-Host "[INFO] Preview mode (dry-run)" -ForegroundColor Cyan
        Write-Host "[INFO] No mutations will be applied" -ForegroundColor Cyan
        $cmd = $baseCmd + @('--dry-run')
    }
    'execute' {
        Write-Host "[INFO] Execute mode" -ForegroundColor Yellow
        Write-Host "[WARN] This will apply mutations!" -ForegroundColor Yellow
        $cmd = $baseCmd + @('--execute')
    }
    'force' {
        Write-Host "[ERROR] Force mode - dangerous!" -ForegroundColor Red
        Write-Host "[WARN] This will skip idempotency checks!" -ForegroundColor Yellow
        $cmd = $baseCmd + @('--execute', '--force')
    }
    'help' {
        Write-Host "Usage: .\scripts\run_sanitize.ps1 -Action <action> [-RootDir <dir>] [-DataDir <dir>]"
        Write-Host ""
        Write-Host "Actions:"
        Write-Host "  preview   - Show what will happen (default, no mutations)"
        Write-Host "  execute   - Apply mutations"
        Write-Host "  force     - Force apply (skip idempotency checks, expert mode)"
        Write-Host "  help      - Show this help"
        Write-Host ""
        Write-Host "Examples:"
        Write-Host "  .\scripts\run_sanitize.ps1                           # Preview mutations"
        Write-Host "  .\scripts\run_sanitize.ps1 -Action execute           # Apply mutations"
        Write-Host "  .\scripts\run_sanitize.ps1 -Action preview -RootDir . # Custom root"
        exit 0
    }
}

# Run command
Write-Host ""
Write-Host "Running: python $($cmd -join ' ')" -ForegroundColor Cyan
Write-Host ""

& python @cmd
$exitCode = $LASTEXITCODE

if ($exitCode -eq 0) {
    Write-Host ""
    Write-Host "[SUCCESS] Command completed successfully" -ForegroundColor Green
} else {
    Write-Host ""
    Write-Host "[ERROR] Command failed with exit code: $exitCode" -ForegroundColor Red
}

exit $exitCode
