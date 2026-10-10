param([switch]$SkipInstall)

$ErrorActionPreference = 'Stop'
Set-Location -LiteralPath $PSScriptRoot
if (-not (Test-Path -LiteralPath '.venv\Scripts\python.exe')) {
    python -m venv .venv
    if ($LASTEXITCODE -ne 0) { throw 'Python 3.14 x64 is recommended for release builds.' }
}
$python = Join-Path $PSScriptRoot '.venv\Scripts\python.exe'
if (-not $SkipInstall) {
    & $python -m pip install -r requirements-build.txt
    if ($LASTEXITCODE -ne 0) { throw 'Dependency installation failed.' }
}
$architecture = & $python -c 'import platform; print(platform.machine())'
if ($LASTEXITCODE -ne 0 -or $architecture -ne 'AMD64') { throw 'The Windows x64 release requires an x64 Python installation.' }
& $python -m unittest discover -s tests
if ($LASTEXITCODE -ne 0) { throw 'Tests failed; no release will be packaged.' }
$version = & $python -c 'from version import __version__; print(__version__)'
if ($LASTEXITCODE -ne 0 -or $version -notmatch '^\d+\.\d+\.\d+$') { throw 'Invalid release version.' }
& $python release_metadata.py
if ($LASTEXITCODE -ne 0) { throw 'Version metadata generation failed.' }
& $python collect_licenses.py
if ($LASTEXITCODE -ne 0) { throw 'Licence collection failed.' }
$env:PYINSTALLER_CONFIG_DIR = Join-Path $PSScriptRoot 'build\cache'
& $python -m PyInstaller --noconfirm --clean --windowed --onedir --workpath build/pyinstaller --distpath dist --name VolumeMixer --version-file build/windows-version.txt --collect-all soundcard app.py
if ($LASTEXITCODE -ne 0) { throw 'Executable build failed.' }
Copy-Item -LiteralPath README.md, CHANGELOG.md, LICENSE, THIRD_PARTY_NOTICES.md -Destination 'dist\VolumeMixer'
Copy-Item -LiteralPath licenses -Destination 'dist\VolumeMixer' -Recurse -Force
Copy-Item -LiteralPath docs -Destination 'dist\VolumeMixer' -Recurse -Force
New-Item -ItemType Directory -Path release -Force | Out-Null
$archive = Join-Path $PSScriptRoot "release\VolumeMixer-$version-windows-x64.zip"
Compress-Archive -Path 'dist\VolumeMixer' -DestinationPath $archive -Force
$hash = (Get-FileHash -LiteralPath $archive -Algorithm SHA256).Hash.ToLowerInvariant()
"$hash  $([IO.Path]::GetFileName($archive))" | Set-Content -LiteralPath "$archive.sha256" -Encoding ascii
Write-Host "Built $archive and its SHA-256 checksum."
