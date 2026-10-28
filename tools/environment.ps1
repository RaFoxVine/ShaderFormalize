$ErrorActionPreference = 'Stop'
$leanWorkspace = Split-Path -Parent $PSScriptRoot
$leanLock = Get-Content -LiteralPath (Join-Path $leanWorkspace 'dependencies.lock.json') -Raw | ConvertFrom-Json
$leanBin = Join-Path $leanWorkspace ('.tools/lean-' + $leanLock.lean.version + '-windows/bin')
foreach ($leanName in @(Get-ChildItem Env: | Where-Object { $_.Name -like 'LEAN_*' -or $_.Name -eq 'FLOATLIB_BUILD_DIR' } | Select-Object -ExpandProperty Name)) {
    [Environment]::SetEnvironmentVariable($leanName, $null, 'Process')
}
$env:PATH = $leanBin + [IO.Path]::PathSeparator + $env:PATH
$env:ELAN_HOME = Join-Path $leanWorkspace '.tools/elan'
$env:LAKE_HOME = Join-Path $leanWorkspace '.cache/lake'
$env:MATHLIB_CACHE_DIR = Join-Path $leanWorkspace '.cache/mathlib'
$env:MATHLIB_NO_CACHE_ON_UPDATE = '1'
$env:CURL_HOME = Join-Path $leanWorkspace '.cache/curl'
New-Item -ItemType Directory -Force -Path $env:CURL_HOME | Out-Null
foreach ($leanFile in @('.curlrc','_curlrc')) {
    Set-Content -LiteralPath (Join-Path $env:CURL_HOME $leanFile) -Value "ipv4`nconnect-timeout = 15`nmax-time = 120" -Encoding ascii
}

function Assert-LeanToolchain {
    foreach ($leanProperty in $leanLock.lean.binaries.PSObject.Properties) {
        $leanPath = Join-Path $leanBin $leanProperty.Name
        if (-not (Test-Path -LiteralPath $leanPath -PathType Leaf) -or
            (Get-FileHash -Algorithm SHA256 -LiteralPath $leanPath).Hash.ToLowerInvariant() -ne $leanProperty.Value) {
            throw "ENVIRONMENT_ERROR: pinned Lean file missing/changed: $($leanProperty.Name)"
        }
    }
}

function Assert-LeanExit([string]$Operation) {
    if ($LASTEXITCODE -ne 0) { throw "$Operation failed (exit $LASTEXITCODE)" }
}
