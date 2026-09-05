param(
    [ValidateRange(1, 65535)]
    [int]$Port = 8000,

    [ValidateRange(1, 65535)]
    [int]$AdbServerPort = 5038
)

$projectRoot = Split-Path -Parent $PSScriptRoot
$python = Join-Path $projectRoot '.venv\Scripts\python.exe'
$sdkRoot = if ($env:ANDROID_SDK_ROOT) { $env:ANDROID_SDK_ROOT } elseif ($env:ANDROID_HOME) { $env:ANDROID_HOME } else { Join-Path $env:LOCALAPPDATA 'Android\Sdk' }
$adb = Join-Path $sdkRoot 'platform-tools\adb.exe'

if (-not (Test-Path -LiteralPath $python)) {
    throw "找不到项目 Python 环境：$python"
}
if (-not (Test-Path -LiteralPath $adb)) {
    throw "找不到 Android SDK adb：$adb"
}

& $adb -P $AdbServerPort start-server
if ($LASTEXITCODE -ne 0) { throw 'ADB 启动失败' }

& $adb -P $AdbServerPort reverse "tcp:$Port" "tcp:$Port"
if ($LASTEXITCODE -ne 0) { throw 'ADB reverse 失败，请确认真机已连接并授权 USB 调试' }

$env:PYTHONPATH = Join-Path $projectRoot 'backend'
Write-Host "Android 调试通道已建立：http://127.0.0.1:$Port → 本机 FastAPI"
Write-Host '保持此窗口运行；应用进程结束后登录会话不会保留。'

& $python -m uvicorn app.main:app --app-dir (Join-Path $projectRoot 'backend') --host 127.0.0.1 --port $Port
