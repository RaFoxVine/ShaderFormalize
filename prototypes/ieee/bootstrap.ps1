param([switch]$SkipDownload, [switch]$SkipCache)
$ErrorActionPreference = 'Stop'
$ProgressPreference = 'SilentlyContinue'
. (Join-Path $PSScriptRoot 'environment.ps1')
$ieeeLock = Get-Content -LiteralPath (Join-Path $PSScriptRoot 'dependencies.lock.json') -Raw | ConvertFrom-Json
$ieeeDownloads = Join-Path $ieeeWorkspace '.cache/ieee/downloads'
$ieeeArchive = Join-Path $ieeeDownloads 'lean-4.35.0-windows.zip'
$ieeeStamp = Join-Path (Split-Path -Parent $ieeeBin) '.shaderformalize-archive-sha256'
New-Item -ItemType Directory -Force -Path $ieeeDownloads,(Join-Path $ieeeWorkspace '.tools') | Out-Null
if (-not (Test-Path -LiteralPath $ieeeStamp) -or (Get-Content -LiteralPath $ieeeStamp -Raw).Trim() -ne $ieeeLock.lean.sha256) {
    if (-not $SkipDownload) {
        python (Join-Path $ieeeWorkspace 'tools/download_release.py') --url $ieeeLock.lean.url --output $ieeeArchive --size $ieeeLock.lean.size --sha256 $ieeeLock.lean.sha256 --workers 8 --max-seconds 1800
        Assert-IeeeExit 'Lean release download'
    }
    if (-not (Test-Path -LiteralPath $ieeeArchive)) { throw 'Lean archive missing' }
    if ((Get-FileHash -Algorithm SHA256 -LiteralPath $ieeeArchive).Hash.ToLowerInvariant() -ne $ieeeLock.lean.sha256) {
        throw 'Lean archive SHA256 mismatch'
    }
    if (Get-Command tar.exe -ErrorAction SilentlyContinue) {
        & tar.exe -xf $ieeeArchive -C (Join-Path $ieeeWorkspace '.tools')
        Assert-IeeeExit 'Lean archive extraction'
    } else {
        Expand-Archive -LiteralPath $ieeeArchive -DestinationPath (Join-Path $ieeeWorkspace '.tools') -Force
    }
    Set-Content -LiteralPath $ieeeStamp -Value $ieeeLock.lean.sha256 -Encoding ascii
}
Assert-IeeeToolchain
$ieeeVersion = & (Join-Path $ieeeBin 'lean.exe') --version
Assert-IeeeExit 'Independent Lean toolchain'
if ($ieeeVersion -notmatch 'version 4\.35\.0\b') { throw "Unexpected IEEE Lean version: $ieeeVersion" }
Write-Host $ieeeVersion
python (Join-Path $PSScriptRoot 'seed_sources.py')
Assert-IeeeExit 'Pinned dependency sources'
Push-Location $PSScriptRoot
try {
    if (-not $SkipCache) {
        $ieeeTargets = @(python (Join-Path $PSScriptRoot 'cache_targets.py'))
        Assert-IeeeExit 'Required Mathlib import discovery'
        Assert-IeeeToolchain
        & (Join-Path $ieeeBin 'lake.exe') exe cache get @ieeeTargets
        Assert-IeeeExit 'Required Mathlib cache'
    }
    Assert-IeeeToolchain
    & (Join-Path $ieeeBin 'lake.exe') build +Main:olean
    Assert-IeeeExit 'IEEE prototype Lean build'
} finally { Pop-Location }
Write-Host 'Independent IEEE prototype ready. Run prototypes/ieee/run.ps1.'
