param([switch]$SkipMathlibCache)
$ErrorActionPreference = 'Stop'
$ProgressPreference = 'SilentlyContinue'
$workspace = Split-Path -Parent $PSScriptRoot
$lock = Get-Content -LiteralPath (Join-Path $workspace 'dependencies.lock.json') -Raw | ConvertFrom-Json
$downloads = Join-Path $workspace '.cache/downloads'
New-Item -ItemType Directory -Force -Path $downloads,(Join-Path $workspace '.tools'),(Join-Path $workspace '.cache/mathlib') | Out-Null

function Get-LockedArchive($dependency, $filename) {
    $archive = Join-Path $downloads $filename
    if ((Test-Path -LiteralPath $archive) -and ((Get-FileHash -Algorithm SHA256 -LiteralPath $archive).Hash.ToLowerInvariant() -eq $dependency.sha256)) {
        return $archive
    }
    Write-Host "Downloading $filename"
    Invoke-WebRequest -Uri $dependency.url -OutFile $archive -TimeoutSec 1800
    if ((Get-FileHash -Algorithm SHA256 -LiteralPath $archive).Hash.ToLowerInvariant() -ne $dependency.sha256) {
        throw "Checksum mismatch: $filename"
    }
    return $archive
}

$leanBin = Join-Path $workspace '.tools/lean-4.24.0-windows/bin'
if (-not (Test-Path -LiteralPath (Join-Path $leanBin 'lean.exe'))) {
    $archive = Get-LockedArchive $lock.lean 'lean-4.24.0-windows.zip'
    Expand-Archive -LiteralPath $archive -DestinationPath (Join-Path $workspace '.tools') -Force
}
foreach ($property in $lock.lean.binaries.PSObject.Properties) {
    if ((Get-FileHash -Algorithm SHA256 -LiteralPath (Join-Path $leanBin $property.Name)).Hash.ToLowerInvariant() -ne $property.Value) {
        throw "Lean binary changed: $($property.Name)"
    }
}
$dxcBin = Join-Path $workspace '.tools/dxc/bin/x64'
if (-not (Test-Path -LiteralPath (Join-Path $dxcBin 'dxc.exe'))) {
    $archive = Get-LockedArchive $lock.dxc 'dxc_2025_07_14.zip'
    Expand-Archive -LiteralPath $archive -DestinationPath (Join-Path $workspace '.tools/dxc') -Force
}
foreach ($property in $lock.dxc.binaries.PSObject.Properties) {
    if ((Get-FileHash -Algorithm SHA256 -LiteralPath (Join-Path $dxcBin $property.Name)).Hash.ToLowerInvariant() -ne $property.Value) {
        throw "DXC binary changed: $($property.Name)"
    }
}

$leantar = Join-Path $workspace '.cache/mathlib/leantar-0.1.15.exe'
if (-not (Test-Path -LiteralPath $leantar)) {
    $archive = Get-LockedArchive $lock.leantar 'leantar-v0.1.15.zip'
    Expand-Archive -LiteralPath $archive -DestinationPath (Join-Path $workspace '.tools/leantar') -Force
    Copy-Item -LiteralPath (Join-Path $workspace '.tools/leantar/leantar-v0.1.15-x86_64-pc-windows-msvc/leantar.exe') -Destination $leantar
}
if ((Get-FileHash -Algorithm SHA256 -LiteralPath $leantar).Hash.ToLowerInvariant() -ne $lock.leantar.binary_sha256) {
    throw 'leantar binary changed'
}

# Only this script/process sees these variables; do not change user/global settings.
$env:PATH = $leanBin + [IO.Path]::PathSeparator + $env:PATH
$env:MATHLIB_CACHE_DIR = Join-Path $workspace '.cache/mathlib'
$env:LAKE_HOME = Join-Path $workspace '.cache/lake'
$env:ELAN_HOME = Join-Path $workspace '.tools/elan'
$env:MATHLIB_NO_CACHE_ON_UPDATE = '1'
$env:CURL_HOME = Join-Path $workspace '.cache/curl'
New-Item -ItemType Directory -Force -Path $env:CURL_HOME | Out-Null
# The current host's IPv6 route stalls on GitHub release assets. Keep the
# transport preference local to this toolchain, with bounded connection waits.
foreach ($filename in @('.curlrc','_curlrc')) {
    Set-Content -LiteralPath (Join-Path $env:CURL_HOME $filename) -Value "ipv4`nconnect-timeout = 15" -Encoding ascii
}
# Process-local Git transport settings; do not edit machine or repository config.
$gitConfigCount = 0
if ($env:GIT_CONFIG_COUNT) { $gitConfigCount = [int]$env:GIT_CONFIG_COUNT }
foreach ($setting in @(@('http.sslBackend','schannel'), @('http.version','HTTP/1.1'))) {
    [Environment]::SetEnvironmentVariable("GIT_CONFIG_KEY_$gitConfigCount", $setting[0], 'Process')
    [Environment]::SetEnvironmentVariable("GIT_CONFIG_VALUE_$gitConfigCount", $setting[1], 'Process')
    $gitConfigCount++
}
$env:GIT_CONFIG_COUNT = [string]$gitConfigCount
$proof = Join-Path $workspace 'proof'
$mathlib = Join-Path $proof '.lake/packages/mathlib'
if (-not (Test-Path -LiteralPath (Join-Path $mathlib '.git'))) {
    New-Item -ItemType Directory -Force -Path $mathlib | Out-Null
    git -C $mathlib init --quiet
    if ($LASTEXITCODE -ne 0) { throw 'git init mathlib failed' }
    git -C $mathlib remote add origin $lock.mathlib.url
    if ($LASTEXITCODE -ne 0) { throw 'git remote mathlib failed' }
}
$currentRevision = git -C $mathlib rev-parse --verify HEAD 2>$null
if ($currentRevision -ne $lock.mathlib.revision) {
    git -C $mathlib fetch --depth 1 origin $lock.mathlib.revision
    if ($LASTEXITCODE -ne 0) { throw 'mathlib fetch failed' }
    git -C $mathlib checkout --detach $lock.mathlib.revision
    if ($LASTEXITCODE -ne 0) { throw 'mathlib checkout failed' }
}
Push-Location $proof
try {
    & (Join-Path $leanBin 'lean.exe') --version
    if ($LASTEXITCODE -ne 0) { throw 'Local Lean cannot run' }
    python (Join-Path $PSScriptRoot 'seed_dependencies.py')
    if ($LASTEXITCODE -ne 0) { throw 'Pinned Lake dependency materialization failed' }
    if (-not $SkipMathlibCache) {
        & (Join-Path $leanBin 'lake.exe') --no-cache exe fetchMathlibCache
        if ($LASTEXITCODE -ne 0) { throw 'mathlib cache download failed' }
    }
} finally { Pop-Location }
Write-Host 'Local toolchain ready. Run: python tools/shaderformalize.py check'
