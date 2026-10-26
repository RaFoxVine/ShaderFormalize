param([string]$JavaHome)
$ErrorActionPreference = 'Stop'
$ProgressPreference = 'SilentlyContinue'
$workspace = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)
$lock = Get-Content -LiteralPath (Join-Path $PSScriptRoot 'dependencies.lock.json') -Raw | ConvertFrom-Json
$archive = Join-Path $workspace '.cache/downloads/vercors-2.4.0-win.zip'
$destination = Join-Path $workspace '.tools/vercors-2.4.0'

if ($JavaHome) {
    $env:JAVA_HOME = (Resolve-Path -LiteralPath $JavaHome).Path
} elseif (-not $env:JAVA_HOME) {
    $javaCommand = Get-Command java.exe -ErrorAction Stop
    $env:JAVA_HOME = Split-Path -Parent (Split-Path -Parent $javaCommand.Source)
}
$java = Join-Path $env:JAVA_HOME 'bin/java.exe'
if (-not (Test-Path -LiteralPath $java)) { throw 'Java is missing. Supply a JDK/JRE 17+ with -JavaHome.' }
& $java -version
if ($LASTEXITCODE -ne 0) { throw 'Java could not start.' }

New-Item -ItemType Directory -Force -Path (Split-Path -Parent $archive) | Out-Null
if (-not (Test-Path -LiteralPath $archive) -or (Get-FileHash -LiteralPath $archive -Algorithm SHA256).Hash.ToLowerInvariant() -ne $lock.vercors.sha256) {
    python (Join-Path $workspace 'tools/download_release.py') --url $lock.vercors.url --output $archive --size $lock.vercors.archive_bytes --sha256 $lock.vercors.sha256 --workers 8
    if ($LASTEXITCODE -ne 0) { throw 'VerCors download failed; partial ranges are retained for retry.' }
}
if ((Get-FileHash -LiteralPath $archive -Algorithm SHA256).Hash.ToLowerInvariant() -ne $lock.vercors.sha256) {
    throw 'VerCors archive checksum mismatch. Preserve the file for diagnosis and retry the download.'
}
$launcher = Join-Path $destination 'vercors.bat'
if (-not (Test-Path -LiteralPath $launcher)) {
    Expand-Archive -LiteralPath $archive -DestinationPath $destination -Force
}
if (-not (Test-Path -LiteralPath $launcher)) { throw 'Expected VerCors launcher was not found in the pinned release.' }
Write-Host "Local VerCors ready: $launcher"
Write-Host 'Run: python prototypes/synchronization/run.py'
