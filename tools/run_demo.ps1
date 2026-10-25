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
    python tools/run_unity.py --example structured --project $UnityProject
    if ($LASTEXITCODE -ne 0) { throw 'Structured material/HDRP scene verification failed; see artifacts/structured/unity' }
    python tools/run_unity.py --example textured --project $UnityProject
    if ($LASTEXITCODE -ne 0) { throw 'Textured material/clip/derivative verification failed; see artifacts/textured/unity' }
    Write-Host 'Demo passed: lerp, Unlit, structured and textured HLSL proofs, GPU/CPU cases and reloaded HDRP scenes.'
} finally { Pop-Location }
