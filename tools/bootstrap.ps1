param([switch]$SkipMathlibCache, [switch]$SkipDownload)
$ErrorActionPreference = 'Stop'
$ProgressPreference = 'SilentlyContinue'
. (Join-Path $PSScriptRoot 'environment.ps1')
$workspace = $leanWorkspace
$lock = $leanLock
$downloads = Join-Path $workspace '.cache/downloads'
New-Item -ItemType Directory -Force -Path $downloads,(Join-Path $workspace '.tools') | Out-Null

function Get-LockedArchive($dependency, $filename) {
    $archive = Join-Path $downloads $filename
    if ((Test-Path -LiteralPath $archive) -and ((Get-FileHash -Algorithm SHA256 -LiteralPath $archive).Hash.ToLowerInvariant() -eq $dependency.sha256)) { return $archive }
    if ($SkipDownload) { throw "Locked archive unavailable: $archive" }
    if ($dependency.PSObject.Properties.Name -contains 'size') {
        python (Join-Path $PSScriptRoot 'download_release.py') --url $dependency.url --output $archive --size $dependency.size --sha256 $dependency.sha256 --workers 8 --max-seconds 1800 | Out-Host
        Assert-LeanExit "Download $filename"
    } else {
        & curl.exe -4 --location --fail --silent --show-error --connect-timeout 15 --max-time 1800 --retry 3 --retry-delay 2 --output $archive $dependency.url
        Assert-LeanExit "Download $filename"
    }
    if ((Get-FileHash -Algorithm SHA256 -LiteralPath $archive).Hash.ToLowerInvariant() -ne $dependency.sha256) { throw "Checksum mismatch: $filename" }
    return $archive
}

if (-not (Test-Path -LiteralPath (Join-Path $leanBin 'lean.exe'))) {
    $archive = Get-LockedArchive $lock.lean ('lean-' + $lock.lean.version + '-windows.zip')
    & tar.exe -xf $archive -C (Join-Path $workspace '.tools')
    Assert-LeanExit 'Lean archive extraction'
}
Assert-LeanToolchain
$dxcBin = Join-Path $workspace '.tools/dxc/bin/x64'
if (-not (Test-Path -LiteralPath (Join-Path $dxcBin 'dxc.exe'))) {
    $archive = Get-LockedArchive $lock.dxc 'dxc_2025_07_14.zip'
    Expand-Archive -LiteralPath $archive -DestinationPath (Join-Path $workspace '.tools/dxc') -Force
}
foreach ($property in $lock.dxc.binaries.PSObject.Properties) {
    if ((Get-FileHash -Algorithm SHA256 -LiteralPath (Join-Path $dxcBin $property.Name)).Hash.ToLowerInvariant() -ne $property.Value) { throw "DXC binary changed: $($property.Name)" }
}
python (Join-Path $PSScriptRoot 'seed_dependencies.py')
Assert-LeanExit 'Pinned Lake dependency materialization'
$proof = Join-Path $workspace 'proof'
Push-Location $proof
try {
    Assert-LeanToolchain
    & (Join-Path $leanBin 'lean.exe') --version
    Assert-LeanExit 'Local Lean'
    if (-not $SkipMathlibCache) {
        $targets = @(python (Join-Path $PSScriptRoot 'cache_targets.py'))
        Assert-LeanExit 'Required Mathlib imports'
        if ($targets.Count -eq 0) { throw 'No Mathlib cache roots found' }
        Assert-LeanToolchain
        & (Join-Path $leanBin 'lake.exe') exe cache get @targets
        Assert-LeanExit 'Required Mathlib cache'
        Assert-LeanToolchain
        & (Join-Path $leanBin 'lake.exe') env lean ShaderFormalize/BootstrapSmoke.lean
        Assert-LeanExit 'Required Mathlib import smoke'
        Assert-LeanToolchain
        & (Join-Path $leanBin 'lake.exe') build +ShaderIeee.Model:olean +ShaderIeee.Probe:olean
        Assert-LeanExit 'FloatLib shader model and probe'
    }
} finally { Pop-Location }
Write-Host 'Shared local Lean toolchain and pinned dependencies ready.'
