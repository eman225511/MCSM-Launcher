@echo off
REM Create Desktop and Start Menu shortcuts for MCSM Launcher
REM Place this .bat in the same folder as launcher.exe before running.

setlocal
set "EXEDIR=%~dp0"
set "TARGET=%EXEDIR%launcher.exe"

:: Use PowerShell to create shortcuts and show dialogs
powershell -NoProfile -ExecutionPolicy Bypass -Command "Add-Type -AssemblyName System.Windows.Forms; $t = '%TARGET%'; if (-not (Test-Path $t)) { [System.Windows.Forms.MessageBox]::Show(\"launcher.exe not found in the same folder:\n$t\", 'Error', [System.Windows.Forms.MessageBoxButtons]::OK, [System.Windows.Forms.MessageBoxIcon]::Error); exit 1 }; $shell = New-Object -ComObject WScript.Shell; $desktop = [Environment]::GetFolderPath('Desktop'); $startPrograms = Join-Path ([Environment]::GetFolderPath('StartMenu')) 'Programs'; $lnk1 = Join-Path $desktop 'MCSM Launcher.lnk'; $s1 = $shell.CreateShortcut($lnk1); $s1.TargetPath = $t; $s1.WorkingDirectory = '%EXEDIR%'; $s1.IconLocation = $t; $s1.Save(); $lnk2 = Join-Path $startPrograms 'MCSM Launcher.lnk'; $s2 = $shell.CreateShortcut($lnk2); $s2.TargetPath = $t; $s2.WorkingDirectory = '%EXEDIR%'; $s2.IconLocation = $t; $s2.Save(); [System.Windows.Forms.MessageBox]::Show('Shortcuts created on Desktop and Start Menu','Done',[System.Windows.Forms.MessageBoxButtons]::OK,[System.Windows.Forms.MessageBoxIcon]::Information)"

pause
endlocal
