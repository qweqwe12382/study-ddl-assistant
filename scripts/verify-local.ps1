$ErrorActionPreference = 'Stop'

$projectRoot = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$pythonPath = Join-Path $projectRoot '.venv\Scripts\python.exe'

if (-not (Test-Path -LiteralPath $pythonPath)) {
    throw "Python virtual environment not found: $pythonPath"
}

Set-Location -LiteralPath $projectRoot
$env:PYTHONPATH = Join-Path $projectRoot 'backend'

Write-Host 'Checking Python dependencies...'
& $pythonPath -m pip check
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

Write-Host 'Running backend tests...'
& $pythonPath -m pytest -q
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

Push-Location (Join-Path $projectRoot 'frontend')
try {
    Write-Host 'Running frontend lint...'
    & npm.cmd run lint
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

    Write-Host 'Running frontend build...'
    & npm.cmd run build
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
} finally {
    Pop-Location
}

Write-Host 'Local verification passed.'
