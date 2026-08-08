$ErrorActionPreference = 'Stop'

$vitest = '.\node_modules\.bin\vitest.cmd'
if (-not (Test-Path $vitest)) {
    throw 'Vitest is not installed. Run .\tests\setup_frontend_tests.ps1 first.'
}

$requiredPackages = @(
    '.\node_modules\@testing-library\react',
    '.\node_modules\@testing-library\dom',
    '.\node_modules\jsdom'
)
foreach ($package in $requiredPackages) {
    if (-not (Test-Path $package)) {
        throw 'UI testing dependencies are missing. Run .\tests\setup_frontend_ui_tests.ps1 first.'
    }
}

$testFiles = @(
    'src/components/committees/RoomsManagement.academic-ui.test.jsx',
    'src/components/committees/MyAvailabilityPage.academic-ui.test.jsx',
    'src/components/committees/SchedulePage.academic-ui.test.jsx'
)

Write-Host 'Running frontend committee operations UI tests...'
Write-Host 'Expected: 162 tests.'
& $vitest run --config vitest.ui.config.js @testFiles
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
