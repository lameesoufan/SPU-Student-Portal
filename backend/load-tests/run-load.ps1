param(
    [ValidateSet("baseline", "stress", "spike", "soak")]
    [string]$Profile = "baseline",
    [string]$HostUrl = "http://127.0.0.1:8000",
    [switch]$SkipPrepare
)

$ErrorActionPreference = "Stop"
$env:LOAD_PROFILE = $Profile
$env:LOAD_TEST_HOST = $HostUrl

New-Item -ItemType Directory -Force -Path "$PSScriptRoot/results" | Out-Null

if (-not $SkipPrepare) {
    Write-Host "[load-tests] Preparing load-test identities..."
    python "$PSScriptRoot/prepare_load_users.py"
    if ($LASTEXITCODE -ne 0) {
        exit $LASTEXITCODE
    }
}

python -m locust `
    -f "$PSScriptRoot/profile_load.py" `
    --host $HostUrl `
    --headless `
    --csv "$PSScriptRoot/results/$Profile" `
    --html "$PSScriptRoot/results/$Profile.html"

exit $LASTEXITCODE
