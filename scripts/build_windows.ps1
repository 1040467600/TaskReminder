# TaskReminder Windows one-click build script (ASCII only).
# Usage:
#   powershell -ExecutionPolicy Bypass -File scripts\build_windows.ps1
#   powershell ... build_windows.ps1 -Onefile        # also build portable exe
#   powershell ... build_windows.ps1 -SkipInstaller  # skip TaskReminderSetup.exe
param(
    [switch]$Onefile,
    [switch]$SkipInstaller
)
$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
$Py = Join-Path $Root ".venv\Scripts\python.exe"
if (-not (Test-Path $Py)) { $Py = "python" }

# PyInstaller needs to write __pycache__; make sure the env var is cleared.
Remove-Item Env:PYTHONDONTWRITEBYTECODE -ErrorAction SilentlyContinue

Write-Host "==> 1. Generate assets (icon/sound)" -ForegroundColor Cyan
& $Py (Join-Path $PSScriptRoot "gen_assets.py")
if ($LASTEXITCODE -ne 0) { exit 1 }

Write-Host "==> 2. PyInstaller build (onedir)" -ForegroundColor Cyan
Push-Location $Root
& $Py -m PyInstaller --noconfirm --clean "task_reminder.spec"
if ($LASTEXITCODE -ne 0) { Pop-Location; exit 1 }
Pop-Location

if ($Onefile) {
    Write-Host "==> 3. PyInstaller build (onefile portable)" -ForegroundColor Cyan
    Push-Location $Root
    & $Py -m PyInstaller --noconfirm --onefile --windowed --name TaskReminder `
        --icon "app.ico" --add-data "task_reminder\assets;assets" `
        --hidden-import PyQt6.QtMultimedia "run.py"
    if ($LASTEXITCODE -ne 0) { Pop-Location; exit 1 }
    Pop-Location
}

if (-not $SkipInstaller) {
    Write-Host "==> 4. Build self-contained installer" -ForegroundColor Cyan
    $Zip = Join-Path $Root "build\installer_payload.zip"
    if (Test-Path $Zip) { Remove-Item $Zip -Force }
    Compress-Archive -Path (Join-Path $Root "dist\TaskReminder\*") -DestinationPath $Zip

    # version file for the installer（脚本文件取版本，避免 -c 引号/参数传递问题）
    $Ver = & $Py (Join-Path $PSScriptRoot "print_version.py")
    if (-not $Ver) { $Ver = "0.0.0" }
    Write-Host "installer version: $Ver" -ForegroundColor Yellow
    Set-Content -Path (Join-Path $Root "build\app_version.txt") -Value $Ver -NoNewline -Encoding Ascii

    Push-Location $Root
    & $Py -m PyInstaller --noconfirm --onefile --windowed --name TaskReminderSetup `
        --icon "app.ico" `
        --add-data "build\installer_payload.zip;payload" `
        --add-data "build\app_version.txt;." `
        "scripts\make_installer.py"
    if ($LASTEXITCODE -ne 0) { Pop-Location; exit 1 }
    Pop-Location
}

Write-Host "" -ForegroundColor Cyan
Write-Host "Build outputs:" -ForegroundColor Green
Get-ChildItem (Join-Path $Root "dist") | ForEach-Object {
    if ($_.PSIsContainer) {
        $size = (Get-ChildItem $_.FullName -Recurse -File | Measure-Object Length -Sum).Sum / 1MB
        Write-Host ("  {0}  ({1:N1} MB)" -f $_.Name, $size)
    } else {
        Write-Host ("  {0}  ({1:N1} MB)" -f $_.Name, ($_.Length / 1MB))
    }
}
Write-Host "Done." -ForegroundColor Green
