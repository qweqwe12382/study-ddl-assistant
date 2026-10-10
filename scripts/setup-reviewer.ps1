[CmdletBinding()]
param([switch]$SkipInstall)
$ErrorActionPreference = 'Stop'
$root = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
Push-Location $root
try {
    if (-not (Test-Path '.venv\Scripts\python.exe')) {
        & py -3.14 -m venv .venv
        if ($LASTEXITCODE -ne 0) { throw 'Python 3.14 is required; install it and retry.' }
    }
    if (-not $SkipInstall) {
        & .\.venv\Scripts\python.exe -m pip install -r backend\requirements.txt
        if ($LASTEXITCODE -ne 0) { throw 'Backend dependency installation failed.' }
        Push-Location frontend
        try {
            & npm.cmd ci --cache (Join-Path $root '.tmp\npm-cache')
            if ($LASTEXITCODE -ne 0) { throw 'Frontend dependency installation failed.' }
        } finally { Pop-Location }
    }
    if (-not (Test-Path .env)) { Copy-Item .env.example .env }
    if (-not (Test-Path frontend\.env)) { Copy-Item frontend\.env.example frontend\.env }
    Write-Host 'Ready. Run: .\scripts\start-reviewer.ps1'
} finally { Pop-Location }
