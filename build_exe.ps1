$ErrorActionPreference = "Stop"

$projectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $projectRoot

$tempBuildRoot = Join-Path $env:TEMP "ReccioPyInstaller"
$workPath = Join-Path $tempBuildRoot "build"
$distPath = Join-Path $projectRoot "dist"
$distAppPath = Join-Path $distPath "Reccio"

if (Test-Path $workPath) {
    Remove-Item -LiteralPath $workPath -Recurse -Force
}

if (Test-Path $distAppPath) {
    Remove-Item -LiteralPath $distAppPath -Recurse -Force
}

python -m PyInstaller `
    --noconfirm `
    --clean `
    --workpath "$workPath" `
    --distpath "$distPath" `
    Reccio.spec

if ($LASTEXITCODE -ne 0) {
    throw "PyInstaller build zlyhal s kodom $LASTEXITCODE."
}

Write-Host ""
Write-Host "Build hotovy:"
Write-Host "dist\Reccio\Reccio.exe"
