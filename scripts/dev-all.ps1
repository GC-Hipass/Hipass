# Start the whole stack in dev mode: DB (docker compose) + backend + frontend.
# Each long-running process opens in its own PowerShell window so logs are visible.
#
# Usage:
#   powershell -ExecutionPolicy Bypass -File scripts\dev-all.ps1
#
# Options:
#   -NoBrowser   Do not open the frontend URL automatically

param(
    [switch]$NoBrowser
)

$ErrorActionPreference = "Stop"
$ProjectRoot = Resolve-Path (Join-Path $PSScriptRoot "..")
Set-Location $ProjectRoot

function Write-Step($msg) {
    Write-Host "[dev-all] $msg" -ForegroundColor Cyan
}

# ---------- 1) DB ----------
Write-Step "starting DB container..."
docker compose up -d
if ($LASTEXITCODE -ne 0) { throw "docker compose failed" }

Write-Host "[dev-all] waiting for postgres healthy..." -ForegroundColor DarkGray
$ready = $false
for ($i = 0; $i -lt 60; $i++) {
    $status = docker inspect --format='{{.State.Health.Status}}' pg-interview 2>$null
    if ($status -eq "healthy") {
        $ready = $true
        break
    }
    Start-Sleep -Milliseconds 500
}
if (-not $ready) { Write-Warning "postgres not healthy yet, continuing anyway" }
else { Write-Host "[dev-all] postgres healthy" -ForegroundColor Green }

# ---------- 2) Backend window ----------
Write-Step "launching backend window (port 8002)..."
$backendCmd = "Set-Location '$ProjectRoot'; & '$PSScriptRoot\dev.ps1'"
Start-Process powershell -ArgumentList "-NoExit", "-ExecutionPolicy", "Bypass", "-Command", $backendCmd

# ---------- 3) Frontend window ----------
$FrontendDir = Join-Path $ProjectRoot "frontend"
if (-not (Test-Path (Join-Path $FrontendDir "package.json"))) {
    throw "frontend/package.json not found"
}

$nodeModules = Join-Path $FrontendDir "node_modules"
$envFile = Join-Path $FrontendDir ".env"
$envExample = Join-Path $FrontendDir ".env.example"
if (-not (Test-Path $envFile) -and (Test-Path $envExample)) {
    Copy-Item $envExample $envFile
    Write-Host "[dev-all] frontend\.env created from .env.example" -ForegroundColor Yellow
}

Write-Step "launching frontend window (port 5173)..."
$installStep = if (Test-Path $nodeModules) { "" } else { "npm install; " }
$frontendCmd = "Set-Location '$FrontendDir'; $installStep" + "npm run dev"
Start-Process powershell -ArgumentList "-NoExit", "-ExecutionPolicy", "Bypass", "-Command", $frontendCmd

# ---------- 4) Open browser ----------
if (-not $NoBrowser) {
    Write-Host "[dev-all] opening http://localhost:5173 in 8s..." -ForegroundColor DarkGray
    Start-Sleep -Seconds 8
    Start-Process "http://localhost:5173"
}

Write-Host ""
Write-Host "[dev-all] all started." -ForegroundColor Green
Write-Host "  - DB       : localhost:6543 (docker pg-interview)" -ForegroundColor DarkGray
Write-Host "  - Backend  : http://localhost:8002  (Swagger /docs)" -ForegroundColor DarkGray
Write-Host "  - Frontend : http://localhost:5173" -ForegroundColor DarkGray
Write-Host ""
Write-Host "[dev-all] close the new PowerShell windows to stop backend/frontend." -ForegroundColor DarkGray
Write-Host "[dev-all] stop DB with: docker compose down" -ForegroundColor DarkGray
