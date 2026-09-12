[CmdletBinding()]
param(
    [ValidateRange(5, 120)]
    [int]$StartupTimeoutSeconds = 45
)

$ErrorActionPreference = 'Stop'

$projectRoot = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$pythonPath = Join-Path $projectRoot '.venv\Scripts\python.exe'
$backendRoot = Join-Path $projectRoot 'backend'
$frontendRoot = Join-Path $projectRoot 'frontend'
$runtimeRoot = Join-Path $projectRoot '.tmp\dev-runtime'
$pidFile = Join-Path $runtimeRoot 'services.json'
$backendHealthUrl = 'http://127.0.0.1:8000/api/health'
$frontendUrl = 'http://127.0.0.1:5173/'

function Test-TcpPort {
    param([Parameter(Mandatory)][int]$Port)

    $client = [System.Net.Sockets.TcpClient]::new()
    try {
        $task = $client.ConnectAsync('127.0.0.1', $Port)
        return $task.Wait(350) -and $client.Connected
    } catch {
        return $false
    } finally {
        $client.Dispose()
    }
}

function Test-BackendHealth {
    try {
        $response = Invoke-RestMethod -Uri $backendHealthUrl -Method Get -TimeoutSec 2
        return (
            $response.status -eq 'ok' -and
            $response.database -eq 'ok' -and
            $response.service -eq 'learning-assistant-api'
        )
    } catch {
        return $false
    }
}

function Test-FrontendHttp {
    try {
        $response = Invoke-WebRequest -Uri $frontendUrl -Method Get -TimeoutSec 2 -UseBasicParsing
        return (
            $response.StatusCode -eq 200 -and
            $response.Content -match '<title>\s*学伴管家\s*</title>' -and
            $response.Content -match '<script\s+type="module"\s+src="/src/main\.js"'
        )
    } catch {
        return $false
    }
}

function Stop-OwnedProcessTree {
    param([Parameter(Mandatory)][int[]]$ProcessIds)

    $allProcesses = @(Get-CimInstance Win32_Process -ErrorAction SilentlyContinue)
    $owned = [System.Collections.Generic.HashSet[int]]::new()
    $pending = [System.Collections.Generic.Queue[int]]::new()
    foreach ($processId in $ProcessIds) {
        if ($processId -gt 0 -and $owned.Add($processId)) { $pending.Enqueue($processId) }
    }
    while ($pending.Count -gt 0) {
        $parentId = $pending.Dequeue()
        foreach ($child in $allProcesses | Where-Object { $_.ParentProcessId -eq $parentId }) {
            if ($owned.Add([int]$child.ProcessId)) { $pending.Enqueue([int]$child.ProcessId) }
        }
    }
    foreach ($processId in @($owned) | Sort-Object -Descending) {
        Stop-Process -Id $processId -Force -ErrorAction SilentlyContinue
    }
}

if (-not (Test-Path -LiteralPath $pythonPath -PathType Leaf)) {
    throw "Python virtual environment not found: $pythonPath"
}
if (-not (Test-Path -LiteralPath (Join-Path $backendRoot 'app\main.py') -PathType Leaf)) {
    throw "Backend entry point not found: $backendRoot"
}
if (-not (Test-Path -LiteralPath (Join-Path $frontendRoot 'package.json') -PathType Leaf)) {
    throw "Frontend package.json not found: $frontendRoot"
}
if (-not (Get-Command npm.cmd -ErrorAction SilentlyContinue)) {
    throw 'npm.cmd was not found on PATH.'
}
if (-not (Test-Path -LiteralPath (Join-Path $frontendRoot 'node_modules\.bin\vite.cmd') -PathType Leaf)) {
    throw "Frontend dependencies are missing. Run 'npm.cmd install' in $frontendRoot first."
}

& $pythonPath -c 'import fastapi, uvicorn'
if ($LASTEXITCODE -ne 0) {
    throw 'Backend dependencies are incomplete. Install the project Python dependencies first.'
}
& npm.cmd --version | Out-Null
if ($LASTEXITCODE -ne 0) { throw 'npm.cmd could not be executed.' }

$backendPortOpen = Test-TcpPort -Port 8000
$frontendPortOpen = Test-TcpPort -Port 5173
if ($backendPortOpen -or $frontendPortOpen) {
    if ($backendPortOpen -and $frontendPortOpen -and (Test-BackendHealth) -and (Test-FrontendHttp)) {
        Write-Host 'The local backend and frontend are already healthy; reusing them without launching duplicates.'
        Write-Host 'Backend: http://127.0.0.1:8000/docs'
        Write-Host "Frontend: $frontendUrl"
        exit 0
    }
    $occupied = @()
    if ($backendPortOpen) { $occupied += '8000' }
    if ($frontendPortOpen) { $occupied += '5173' }
    throw "Required local port(s) already occupied: $($occupied -join ', '). Stop or move those services, then retry."
}

New-Item -ItemType Directory -Path $runtimeRoot -Force | Out-Null
$backendStdout = Join-Path $runtimeRoot 'backend.stdout.log'
$backendStderr = Join-Path $runtimeRoot 'backend.stderr.log'
$frontendStdout = Join-Path $runtimeRoot 'frontend.stdout.log'
$frontendStderr = Join-Path $runtimeRoot 'frontend.stderr.log'
$startedProcesses = @()

try {
    # Keep path-bearing values in FilePath/WorkingDirectory. The native
    # ArgumentList contains only space-free tokens, so a checkout path with
    # spaces cannot be split by Start-Process's Windows argument serialization.
    $backendProcess = Start-Process -FilePath $pythonPath -WindowStyle Hidden -WorkingDirectory $projectRoot -ArgumentList @(
        '-m', 'uvicorn', 'app.main:app', '--app-dir', 'backend', '--host', '127.0.0.1', '--port', '8000'
    ) -RedirectStandardOutput $backendStdout -RedirectStandardError $backendStderr -PassThru
    $startedProcesses += $backendProcess

    $frontendProcess = Start-Process -FilePath 'npm.cmd' -WindowStyle Hidden -WorkingDirectory $frontendRoot -ArgumentList @(
        'run', 'dev', '--', '--host', '127.0.0.1', '--port', '5173', '--strictPort'
    ) -RedirectStandardOutput $frontendStdout -RedirectStandardError $frontendStderr -PassThru
    $startedProcesses += $frontendProcess

    $startedAt = (Get-Date).ToString('o')

    $deadline = (Get-Date).AddSeconds($StartupTimeoutSeconds)
    $backendReady = $false
    $frontendReady = $false
    do {
        if (-not $backendReady) { $backendReady = Test-BackendHealth }
        if (-not $frontendReady) { $frontendReady = Test-FrontendHttp }
        if ($backendReady -and $frontendReady) { break }
        Start-Sleep -Milliseconds 500
    } while ((Get-Date) -lt $deadline)

    if (-not ($backendReady -and $frontendReady)) {
        throw "Startup health check timed out after $StartupTimeoutSeconds seconds (backend=$backendReady, frontend=$frontendReady). Logs: $runtimeRoot"
    }

    @{
        started_at = $startedAt
        project_root = $projectRoot
        backend_pid = $backendProcess.Id
        frontend_pid = $frontendProcess.Id
        backend_url = $backendHealthUrl
        frontend_url = $frontendUrl
        backend_fingerprint = 'learning-assistant-api'
        frontend_fingerprint = '学伴管家:/src/main.js'
    } | ConvertTo-Json | Set-Content -LiteralPath $pidFile -Encoding UTF8
} catch {
    if ($startedProcesses.Count -gt 0) {
        Stop-OwnedProcessTree -ProcessIds @($startedProcesses | ForEach-Object { $_.Id })
    }
    Remove-Item -LiteralPath $pidFile -Force -ErrorAction SilentlyContinue
    throw
}

Write-Host 'Local services started and passed health checks.'
Write-Host 'Backend: http://127.0.0.1:8000/docs'
Write-Host "Frontend: $frontendUrl"
Write-Host "Runtime evidence: $runtimeRoot"
Write-Host 'Set DEMO_MODE=true in .env before starting to load demo data.'
Write-Host "This script can be called from any PowerShell: & '$PSCommandPath'"
