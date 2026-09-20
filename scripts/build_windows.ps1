# Build the desktop executable in one step (Windows PowerShell).
# Usage: powershell -ExecutionPolicy Bypass -File scripts\build_windows.ps1
$ErrorActionPreference = "Stop"

if (-not (Test-Path ".venv")) {
    python -m venv .venv
}
& .venv\Scripts\python.exe -m pip install --quiet -r requirements.txt pyinstaller

& .venv\Scripts\pyinstaller.exe StudentManagementSystem.spec --noconfirm
if ($LASTEXITCODE -ne 0) { throw "PyInstaller build failed" }

Write-Host ""
Write-Host "Build complete: dist\StudentManagementSystem\StudentManagementSystem.exe"
