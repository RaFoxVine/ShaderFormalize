param(
    [Parameter(Mandatory=$true)][string]$UnityProject,
    [switch]$Bootstrap
)
$ErrorActionPreference = 'Stop'
$workspace = Split-Path -Parent $PSScriptRoot
Push-Location $workspace
try {
    if ($Bootstrap) { & "$PSScriptRoot/bootstrap.ps1" }
    python tools/verify_demo.py
    if ($LASTEXITCODE -ne 0) { throw 'Formal/import verification failed; see artifacts/acceptance' }
    python tools/run_unity.py --project $UnityProject
    if ($LASTEXITCODE -ne 0) { throw 'Unity GPU verification failed; see artifacts/unity' }
    python tools/run_unity.py --example unlit --project $UnityProject
    if ($LASTEXITCODE -ne 0) { throw 'Unlit material/HDRP scene verification failed; see artifacts/unlit/unity' }
    Write-Host 'Demo passed: lerp + Unlit Lean checks, GPU/CPU cases and reloaded HDRP scene.'
} finally { Pop-Location }
