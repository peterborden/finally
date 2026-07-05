#!/usr/bin/env pwsh
<#
.SYNOPSIS
    Idempotent one-command launcher for FinAlly on Windows.

.DESCRIPTION
    Mirrors scripts/start_mac.sh: builds the "finally" image only if it is
    missing (or -Build is passed), runs the container with the finally-data
    volume mounted, and prints the app URL. Safe to re-run — if the
    container is already running, it prints the URL and exits without
    creating a duplicate.

.PARAMETER Build
    Force a rebuild of the "finally" image even if it already exists.

.EXAMPLE
    scripts/start_windows.ps1
    scripts/start_windows.ps1 -Build
#>
param(
    [switch]$Build
)

$ErrorActionPreference = 'Stop'

$ImageName = 'finally'
$ContainerName = 'finally'
$VolumeName = 'finally-data'
$Port = 8000
$Url = "http://localhost:$Port"

# Resolve the repo root relative to this script's location so it can be run
# from anywhere.
$RepoRoot = Resolve-Path (Join-Path $PSScriptRoot '..')
Set-Location $RepoRoot

# First-time convenience: create .env from the template if it's missing.
$EnvPath = Join-Path $RepoRoot '.env'
$EnvExamplePath = Join-Path $RepoRoot '.env.example'
if (-not (Test-Path $EnvPath)) {
    Copy-Item $EnvExamplePath $EnvPath
    Write-Host "Created .env from .env.example -- edit it to add OPENROUTER_API_KEY / MASSIVE_API_KEY, or leave blank / set LLM_MOCK=true to run without keys."
}

# If the container is already running, this is a no-op -- print the URL and exit.
$running = docker ps --format '{{.Names}}' | Where-Object { $_ -eq $ContainerName }
if ($running) {
    Write-Host "FinAlly is already running at $Url"
    exit 0
}

# Build the image only if it's missing, or if the user forced a rebuild.
$imageExists = $true
try {
    docker image inspect $ImageName *> $null
} catch {
    $imageExists = $false
}

if ($Build) {
    Write-Host "Building $ImageName image (-Build requested)..."
    docker build -t $ImageName .
} elseif (-not $imageExists) {
    Write-Host "Building $ImageName image (no existing image found)..."
    docker build -t $ImageName .
} else {
    Write-Host "Reusing existing $ImageName image (pass -Build to force a rebuild)."
}

# Remove a stopped container with the same name so we can start fresh.
$existing = docker ps -a --format '{{.Names}}' | Where-Object { $_ -eq $ContainerName }
if ($existing) {
    docker rm $ContainerName | Out-Null
}

docker run -d `
    --name $ContainerName `
    -p "${Port}:${Port}" `
    -v finally-data:/app/db `
    --env-file .env `
    $ImageName

Write-Host "FinAlly is starting at $Url"

# Best-effort browser open; never fail if it doesn't work.
try {
    Start-Process $Url | Out-Null
} catch {
    # Ignore -- opening a browser is optional convenience.
}
