$ErrorActionPreference = "Stop"

function Run-Step {
    param(
        [string]$Label,
        [string[]]$Arguments
    )

    Write-Host ""
    Write-Host "=== $Label ==="
    & python @Arguments
    if ($LASTEXITCODE -ne 0) {
        throw "$Label failed with exit code $LASTEXITCODE"
    }
}

New-Item -ItemType Directory -Force -Path ".test-artifacts" | Out-Null

Run-Step "Static release contracts" @(
    "-m", "pytest", "tests/release", "-v"
)

Run-Step "Smoke and project quality gates" @(
    "-m", "pytest", "tests/smoke", "-v"
)

Run-Step "Cross-application integration" @(
    "-m", "pytest", "tests/integration", "-v"
)

Run-Step "Full suite with coverage" @(
    "-m", "pytest",
    "--cov-config=.coveragerc",
    "--cov=accounts",
    "--cov=projects",
    "--cov=workflow",
    "--cov=project_management",
    "--cov=notifications",
    "--cov=grades",
    "--cov=committees",
    "--cov=project_imports",
    "--cov=gitlab_integration",
    "--cov=dy_forms",
    "--cov=backend",
    "--cov-report=term-missing",
    "--cov-report=xml:.test-artifacts/coverage.xml",
    "--cov-report=html:.test-artifacts/htmlcov",
    "--cov-fail-under=70",
    "-q"
)

Write-Host ""
Write-Host "All release gates passed."
Write-Host "Coverage XML: .test-artifacts/coverage.xml"
Write-Host "Coverage HTML: .test-artifacts/htmlcov/index.html"
