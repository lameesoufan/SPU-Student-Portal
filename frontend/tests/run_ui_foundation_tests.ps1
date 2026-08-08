$ErrorActionPreference = 'Stop'

$vitest = '.\node_modules\.bin\vitest.cmd'
if (-not (Test-Path $vitest)) {
    throw 'Vitest is not installed. Run .\tests\setup_frontend_ui_tests.ps1 first.'
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
    'src/__tests__/ThemeContext.ui.test.jsx',
    'src/hooks/__tests__/usePageHistory.ui.test.jsx',
    'src/hooks/__tests__/usePolling.ui.test.jsx',
    'src/components/__tests__/Login.ui.test.jsx',
    'src/components/__tests__/OTPVerification.ui.test.jsx',
    'src/components/__tests__/ForgotPassword.ui.test.jsx',
    'src/components/__tests__/ChangePassword.ui.test.jsx',
    'src/components/__tests__/ChangeUsername.ui.test.jsx',
    'src/components/ui/__tests__/UIPrimitives.ui.test.jsx'
)

Write-Host 'Running frontend React UI foundation tests...'
& $vitest run --config vitest.ui.config.js @testFiles
if ($LASTEXITCODE -ne 0) {
    exit $LASTEXITCODE
}
