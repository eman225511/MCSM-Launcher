# PowerShell build script for creating a single-file Windows exe using PyInstaller
# - Converts assets/Logo.png to build/Logo.ico using the helper script
# - Installs pyinstaller and pillow into the current Python environment if needed
# - Bundles the assets/ folder into the single-file exe

param(
    [string]$PythonExe = "python"
)

$ErrorActionPreference = 'Stop'

Write-Host "Using Python: $PythonExe"

# Ensure build directory
if (!(Test-Path "build")) { New-Item -ItemType Directory -Path build | Out-Null }

Write-Host "Installing build dependencies (pyinstaller, pillow)..."
& $PythonExe -m pip install --upgrade pip > $null
& $PythonExe -m pip install pyinstaller pillow > $null

# Convert Logo.png to ico
$png = Join-Path -Path "assets" -ChildPath "Logo.png"
$ico = Join-Path -Path "tools" -ChildPath "Logo.ico"
if (!(Test-Path $png)) {
    Write-Error "assets/Logo.png not found. Place your logo at assets/Logo.png"
    exit 1
}


# Remove previous build/dist/spec
if (Test-Path "build\launcher.spec") { Remove-Item "build\launcher.spec" -Force }

# Run PyInstaller. Use --noconsole for GUI app; change if you want console output.
Write-Host "Running PyInstaller... this may take a while"
# On Windows PyInstaller expects add-data with a semicolon separator
$addData = "assets;assets"
& $PythonExe -m PyInstaller --noconsole --onefile --icon $ico --add-data $addData launcher.py

Write-Host "Done. The single-file executable is in the 'dist' folder."
Write-Host "Example: dist\launcher.exe"
