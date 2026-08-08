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
    'src/components/__tests__/MyIdeas.student-ui.test.jsx',
    'src/components/__tests__/MyInvitations.student-ui.test.jsx',
    'src/components/__tests__/SubmitIdea.student-ui.test.jsx',
    'src/components/__tests__/StudentSearch.student-ui.test.jsx',
    'src/components/__tests__/MyProject.student-ui.test.jsx',
    'src/components/__tests__/AccountAccess.student-ui.test.jsx',
    'src/components/__tests__/HodIdeaReview.student-ui.test.jsx'
)

Write-Host 'Running frontend student/projects/account access UI tests...'
Write-Host 'Expected: 264 tests.'
& $vitest run --config vitest.ui.config.js @testFiles
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
