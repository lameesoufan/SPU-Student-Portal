$ErrorActionPreference = "Stop"
Write-Host "Running final frontend fix verification tests..."
npx vitest run --config vitest.ui.config.js `
  src/__tests__/FrontendRemainingContracts.final-ui.test.js `
  src/components/__tests__/BrowsePropose.final-ui.test.jsx `
  src/components/committees/GradeEntry.academic-ui.test.jsx
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
