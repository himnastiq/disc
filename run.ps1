# Discovery Engine - PowerShell Forwarder (P10.1)
$PythonExe = if (Test-Path "$PSScriptRoot\.venv\Scripts\python.exe") { "$PSScriptRoot\.venv\Scripts\python.exe" } elseif (Test-Path "$PSScriptRoot\backend\.venv\Scripts\python.exe") { "$PSScriptRoot\backend\.venv\Scripts\python.exe" } else { "python" }
& $PythonExe "$PSScriptRoot\tools\demo.py" @args
exit $LASTEXITCODE
