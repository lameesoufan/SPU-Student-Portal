$ErrorActionPreference = "Stop"

function Run-Step {
    param(
        [string]$Label,
        [string[]]$PytestArgs
    )

    Write-Host ""
    Write-Host "=== $Label ==="
    python -m pytest @PytestArgs
    if ($LASTEXITCODE -ne 0) {
        throw "$Label failed with exit code $LASTEXITCODE"
    }
}

Run-Step "Smoke and project quality gates" @("tests/smoke", "-v")
Run-Step "Cross-application integration" @("tests/integration", "-v")
Run-Step "Full configured pytest suite" @("-v")

Write-Host ""
Write-Host "All quality gates passed."
