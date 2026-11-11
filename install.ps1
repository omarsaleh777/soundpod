$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot

Write-Host "Installing Python packages..."
python -m pip install -r requirements.txt

$shell = New-Object -ComObject WScript.Shell
$shortcut = $shell.CreateShortcut((Join-Path $PSScriptRoot "SoundPod.lnk"))
$shortcut.TargetPath = Join-Path $PSScriptRoot "run.bat"
$shortcut.WorkingDirectory = $PSScriptRoot
$shortcut.Description = "SoundPod soundboard"
$shortcut.Save()

Write-Host ""
Write-Host "Done. Run .\run.bat or the new SoundPod.lnk."
Write-Host "For microphone injection, install VB-CABLE and select CABLE Input in Devices."
