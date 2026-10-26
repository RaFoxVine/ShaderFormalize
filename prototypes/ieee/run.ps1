$ErrorActionPreference = 'Stop'
$ieeeWorkspace = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot '../..'))
$ieeeOutput = Join-Path $ieeeWorkspace 'artifacts/ieee'
New-Item -ItemType Directory -Force -Path $ieeeOutput | Out-Null
$ieeeLog = Join-Path $ieeeOutput 'probe.log'
$ieeeResult = Join-Path $ieeeOutput 'result.json'
@{ schema = 1; status = 'IN_PROGRESS'; checked_at = (Get-Date).ToString('o') } |
    ConvertTo-Json | Set-Content -LiteralPath $ieeeResult -Encoding utf8
Set-Content -LiteralPath $ieeeLog -Value 'IN_PROGRESS' -Encoding utf8
$ieeePushed = $false
$ieeeExit = -1
try {
    . (Join-Path $PSScriptRoot 'environment.ps1')
    Push-Location $PSScriptRoot
    $ieeePushed = $true
    $ieeeText = & (Join-Path $ieeeBin 'lake.exe') env lean --run Main.lean 2>&1
    $ieeeExit = $LASTEXITCODE
    $ieeeText | Set-Content -LiteralPath $ieeeLog -Encoding utf8
    $ieeePassed = $ieeeExit -eq 0 -and ($ieeeText -match '^IEEE_PROTOTYPE_PASSED$')
    if (-not $ieeePassed) { throw "IEEE prototype failed. See $ieeeLog" }
    $ieeeManifest = Get-Content -LiteralPath 'lake-manifest.json' -Raw | ConvertFrom-Json
    $ieeeReport = [ordered]@{
        schema = 1
        status = $(if ($ieeePassed) { 'EXTERNAL_LIBRARY_PROTOTYPE_PASSED' } else { 'FAILED' })
        checked_at = (Get-Date).ToString('o')
        command = 'lake env lean --run Main.lean'
        exit_code = $ieeeExit
        lean_version = (& (Join-Path $ieeeBin 'lean.exe') --version | Out-String).Trim()
        shader_cli_ieee_integrated = $false
        interpretation = 'FloatLib binary32 reference operations, nearest ties-to-even; HLSL GPU profile not yet connected'
        main_sha256 = (Get-FileHash -Algorithm SHA256 -LiteralPath 'Main.lean').Hash.ToLowerInvariant()
        lake_manifest_sha256 = (Get-FileHash -Algorithm SHA256 -LiteralPath 'lake-manifest.json').Hash.ToLowerInvariant()
        dependency_lock_sha256 = (Get-FileHash -Algorithm SHA256 -LiteralPath 'dependencies.lock.json').Hash.ToLowerInvariant()
        log_sha256 = (Get-FileHash -Algorithm SHA256 -LiteralPath $ieeeLog).Hash.ToLowerInvariant()
        packages = @($ieeeManifest.packages | Select-Object name,url,rev)
        checks_passed = @($ieeeText | Where-Object { $_ -match '^PASS ' }).Count
    }
    $ieeeReport | ConvertTo-Json -Depth 8 | Set-Content -LiteralPath $ieeeResult -Encoding utf8
    Write-Host ($ieeeReport | ConvertTo-Json -Depth 8)
} catch {
    $ieeeFailure = $_.Exception.Message
    Add-Content -LiteralPath $ieeeLog -Value $ieeeFailure -Encoding utf8
    @{ schema = 1; status = 'FAILED'; checked_at = (Get-Date).ToString('o');
       exit_code = $ieeeExit; message = $ieeeFailure; shader_cli_ieee_integrated = $false } |
        ConvertTo-Json | Set-Content -LiteralPath $ieeeResult -Encoding utf8
    Write-Host "FAILED: $ieeeFailure"
    exit 1
} finally {
    if ($ieeePushed) { Pop-Location }
}
