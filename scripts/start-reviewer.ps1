[CmdletBinding()]
param([ValidateRange(1,65535)][int]$ApiPort = 8000, [ValidateRange(1,65535)][int]$WebPort = 5173)
$ErrorActionPreference = 'Stop'
if ($ApiPort -eq $WebPort) { throw 'ApiPort and WebPort must be different.' }
$root = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$runtime = Join-Path $root '.tmp\reviewer-demo'
$python = Join-Path $root '.venv\Scripts\python.exe'
if (-not (Test-Path $python)) { throw 'Run scripts/setup-reviewer.ps1 first.' }
if (-not (Test-Path (Join-Path $root 'frontend\node_modules\vite\bin\vite.js'))) { throw 'Run scripts/setup-reviewer.ps1 first.' }
foreach ($port in @($ApiPort, $WebPort)) {
    $client = [Net.Sockets.TcpClient]::new()
    try { $client.Connect('127.0.0.1', $port); throw "Port $port is occupied. Choose different -ApiPort and -WebPort." }
    catch [Net.Sockets.SocketException] { }
    finally { $client.Dispose() }
}
New-Item -ItemType Directory -Path $runtime -Force | Out-Null
$env:DATABASE_URL = 'sqlite:///' + ($runtime.Replace('\','/')) + '/system.db'
$env:AUTH_DATABASE_URL = 'sqlite:///' + ($runtime.Replace('\','/')) + '/auth.db'
$env:USER_DATABASE_DIR = Join-Path $runtime 'users'
$env:UPLOAD_DIR = Join-Path $runtime 'uploads'
$env:APP_ENV = 'development'
$env:DEMO_MODE = 'true'
$env:AUTH_COOKIE_SECURE = 'false'
$env:PYTHON_DOTENV_DISABLED = '1'
$env:LLM_API_KEY = ''
$env:LLM_MODEL = ''
$env:LLM_BASE_URL = ''
$env:CORS_ORIGINS = "http://127.0.0.1:$WebPort"
$env:VITE_API_BASE_URL = "http://127.0.0.1:$ApiPort/api"
$env:PYTHONPATH = Join-Path $root 'backend'
$backend = $null
try {
    $backend = Start-Process -FilePath $python -ArgumentList @('-m','uvicorn','app.main:app','--host','127.0.0.1','--port',"$ApiPort") -WorkingDirectory $root -WindowStyle Hidden -PassThru -RedirectStandardOutput (Join-Path $runtime 'api.log') -RedirectStandardError (Join-Path $runtime 'api-error.log')
    $ready = $false
    for ($attempt = 0; $attempt -lt 40; $attempt++) {
        if ($backend.HasExited) { throw 'Backend stopped. See .tmp/reviewer-demo/api-error.log.' }
        try { $health = Invoke-RestMethod "http://127.0.0.1:$ApiPort/api/health" -TimeoutSec 2; if ($health.status -eq 'ok') { $ready = $true; break } } catch { }
        Start-Sleep -Milliseconds 500
    }
    if (-not $ready) { throw 'Backend health check timed out.' }
    Write-Host "Open http://127.0.0.1:$WebPort and choose the demo-space button. Ctrl+C stops this session."
    Push-Location (Join-Path $root 'frontend')
    try {
        & npm.cmd run dev -- --host 127.0.0.1 --port $WebPort --strictPort
        if ($LASTEXITCODE -ne 0) { throw 'Frontend stopped with an error.' }
    }
    finally { Pop-Location }
} finally {
    if ($backend -and -not $backend.HasExited) { Stop-Process -Id $backend.Id }
}
