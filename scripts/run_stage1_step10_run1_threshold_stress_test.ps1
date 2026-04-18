Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$repoRoot = Resolve-Path (Join-Path $scriptDir "..")
Push-Location $repoRoot

try {
    $venvActivate = Join-Path $repoRoot ".venv\Scripts\Activate.ps1"
    if (-not (Test-Path $venvActivate)) {
        throw "Missing virtual environment activation script: $venvActivate"
    }

    . $venvActivate

    $step9Stamp = "20260418-150930"
    $tradingEvalGlob = "logs/stage1_trading_eval_step9_*_${step9Stamp}.json"
    $diagStamp = Get-Date -Format "yyyyMMdd-HHmmss"

    $runs = @(
        @{ MinVal = "0.008"; MinTest = "0.008"; Label = "0p008" },
        @{ MinVal = "0.006"; MinTest = "0.006"; Label = "0p006" },
        @{ MinVal = "0.004"; MinTest = "0.004"; Label = "0p004" }
    )

    foreach ($run in $runs) {
        $outJson = "logs/stage1_gate_report_step9_diag_r2_$($run.Label)_$diagStamp.json"
        $outMd = "logs/stage1_gate_report_step9_diag_r2_$($run.Label)_$diagStamp.md"

        Write-Host "Running threshold diagnostic: val=$($run.MinVal), test=$($run.MinTest)"

        & python.exe scripts/stage1_gate.py `
            --results-dir results/stage1_step9 `
            --trading-eval-glob $tradingEvalGlob `
            --min-val-r2 $run.MinVal `
            --min-test-r2 $run.MinTest `
            --output-json $outJson `
            --output-md $outMd

        if ($LASTEXITCODE -ne 0) {
            throw "stage1_gate.py failed for threshold label $($run.Label)"
        }
    }

    Write-Host "Run 1 complete. Outputs written to logs/"
}
finally {
    Pop-Location
}
