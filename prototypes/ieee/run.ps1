$ErrorActionPreference = 'Stop'
$ieeeWorkspace = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot '../..'))
python (Join-Path $ieeeWorkspace 'tools/run_ieee_probe.py')
exit $LASTEXITCODE
