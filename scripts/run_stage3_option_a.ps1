# Stage 3 · Option A — Directional Classification Runner
# Activates the project venv and runs run_stage2_h2_directional.py
# with the gate-contract defaults defined in PROJECT_STATE_2026_04_29.md

param(
    [int]   $TargetHorizon       = 3,
    [double]$DirectionThreshold  = 0.005,
    [double]$TradeProbThreshold  = 0.60,
    [string[]]$Models            = @("logistic", "xgboost"),
    [int]   $Seed                = 42,
    [string]$OutputDir           = "results/stage3_h2_directional",
    [string]$LedgerOut           = "logs/stage3_h2_directional_ledger.json"
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$RepoRoot  = Split-Path -Parent $PSScriptRoot
$Python    = Join-Path $RepoRoot ".venv\Scripts\python.exe"
$Script    = Join-Path $RepoRoot "scripts\run_stage2_h2_directional.py"

# ── Sanity checks ────────────────────────────────────────────────────────────
if (-not (Test-Path $Python)) {
    Write-Error "Python venv not found at $Python — run: python -m venv .venv && .venv\Scripts\pip install -r requirements.txt"
    exit 1
}
if (-not (Test-Path $Script)) {
    Write-Error "Script not found: $Script"
    exit 1
}

# ── Header ───────────────────────────────────────────────────────────────────
Write-Host ""
Write-Host "═══════════════════════════════════════════════════════════════════" -ForegroundColor Cyan
Write-Host "  Stage 3 · Option A   Directional Classification" -ForegroundColor Cyan
Write-Host "═══════════════════════════════════════════════════════════════════" -ForegroundColor Cyan
Write-Host "  Horizon        : ${TargetHorizon}d"
Write-Host "  Abstain band   : ±$($DirectionThreshold * 100)%"
Write-Host "  Prob threshold : $($TradeProbThreshold * 100)%"
Write-Host "  Models         : $($Models -join ', ')"
Write-Host "  Seed           : $Seed"
Write-Host "  Ledger out     : $LedgerOut"
Write-Host "═══════════════════════════════════════════════════════════════════" -ForegroundColor Cyan
Write-Host ""

# ── Build argument list ───────────────────────────────────────────────────────
$PythonArgs = @(
    $Script,
    "--target-horizon",      $TargetHorizon,
    "--direction-threshold", $DirectionThreshold,
    "--trade-prob-threshold",$TradeProbThreshold,
    "--models"
) + $Models + @(
    "--seed",       $Seed,
    "--output-dir", $OutputDir,
    "--ledger-out", $LedgerOut
)

# ── Run ───────────────────────────────────────────────────────────────────────
$StartTime = Get-Date
& $Python @PythonArgs
$ExitCode  = $LASTEXITCODE
$Elapsed   = (Get-Date) - $StartTime

Write-Host ""
Write-Host "───────────────────────────────────────────────────────────────────" -ForegroundColor DarkGray
Write-Host "  Elapsed : $($Elapsed.ToString('mm\:ss'))" -ForegroundColor DarkGray
Write-Host "  Ledger  : $LedgerOut" -ForegroundColor DarkGray

if ($ExitCode -eq 0) {
    Write-Host "  Result  : PASS — RL escalation unlocked" -ForegroundColor Green
} else {
    Write-Host "  Result  : KILL — no durable directional content found" -ForegroundColor Red
    Write-Host "  Next    : Review ledger, then decide Fork B (override) or Fork C (exit)" -ForegroundColor Yellow
}
Write-Host "───────────────────────────────────────────────────────────────────" -ForegroundColor DarkGray
Write-Host ""

exit $ExitCode
