[CmdletBinding()]
param()

$ErrorActionPreference = 'Stop'

$projectRoot = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$pythonPath = Join-Path $projectRoot '.venv\Scripts\python.exe'
$testPath = Join-Path $projectRoot 'backend\tests\integration\test_reviewer_reproduction_smoke.py'
$runName = 'reviewer-smoke-{0}-{1}' -f (Get-Date -Format 'yyyyMMdd-HHmmss'), ([guid]::NewGuid().ToString('N'))
$runParent = Join-Path (Join-Path $projectRoot '.pytest-tmp') $runName
$pytestBase = Join-Path $runParent 'pytest'

if (-not (Test-Path -LiteralPath $pythonPath -PathType Leaf)) {
    throw "Python virtual environment not found: $pythonPath"
}
if (-not (Test-Path -LiteralPath $testPath -PathType Leaf)) {
    throw "Reviewer smoke test not found: $testPath"
}

New-Item -ItemType Directory -Path $runParent -Force | Out-Null
$env:PYTHONPATH = Join-Path $projectRoot 'backend'

Write-Host 'Running the isolated reviewer workflow...'
Write-Host "Evidence directory: $runParent"
& $pythonPath -m pytest $testPath -q -s --basetemp $pytestBase
$smokeExitCode = $LASTEXITCODE
if ($smokeExitCode -ne 0) { exit $smokeExitCode }

Write-Host 'Isolated reviewer workflow passed.'
