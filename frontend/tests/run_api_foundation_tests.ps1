$ErrorActionPreference = 'Stop'

if (-not (Test-Path '.\package.json')) {
  Write-Error 'Run this script from the frontend directory.'
  exit 1
}

if (-not (Test-Path '.\node_modules\.bin\vitest.cmd')) {
  Write-Error 'Vitest is not installed. Run .\tests\setup_frontend_tests.ps1 first.'
  exit 1
}

npm run test:api
exit $LASTEXITCODE
