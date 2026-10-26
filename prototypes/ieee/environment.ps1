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

function Assert-IeeeExit([string]$Operation) {
    if ($LASTEXITCODE -ne 0) { throw "$Operation failed (exit $LASTEXITCODE)" }
}
