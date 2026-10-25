param(
    [Parameter(Mandatory=$true)][string]$UnityProject,
    [ValidateSet('all','lerp','unlit','structured','textured','branched')][string]$Example = 'all'
)
$ErrorActionPreference = 'Stop'
$workspace = Split-Path -Parent $PSScriptRoot
Push-Location $workspace
try {
    $examples = if ($Example -eq 'all') { @('lerp','unlit','structured','textured','branched') } else { @($Example) }
    foreach ($name in $examples) {
        python tools/run_unity.py --example $name --project $UnityProject
        if ($LASTEXITCODE -ne 0) { throw "Optional Unity development check failed for $name" }
    }
    Write-Host 'Explicitly requested Unity development suite passed.'
} finally { Pop-Location }
