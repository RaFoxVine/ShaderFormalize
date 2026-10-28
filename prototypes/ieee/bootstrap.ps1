param([switch]$SkipDownload, [switch]$SkipCache)
$ErrorActionPreference = 'Stop'
$ieeeWorkspace = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot '../..'))
& (Join-Path $ieeeWorkspace 'tools/bootstrap.ps1') -SkipMathlibCache:$SkipCache -SkipDownload:$SkipDownload
