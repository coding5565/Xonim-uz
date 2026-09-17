$ErrorActionPreference = 'Stop'
$taskRoot = $PSScriptRoot
$taskPython = Join-Path $taskRoot '.venv\Scripts\python.exe'
$taskBackend = Join-Path $taskRoot 'honim_backend'
$taskFrontend = Join-Path $taskRoot 'honim_frontend'
$taskLogs = Join-Path $taskRoot '.run'
New-Item -ItemType Directory -Path $taskLogs -Force | Out-Null
if (-not (Test-Path -LiteralPath $taskPython)) { throw 'Install Python dependencies first; see README.md.' }
function Start-HonimProcess {
    param([string]$FilePath, [string[]]$Arguments, [string]$WorkingDirectory, [string]$PidPath)
    $taskInfo = [System.Diagnostics.ProcessStartInfo]::new()
    $taskInfo.FileName = $FilePath
    $taskInfo.WorkingDirectory = $WorkingDirectory
    $taskInfo.UseShellExecute = $false
    $taskInfo.CreateNoWindow = $true
    $taskInfo.Arguments = ($Arguments -join ' ')
    $taskProcess = [System.Diagnostics.Process]::Start($taskInfo)
    if (-not $taskProcess) { throw "Could not start $FilePath" }
    $taskProcess.Id | Set-Content -LiteralPath $PidPath
}
function Test-HonimPort {
    param([int]$Port)
    $taskClient = [System.Net.Sockets.TcpClient]::new()
    try {
        $taskConnect = $taskClient.BeginConnect('127.0.0.1', $Port, $null, $null)
        return ($taskConnect.AsyncWaitHandle.WaitOne(250) -and $taskClient.Connected)
    } catch { return $false } finally { $taskClient.Dispose() }
}
& $taskPython (Join-Path $taskBackend 'manage.py') migrate --noinput
if ($LASTEXITCODE -ne 0) { throw 'Database migration failed.' }
& $taskPython (Join-Path $taskBackend 'manage.py') seed_demo
if ($LASTEXITCODE -ne 0) { throw 'Local initialization failed.' }
if (-not (Test-HonimPort -Port 8000)) {
    Start-HonimProcess -FilePath $taskPython -Arguments @('manage.py','runserver','127.0.0.1:8000','--noreload') -WorkingDirectory $taskBackend -PidPath (Join-Path $taskLogs 'backend.pid')
} else { Write-Output 'Port 8000 is occupied; existing process was not changed.' }
if (-not (Test-HonimPort -Port 5173)) {
    $taskNode = (Get-Command node.exe).Source
    Start-HonimProcess -FilePath $taskNode -Arguments @('node_modules/vite/bin/vite.js','--host','127.0.0.1') -WorkingDirectory $taskFrontend -PidPath (Join-Path $taskLogs 'frontend.pid')
} else { Write-Output 'Port 5173 is occupied; existing process was not changed.' }
Write-Output 'Local URL: http://127.0.0.1:5173'
Write-Output 'Login details: .local-access.txt (keep private, do not commit).'
