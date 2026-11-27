<#
.SYNOPSIS
  FinAlly - stop script (Windows PowerShell). Idempotent.

.DESCRIPTION
  Stops and removes the running container. Does NOT remove the named data
  volume, so the SQLite database (portfolio, trades, chat) persists.

.EXAMPLE
  ./scripts/stop_windows.ps1
#>
[CmdletBinding()]
param()

$ErrorActionPreference = "Stop"
$ContainerName = "finally"

if (-not (Get-Command docker -ErrorAction SilentlyContinue)) {
  Write-Error "docker is not installed or not on PATH."
  exit 1
}

$existing = docker ps -a --format '{{.Names}}' | Select-String -SimpleMatch -Pattern $ContainerName
if ($existing) {
  Write-Host "==> Stopping and removing container $ContainerName ..."
  docker rm -f $ContainerName *> $null
  Write-Host "==> Done. Data volume 'finally-data' preserved."
} else {
  Write-Host "==> Container $ContainerName is not present. Nothing to do."
}
