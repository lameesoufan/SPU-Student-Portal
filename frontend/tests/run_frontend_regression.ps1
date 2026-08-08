$ErrorActionPreference = 'Stop'

$vitest = '.\node_modules\.bin\vitest.cmd'
if (-not (Test-Path $vitest)) {
    throw 'Vitest is not installed. Run .\tests\setup_frontend_tests.ps1 first.'
}

Write-Host '=== Frontend API foundation (209) ==='
& '.\tests\run_api_foundation_tests.ps1'
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

Write-Host ''
Write-Host '=== Frontend UI regression (1382) ==='
& $vitest run --config vitest.ui.config.js
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

Write-Host ''
Write-Host 'All frontend regression tests passed.'
Write-Host 'Expected total: 1591 tests.'
