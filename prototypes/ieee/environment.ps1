$ErrorActionPreference = 'Stop'
$ieeeWorkspace = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot '../..'))
$ieeeBin = Join-Path $ieeeWorkspace '.tools/lean-4.35.0-windows/bin'
$ieeeForeignNames = @(Get-ChildItem Env: | Where-Object { $_.Name -like 'LEAN_*' } | Select-Object -ExpandProperty Name)
foreach ($ieeeName in $ieeeForeignNames + @('FLOATLIB_BUILD_DIR')) {
    [Environment]::SetEnvironmentVariable($ieeeName, $null, 'Process')
}
$env:PATH = $ieeeBin + [IO.Path]::PathSeparator + $env:PATH
$env:ELAN_HOME = Join-Path $ieeeWorkspace '.tools/ieee-elan'
$env:LAKE_HOME = Join-Path $ieeeWorkspace '.cache/ieee/lake'
$env:MATHLIB_CACHE_DIR = Join-Path $ieeeWorkspace '.cache/ieee/mathlib'
$env:MATHLIB_NO_CACHE_ON_UPDATE = '1'
$env:CURL_HOME = Join-Path $ieeeWorkspace '.cache/ieee/curl'
New-Item -ItemType Directory -Force -Path $env:CURL_HOME | Out-Null
foreach ($ieeeFile in @('.curlrc','_curlrc')) {
    Set-Content -LiteralPath (Join-Path $env:CURL_HOME $ieeeFile) -Value "ipv4`nconnect-timeout = 15`nmax-time = 120" -Encoding ascii
}

$ieeeBinaryLock = @{
    'lean.exe' = 'ec7a472d1c12a09b0c0c718f7427c2be527b3f5f07810fdbe076c2507c7a91ea'
    'lake.exe' = '023feb24d3e7244fe671dba79f1cd1affc6c7a7cacfe497bf3675febb506578c'
}

function Assert-IeeeToolchain {
    foreach ($ieeeName in @('lean.exe', 'lake.exe')) {
        $ieeePath = Join-Path $ieeeBin $ieeeName
        if (-not (Test-Path -LiteralPath $ieeePath -PathType Leaf)) {
            throw "ENVIRONMENT_ERROR: pinned IEEE tool missing: $ieeeName"
        }
        $ieeeActual = (Get-FileHash -Algorithm SHA256 -LiteralPath $ieeePath).Hash.ToLowerInvariant()
        if ($ieeeActual -ne $ieeeBinaryLock[$ieeeName]) {
            throw "ENVIRONMENT_ERROR: pinned IEEE tool SHA256 mismatch: $ieeeName"
        }
    }
}

function Assert-IeeeExit([string]$Operation) {
    if ($LASTEXITCODE -ne 0) { throw "$Operation failed (exit $LASTEXITCODE)" }
}
