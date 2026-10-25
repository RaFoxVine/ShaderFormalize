param(
    [string]$UnityProject,
    [ValidateSet('all','lerp','unlit','structured','textured','branched')][string]$Example = 'all',
    [switch]$Bootstrap
)
$ErrorActionPreference = 'Stop'
$workspace = Split-Path -Parent $PSScriptRoot
Push-Location $workspace
try {
    if ($Bootstrap) { & "$PSScriptRoot/bootstrap.ps1" }
    python tools/verify_demo.py --example $Example
    if ($LASTEXITCODE -ne 0) { throw 'Formal/import verification failed; see artifacts/acceptance' }
    if (-not $UnityProject) {
        Write-Host 'Core checks passed. Unity is an optional development integration.'
        return
    }
    & "$PSScriptRoot/run_unity_suite.ps1" -UnityProject $UnityProject -Example $Example
    Write-Host 'Core and explicitly requested Unity development checks passed.'
} finally { Pop-Location }
