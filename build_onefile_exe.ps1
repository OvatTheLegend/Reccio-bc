$ErrorActionPreference = "Stop"

$projectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $projectRoot

$tempBuildRoot = Join-Path $env:TEMP "ReccioPyInstallerOnefile"
$workPath = Join-Path $tempBuildRoot "build"
$distPath = Join-Path $projectRoot "dist_onefile"
$exePath = Join-Path $distPath "Reccio.exe"

if (Test-Path $workPath) {
    Remove-Item -LiteralPath $workPath -Recurse -Force
}

if (Test-Path $exePath) {
    Remove-Item -LiteralPath $exePath -Force
}

python -m PyInstaller `
    --noconfirm `
    --clean `
    --workpath "$workPath" `
    --distpath "$distPath" `
    Reccio_onefile.spec

if ($LASTEXITCODE -ne 0) {
    throw "PyInstaller onefile build zlyhal s kodom $LASTEXITCODE."
}

Write-Host ""
Write-Host "Onefile build hotovy:"
Write-Host "dist_onefile\Reccio.exe"
