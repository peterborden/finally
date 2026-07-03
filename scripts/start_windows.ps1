<#
.SYNOPSIS
  FinAlly - start script (Windows PowerShell). Idempotent.

.DESCRIPTION
  Builds the Docker image if it does not exist yet (or when -Build / -NoCache is
  passed), then (re)starts the container with the persistent data volume, port
  mapping, and .env file. Prints the URL and can open a browser.

.EXAMPLE
  ./scripts/start_windows.ps1
  ./scripts/start_windows.ps1 -Build
  ./scripts/start_windows.ps1 -NoCache
  ./scripts/start_windows.ps1 -Open
#>
[CmdletBinding()]
param(
  [switch]$Build,
  [switch]$NoCache,
  [switch]$Open
)

$ErrorActionPreference = "Stop"

# --- config ------------------------------------------------------------------
$ImageName     = "finally:latest"
$ContainerName = "finally"
$VolumeName    = "finally-data"
$HostPort      = "8000"
$ContainerPort = "8000"
$Url           = "http://localhost:$HostPort"

# Resolve project root (parent of this script's dir) and work from there.
$ScriptDir   = Split-Path -Parent $MyInvocation.MyCommand.Path
$ProjectRoot = Split-Path -Parent $ScriptDir
Set-Location $ProjectRoot

# --- preflight ---------------------------------------------------------------
if (-not (Get-Command docker -ErrorAction SilentlyContinue)) {
  Write-Error "docker is not installed or not on PATH."
  exit 1
}
docker info *> $null
if ($LASTEXITCODE -ne 0) {
  Write-Error "The Docker daemon is not running. Start Docker Desktop and retry."
  exit 1
}

# --- build (if needed) -------------------------------------------------------
docker image inspect $ImageName *> $null
$ImageExists = ($LASTEXITCODE -eq 0)

if ($Build -or $NoCache -or (-not $ImageExists)) {
  Write-Host "==> Building image $ImageName ..."
  if ($NoCache) {
    docker build --no-cache -t $ImageName .
  } else {
    docker build -t $ImageName .
  }
  if ($LASTEXITCODE -ne 0) { Write-Error "Build failed."; exit 1 }
} else {
  Write-Host "==> Image $ImageName already exists (use -Build to rebuild)."
}

# --- env file ----------------------------------------------------------------
$EnvArgs = @()
if (Test-Path ".env") {
  $EnvArgs = @("--env-file", ".env")
  Write-Host "==> Using .env"
} else {
  Write-Host "==> No .env found - running with defaults (simulator market data, no LLM key)."
  Write-Host "    Copy .env.example to .env and add OPENROUTER_API_KEY for AI chat."
}

# --- (re)start container -----------------------------------------------------
# Idempotent: remove any existing container (running or stopped) with this name.
$existing = docker ps -a --format '{{.Names}}' | Select-String -SimpleMatch -Pattern $ContainerName
if ($existing) {
  Write-Host "==> Removing existing container $ContainerName ..."
  docker rm -f $ContainerName *> $null
}

Write-Host "==> Starting $ContainerName ..."
docker run -d `
  --name $ContainerName `
  -p "${HostPort}:${ContainerPort}" `
  -v "${VolumeName}:/app/db" `
  @EnvArgs `
  --restart unless-stopped `
  $ImageName *> $null
if ($LASTEXITCODE -ne 0) { Write-Error "Failed to start container."; exit 1 }

Write-Host ""
Write-Host "  FinAlly is starting at $Url"
Write-Host "  Logs:  docker logs -f $ContainerName"
Write-Host "  Stop:  ./scripts/stop_windows.ps1"
Write-Host ""

if ($Open) {
  Start-Process $Url
}
