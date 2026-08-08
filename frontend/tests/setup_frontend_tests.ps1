$ErrorActionPreference = 'Stop'

if (-not (Test-Path '.\package.json')) {
    throw 'Run this script from the frontend directory.'
}

Write-Host 'Installing frontend dependencies from package.json...'
npm install
if ($LASTEXITCODE -ne 0) {
    throw 'npm install failed.'
}

Write-Host 'Frontend dependencies installed from package.json.'
