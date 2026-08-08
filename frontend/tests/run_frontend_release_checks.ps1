$ErrorActionPreference = 'Stop'

Write-Host '=== Frontend final regression: 1591 tests ==='
& '.\tests\run_frontend_regression.ps1'
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

Write-Host ''
Write-Host '=== ESLint ==='
& npm run lint
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

Write-Host ''
Write-Host '=== Production build ==='
& npm run build
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

Write-Host ''
Write-Host 'Frontend release checks passed: regression, lint, and production build.'
