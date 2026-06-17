param(
    [string]$PythonBin = ""
)

$ErrorActionPreference = "Stop"

$RootDir = Resolve-Path (Join-Path $PSScriptRoot "..")
if (-not $PythonBin) {
    $PythonBin = if ($env:PYTHON_BIN) { $env:PYTHON_BIN } else { "python" }
}

Push-Location $RootDir
try {
    if (-not $env:PYINSTALLER_CONFIG_DIR) {
        $env:PYINSTALLER_CONFIG_DIR = Join-Path $RootDir "build\pyinstaller_config"
    }
    New-Item -ItemType Directory -Force -Path $env:PYINSTALLER_CONFIG_DIR | Out-Null

    & $PythonBin -c "import PyInstaller" | Out-Null
    if ($LASTEXITCODE -ne 0) {
        throw "PyInstaller is not installed. Run: pip install -r requirements-desktop.txt"
    }

    if ($env:ASL_PLATFORM_TOOLS_DIR) {
        Write-Host "Bundling Android platform-tools from: $env:ASL_PLATFORM_TOOLS_DIR"
    }

    & $PythonBin -m PyInstaller --noconfirm "packaging\pyinstaller\AndroidStabilityLab.spec"
    if ($LASTEXITCODE -ne 0) {
        throw "PyInstaller build failed."
    }

    Write-Host "Desktop bundle written to: $(Join-Path $RootDir 'dist\AndroidStabilityLab')"
    Write-Host "Windows executable: $(Join-Path $RootDir 'dist\AndroidStabilityLab\AndroidStabilityLab.exe')"
}
finally {
    Pop-Location
}
