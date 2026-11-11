# Build SoundPod.exe and SoundPodRecorder.exe, then zip the release folder.
# Run from PowerShell:  .\build.ps1
$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot

Write-Host "== Installing dependencies ==" -ForegroundColor Cyan
python -m pip install -r requirements-build.txt

Write-Host "== Generating icons ==" -ForegroundColor Cyan
python packaging\make_icon.py
python packaging\make_splash.py

Write-Host "== Building recorder helper ==" -ForegroundColor Cyan
python -m PyInstaller packaging\recorder.spec --noconfirm --clean --distpath dist\recorder

Write-Host "== Building SoundPod ==" -ForegroundColor Cyan
python -m PyInstaller packaging\soundpod.spec --noconfirm --clean

Write-Host "== Assembling release folder ==" -ForegroundColor Cyan
$release = Join-Path $PSScriptRoot "release"
if (Test-Path $release) { Remove-Item $release -Recurse -Force }
New-Item -ItemType Directory -Path $release | Out-Null
Copy-Item "dist\SoundPod.exe" $release
Copy-Item "dist\recorder\SoundPodRecorder.exe" $release
New-Item -ItemType Directory -Path "$release\tools\SoundVolumeView" -Force | Out-Null
Copy-Item "tools\SoundVolumeView\SoundVolumeView.exe" "$release\tools\SoundVolumeView"
Copy-Item "tools\SoundVolumeView\readme.txt" "$release\tools\SoundVolumeView"
Copy-Item "tools\SoundVolumeView\SoundVolumeView.chm" "$release\tools\SoundVolumeView"
Copy-Item "README.md" $release
Copy-Item "LICENSE" $release
Copy-Item "packaging\START-HERE.txt" $release

Write-Host "== Creating zip ==" -ForegroundColor Cyan
$zip = Join-Path $PSScriptRoot "SoundPod-release.zip"
if (Test-Path $zip) { Remove-Item $zip -Force }
Compress-Archive -Path "$release\*" -DestinationPath $zip -Force

Write-Host ""
Write-Host "Done:" -ForegroundColor Green
Write-Host "  $release"
Write-Host "  $zip"
