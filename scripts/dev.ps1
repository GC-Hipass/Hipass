# Dev bootstrap + run server (Windows PowerShell).
#
# Usage:
#   powershell -ExecutionPolicy Bypass -File scripts\dev.ps1
#
# Options:
#   -SkipRun    Set up only, do not start uvicorn
#   -Port N     Run port (default 8002)
#   -Reinstall  Drop and recreate venv

param(
    [switch]$SkipRun,
    [int]$Port = 8002,
    [switch]$Reinstall
)

$ErrorActionPreference = "Stop"
$ProjectRoot = Resolve-Path (Join-Path $PSScriptRoot "..")
Set-Location $ProjectRoot

$VenvDir = Join-Path $ProjectRoot ".venv"
$VenvPython = Join-Path $VenvDir "Scripts\python.exe"
$RequirementsFile = Join-Path $ProjectRoot "requirements.txt"
$RequirementsHashFile = Join-Path $VenvDir ".requirements.sha256"

function Resolve-PythonInterp {
    $candidates = @()
    try {
        $py = Get-Command py -ErrorAction SilentlyContinue
        if ($py) {
            foreach ($v in @("3.10", "3.11", "3.12")) {
                & py "-$v" --version 2>$null | Out-Null
                if ($LASTEXITCODE -eq 0) {
                    $candidates += @{ Cmd = "py"; Args = @("-$v") }
                }
            }
        }
    } catch {}

    foreach ($name in @("python3.10", "python3.11", "python3.12", "python3", "python")) {
        $cmd = Get-Command $name -ErrorAction SilentlyContinue
        if ($cmd) {
            $version = & $cmd.Source --version 2>&1
            if ($version -match "Python (\d+)\.(\d+)") {
                $major = [int]$Matches[1]; $minor = [int]$Matches[2]
                if ($major -eq 3 -and $minor -ge 10 -and $minor -lt 13) {
                    $candidates += @{ Cmd = $cmd.Source; Args = @() }
                }
            }
        }
    }

    if ($candidates.Count -eq 0) {
        throw "Python 3.10 - 3.12 is required. Install from https://www.python.org/downloads/"
    }
    return $candidates[0]
}

function Get-FileHashHex($path) {
    if (-not (Test-Path $path)) { return "" }
    return (Get-FileHash -Algorithm SHA256 -Path $path).Hash
}

# 1) venv
if ($Reinstall -and (Test-Path $VenvDir)) {
    Write-Host "[dev] removing existing venv..." -ForegroundColor Yellow
    Remove-Item -Recurse -Force $VenvDir
}

if (-not (Test-Path $VenvPython)) {
    $py = Resolve-PythonInterp
    Write-Host "[dev] creating venv with $($py.Cmd) $($py.Args -join ' ')" -ForegroundColor Cyan
    & $py.Cmd @($py.Args + @("-m", "venv", $VenvDir))
    if ($LASTEXITCODE -ne 0) { throw "venv creation failed" }
    & $VenvPython -m pip install --upgrade pip --quiet
}

# 2) deps
$currentHash = Get-FileHashHex $RequirementsFile
$installedHash = if (Test-Path $RequirementsHashFile) { Get-Content $RequirementsHashFile } else { "" }

if ($currentHash -ne $installedHash) {
    Write-Host "[dev] requirements.txt changed - syncing dependencies" -ForegroundColor Cyan
    & $VenvPython -m pip install -r $RequirementsFile
    if ($LASTEXITCODE -ne 0) { throw "pip install failed" }
    Set-Content -Path $RequirementsHashFile -Value $currentHash -Encoding ascii
} else {
    Write-Host "[dev] dependencies up to date (skip)" -ForegroundColor DarkGray
}

# 3) .env
$EnvFile = Join-Path $ProjectRoot ".env"
$EnvExample = Join-Path $ProjectRoot ".env.example"
if (-not (Test-Path $EnvFile) -and (Test-Path $EnvExample)) {
    Copy-Item $EnvExample $EnvFile
    Write-Host ""
    Write-Host "[dev] .env not found - copied from .env.example" -ForegroundColor Yellow
    Write-Host "      Fill in DATABASE_URL / NCLOUD / CLOVA keys then run again." -ForegroundColor Yellow
    Write-Host ""
}

# 4) run
if ($SkipRun) {
    Write-Host "[dev] setup complete (run skipped)" -ForegroundColor Green
    exit 0
}

Write-Host "[dev] uvicorn http://localhost:$Port" -ForegroundColor Green
& $VenvPython -m uvicorn app.main:app --reload --port $Port
