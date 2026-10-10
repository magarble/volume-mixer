$ErrorActionPreference = 'Stop'
Set-Location -LiteralPath $PSScriptRoot
if (-not (Test-Path -LiteralPath '.venv\Scripts\python.exe')) {
    python -m venv .venv
    if ($LASTEXITCODE -ne 0) { throw 'Python 3.11 or newer is required.' }
}
& '.\.venv\Scripts\python.exe' -m pip install -r requirements.txt pyinstaller
if ($LASTEXITCODE -ne 0) { throw 'Dependency installation failed.' }
$env:PYINSTALLER_CONFIG_DIR = Join-Path $PSScriptRoot 'build\cache-scroll-fix'
& '.\.venv\Scripts\python.exe' -m PyInstaller --noconfirm --clean --windowed --onedir --workpath build/scroll-fix --distpath dist-scroll-fix --name VolumeMixer --collect-all soundcard app.py
if ($LASTEXITCODE -ne 0) { throw 'Executable build failed.' }
Write-Host 'Built dist-scroll-fix\VolumeMixer\VolumeMixer.exe. Keep the entire VolumeMixer folder together.'
