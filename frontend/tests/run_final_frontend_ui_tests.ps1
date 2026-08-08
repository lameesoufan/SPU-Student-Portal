$ErrorActionPreference = 'Stop'

$vitest = '.\node_modules\.bin\vitest.cmd'
if (-not (Test-Path $vitest)) {
    throw 'Vitest is not installed. Run .\tests\setup_frontend_tests.ps1 first.'
}

Write-Host 'Running final remaining frontend UI mega batch (507 tests)...'
& $vitest run --config vitest.ui.config.js `
  'src/components/__tests__/RemainingHelpers.final-ui.test.jsx' `
  'src/components/__tests__/BrowsePropose.final-ui.test.jsx' `
  'src/__tests__/FrontendRemainingContracts.final-ui.test.js'
exit $LASTEXITCODE
