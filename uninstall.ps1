# Removes only what install.ps1 created. Use -Purge to also delete .\venv and %APPDATA%\XMusic (settings/playlists).
param([switch]$Purge)
$dir = Split-Path -Parent $MyInvocation.MyCommand.Path
$cmd = Join-Path $env:LOCALAPPDATA "XMusic\bin\xmusic.cmd"
if ((Test-Path $cmd) -and (Select-String -Path $cmd -Pattern "XMusic launcher" -Quiet)) { Remove-Item $cmd; Write-Host "* removed $cmd" } else { Write-Host "* no XMusic launcher found" }
if ($Purge) {
    Remove-Item -Recurse -Force (Join-Path $dir "venv") -ErrorAction SilentlyContinue
    Remove-Item -Recurse -Force (Join-Path $env:APPDATA "XMusic") -ErrorAction SilentlyContinue
    Write-Host "* removed venv and settings"
}
