#Requires -Version 5.1
<#
.SYNOPSIS
    Downloads and installs the latest VoiceFlow release.
.EXAMPLE
    irm https://raw.githubusercontent.com/apgodlike/voiceflow/main/install.ps1 | iex
#>

$ErrorActionPreference = "Stop"
$repo = "apgodlike/voiceflow"

Write-Host "Fetching latest VoiceFlow release..."
$release = Invoke-RestMethod "https://api.github.com/repos/$repo/releases/latest" `
    -Headers @{ "User-Agent" = "VoiceFlow-Installer"; "Accept" = "application/vnd.github+json" }

$asset = $release.assets | Where-Object { $_.name -eq "VoiceFlow-Setup.exe" } | Select-Object -First 1
if (-not $asset) {
    Write-Error "VoiceFlow-Setup.exe not found in release $($release.tag_name). Check https://github.com/$repo/releases"
    exit 1
}

$version = $release.tag_name
$tmp = Join-Path $env:TEMP "VoiceFlow-Setup-$version.exe"

Write-Host "Downloading VoiceFlow $version..."
Invoke-WebRequest -Uri $asset.browser_download_url -OutFile $tmp -UseBasicParsing

Write-Host ""
Write-Host "Starting installer..."
if (-not (Test-Path $tmp)) {
    Write-Error "Download failed — file not found at $tmp"
    exit 1
}

$proc = Start-Process -FilePath $tmp -PassThru -Wait
if ($proc.ExitCode -ne 0 -and $proc.ExitCode -ne $null) {
    Write-Warning "Installer exited with code $($proc.ExitCode)."
    exit $proc.ExitCode
}

Write-Host ""
Write-Host "VoiceFlow $version installed."
Write-Host "Launch it from the Start Menu or find VoiceFlow in your taskbar tray."
Write-Host "On first launch, a wizard sets up Local mode (no API key, runs Parakeet/Whisper on your PC) or Cloud (OpenAI)."
