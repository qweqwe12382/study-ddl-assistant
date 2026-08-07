$ErrorActionPreference = 'Stop'

$projectRoot = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$pythonPath = Join-Path $projectRoot '.venv\Scripts\python.exe'
$frontendRoot = Join-Path $projectRoot 'frontend'

if (-not (Test-Path -LiteralPath $pythonPath)) {
    throw "Python virtual environment not found: $pythonPath"
}
if (-not (Test-Path -LiteralPath (Join-Path $frontendRoot 'package.json'))) {
    throw "Frontend package.json not found: $frontendRoot"
}

$backendPath = Join-Path $projectRoot 'backend'
$backendCommand = "& '$pythonPath' -m uvicorn app.main:app --app-dir '$backendPath' --host 127.0.0.1 --port 8000"
$frontendCommand = "Set-Location -LiteralPath '$frontendRoot'; & npm.cmd run dev -- --host 127.0.0.1"

# Keep service windows hidden so one command starts a quiet local demo.
Start-Process -FilePath 'powershell.exe' -WindowStyle Hidden -ArgumentList '-NoProfile', '-ExecutionPolicy', 'Bypass', '-Command', $backendCommand
Start-Process -FilePath 'powershell.exe' -WindowStyle Hidden -ArgumentList '-NoProfile', '-ExecutionPolicy', 'Bypass', '-Command', $frontendCommand

Write-Host 'Backend: http://127.0.0.1:8000/docs'
Write-Host 'Frontend: http://127.0.0.1:5173/'
Write-Host 'Set DEMO_MODE=true in .env before starting to load demo data.'
