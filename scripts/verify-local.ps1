$ErrorActionPreference = 'Stop'

$projectRoot = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$pythonPath = Join-Path $projectRoot '.venv\Scripts\python.exe'
$frontendRoot = Join-Path $projectRoot 'frontend'
$pytestRoot = Join-Path $projectRoot '.pytest-tmp'
$runName = 'run-{0}-{1}' -f (Get-Date -Format 'yyyyMMdd-HHmmss'), ([guid]::NewGuid().ToString('N'))
$runParent = Join-Path $pytestRoot $runName
$pytestLeaf = Join-Path $runParent 'pytest'

if (-not (Test-Path -LiteralPath $pythonPath -PathType Leaf)) {
    throw "Python virtual environment not found: $pythonPath"
}
if (-not (Get-Command npm.cmd -ErrorAction SilentlyContinue)) {
    throw 'npm.cmd was not found on PATH.'
}
if (-not (Test-Path -LiteralPath (Join-Path $frontendRoot 'package.json') -PathType Leaf)) {
    throw "Frontend package.json not found: $frontendRoot"
}

# pytest removes and recreates the basetemp leaf. Its unique parent must exist
# first on Windows, where the system temp folder may be inaccessible.
New-Item -ItemType Directory -Path $runParent -Force | Out-Null
$env:PYTHONPATH = Join-Path $projectRoot 'backend'

Write-Host "Project root: $projectRoot"
Write-Host "Pytest evidence directory: $pytestLeaf"

Write-Host 'Checking Python dependencies...'
& $pythonPath -m pip check
$stepExitCode = $LASTEXITCODE
if ($stepExitCode -ne 0) { exit $stepExitCode }

Write-Host 'Running backend tests with an isolated in-repository basetemp...'
& $pythonPath -m pytest (Join-Path $projectRoot 'backend\tests') -q --basetemp $pytestLeaf
$stepExitCode = $LASTEXITCODE
if ($stepExitCode -ne 0) { exit $stepExitCode }

$frontendExitCode = 0
Push-Location -LiteralPath $frontendRoot
try {
    Write-Host 'Running the complete frontend verification (contracts, build, and bundle budget)...'
    & npm.cmd run verify
    $frontendExitCode = $LASTEXITCODE
} finally {
    Pop-Location
}
if ($frontendExitCode -ne 0) { exit $frontendExitCode }

Write-Host 'Local verification passed: pip check, backend pytest, and frontend verify.'
