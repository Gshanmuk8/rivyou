$ErrorActionPreference = 'Stop'
Set-Location -LiteralPath $PSScriptRoot
if (-not (Test-Path -LiteralPath '.venv\Scripts\python.exe')) {
    py -3.12 -m venv .venv
    if ($LASTEXITCODE -ne 0) { throw 'Python 3.12+ is required.' }
}
& '.\.venv\Scripts\python.exe' -m pip install -r requirements.lock
if ($LASTEXITCODE -ne 0) { throw 'Dependency installation failed.' }
& '.\.venv\Scripts\python.exe' -m pip install -e . --no-deps
if ($LASTEXITCODE -ne 0) { throw 'Project installation failed.' }
Write-Host 'Rivyou is available at http://127.0.0.1:8765'
& '.\.venv\Scripts\python.exe' -m rivyou.cli serve
