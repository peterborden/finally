#!/usr/bin/env pwsh
<#
.SYNOPSIS
    Idempotent stop script for FinAlly on Windows.

.DESCRIPTION
    Mirrors scripts/stop_mac.sh: stops and removes the "finally" container
    but explicitly preserves the "finally-data" volume so portfolio,
    watchlist, and trade history survive. Safe to re-run -- exits cleanly
    even if the container is already stopped or removed.
#>

$ErrorActionPreference = 'Stop'

$ContainerName = 'finally'
$VolumeName = 'finally-data'

$existing = docker ps -a --format '{{.Names}}' | Where-Object { $_ -eq $ContainerName }
if ($existing) {
    docker rm -f $ContainerName | Out-Null
    Write-Host "Stopped and removed the $ContainerName container."
} else {
    Write-Host "No $ContainerName container found -- nothing to stop."
}

Write-Host "Data preserved in the $VolumeName volume (not removed)."
