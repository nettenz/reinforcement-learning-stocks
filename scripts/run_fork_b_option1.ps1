# Fork B · Option 1 — Simplified RL Runner
# Binary long/flat actions, pure rolling Sharpe reward, all shaping terms zeroed.
# Run this ONLY after Stage 3 Option A returns KILL.

param(
    [string]$Ticker    = "nvda",
    [string]$Seeds     = "7,13,21,42,99",
    [int]   $Timesteps = 30000,
    [string]$EntCoef   = "0.05",
    [string]$LedgerOut = "logs\fork_b_option1_ledger.json"
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$RepoRoot = Split-Path -Parent $PSScriptRoot
$Python   = Join-Path $RepoRoot ".venv\Scripts\python.exe"
$Script   = Join-Path $RepoRoot "scripts\run_fork_b_option1.py"

if (-not (Test-Path $Python)) {
    Write-Error "Python venv not found at $Python"
    exit 1
}

Write-Host ""
Write-Host "=================================================================" -ForegroundColor Cyan
Write-Host "  Fork B · Option 1   Simplified RL" -ForegroundColor Cyan
Write-Host "=================================================================" -ForegroundColor Cyan
Write-Host "  Ticker     : $Ticker"
Write-Host "  Seeds      : $Seeds"
Write-Host "  Timesteps  : $Timesteps"
Write-Host "  Ent coef   : $EntCoef"
Write-Host "  Reward     : pure rolling Sharpe (all shaping = 0)"
Write-Host "  Actions    : binary long/flat only"
Write-Host "=================================================================" -ForegroundColor Cyan
Write-Host ""

$StartTime = Get-Date

& $Python $Script `
    --ticker    $Ticker    `
    --seeds     $Seeds     `
    --timesteps $Timesteps `
    --ent-coef  $EntCoef   `
    --ledger-out $LedgerOut

$ExitCode = $LASTEXITCODE
$Elapsed  = (Get-Date) - $StartTime

Write-Host ""
Write-Host "-----------------------------------------------------------------" -ForegroundColor DarkGray
Write-Host "  Elapsed : $($Elapsed.ToString('mm\:ss'))" -ForegroundColor DarkGray
Write-Host "  Ledger  : $LedgerOut" -ForegroundColor DarkGray

if ($ExitCode -eq 0) {
    Write-Host "  Result  : PASS — proceed to Option 2 (sparse episodic reward)" -ForegroundColor Green
} else {
    Write-Host "  Result  : KILL — feature absence confirmed. Recommend Fork C." -ForegroundColor Red
}
Write-Host "-----------------------------------------------------------------" -ForegroundColor DarkGray
Write-Host ""

exit $ExitCode
