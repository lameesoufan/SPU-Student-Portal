Write-Host 'Running frontend role/navigation UI tests...'
npm run test:role-ui
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
